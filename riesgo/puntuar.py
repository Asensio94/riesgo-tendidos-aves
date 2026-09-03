"""Puntuar proyectos (polígonos) con los rásteres de riesgo ya calculados.

Pensado para el observatorio de alegaciones: cada anuncio de un parque eólico o una línea eléctrica llega con la
geometría de sus municipios; aquí se le asigna el índice de riesgo de la región (medio y máximo por mes) para
priorizar qué proyectos merecen alegación por avifauna.
"""
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


def _slug(s):
    """Misma regla que observatorio.geo._slug, para reutilizar su caché de geometrías municipales."""
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def features_observatorio(estado_json, geo_cache, categorias=None):
    """Convierte los anuncios geolocalizados del observatorio en features GeoJSON (unión de sus municipios)."""
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    estado = json.loads(Path(estado_json).read_text(encoding="utf-8"))
    geo_cache = Path(geo_cache)
    feats = []
    for ident, a in estado.get("anuncios", {}).items():
        if not a.get("geolocalizado"):
            continue
        if categorias and a.get("categoria") not in categorias:
            continue
        geoms = []
        provs = a.get("provincias") or [None]
        for muni in a.get("municipios", []):
            for prov in provs + [None]:
                p = geo_cache / f"{_slug(f'{muni}_{prov or ''}')}.json"
                if p.exists():
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data:
                        geoms.append(shape(data))
                    break
        if not geoms:
            continue
        feats.append({"type": "Feature", "geometry": mapping(unary_union(geoms)),
                      "properties": {"id": ident, "titulo": a.get("titulo", "")[:140], "categoria": a.get("categoria"),
                                     "fecha": a.get("fecha"), "fecha_limite": a.get("fecha_limite"),
                                     "municipios": ", ".join(a.get("municipios", [])), "url": a.get("url_html")}})
    return {"type": "FeatureCollection", "features": feats}


def puntuar(features, carpeta_region):
    """Para cada feature, estadísticas del índice total (y por mecanismo) de la región sobre su polígono.

    Devuelve un DataFrame con riesgo_medio, riesgo_max, mes_pico, % de celdas con infraestructura y, por mecanismo,
    el máximo anual. Los polígonos fuera del ráster quedan con NaN.
    """
    import rasterio
    from rasterio.mask import mask
    from shapely.geometry import shape

    carpeta = Path(carpeta_region)
    rasters = {"total": carpeta / "riesgo_total.tif"}
    for k in ("electro", "col_lin", "col_aer"):
        p = carpeta / f"riesgo_{k}.tif"
        if p.exists():
            rasters[k] = p
    filas = []
    abiertos = {k: rasterio.open(p) for k, p in rasters.items() if p.exists()}
    try:
        for f in features["features"]:
            geom = shape(f["geometry"])
            fila = dict(f.get("properties", {}))
            fila["area_km2"] = round(geom.area * 111.32 * 111.32 * np.cos(np.radians(geom.centroid.y)), 1)
            try:
                arr, _ = mask(abiertos["total"], [f["geometry"]], crop=True, all_touched=True, nodata=np.nan)
            except ValueError:  # fuera del ráster
                fila.update(riesgo_medio=np.nan, riesgo_max=np.nan, mes_pico=None, pct_celdas_con_infra=np.nan)
                filas.append(fila)
                continue
            valido = np.isfinite(arr)
            if not valido.any():
                fila.update(riesgo_medio=np.nan, riesgo_max=np.nan, mes_pico=None, pct_celdas_con_infra=np.nan)
                filas.append(fila)
                continue
            con_infra = np.nanmax(arr, axis=0) > 0
            medias = np.array([np.nanmean(arr[m][con_infra]) if con_infra.any() else 0.0 for m in range(arr.shape[0])])
            fila["riesgo_medio"] = round(float(medias.mean()), 1)
            fila["riesgo_max"] = round(float(np.nanmax(arr)), 1)
            fila["mes_pico"] = config.MESES[int(medias.argmax())]
            fila["pct_celdas_con_infra"] = round(100 * con_infra.sum() / valido.any(axis=0).sum(), 1)
            for k in ("electro", "col_lin", "col_aer"):
                if k in abiertos:
                    a2, _ = mask(abiertos[k], [f["geometry"]], crop=True, all_touched=True, nodata=np.nan)
                    fila[f"max_{k}"] = round(float(np.nanmax(a2)), 1) if np.isfinite(a2).any() else np.nan
            filas.append(fila)
    finally:
        for r in abiertos.values():
            r.close()
    df = pd.DataFrame(filas)
    if not df.empty and "riesgo_max" in df:
        df = df.sort_values("riesgo_max", ascending=False).reset_index(drop=True)
    return df
