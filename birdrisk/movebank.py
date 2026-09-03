"""GPS tracking data from Movebank (optional).

Three routes, from least to most demanding:
1. Movebank Data Repository (DSpace, datasets published under CC0/CC-BY): search by species and download CSVs.
2. Movebank public JSON endpoint for studies flagged as public (by study_id).
3. The direct-read API with Movebank credentials (MOVEBANK_USER / MOVEBANK_PASSWORD).
The data are clipped to the bbox and aggregated into "individual-days per cell and month".
"""
import hashlib
import io
import json
import time
import zipfile

import numpy as np
import pandas as pd
import requests

from . import config
from .grid import smooth

_S = requests.Session()
_S.headers["User-Agent"] = config.USER_AGENT

COLS = {"location-long": "lon", "location-lat": "lat", "timestamp": "timestamp",
        "individual-local-identifier": "individual", "height-above-ellipsoid": "height",
        "height-above-msl": "height_msl", "individual-taxon-canonical-name": "species"}


# columns of the caches written before the package was translated; renamed on read so no re-download is needed
LEGACY_COLS = {"individuo": "individual", "altura": "height", "altura_msl": "height_msl",
               "especie": "species", "fuente": "source", "licencia": "licence"}


def _from_cache(path):
    """Read a cached parquet, translating the legacy Spanish column names if it is an old one."""
    df = pd.read_parquet(path)
    return df.rename(columns={k: v for k, v in LEGACY_COLS.items() if k in df.columns})


def search_repository(species, max_items=20):
    """Movebank Data Repository items whose title or subject mentions the species."""
    r = _S.get(config.MOVEBANK_REPO_SEARCH, params={"query": f'"{species}"', "size": max_items,
                                                    "dsoType": "ITEM"}, timeout=90)
    r.raise_for_status()
    objs = r.json()["_embedded"]["searchResult"]["_embedded"]["objects"]
    items = []
    for o in objs:
        obj = o["_embedded"]["indexableObject"]
        md = obj.get("metadata", {})
        species_names = [v["value"] for v in md.get("dwc.scientificName", [])] or \
                        [v["value"] for v in md.get("dc.subject", [])]
        items.append({"uuid": obj["uuid"], "title": obj.get("name"),
                      "licence": (md.get("dc.rights") or [{}])[0].get("value"), "species": species_names})
    return items


def bitstreams(uuid):
    b = _S.get(config.MOVEBANK_REPO_ITEM.format(uuid=uuid) + "/bundles", timeout=90).json()
    for bundle in b["_embedded"]["bundles"]:
        if bundle["name"] != "ORIGINAL":
            continue
        bs = _S.get(bundle["_links"]["bitstreams"]["href"], params={"size": 100}, timeout=90).json()
        return [{"name": x["name"], "bytes": x["sizeBytes"], "url": x["_links"]["content"]["href"]}
                for x in bs["_embedded"]["bitstreams"]]
    return []


def _read_filtered_csv(raw, name, bbox):
    lat_min, lon_min, lat_max, lon_max = bbox
    parts = []

    def _filter(fh):
        for chunk in pd.read_csv(fh, usecols=lambda c: c in COLS, chunksize=200_000, low_memory=False,
                                 encoding="utf-8", encoding_errors="replace"):
            chunk = chunk.rename(columns=COLS)
            if "lon" not in chunk or "lat" not in chunk:
                return
            m = chunk.lat.between(lat_min, lat_max) & chunk.lon.between(lon_min, lon_max)
            if m.any():
                parts.append(chunk[m])

    if name.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    with z.open(n) as fh:
                        _filter(fh)
    else:
        _filter(io.BytesIO(raw))
    return pd.concat(parts) if parts else pd.DataFrame(columns=list(COLS.values()))


def _download_with_retries(url, attempts=3, log=print):
    """Streaming download; the repository server drops long connections fairly often."""
    for i in range(attempts):
        try:
            with _S.get(url, stream=True, timeout=(30, 300)) as r:
                if r.status_code != 200:
                    return None
                buf = io.BytesIO()
                for chunk in r.iter_content(chunk_size=1 << 20):
                    buf.write(chunk)
                return buf.getvalue()
        except requests.RequestException as e:
            log(f"    attempt {i + 1}/{attempts} failed ({str(e)[:60]}...)")
            time.sleep(10 * (i + 1))
    return None


def download_repository(species, bbox, log=print):
    """GPS fixes of the species inside the bbox from datasets published in the repository."""
    h = hashlib.md5(json.dumps(bbox).encode()).hexdigest()[:8]
    cache = config.CACHE_DIR / "movebank" / f"repo_{species.replace(' ', '_')}_{h}.parquet"
    if cache.exists():
        return _from_cache(cache)
    frames = []
    for item in search_repository(species):
        if not any(species.lower() in s.lower() for s in item["species"]):
            continue
        for bs in bitstreams(item["uuid"]):
            n = bs["name"].lower()
            if not (n.endswith(".csv") or n.endswith(".csv.zip")) or "reference-data" in n or "acceleration" in n \
                    or n.startswith("readme") or bs["bytes"] < 1000:
                continue
            if bs["bytes"] > config.MOVEBANK_MAX_MB * 1e6:
                log(f"  Movebank repo: {bs['name']} ({bs['bytes'] / 1e6:.0f} MB) is over the limit, skipped")
                continue
            log(f"  Movebank repo: downloading {bs['name']} ({bs['bytes'] / 1e6:.0f} MB)")
            raw = _download_with_retries(bs["url"], log=log)
            if raw is None:
                continue
            df = _read_filtered_csv(raw, bs["name"], bbox)
            df["source"] = item["title"]
            df["licence"] = item["licence"]
            frames.append(df)
    out = pd.concat(frames) if frames else pd.DataFrame(columns=list(COLS.values()) + ["source", "licence"])
    out["species"] = species
    out = out.astype({"individual": str})
    out.to_parquet(cache)
    return out


def download_public_study(study_id, bbox, log=print):
    """Public JSON endpoint (no login). Subject to rate limiting."""
    cache = config.CACHE_DIR / "movebank" / f"study_{study_id}.parquet"
    if cache.exists():
        df = _from_cache(cache)
    else:
        r = None
        for attempt in range(3):
            r = _S.get(config.MOVEBANK_PUBLIC_JSON, params={"study_id": study_id, "sensor_type": "gps"}, timeout=300)
            if r.status_code == 200 and r.text.startswith("{"):
                break
            time.sleep(20 * (attempt + 1))
        else:
            log(f"  Movebank: study {study_id} unavailable ({(r.text if r is not None else '')[:80]})")
            return pd.DataFrame()
        rows = []
        for ind in r.json().get("individuals", []):
            for loc in ind.get("locations", []):
                rows.append((loc["location_long"], loc["location_lat"], pd.Timestamp(loc["timestamp"], unit="ms"),
                             str(ind["individual_local_identifier"]), ind.get("individual_taxon_canonical_name")))
        df = pd.DataFrame(rows, columns=["lon", "lat", "timestamp", "individual", "species"])
        df.to_parquet(cache)
    lat_min, lon_min, lat_max, lon_max = bbox
    return df[df.lat.between(lat_min, lat_max) & df.lon.between(lon_min, lon_max)]


def download_direct_read(study_id, bbox, log=print):
    """Authenticated API. Requires MOVEBANK_USER, MOVEBANK_PASSWORD and having accepted the study licence."""
    if not (config.MOVEBANK_USER and config.MOVEBANK_PASSWORD):
        return pd.DataFrame()
    attrs = ("timestamp,location_long,location_lat,individual_local_identifier,height_above_ellipsoid,"
             "individual_taxon_canonical_name")
    params = {"entity_type": "event", "study_id": study_id, "sensor_type_id": 653, "attributes": attrs}
    r = _S.get(config.MOVEBANK_DIRECT_READ, params=params,
               auth=(config.MOVEBANK_USER, config.MOVEBANK_PASSWORD), timeout=900)
    if r.status_code != 200 or r.text.startswith("<"):
        log(f"  Movebank direct-read {study_id}: HTTP {r.status_code} (licence terms not accepted?)")
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(r.text))
    df = df.rename(columns={"location_long": "lon", "location_lat": "lat",
                            "individual_local_identifier": "individual", "height_above_ellipsoid": "height",
                            "individual_taxon_canonical_name": "species"})
    lat_min, lon_min, lat_max, lon_max = bbox
    return df[df.lat.between(lat_min, lat_max) & df.lon.between(lon_min, lon_max)]


def monthly_use(df, grid):
    """0-1 index (12, ny, nx) of space use: distinct individual-days per cell and month, smoothed."""
    if df is None or df.empty:
        return None
    df = df.dropna(subset=["lon", "lat", "timestamp"]).copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df = df.dropna(subset=["timestamp"])
    if "height" in df and df["height"].notna().any():
        # keep the low-altitude fixes where the height is known; where it is not, keep everything
        df = df[df["height"].isna() | (df["height"] < config.MOVEBANK_RISK_HEIGHT_M + 200)]
    df["month"] = df.timestamp.dt.month
    df["day"] = df.timestamp.dt.date
    row, col = grid.idx(df.lon.values, df.lat.values)
    df = df.assign(cell=row * grid.nx + col)[row >= 0]
    agg = df.drop_duplicates(["individual", "day", "cell"]).groupby(["month", "cell"]).size()
    out = np.zeros((12,) + grid.shape)
    for (m, cell), n in agg.items():
        out[m - 1].flat[int(cell)] += n
    sig = grid.sigma_px(config.KDE_SIGMA_M)
    for m in range(12):
        out[m] = smooth(out[m], sig)
    mx = out.max()
    return out / mx if mx > 0 else None


def species_tracking(species, bbox, grid, use_repo=True, study_ids=(), log=print):
    """Returns (monthly space-use index or None, number of GPS fixes inside the bbox)."""
    frames = []
    if use_repo:
        try:
            frames.append(download_repository(species, bbox, log=log))
        except Exception as e:  # noqa: BLE001
            log(f"  Movebank repo failed for {species}: {e}")
    for sid in study_ids:
        df = download_direct_read(sid, bbox, log=log) if config.MOVEBANK_USER \
            else download_public_study(sid, bbox, log=log)
        if not df.empty and "species" in df:
            df = df[df.species.fillna("").str.lower() == species.lower()]
        frames.append(df)
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return None, 0
    df = pd.concat(frames)
    return monthly_use(df, grid), len(df)
