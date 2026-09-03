"""Risk model: species presence x exposure to the infrastructure x terrain factors.

For each species s and month m, on every grid cell:

  electro[s,m] = P[s,m] * w_electro[s] * pylons_eq                        (distribution pylons, <=66 kV)
  col_lin[s,m] = P[s,m] * w_col_lin[s] * line_km * (1 + relief)           (all conductors)
  col_aer[s,m] = P[s,m] * w_col_aer[s] * n_turbines * (1 + ridge)

P is the 0-1 relative presence (GBIF/eBird, blended with Movebank where available); pylons_eq combines the mapped
pylons with an estimate from the km of distribution line where OSM has no pylons. The indices are rescaled to
0-100 by the 99th percentile so that months and mechanisms are comparable.
"""
import numpy as np
import pandas as pd

from . import config

MECHANISMS = ("electro", "col_lin", "col_aer")
# Canonical mechanism label written to the ranking files, per internal mechanism key.
MECHANISM_LABEL = {"electro": "electrocution", "col_lin": "line_collision", "col_aer": "turbine_collision"}
PYLONS_PER_KM = 6.0  # typical pylons per km of distribution line when OSM has none mapped


def _scale_100(arr, p=99):
    """Rescale so that percentile `p` of the non-zero cells becomes 100.

    Nothing is clipped: values above 100 (the top 1%) keep their order, which is what lets the ranking
    discriminate inside that tail; the map simply paints them saturated.
    """
    nz = arr[arr > 0]
    if nz.size == 0:
        return np.zeros_like(arr)
    ref = np.percentile(nz, p)
    return arr / max(ref, 1e-12) * 100.0


def base_exposure(expo):
    mapped = expo["n_pylons_distribution"] + 0.5 * expo["n_pylons_unknown"]
    estimated = PYLONS_PER_KM * (expo["line_km_distribution"] + 0.5 * expo["line_km_unknown"])
    return {
        # cap per cell: dozens of pylons in ~0.2 km2 are a substation, not a more dangerous power line
        "pylons_eq": np.minimum(np.maximum(mapped, estimated), config.PYLONS_MAX_PER_CELL),
        "line_km": expo["line_km_total"],
        "turbines": expo["n_turbines"],
    }


def compute(presences, expo, factors, species_cfg, confidence=None):
    """presences: {species: array (12, ny, nx)}; confidence: {species: 0-1} (reliability of that species' map).

    Returns a dict with the per-species and aggregate layers.
    """
    base = base_exposure(expo)
    relief, ridge = factors["relief"], factors["ridge"]
    confidence = confidence or {}
    by_species = {}
    aggregate = {k: np.zeros_like(next(iter(presences.values()))) for k in MECHANISMS}
    for sp, P in presences.items():
        cfg = species_cfg[sp]
        raw = {
            "electro": P * cfg["electro"] * base["pylons_eq"][None],
            "col_lin": P * cfg["col_lin"] * base["line_km"][None] * (1 + relief)[None],
            "col_aer": P * cfg["col_aer"] * base["turbines"][None] * (1 + ridge)[None],
        }
        by_species[sp] = {k: _scale_100(v) for k, v in raw.items()}
        for k in MECHANISMS:
            aggregate[k] += cfg["status"] * confidence.get(sp, 1.0) * raw[k]
    aggregate = {k: _scale_100(v) for k, v in aggregate.items()}
    weights = config.MECHANISM_WEIGHT
    total = sum(weights[k] * aggregate[k] for k in MECHANISMS) / sum(weights.values())
    total = _scale_100(total)
    for sp in by_species:
        t = sum(weights[k] * by_species[sp][k] for k in MECHANISMS) / sum(weights.values())
        by_species[sp]["total"] = _scale_100(t)
    return {"by_species": by_species, "aggregate": aggregate, "total": total, "base": base}


def _cell_of(grid, lon, lat):
    row, col = grid.idx(np.array([lon]), np.array([lat]))
    return int(row[0]), int(col[0])


def _dominant_species(result, mechanism, r, c, m, n=3):
    """Scientific names of the species contributing most to a cell, comma separated (language-independent)."""
    contrib = []
    for sp, layers in result["by_species"].items():
        v = layers[mechanism][m, r, c]
        if v > 0:
            contrib.append((v, sp))
    contrib.sort(reverse=True)
    return ", ".join(sp for _, sp in contrib[:n])


def rank_elements(result, infra, grid):
    """Score every pylon, wind turbine and line segment from the cells it occupies."""
    rows = []
    agg = result["aggregate"]
    for a in infra["pylons"]:
        if a["category"] == "transmission":
            continue
        r, c = _cell_of(grid, a["lon"], a["lat"])
        if r < 0:
            continue
        # cell index x the pylon's own hazard factor (1.0 when OSM has no attributes for it)
        hazard = a.get("hazard", 1.0)
        series = agg["electro"][:, r, c] * hazard
        m = int(series.argmax())
        rows.append(dict(type="pylon", osm_id=a["id"], osm_url=f"https://www.openstreetmap.org/node/{a['id']}",
                         lat=a["lat"], lon=a["lon"], mechanism=MECHANISM_LABEL["electro"], category=a["category"],
                         voltage=a["voltage"], detail=a["type"], operator=a["operator"], hazard=hazard,
                         risk_max=float(series.max()), risk_mean=float(series.mean()),
                         peak_month=config.MONTHS[m], species=_dominant_species(result, "electro", r, c, m)))
    for t in infra["turbines"]:
        r, c = _cell_of(grid, t["lon"], t["lat"])
        if r < 0:
            continue
        series = agg["col_aer"][:, r, c]
        m = int(series.argmax())
        rows.append(dict(type="turbine", osm_id=t["id"], osm_url=f"https://www.openstreetmap.org/node/{t['id']}",
                         lat=t["lat"], lon=t["lon"], mechanism=MECHANISM_LABEL["col_aer"], category="wind",
                         voltage=None, detail=t["power_output"], operator=t["operator"],
                         risk_max=float(series.max()), risk_mean=float(series.mean()),
                         peak_month=config.MONTHS[m], species=_dominant_species(result, "col_aer", r, c, m)))
    for ln in infra["lines"]:
        lon = np.array([p[0] for p in ln["coords"]])
        lat = np.array([p[1] for p in ln["coords"]])
        row, col = grid.idx(lon, lat)
        ok = row >= 0
        if not ok.any():
            continue
        cells = np.unique(row[ok] * grid.nx + col[ok])
        series = agg["col_lin"].reshape(12, -1)[:, cells].mean(axis=1)
        m = int(series.argmax())
        worst = int(agg["col_lin"][m].flat[cells].argmax())
        r, c = divmod(int(cells[worst]), grid.nx)
        rows.append(dict(type="line", osm_id=ln["id"], osm_url=f"https://www.openstreetmap.org/way/{ln['id']}",
                         lat=float(lat[ok].mean()), lon=float(lon[ok].mean()),
                         mechanism=MECHANISM_LABEL["col_lin"], category=ln["category"], voltage=ln["voltage"],
                         detail=ln["name"] or ln["power"], operator=ln["operator"],
                         risk_max=float(series.max()), risk_mean=float(series.mean()),
                         peak_month=config.MONTHS[m], species=_dominant_species(result, "col_lin", r, c, m)))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("risk_max", ascending=False).reset_index(drop=True)


def seasonal_table(result):
    """Mean of the total index per species and month over the cells with infrastructure.

    Indexed by scientific name (plus the literal 'TOTAL' row) and with the canonical month names as columns,
    so the report can translate both at render time.
    """
    rows = {}
    for sp, layers in result["by_species"].items():
        t = layers["total"]
        with_infra = t.reshape(12, -1).max(axis=0) > 0
        rows[sp] = [float(t[m].reshape(-1)[with_infra].mean()) if with_infra.any() else 0.0 for m in range(12)]
    total = result["total"]
    with_infra = total.reshape(12, -1).max(axis=0) > 0
    rows["TOTAL"] = [float(total[m].reshape(-1)[with_infra].mean()) if with_infra.any() else 0.0 for m in range(12)]
    return pd.DataFrame(rows, index=config.MONTHS).T
