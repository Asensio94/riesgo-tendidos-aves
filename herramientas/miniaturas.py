"""Miniaturas PNG del índice anual (máximo mensual) por región, para la web del proyecto.

Uso: .venv/Scripts/python.exe herramientas/miniaturas.py [region ...]  → web/img/<region>.png
Solo PIL + rasterio; sin matplotlib.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riesgo import config, osm  # noqa: E402

ESCALA = 4  # píxeles por celda
# paleta claro→oscuro (amarillo → naranja → rojo → granate), índice 0-150
PALETA = [(255, 245, 200), (254, 204, 92), (253, 141, 60), (227, 26, 28), (128, 0, 38)]


def color(v, vmax=150.0):
    t = float(np.clip(v / vmax, 0, 1)) * (len(PALETA) - 1)
    i = int(t)
    if i >= len(PALETA) - 1:
        return PALETA[-1]
    f = t - i
    return tuple(int(a + (b - a) * f) for a, b in zip(PALETA[i], PALETA[i + 1]))


def miniatura(region):
    reg = config.REGIONES[region]
    carpeta = config.OUTPUT_DIR / region
    with rasterio.open(carpeta / "riesgo_total.tif") as src:
        arr = src.read()
        transform = src.transform
        ny, nx = src.height, src.width
    anual = np.nanmax(arr, axis=0)
    W, H = nx * ESCALA, ny * ESCALA
    img = Image.new("RGB", (W, H), (244, 241, 234))
    px = img.load()
    for r in range(ny):
        for c in range(nx):
            v = anual[r, c]
            if np.isfinite(v) and v > 2:
                col = color(v)
                for dy in range(ESCALA):
                    for dx in range(ESCALA):
                        px[c * ESCALA + dx, r * ESCALA + dy] = col

    def xy(lon, lat):
        col, row = ~transform * (lon, lat)
        return col * ESCALA, row * ESCALA

    draw = ImageDraw.Draw(img, "RGBA")
    infra = osm.obtener_infraestructura(tuple(reg["bbox"]))
    for ln in infra["lineas"]:
        pts = [xy(lo, la) for lo, la in ln["coords"]]
        if len(pts) > 1:
            draw.line(pts, fill=(60, 60, 60, 110), width=1)
    for a in infra["aerogeneradores"]:
        x, y = xy(a["lon"], a["lat"])
        draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(30, 30, 30, 200))
    rk = pd.read_csv(carpeta / "ranking_elementos.csv").head(40)
    for r in rk.itertuples():
        x, y = xy(r.lon, r.lat)
        draw.ellipse([x - 7, y - 7, x + 7, y + 7], outline=(20, 20, 20, 230), width=2)
    destino = Path(__file__).resolve().parents[1] / "web" / "img" / f"{region}.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    # limitar anchura a 1400 px para la web
    if W > 1400:
        img = img.resize((1400, int(H * 1400 / W)), Image.LANCZOS)
    img.save(destino, optimize=True)
    print(destino, img.size)


if __name__ == "__main__":
    for region in sys.argv[1:] or ("cantabria", "estrecho"):
        miniatura(region)
