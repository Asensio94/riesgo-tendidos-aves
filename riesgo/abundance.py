"""Abundancia relativa mensual por especie a partir de GBIF (que integra el eBird Observation Dataset).

Idea: densidad de citas de la especie / densidad de citas de todas las aves (esfuerzo de observación),
por mes, suavizada sobre la malla. Es una frecuencia relativa, no una abundancia absoluta.
"""
import hashlib
import json
import time

import numpy as np
import pandas as pd
import requests

from . import config
from .grid import suavizar

_S = requests.Session()
_S.headers["User-Agent"] = config.USER_AGENT


def _get(params, reintentos=config.GBIF_REINTENTOS):
    """GET con reintentos pacientes: GBIF devuelve 503 'Backend fetch failed' o 429 en picos de carga."""
    ultimo = None
    for i in range(reintentos):
        try:
            r = _S.get(config.GBIF_OCC_URL, params=params, timeout=180)
            if r.status_code == 200:
                return r.json()
            ultimo = f"HTTP {r.status_code}"
            espera = float(r.headers.get("Retry-After", 0) or 0)
        except requests.RequestException as e:
            ultimo, espera = str(e)[:80], 0
        time.sleep(max(espera, min(5 * 2 ** i, 120)))
    raise RuntimeError(f"GBIF no responde ({ultimo}) tras {reintentos} intentos: {params}")


def clave_especie(nombre):
    p = config.CACHE_DIR / "gbif" / "claves.json"
    claves = json.loads(p.read_text()) if p.exists() else {}
    if nombre not in claves:
        r = _S.get(config.GBIF_MATCH_URL, params={"name": nombre, "kingdom": "Animalia"}, timeout=60).json()
        if r.get("matchType") == "NONE" or "usageKey" not in r:
            raise ValueError(f"GBIF no reconoce la especie {nombre}")
        claves[nombre] = r["usageKey"]
        p.write_text(json.dumps(claves, indent=1))
    return claves[nombre]


def _bbox_params(bbox):
    lat_min, lon_min, lat_max, lon_max = bbox
    return {"decimalLatitude": f"{lat_min},{lat_max}", "decimalLongitude": f"{lon_min},{lon_max}",
            "hasCoordinate": "true", "hasGeospatialIssue": "false",
            "year": f"{config.GBIF_YEAR_FROM},2100"}


def _cache_key(*parts):
    return hashlib.md5(json.dumps(parts).encode()).hexdigest()[:12]


COLUMNAS = ["lon", "lat", "month", "year", "datasetKey", "individualCount"]


def _fila(r):
    return (r.get("decimalLongitude"), r.get("decimalLatitude"), r.get("month"),
            r.get("year"), r.get("datasetKey"), r.get("individualCount"))


def _paginar_bloque(params, total):
    """Páginas de un bloque (≤ GBIF_MAX_OFFSET citas), GBIF_HILOS en paralelo."""
    from concurrent.futures import ThreadPoolExecutor

    offsets = list(range(0, min(total, config.GBIF_MAX_OFFSET), config.GBIF_PAGE))
    filas = []
    with ThreadPoolExecutor(max_workers=config.GBIF_HILOS) as ex:
        for d in ex.map(lambda off: _get({**params, "offset": off}), offsets):
            filas.extend(_fila(r) for r in d["results"])
    return filas


def _paginar(params, total=None, log=print):
    """Descarga las citas por bloques anuales (de más reciente a más antiguo) para mantener offsets pequeños,
    hasta GBIF_MAX_CITAS. El paginado profundo de GBIF es muy lento; los años recientes son además los
    más representativos de la infraestructura actual."""
    d = _get({**params, "limit": 0, "facet": "year", "facetLimit": 200})
    por_year = sorted(((int(c["name"]), c["count"]) for f in d.get("facets", []) for c in f["counts"]), reverse=True)
    filas, acumulado = [], 0
    for year, n in por_year:
        if n == 0:
            continue
        if acumulado >= config.GBIF_MAX_CITAS:
            log(f"    tope de {config.GBIF_MAX_CITAS} citas alcanzado; se omiten años ≤ {year}")
            break
        p = {**params, "year": str(year)}
        # cada bloque anual se cachea aparte para poder reanudar si GBIF se cae a mitad
        pc = config.CACHE_DIR / "gbif" / "bloques" / f"{_cache_key(p)}.parquet"
        if pc.exists():
            bloque = [tuple(x) for x in pd.read_parquet(pc).itertuples(index=False)]
        else:
            if n > config.GBIF_MAX_OFFSET:  # año enorme: trocear por mes
                bloque = []
                for m in range(1, 13):
                    sub = _get({**p, "month": m, "limit": 0})["count"]
                    bloque += _paginar_bloque({**p, "month": m}, sub)
            else:
                bloque = _paginar_bloque(p, n)
            pc.parent.mkdir(exist_ok=True)
            pd.DataFrame(bloque, columns=COLUMNAS).to_parquet(pc)
        filas += bloque
        acumulado += n
    return filas


def citas_especie(nombre, bbox, log=print):
    """DataFrame con lon, lat, month, year, datasetKey de las citas de la especie en la bbox."""
    key = clave_especie(nombre)
    p = config.CACHE_DIR / "gbif" / f"citas_{key}_{_cache_key(bbox)}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    params = {**_bbox_params(bbox), "taxonKey": key, "limit": config.GBIF_PAGE}
    total = _get({**params, "limit": 0})["count"]
    log(f"  {nombre}: {total} citas en GBIF")
    filas = _paginar(params, total=total, log=log) if total else []
    df = pd.DataFrame(filas, columns=COLUMNAS)
    df = df.dropna(subset=["month", "lon", "lat"])
    df["month"] = df["month"].astype(int)
    df.to_parquet(p)
    return df


def esfuerzo_mensual(bbox, log=print):
    """Nº de citas de Aves por tesela (EFFORT_TILE_DEG) y mes. DataFrame lat, lon (centro), month, n."""
    p = config.CACHE_DIR / "gbif" / f"esfuerzo_{_cache_key(bbox, config.EFFORT_TILE_DEG, config.GBIF_YEAR_FROM)}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    lat_min, lon_min, lat_max, lon_max = bbox
    t = config.EFFORT_TILE_DEG
    lats = np.arange(lat_min, lat_max - 1e-9, t)
    lons = np.arange(lon_min, lon_max - 1e-9, t)
    log(f"  esfuerzo de muestreo (todas las aves): {len(lats) * len(lons)} teselas de {t}°")
    filas = []
    for la in lats:
        for lo in lons:
            sub = (la, lo, min(la + t, lat_max), min(lo + t, lon_max))
            d = _get({**_bbox_params(sub), "taxonKey": config.AVES_TAXON_KEY, "limit": 0,
                      "facet": "month", "facetLimit": 12})
            conteo = {int(c["name"]): c["count"] for f in d.get("facets", []) for c in f["counts"]}
            for m in range(1, 13):
                filas.append((la, lo, m, conteo.get(m, 0)))
    df = pd.DataFrame(filas, columns=["lat0", "lon0", "month", "n"])
    df.to_parquet(p)
    return df


def raster_esfuerzo(esf, grid):
    """Esfuerzo por mes sobre la malla (citas de aves por km²), suavizado. Shape (12, ny, nx)."""
    out = np.zeros((12,) + grid.shape)
    t = config.EFFORT_TILE_DEG
    lat_c, lon_c = grid.lat_centros(), grid.lon_centros()
    sig = grid.sigma_px(t * 111_320 / 2)
    for m in range(1, 13):
        arr = np.zeros(grid.shape)
        for r in esf[esf.month == m].itertuples():
            filas = (lat_c >= r.lat0) & (lat_c < r.lat0 + t)
            cols = (lon_c >= r.lon0) & (lon_c < r.lon0 + t)
            n_celdas = filas.sum() * cols.sum()
            if n_celdas:
                arr[np.ix_(filas, cols)] = r.n / n_celdas
        out[m - 1] = suavizar(arr, sig) / grid.area_km2
    return out


def presencia_mensual(nombre, bbox, grid, esfuerzo_raster, log=print):
    """Índice 0-1 de frecuencia relativa por mes (12, ny, nx) y nº de citas. None si hay muy pocas citas."""
    df = citas_especie(nombre, bbox, log=log)
    if len(df) < config.MIN_CITAS_ESPECIE:
        log(f"  {nombre}: solo {len(df)} citas, se omite")
        return None, len(df)
    out = np.zeros((12,) + grid.shape)
    for m in range(1, 13):
        sub = df[df.month == m]
        if sub.empty:
            continue
        # suavizado adaptativo: con pocas citas solo se puede afirmar un patrón amplio
        factor = max(1.0, np.sqrt(config.KDE_N_REF / len(sub)))
        sig = grid.sigma_px(config.KDE_SIGMA_M * factor)
        # las citas repetidas en el mismo punto (~100 m) y mismo mes/año (un observador que vuelve, varias listas
        # de eBird del mismo día) cuentan con peso sqrt(n): informan de presencia regular, pero no n veces
        pila = sub.groupby([sub.year, sub.month, sub.lat.round(3), sub.lon.round(3)]).size().reset_index(name="n")
        dens = suavizar(grid.contar(pila.lon.values, pila.lat.values, np.sqrt(pila.n.values)), sig) / grid.area_km2
        esf = esfuerzo_raster[m - 1]
        # prior (esfuerzo mediano) para no disparar celdas casi sin esfuerzo de observación
        prior = np.percentile(esf[esf > 0], 50) if (esf > 0).any() else 1.0
        out[m - 1] = dens / (esf + prior)
    mx = out.max()
    if mx > 0:
        out /= mx
    return out, len(df)
