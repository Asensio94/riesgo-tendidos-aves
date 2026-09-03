"""Abundancia semanal modelada de eBird Status & Trends (opcional).

eBird S&T publica, por especie, un GeoTIFF de 52 bandas (una por semana) con la abundancia relativa esperada a 3 km.
Es la mejor capa de abundancia disponible, pero exige solicitar una clave de acceso y hoy se descarga con el paquete
R `ebirdst`:

    library(ebirdst)
    set_ebirdst_access_key("XXXX")
    ebirdst_download_status("egyvul1", pattern = "abundance_median_3km")   # p. ej. alimoche

Copia los .tif resultantes a data/ebirdst/<Genus_species>/ (o deja que el nombre del fichero contenga el código eBird
indicado en EBIRD_CODES). Si existen, `presencia_mensual` los reproyecta a la malla, agrega semanas → meses y
devuelve un índice 0-1 que la CLI mezcla con la frecuencia GBIF (config.PESO_EBIRDST).
"""
from datetime import date, timedelta

import numpy as np

from . import config

# Códigos eBird de las especies del catálogo (para reconocer ficheros descargados con ebirdst)
EBIRD_CODES = {
    "Gyps fulvus": "eurgri1", "Aegypius monachus": "cinvul1", "Neophron percnopterus": "egyvul1",
    "Aquila adalberti": "spaeag1", "Aquila fasciata": "boneag2", "Aquila chrysaetos": "goleag",
    "Circaetus gallicus": "shteag1", "Hieraaetus pennatus": "booeag1", "Milvus migrans": "blakit1",
    "Milvus milvus": "redkit1", "Ciconia ciconia": "whisto1", "Ciconia nigra": "blasto1", "Grus grus": "comcra",
    "Otis tarda": "grebus1", "Bubo bubo": "eueowl1", "Gypaetus barbatus": "lambea1", "Pernis apivorus": "euhbuz1",
    "Falco peregrinus": "perfal", "Pyrrhocorax pyrrhocorax": "rebcho1", "Platalea leucorodia": "eurspo1",
    "Ardea cinerea": "gryher1",
}


def ficheros_especie(nombre):
    """Rutas de GeoTIFF de abundancia disponibles para la especie."""
    if not config.EBIRDST_DIR.exists():
        return []
    carpeta = config.EBIRDST_DIR / nombre.replace(" ", "_")
    ficheros = sorted(carpeta.glob("*abundance*median*.tif")) if carpeta.exists() else []
    codigo = EBIRD_CODES.get(nombre)
    if codigo:
        ficheros += [p for p in config.EBIRDST_DIR.rglob(f"*{codigo}*abundance*median*.tif") if p not in ficheros]
    return ficheros


def _mes_de_semana(i, year=2023):
    """Mes (1-12) de la semana i (0-51) de eBird S&T: 52 semanas iguales que arrancan el 4 de enero."""
    d = date(year, 1, 4) + timedelta(days=int(round(i * 365.25 / 52)) + 3)
    return min(d.month, 12)


def presencia_mensual(nombre, grid, log=print):
    """Índice 0-1 (12, ny, nx) de abundancia mensual a partir del GeoTIFF semanal, o None si no hay fichero."""
    ficheros = ficheros_especie(nombre)
    if not ficheros:
        return None
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    dst_transform = grid.transform()
    out = np.zeros((12,) + grid.shape)
    cuenta = np.zeros(12)
    with rasterio.open(ficheros[0]) as src:
        if src.count < 52:
            log(f"  eBird S&T {nombre}: {ficheros[0].name} tiene {src.count} bandas, no 52; se ignora")
            return None
        for i in range(52):
            banda = src.read(i + 1).astype("float64")
            banda = np.where(np.isfinite(banda) & (banda != src.nodata), banda, np.nan) if src.nodata is not None \
                else np.where(np.isfinite(banda), banda, np.nan)
            dst = np.full(grid.shape, np.nan)
            reproject(banda, dst, src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan,
                      dst_transform=dst_transform, dst_crs="EPSG:4326", dst_nodata=np.nan,
                      resampling=Resampling.bilinear)
            m = _mes_de_semana(i) - 1
            out[m] += np.nan_to_num(dst)
            cuenta[m] += 1
    for m in range(12):
        if cuenta[m]:
            out[m] /= cuenta[m]
    mx = out.max()
    if mx <= 0:
        return None
    log(f"  eBird S&T {nombre}: {ficheros[0].name} incorporado")
    return out / mx
