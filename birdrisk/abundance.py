"""Monthly relative abundance per species from GBIF (which mirrors the eBird Observation Dataset).

The idea: density of records of the species / density of records of all birds (observation effort), by month,
smoothed over the grid. It is a relative frequency, not an absolute abundance.
"""
import hashlib
import json
import time

import numpy as np
import pandas as pd
import requests

from . import config
from .grid import smooth

_S = requests.Session()
_S.headers["User-Agent"] = config.USER_AGENT


def _get(params, retries=config.GBIF_RETRIES):
    """GET with patient retries: GBIF returns 503 'Backend fetch failed' or 429 under load."""
    last = None
    for i in range(retries):
        try:
            r = _S.get(config.GBIF_OCC_URL, params=params, timeout=180)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
            wait = float(r.headers.get("Retry-After", 0) or 0)
        except requests.RequestException as e:
            last, wait = str(e)[:80], 0
        time.sleep(max(wait, min(5 * 2 ** i, 120)))
    raise RuntimeError(f"GBIF not responding ({last}) after {retries} attempts: {params}")


def species_key(name):
    p = config.CACHE_DIR / "gbif" / "claves.json"  # legacy file name, kept so the download cache stays valid
    keys = json.loads(p.read_text()) if p.exists() else {}
    if name not in keys:
        r = _S.get(config.GBIF_MATCH_URL, params={"name": name, "kingdom": "Animalia"}, timeout=60).json()
        if r.get("matchType") == "NONE" or "usageKey" not in r:
            raise ValueError(f"GBIF does not recognise the species {name}")
        keys[name] = r["usageKey"]
        p.write_text(json.dumps(keys, indent=1))
    return keys[name]


def _bbox_params(bbox):
    lat_min, lon_min, lat_max, lon_max = bbox
    return {"decimalLatitude": f"{lat_min},{lat_max}", "decimalLongitude": f"{lon_min},{lon_max}",
            "hasCoordinate": "true", "hasGeospatialIssue": "false",
            "year": f"{config.GBIF_YEAR_FROM},2100"}


def _cache_key(*parts):
    return hashlib.md5(json.dumps(parts).encode()).hexdigest()[:12]


COLUMNS = ["lon", "lat", "month", "year", "datasetKey", "individualCount"]


def _row(r):
    return (r.get("decimalLongitude"), r.get("decimalLatitude"), r.get("month"),
            r.get("year"), r.get("datasetKey"), r.get("individualCount"))


def _paginate_block(params, total):
    """Pages of one block (at most GBIF_MAX_OFFSET records), GBIF_THREADS in parallel."""
    from concurrent.futures import ThreadPoolExecutor

    offsets = list(range(0, min(total, config.GBIF_MAX_OFFSET), config.GBIF_PAGE))
    rows = []
    with ThreadPoolExecutor(max_workers=config.GBIF_THREADS) as ex:
        for d in ex.map(lambda off: _get({**params, "offset": off}), offsets):
            rows.extend(_row(r) for r in d["results"])
    return rows


def _paginate(params, total=None, log=print):
    """Download the records in yearly blocks (newest first) to keep the offsets small, up to GBIF_MAX_RECORDS.

    Deep paging in GBIF is very slow, and the recent years are also the ones that best match the infrastructure
    as it stands today.
    """
    d = _get({**params, "limit": 0, "facet": "year", "facetLimit": 200})
    by_year = sorted(((int(c["name"]), c["count"]) for f in d.get("facets", []) for c in f["counts"]), reverse=True)
    rows, accumulated = [], 0
    for year, n in by_year:
        if n == 0:
            continue
        if accumulated >= config.GBIF_MAX_RECORDS:
            log(f"    cap of {config.GBIF_MAX_RECORDS} records reached; years <= {year} are skipped")
            break
        p = {**params, "year": str(year)}
        # each yearly block is cached separately so a run can resume if GBIF goes down halfway
        pc = config.CACHE_DIR / "gbif" / "bloques" / f"{_cache_key(p)}.parquet"  # legacy folder name, keeps the cache
        if pc.exists():
            block = [tuple(x) for x in pd.read_parquet(pc).itertuples(index=False)]
        else:
            if n > config.GBIF_MAX_OFFSET:  # huge year: split it by month
                block = []
                for m in range(1, 13):
                    sub = _get({**p, "month": m, "limit": 0})["count"]
                    block += _paginate_block({**p, "month": m}, sub)
            else:
                block = _paginate_block(p, n)
            pc.parent.mkdir(exist_ok=True)
            pd.DataFrame(block, columns=COLUMNS).to_parquet(pc)
        rows += block
        accumulated += n
    return rows


def species_records(name, bbox, log=print):
    """DataFrame with lon, lat, month, year and datasetKey of the records of the species inside the bbox."""
    key = species_key(name)
    p = config.CACHE_DIR / "gbif" / f"citas_{key}_{_cache_key(bbox)}.parquet"  # legacy prefix, keeps the cache valid
    if p.exists():
        return pd.read_parquet(p)
    params = {**_bbox_params(bbox), "taxonKey": key, "limit": config.GBIF_PAGE}
    total = _get({**params, "limit": 0})["count"]
    log(f"  {name}: {total} records in GBIF")
    rows = _paginate(params, total=total, log=log) if total else []
    df = pd.DataFrame(rows, columns=COLUMNS)
    df = df.dropna(subset=["month", "lon", "lat"])
    df["month"] = df["month"].astype(int)
    df.to_parquet(p)
    return df


def monthly_effort(bbox, log=print):
    """Number of Aves records per tile (EFFORT_TILE_DEG) and month. DataFrame lat, lon (corner), month, n."""
    p = config.CACHE_DIR / "gbif" / \
        f"esfuerzo_{_cache_key(bbox, config.EFFORT_TILE_DEG, config.GBIF_YEAR_FROM)}.parquet"  # legacy prefix
    if p.exists():
        return pd.read_parquet(p)
    lat_min, lon_min, lat_max, lon_max = bbox
    t = config.EFFORT_TILE_DEG
    lats = np.arange(lat_min, lat_max - 1e-9, t)
    lons = np.arange(lon_min, lon_max - 1e-9, t)
    log(f"  sampling effort (all birds): {len(lats) * len(lons)} tiles of {t} degrees")
    rows = []
    for la in lats:
        for lo in lons:
            sub = (la, lo, min(la + t, lat_max), min(lo + t, lon_max))
            d = _get({**_bbox_params(sub), "taxonKey": config.AVES_TAXON_KEY, "limit": 0,
                      "facet": "month", "facetLimit": 12})
            counts = {int(c["name"]): c["count"] for f in d.get("facets", []) for c in f["counts"]}
            for m in range(1, 13):
                rows.append((la, lo, m, counts.get(m, 0)))
    df = pd.DataFrame(rows, columns=["lat0", "lon0", "month", "n"])
    df.to_parquet(p)
    return df


def effort_raster(effort, grid):
    """Effort per month on the grid (bird records per km2), smoothed. Shape (12, ny, nx)."""
    out = np.zeros((12,) + grid.shape)
    t = config.EFFORT_TILE_DEG
    lat_c, lon_c = grid.lat_centres(), grid.lon_centres()
    sig = grid.sigma_px(t * 111_320 / 2)
    for m in range(1, 13):
        arr = np.zeros(grid.shape)
        for r in effort[effort.month == m].itertuples():
            rows = (lat_c >= r.lat0) & (lat_c < r.lat0 + t)
            cols = (lon_c >= r.lon0) & (lon_c < r.lon0 + t)
            n_cells = rows.sum() * cols.sum()
            if n_cells:
                arr[np.ix_(rows, cols)] = r.n / n_cells
        out[m - 1] = smooth(arr, sig) / grid.area_km2
    return out


def monthly_presence(name, bbox, grid, effort_raster_arr, log=print):
    """0-1 index of monthly relative frequency (12, ny, nx) and record count. None when there are too few records."""
    df = species_records(name, bbox, log=log)
    if len(df) < config.MIN_RECORDS_PER_SPECIES:
        log(f"  {name}: only {len(df)} records, skipped")
        return None, len(df)
    out = np.zeros((12,) + grid.shape)
    for m in range(1, 13):
        sub = df[df.month == m]
        if sub.empty:
            continue
        # adaptive smoothing: with few records only a broad pattern can be claimed
        factor = max(1.0, np.sqrt(config.KDE_N_REF / len(sub)))
        sig = grid.sigma_px(config.KDE_SIGMA_M * factor)
        # records repeated at the same spot (~100 m) in the same month and year (an observer coming back, several
        # eBird checklists from one day) are weighted sqrt(n): they show regular presence, but not n times over
        stacked = sub.groupby([sub.year, sub.month, sub.lat.round(3), sub.lon.round(3)]).size().reset_index(name="n")
        dens = smooth(grid.count(stacked.lon.values, stacked.lat.values, np.sqrt(stacked.n.values)), sig) / grid.area_km2
        effort = effort_raster_arr[m - 1]
        # prior (median effort) so that cells with almost no observation effort do not blow up
        prior = np.percentile(effort[effort > 0], 50) if (effort > 0).any() else 1.0
        out[m - 1] = dens / (effort + prior)
    mx = out.max()
    if mx > 0:
        out /= mx
    return out, len(df)
