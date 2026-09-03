"""Modelled weekly abundance from eBird Status & Trends (optional).

For each species eBird S&T publishes a 52-band GeoTIFF (one band per week) with the expected relative abundance
at 3 km. It is the best abundance layer available, but it requires requesting an access key and today it is
downloaded with the R package `ebirdst`:

    library(ebirdst)
    set_ebirdst_access_key("XXXX")
    ebirdst_download_status("egyvul1", pattern = "abundance_median_3km")   # e.g. Egyptian Vulture

Copy the resulting .tif files to data/ebirdst/<Genus_species>/ (or let the file name contain the eBird code listed
in EBIRD_CODES). When they exist, `monthly_presence` reprojects them onto the grid, aggregates weeks into months
and returns a 0-1 index that the CLI blends with the GBIF frequency (config.EBIRDST_WEIGHT).
"""
from datetime import date, timedelta

import numpy as np

from . import config

# eBird codes of the catalogue species, used to recognise files downloaded with ebirdst
EBIRD_CODES = {
    "Gyps fulvus": "eurgri1", "Aegypius monachus": "cinvul1", "Neophron percnopterus": "egyvul1",
    "Aquila adalberti": "spaeag1", "Aquila fasciata": "boneag2", "Aquila chrysaetos": "goleag",
    "Circaetus gallicus": "shteag1", "Hieraaetus pennatus": "booeag1", "Milvus migrans": "blakit1",
    "Milvus milvus": "redkit1", "Ciconia ciconia": "whisto1", "Ciconia nigra": "blasto1", "Grus grus": "comcra",
    "Otis tarda": "grebus1", "Bubo bubo": "eueowl1", "Gypaetus barbatus": "lambea1", "Pernis apivorus": "euhbuz1",
    "Falco peregrinus": "perfal", "Pyrrhocorax pyrrhocorax": "rebcho1", "Platalea leucorodia": "eurspo1",
    "Ardea cinerea": "gryher1",
}


def species_files(name):
    """Paths of the abundance GeoTIFFs available for the species."""
    if not config.EBIRDST_DIR.exists():
        return []
    folder = config.EBIRDST_DIR / name.replace(" ", "_")
    files = sorted(folder.glob("*abundance*median*.tif")) if folder.exists() else []
    code = EBIRD_CODES.get(name)
    if code:
        files += [p for p in config.EBIRDST_DIR.rglob(f"*{code}*abundance*median*.tif") if p not in files]
    return files


def _month_of_week(i, year=2023):
    """Month (1-12) of week i (0-51) in eBird S&T: 52 equal weeks starting on 4 January."""
    d = date(year, 1, 4) + timedelta(days=int(round(i * 365.25 / 52)) + 3)
    return min(d.month, 12)


def monthly_presence(name, grid, log=print):
    """0-1 index (12, ny, nx) of monthly abundance from the weekly GeoTIFF, or None when there is no file."""
    files = species_files(name)
    if not files:
        return None
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    dst_transform = grid.transform()
    out = np.zeros((12,) + grid.shape)
    counts = np.zeros(12)
    with rasterio.open(files[0]) as src:
        if src.count < 52:
            log(f"  eBird S&T {name}: {files[0].name} has {src.count} bands instead of 52; ignored")
            return None
        for i in range(52):
            band = src.read(i + 1).astype("float64")
            band = np.where(np.isfinite(band) & (band != src.nodata), band, np.nan) if src.nodata is not None \
                else np.where(np.isfinite(band), band, np.nan)
            dst = np.full(grid.shape, np.nan)
            reproject(band, dst, src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan,
                      dst_transform=dst_transform, dst_crs="EPSG:4326", dst_nodata=np.nan,
                      resampling=Resampling.bilinear)
            m = _month_of_week(i) - 1
            out[m] += np.nan_to_num(dst)
            counts[m] += 1
    for m in range(12):
        if counts[m]:
            out[m] /= counts[m]
    mx = out.max()
    if mx <= 0:
        return None
    log(f"  eBird S&T {name}: {files[0].name} merged in")
    return out / mx
