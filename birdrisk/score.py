"""Score projects (polygons) against the risk rasters already computed.

Built for the public consultation observatory: every notice about a wind farm or a power line arrives with the
geometry of its municipalities; here it gets the risk index of the region (mean and monthly maximum) so that the
projects worth a formal submission on bird grounds can be prioritised.
"""
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


def _slug(s):
    """Same rule as observatorio.geo._slug, so its cache of municipal geometries can be reused."""
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def observatory_features(state_json, geo_cache, categories=None):
    """Turn the geolocated notices of the observatory into GeoJSON features (union of their municipalities).

    The observatory stores its data in Spanish, so its own field names are read verbatim and mapped here.
    """
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    state = json.loads(Path(state_json).read_text(encoding="utf-8"))
    geo_cache = Path(geo_cache)
    feats = []
    for ident, a in state.get("anuncios", {}).items():
        if not a.get("geolocalizado"):
            continue
        if categories and a.get("categoria") not in categories:
            continue
        geoms = []
        provinces = a.get("provincias") or [None]
        for muni in a.get("municipios", []):
            for prov in provinces + [None]:
                p = geo_cache / f"{_slug(muni + '_' + (prov or ''))}.json"
                if p.exists():
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data:
                        geoms.append(shape(data))
                    break
        if not geoms:
            continue
        feats.append({"type": "Feature", "geometry": mapping(unary_union(geoms)),
                      "properties": {"id": ident, "title": a.get("titulo", "")[:140],
                                     "category": a.get("categoria"), "date": a.get("fecha"),
                                     "deadline": a.get("fecha_limite"),
                                     "municipalities": ", ".join(a.get("municipios", [])),
                                     "url": a.get("url_html")}})
    return {"type": "FeatureCollection", "features": feats}


def score(features, region_dir):
    """Statistics of the region's total index (and per mechanism) over each feature's polygon.

    Returns a DataFrame with risk_mean, risk_max, peak_month, the share of cells holding infrastructure and, per
    mechanism, the annual maximum. Polygons outside the raster come back as NaN.
    """
    import rasterio
    from rasterio.mask import mask
    from shapely.geometry import shape

    folder = Path(region_dir)
    rasters = {"total": folder / "risk_total.tif"}
    for k in ("electro", "col_lin", "col_aer"):
        p = folder / f"risk_{k}.tif"
        if p.exists():
            rasters[k] = p
    rows = []
    opened = {k: rasterio.open(p) for k, p in rasters.items() if p.exists()}
    try:
        for f in features["features"]:
            geom = shape(f["geometry"])
            row = dict(f.get("properties", {}))
            row["area_km2"] = round(geom.area * 111.32 * 111.32 * np.cos(np.radians(geom.centroid.y)), 1)
            try:
                arr, _ = mask(opened["total"], [f["geometry"]], crop=True, all_touched=True, nodata=np.nan)
            except ValueError:  # outside the raster
                row.update(risk_mean=np.nan, risk_max=np.nan, peak_month=None, pct_cells_with_infra=np.nan)
                rows.append(row)
                continue
            valid = np.isfinite(arr)
            if not valid.any():
                row.update(risk_mean=np.nan, risk_max=np.nan, peak_month=None, pct_cells_with_infra=np.nan)
                rows.append(row)
                continue
            with_infra = np.nanmax(arr, axis=0) > 0
            means = np.array([np.nanmean(arr[m][with_infra]) if with_infra.any() else 0.0
                              for m in range(arr.shape[0])])
            row["risk_mean"] = round(float(means.mean()), 1)
            row["risk_max"] = round(float(np.nanmax(arr)), 1)
            row["peak_month"] = config.MONTHS[int(means.argmax())]
            row["pct_cells_with_infra"] = round(100 * with_infra.sum() / valid.any(axis=0).sum(), 1)
            for k in ("electro", "col_lin", "col_aer"):
                if k in opened:
                    a2, _ = mask(opened[k], [f["geometry"]], crop=True, all_touched=True, nodata=np.nan)
                    row[f"max_{k}"] = round(float(np.nanmax(a2)), 1) if np.isfinite(a2).any() else np.nan
            rows.append(row)
    finally:
        for r in opened.values():
            r.close()
    df = pd.DataFrame(rows)
    if not df.empty and "risk_max" in df:
        df = df.sort_values("risk_max", ascending=False).reset_index(drop=True)
    return df
