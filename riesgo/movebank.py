"""Datos de seguimiento GPS de Movebank (opcional).

Tres vías, de menos a más exigente:
1. Movebank Data Repository (DSpace, datasets publicados CC0/CC-BY): búsqueda por especie y descarga de CSV.
2. Endpoint JSON público de Movebank para estudios marcados como públicos (por study_id).
3. API direct-read con usuario/contraseña de Movebank (MOVEBANK_USER / MOVEBANK_PASSWORD).
Los datos se filtran a la bbox y se agregan a "individuos-día por celda y mes".
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
from .grid import suavizar

_S = requests.Session()
_S.headers["User-Agent"] = config.USER_AGENT

COLS = {"location-long": "lon", "location-lat": "lat", "timestamp": "timestamp",
        "individual-local-identifier": "individuo", "height-above-ellipsoid": "altura",
        "height-above-msl": "altura_msl", "individual-taxon-canonical-name": "especie"}


def buscar_repositorio(especie, max_items=20):
    """Ítems del Movebank Data Repository cuyo título o asunto menciona la especie."""
    r = _S.get(config.MOVEBANK_REPO_SEARCH, params={"query": f'"{especie}"', "size": max_items,
                                                     "dsoType": "ITEM"}, timeout=90)
    r.raise_for_status()
    objs = r.json()["_embedded"]["searchResult"]["_embedded"]["objects"]
    items = []
    for o in objs:
        io_ = o["_embedded"]["indexableObject"]
        md = io_.get("metadata", {})
        especies = [v["value"] for v in md.get("dwc.scientificName", [])] or \
                   [v["value"] for v in md.get("dc.subject", [])]
        items.append({"uuid": io_["uuid"], "titulo": io_.get("name"),
                      "licencia": (md.get("dc.rights") or [{}])[0].get("value"), "especies": especies})
    return items


def bitstreams(uuid):
    b = _S.get(config.MOVEBANK_REPO_ITEM.format(uuid=uuid) + "/bundles", timeout=90).json()
    for bundle in b["_embedded"]["bundles"]:
        if bundle["name"] != "ORIGINAL":
            continue
        bs = _S.get(bundle["_links"]["bitstreams"]["href"], params={"size": 100}, timeout=90).json()
        return [{"nombre": x["name"], "bytes": x["sizeBytes"], "url": x["_links"]["content"]["href"]}
                for x in bs["_embedded"]["bitstreams"]]
    return []


def _leer_csv_filtrado(raw, nombre, bbox):
    lat_min, lon_min, lat_max, lon_max = bbox
    partes = []

    def _filtrar(fh):
        for chunk in pd.read_csv(fh, usecols=lambda c: c in COLS, chunksize=200_000, low_memory=False,
                                 encoding="utf-8", encoding_errors="replace"):
            chunk = chunk.rename(columns=COLS)
            if "lon" not in chunk or "lat" not in chunk:
                return
            m = chunk.lat.between(lat_min, lat_max) & chunk.lon.between(lon_min, lon_max)
            if m.any():
                partes.append(chunk[m])

    if nombre.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    with z.open(n) as fh:
                        _filtrar(fh)
    else:
        _filtrar(io.BytesIO(raw))
    return pd.concat(partes) if partes else pd.DataFrame(columns=list(COLS.values()))


def _descargar_con_reintentos(url, intentos=3, log=print):
    """Descarga en streaming; el servidor del repositorio corta conexiones largas con cierta frecuencia."""
    for i in range(intentos):
        try:
            with _S.get(url, stream=True, timeout=(30, 300)) as r:
                if r.status_code != 200:
                    return None
                buf = io.BytesIO()
                for chunk in r.iter_content(chunk_size=1 << 20):
                    buf.write(chunk)
                return buf.getvalue()
        except requests.RequestException as e:
            log(f"    intento {i + 1}/{intentos} fallido ({str(e)[:60]}…)")
            time.sleep(10 * (i + 1))
    return None


def descargar_repositorio(especie, bbox, log=print):
    """Posiciones GPS de la especie dentro de la bbox procedentes de datasets publicados en el repositorio."""
    h = hashlib.md5(json.dumps(bbox).encode()).hexdigest()[:8]
    cache = config.CACHE_DIR / "movebank" / f"repo_{especie.replace(' ', '_')}_{h}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    frames = []
    for item in buscar_repositorio(especie):
        if not any(especie.lower() in s.lower() for s in item["especies"]):
            continue
        for bs in bitstreams(item["uuid"]):
            n = bs["nombre"].lower()
            if not (n.endswith(".csv") or n.endswith(".csv.zip")) or "reference-data" in n or "acceleration" in n \
                    or n.startswith("readme") or bs["bytes"] < 1000:
                continue
            if bs["bytes"] > config.MOVEBANK_MAX_MB * 1e6:
                log(f"  Movebank repo: {bs['nombre']} ({bs['bytes'] / 1e6:.0f} MB) supera el límite, se omite")
                continue
            log(f"  Movebank repo: descargando {bs['nombre']} ({bs['bytes'] / 1e6:.0f} MB)")
            raw = _descargar_con_reintentos(bs["url"], log=log)
            if raw is None:
                continue
            df = _leer_csv_filtrado(raw, bs["nombre"], bbox)
            df["fuente"] = item["titulo"]
            df["licencia"] = item["licencia"]
            frames.append(df)
    out = pd.concat(frames) if frames else pd.DataFrame(columns=list(COLS.values()) + ["fuente", "licencia"])
    out["especie"] = especie
    out = out.astype({"individuo": str})
    out.to_parquet(cache)
    return out


def descargar_estudio_publico(study_id, bbox, log=print):
    """Endpoint JSON público (sin login). Sujeto a rate limiting."""
    cache = config.CACHE_DIR / "movebank" / f"study_{study_id}.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
    else:
        r = None
        for intento in range(3):
            r = _S.get(config.MOVEBANK_PUBLIC_JSON, params={"study_id": study_id, "sensor_type": "gps"}, timeout=300)
            if r.status_code == 200 and r.text.startswith("{"):
                break
            time.sleep(20 * (intento + 1))
        else:
            log(f"  Movebank: estudio {study_id} no disponible ({(r.text if r is not None else '')[:80]})")
            return pd.DataFrame()
        filas = []
        for ind in r.json().get("individuals", []):
            for loc in ind.get("locations", []):
                filas.append((loc["location_long"], loc["location_lat"], pd.Timestamp(loc["timestamp"], unit="ms"),
                              str(ind["individual_local_identifier"]), ind.get("individual_taxon_canonical_name")))
        df = pd.DataFrame(filas, columns=["lon", "lat", "timestamp", "individuo", "especie"])
        df.to_parquet(cache)
    lat_min, lon_min, lat_max, lon_max = bbox
    return df[df.lat.between(lat_min, lat_max) & df.lon.between(lon_min, lon_max)]


def descargar_direct_read(study_id, bbox, log=print):
    """API autenticada. Requiere MOVEBANK_USER y MOVEBANK_PASSWORD y haber aceptado la licencia del estudio."""
    if not (config.MOVEBANK_USER and config.MOVEBANK_PASSWORD):
        return pd.DataFrame()
    attrs = "timestamp,location_long,location_lat,individual_local_identifier,height_above_ellipsoid,individual_taxon_canonical_name"
    params = {"entity_type": "event", "study_id": study_id, "sensor_type_id": 653, "attributes": attrs}
    r = _S.get(config.MOVEBANK_DIRECT_READ, params=params,
               auth=(config.MOVEBANK_USER, config.MOVEBANK_PASSWORD), timeout=900)
    if r.status_code != 200 or r.text.startswith("<"):
        log(f"  Movebank direct-read {study_id}: HTTP {r.status_code} (¿términos de licencia sin aceptar?)")
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(r.text))
    df = df.rename(columns={"location_long": "lon", "location_lat": "lat", "individual_local_identifier": "individuo",
                            "height_above_ellipsoid": "altura", "individual_taxon_canonical_name": "especie"})
    lat_min, lon_min, lat_max, lon_max = bbox
    return df[df.lat.between(lat_min, lat_max) & df.lon.between(lon_min, lon_max)]


def uso_mensual(df, grid):
    """Índice 0-1 (12, ny, nx) de uso del espacio: individuos-día distintos por celda y mes, suavizado."""
    if df is None or df.empty:
        return None
    df = df.dropna(subset=["lon", "lat", "timestamp"]).copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df = df.dropna(subset=["timestamp"])
    if "altura" in df and df["altura"].notna().any():
        # nos quedamos con posiciones a baja altura cuando hay dato; si no hay dato, con todas
        df = df[df["altura"].isna() | (df["altura"] < config.MOVEBANK_ALTURA_RIESGO_M + 200)]
    df["month"] = df.timestamp.dt.month
    df["dia"] = df.timestamp.dt.date
    row, col = grid.idx(df.lon.values, df.lat.values)
    df = df.assign(celda=row * grid.nx + col)[row >= 0]
    agg = df.drop_duplicates(["individuo", "dia", "celda"]).groupby(["month", "celda"]).size()
    out = np.zeros((12,) + grid.shape)
    for (m, celda), n in agg.items():
        out[m - 1].flat[int(celda)] += n
    sig = grid.sigma_px(config.KDE_SIGMA_M)
    for m in range(12):
        out[m] = suavizar(out[m], sig)
    mx = out.max()
    return out / mx if mx > 0 else None


def seguimiento_especie(especie, bbox, grid, usar_repo=True, study_ids=(), log=print):
    """Devuelve (índice de uso mensual o None, nº de posiciones GPS dentro de la bbox)."""
    frames = []
    if usar_repo:
        try:
            frames.append(descargar_repositorio(especie, bbox, log=log))
        except Exception as e:  # noqa: BLE001
            log(f"  Movebank repo falló para {especie}: {e}")
    for sid in study_ids:
        df = descargar_direct_read(sid, bbox, log=log) if config.MOVEBANK_USER else descargar_estudio_publico(sid, bbox, log=log)
        if not df.empty and "especie" in df:
            df = df[df.especie.fillna("").str.lower() == especie.lower()]
        frames.append(df)
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return None, 0
    df = pd.concat(frames)
    return uso_mensual(df, grid), len(df)
