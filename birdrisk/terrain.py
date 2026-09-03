"""Terrain from AWS Terrain Tiles (terrarium format, no key needed): elevation, slope and topographic position."""
import io
import math

import numpy as np
import requests
from PIL import Image

from . import config
from .grid import smooth


def _tile_xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n
    return x, y


def _download_tile(z, x, y):
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


def mosaic(bbox, z=config.TERRAIN_ZOOM):
    """Elevation (m) in the Web Mercator pixels covering the bbox, plus the origin (z, tx0, ty0)."""
    lat_min, lon_min, lat_max, lon_max = bbox
    x0, y0 = _tile_xy(lat_max, lon_min, z)
    x1, y1 = _tile_xy(lat_min, lon_max, z)
    tx0, tx1 = int(math.floor(x0)), int(math.floor(x1))
    ty0, ty1 = int(math.floor(y0)), int(math.floor(y1))
    rows = []
    for ty in range(ty0, ty1 + 1):
        row = [_download_tile(z, tx, ty) for tx in range(tx0, tx1 + 1)]
        rows.append(np.hstack(row))
    return np.vstack(rows), (z, tx0, ty0)


def _sample(arr, origin, lons, lats):
    z, tx0, ty0 = origin
    n = 2 ** z
    px = ((lons + 180.0) / 360.0 * n - tx0) * 256.0
    lat_r = np.radians(lats)
    py = ((1.0 - np.log(np.tan(lat_r) + 1.0 / np.cos(lat_r)) / math.pi) / 2.0 * n - ty0) * 256.0
    c = np.clip(px.astype(int), 0, arr.shape[1] - 1)
    r = np.clip(py.astype(int), 0, arr.shape[0] - 1)
    return arr[r, c]


def terrain_layers(bbox, grid):
    """Dict with elevation (m), slope (degrees) and TPI (m) on the analysis grid."""
    elev_px, origin = mosaic(bbox)
    z = origin[0]
    m_px = 40_075_016.686 * math.cos(math.radians(grid.lat_centre)) / (256 * 2 ** z)
    elev_px = smooth(elev_px, 1.0)  # removes the quantisation noise
    gy, gx = np.gradient(elev_px, m_px)
    slope_px = np.degrees(np.arctan(np.hypot(gx, gy)))
    tpi_px = elev_px - smooth(elev_px, config.TPI_RADIUS_M / m_px)

    lons, lats = np.meshgrid(grid.lon_centres(), grid.lat_centres())
    lons, lats = lons.ravel(), lats.ravel()
    return {
        "elevation": _sample(elev_px, origin, lons, lats).reshape(grid.shape),
        "slope": _sample(slope_px, origin, lons, lats).reshape(grid.shape),
        "tpi": _sample(tpi_px, origin, lons, lats).reshape(grid.shape),
    }


def terrain_factors(topo):
    """Factors 0-1 used by the risk model.

    - relief: normalised slope (conductors crossing hillsides and valleys are less visible and concentrate
      slope-soaring flight).
    - ridge: normalised positive TPI (ridges and crests, where orographic soaring and wind farms concentrate).
    """
    relief = np.clip(topo["slope"] / 25.0, 0, 1)
    pos = np.clip(topo["tpi"], 0, None)
    p95 = np.percentile(pos[pos > 0], 95) if (pos > 0).any() else 1.0
    ridge = np.clip(pos / max(p95, 1e-6), 0, 1)
    return {"relief": relief, "ridge": ridge}
