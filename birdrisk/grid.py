"""Regular geographic grid (lat/lon) on which every layer is computed."""
import math
from dataclasses import dataclass

import numpy as np

from . import config


@dataclass
class Grid:
    lat_min: float
    lon_min: float
    lat_max: float
    lon_max: float
    res: float

    @classmethod
    def from_bbox(cls, bbox, res=config.GRID_RES_DEG):
        lat_min, lon_min, lat_max, lon_max = bbox
        return cls(lat_min, lon_min, lat_max, lon_max, res)

    @property
    def ny(self):
        return int(math.ceil((self.lat_max - self.lat_min) / self.res))

    @property
    def nx(self):
        return int(math.ceil((self.lon_max - self.lon_min) / self.res))

    @property
    def shape(self):
        return (self.ny, self.nx)

    @property
    def lat_centre(self):
        return 0.5 * (self.lat_min + self.lat_max)

    @property
    def dy_m(self):
        return self.res * 111_320.0

    @property
    def dx_m(self):
        return self.res * 111_320.0 * math.cos(math.radians(self.lat_centre))

    @property
    def area_km2(self):
        return self.dx_m * self.dy_m / 1e6

    def lat_centres(self):
        # row 0 = north (image convention)
        return self.lat_max - (np.arange(self.ny) + 0.5) * self.res

    def lon_centres(self):
        return self.lon_min + (np.arange(self.nx) + 0.5) * self.res

    def idx(self, lon, lat):
        """(row, col) indices of the given points; -1 when they fall outside the grid."""
        lon = np.asarray(lon, dtype=float)
        lat = np.asarray(lat, dtype=float)
        col = np.floor((lon - self.lon_min) / self.res).astype(int)
        row = np.floor((self.lat_max - lat) / self.res).astype(int)
        ok = (col >= 0) & (col < self.nx) & (row >= 0) & (row < self.ny)
        row = np.where(ok, row, -1)
        col = np.where(ok, col, -1)
        return row, col

    def count(self, lon, lat, weights=None):
        """Accumulate points (or weights) on the grid."""
        arr = np.zeros(self.shape)
        if len(lon) == 0:
            return arr
        row, col = self.idx(lon, lat)
        ok = row >= 0
        w = np.ones(ok.sum()) if weights is None else np.asarray(weights)[ok]
        np.add.at(arr, (row[ok], col[ok]), w)
        return arr

    def bounds_folium(self):
        return [[self.lat_min, self.lon_min], [self.lat_max, self.lon_max]]

    def sigma_px(self, sigma_m):
        """Sigma in pixels (rows, columns) for a sigma given in metres."""
        return (sigma_m / self.dy_m, sigma_m / self.dx_m)

    def transform(self):
        """Affine transform for rasterio (north up)."""
        from rasterio.transform import from_origin

        return from_origin(self.lon_min, self.lat_max, self.res, self.res)


def smooth(arr, sigma_px):
    from scipy.ndimage import gaussian_filter

    return gaussian_filter(arr, sigma=sigma_px, mode="nearest")
