"""Topografía a partir de AWS Terrain Tiles (formato terrarium, sin clave): elevación, pendiente y posición topográfica."""
import io
import math

import numpy as np
import requests
from PIL import Image

from . import config
from .grid import suavizar


def _tile_xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n
    return x, y


def _descargar_tesela(z, x, y):
    p = config.CACHE_DIR / "terrain" / f"{z}_{x}_{y}.png"
    if p.exists():
        raw = p.read_bytes()
    else:
        r = requests.get(config.TERRAIN_URL.format(z=z, x=x, y=y), timeout=60,
                         headers={"User-Agent": config.USER_AGENT})
        r.raise_for_status()
        raw = r.content
        p.write_bytes(raw)
    im = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")).astype(np.float64)
    return im[..., 0] * 256.0 + im[..., 1] + im[..., 2] / 256.0 - 32768.0


def mosaico(bbox, z=config.TERRAIN_ZOOM):
    """Elevación (m) en píxeles Web Mercator que cubren la bbox y origen (z, tx0, ty0)."""
    lat_min, lon_min, lat_max, lon_max = bbox
    x0, y0 = _tile_xy(lat_max, lon_min, z)
    x1, y1 = _tile_xy(lat_min, lon_max, z)
    tx0, tx1 = int(math.floor(x0)), int(math.floor(x1))
    ty0, ty1 = int(math.floor(y0)), int(math.floor(y1))
    filas = []
    for ty in range(ty0, ty1 + 1):
        fila = [_descargar_tesela(z, tx, ty) for tx in range(tx0, tx1 + 1)]
        filas.append(np.hstack(fila))
    return np.vstack(filas), (z, tx0, ty0)


def _muestrear(arr, origen, lons, lats):
    z, tx0, ty0 = origen
    n = 2 ** z
    px = ((lons + 180.0) / 360.0 * n - tx0) * 256.0
    lat_r = np.radians(lats)
    py = ((1.0 - np.log(np.tan(lat_r) + 1.0 / np.cos(lat_r)) / math.pi) / 2.0 * n - ty0) * 256.0
    c = np.clip(px.astype(int), 0, arr.shape[1] - 1)
    r = np.clip(py.astype(int), 0, arr.shape[0] - 1)
    return arr[r, c]


def capas_topografia(bbox, grid):
    """Devuelve dict con elevación (m), pendiente (grados) y TPI (m) sobre la malla de análisis."""
    elev_px, origen = mosaico(bbox)
    z = origen[0]
    m_px = 40_075_016.686 * math.cos(math.radians(grid.lat_centro)) / (256 * 2 ** z)
    elev_px = suavizar(elev_px, 1.0)  # quita el ruido de cuantización
    gy, gx = np.gradient(elev_px, m_px)
    pend_px = np.degrees(np.arctan(np.hypot(gx, gy)))
    tpi_px = elev_px - suavizar(elev_px, config.TPI_RADIO_M / m_px)

    lons, lats = np.meshgrid(grid.lon_centros(), grid.lat_centros())
    lons, lats = lons.ravel(), lats.ravel()
    return {
        "elevacion": _muestrear(elev_px, origen, lons, lats).reshape(grid.shape),
        "pendiente": _muestrear(pend_px, origen, lons, lats).reshape(grid.shape),
        "tpi": _muestrear(tpi_px, origen, lons, lats).reshape(grid.shape),
    }


def factores_topograficos(topo):
    """Factores 0-1 usados en el modelo.

    - relieve: pendiente normalizada (conductores que cruzan laderas y vaguadas son menos visibles
      y concentran el vuelo de ladera).
    - cresta: TPI positivo normalizado (crestas y cordales, donde se concentran el vuelo orográfico
      de planeadoras y los parques eólicos).
    """
    relieve = np.clip(topo["pendiente"] / 25.0, 0, 1)
    pos = np.clip(topo["tpi"], 0, None)
    p95 = np.percentile(pos[pos > 0], 95) if (pos > 0).any() else 1.0
    cresta = np.clip(pos / max(p95, 1e-6), 0, 1)
    return {"relieve": relieve, "cresta": cresta}
