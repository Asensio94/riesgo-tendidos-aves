"""Miniaturas PNG del índice anual (máximo mensual) por región, para la web del proyecto.

Fondo: relieve sombreado con tinte altitudinal y mar, calculado desde output/<region>/topografia.tif (AWS Terrain
Tiles, ya descargado por el pipeline); encima el índice de riesgo, los tendidos y aerogeneradores de OSM, los 40
primeros del ranking y topónimos de referencia.

Uso: .venv/Scripts/python.exe herramientas/miniaturas.py [region ...]  → web/img/<region>.png
Solo PIL + rasterio + numpy; sin matplotlib ni teselas externas.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riesgo import config, osm  # noqa: E402

ANCHO_OBJETIVO = 1400  # px
# paleta del índice (amarillo → granate), valores 0-150
PALETA_RIESGO = [(255, 237, 160), (254, 178, 76), (240, 90, 40), (200, 20, 30), (110, 0, 40)]
# tinte altitudinal (m → color)
HIPSO = [(0, (214, 226, 190)), (250, (190, 208, 160)), (700, (204, 190, 145)), (1300, (176, 150, 112)),
         (2000, (150, 130, 110)), (2700, (235, 232, 228))]
MAR = (168, 200, 222)
# topónimos de referencia por región: (nombre, lat, lon)
TOPONIMOS = {
    "cantabria": [("Santander", 43.462, -3.810), ("Torrelavega", 43.353, -4.048), ("Castro Urdiales", 43.384, -3.219),
                  ("Laredo", 43.411, -3.410), ("Reinosa", 43.001, -4.138), ("Potes", 43.154, -4.623),
                  ("Cabezón de la Sal", 43.308, -4.235), ("Aguilar de Campoo", 42.793, -4.259),
                  ("Medina de Pomar", 42.929, -3.487), ("Villarcayo", 42.940, -3.573), ("Espinosa de los Monteros", 43.078, -3.560),
                  ("Ramales", 43.256, -3.462), ("San Vicente de la Barquera", 43.385, -4.399), ("Picos de Europa", 43.19, -4.85),
                  ("Cervera de Pisuerga", 42.868, -4.500)],
    "estrecho": [("Tarifa", 36.013, -5.606), ("Algeciras", 36.128, -5.453), ("La Línea", 36.168, -5.348),
                 ("Los Barrios", 36.185, -5.490), ("Facinas", 36.137, -5.693), ("Castellar", 36.317, -5.452),
                 ("Jimena de la Frontera", 36.434, -5.454), ("Zahara de los Atunes", 36.134, -5.847),
                 ("Bolonia", 36.089, -5.773), ("San Roque", 36.210, -5.384), ("Estrecho de Gibraltar", 35.99, -5.55)],
}


def interp_color(v, tabla):
    if v <= tabla[0][0]:
        return tabla[0][1]
    for (v0, c0), (v1, c1) in zip(tabla[:-1], tabla[1:]):
        if v <= v1:
            f = (v - v0) / (v1 - v0)
            return tuple(int(a + (b - a) * f) for a, b in zip(c0, c1))
    return tabla[-1][1]


def color_riesgo(v, vmax=150.0):
    t = float(np.clip(v / vmax, 0, 1)) * (len(PALETA_RIESGO) - 1)
    i = min(int(t), len(PALETA_RIESGO) - 2)
    f = t - i
    return tuple(int(a + (b - a) * f) for a, b in zip(PALETA_RIESGO[i], PALETA_RIESGO[i + 1]))


def fondo_relieve(elev, dx_m, dy_m, escala):
    """Imagen RGB del relieve sombreado con tinte altitudinal y mar, ya reescalada."""
    ny, nx = elev.shape
    z = np.nan_to_num(elev, nan=0.0)
    # sombreado (azimut 315°, altura 45°, exageración vertical ×2)
    gy, gx = np.gradient(z * 2.0, dy_m, dx_m)
    pendiente = np.arctan(np.hypot(gx, gy))
    aspecto = np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(45)
    sombra = np.cos(alt) * np.cos(pendiente) + np.sin(alt) * np.sin(pendiente) * np.cos(az - aspecto)
    sombra = np.clip(sombra, 0, 1)
    rgb = np.zeros((ny, nx, 3), dtype=np.float64)
    tabla_v = np.array([v for v, _ in HIPSO], dtype=float)
    tabla_c = np.array([c for _, c in HIPSO], dtype=float)
    for k in range(3):
        rgb[..., k] = np.interp(z, tabla_v, tabla_c[:, k])
    rgb *= (0.5 + 0.5 * sombra)[..., None]
    mar = z <= 0
    rgb[mar] = MAR
    img = Image.fromarray(np.clip(rgb, 0, 255).astype("uint8"))
    return img.resize((nx * escala, ny * escala), Image.BICUBIC)


def capa_riesgo(anual, escala):
    """Capa RGBA del índice: color por valor, alfa creciente; celdas sin infraestructura transparentes."""
    ny, nx = anual.shape
    rgba = np.zeros((ny, nx, 4), dtype="uint8")
    for r in range(ny):
        for c in range(nx):
            v = anual[r, c]
            if np.isfinite(v) and v > 3:
                rgba[r, c, :3] = color_riesgo(v)
                rgba[r, c, 3] = int(np.clip(120 + v * 1.2, 120, 235))
    img = Image.fromarray(rgba, "RGBA")
    return img.resize((nx * escala, ny * escala), Image.BILINEAR)


def fuente(tam, negrita=False):
    for nombre in (("segoeuib.ttf" if negrita else "segoeui.ttf"), "arialbd.ttf" if negrita else "arial.ttf", "DejaVuSans-Bold.ttf" if negrita else "DejaVuSans.ttf"):
        for carpeta in ("C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", ""):
            try:
                return ImageFont.truetype(carpeta + nombre, tam)
            except OSError:
                continue
    return ImageFont.load_default()


def texto_con_halo(draw, xy, texto, fnt, color=(30, 30, 30), halo=(255, 255, 255), ancla="la"):
    x, y = xy
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                draw.text((x + dx, y + dy), texto, font=fnt, fill=halo, anchor=ancla)
    draw.text((x, y), texto, font=fnt, fill=color, anchor=ancla)


def miniatura(region):
    reg = config.REGIONES[region]
    carpeta = config.OUTPUT_DIR / region
    with rasterio.open(carpeta / "riesgo_total.tif") as src:
        arr = src.read()
        transform = src.transform
        ny, nx = src.height, src.width
    with rasterio.open(carpeta / "topografia.tif") as src:
        elev = src.read(1).astype("float64")
    anual = np.nanmax(arr, axis=0)
    escala = max(4, ANCHO_OBJETIVO // nx)
    lat0 = (reg["bbox"][0] + reg["bbox"][2]) / 2
    dx_m = abs(transform.a) * 111_320 * np.cos(np.radians(lat0))
    dy_m = abs(transform.e) * 111_320

    img = fondo_relieve(elev, dx_m, dy_m, escala).convert("RGBA")
    img.alpha_composite(capa_riesgo(anual, escala))
    W, H = img.size

    def xy(lon, lat):
        col, row = ~transform * (lon, lat)
        return col * escala, row * escala

    draw = ImageDraw.Draw(img, "RGBA")
    infra = osm.obtener_infraestructura(tuple(reg["bbox"]))
    for ln in infra["lineas"]:
        pts = [xy(lo, la) for lo, la in ln["coords"]]
        if len(pts) > 1:
            grosor = 2 if ln.get("categoria") == "transporte" else 1
            draw.line(pts, fill=(40, 40, 40, 150), width=grosor)
    for a in infra["aerogeneradores"]:
        x, y = xy(a["lon"], a["lat"])
        draw.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=(20, 20, 20, 230), outline=(255, 255, 255, 200))
    rk = pd.read_csv(carpeta / "ranking_elementos.csv").head(40)
    for r in rk.itertuples():
        x, y = xy(r.lon, r.lat)
        draw.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(255, 255, 255, 240), width=4)
        draw.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(15, 15, 15, 255), width=2)

    fnt = fuente(max(13, W // 95))
    fnt_it = fuente(max(12, W // 105))
    for nombre, lat, lon in TOPONIMOS.get(region, []):
        x, y = xy(lon, lat)
        if 0 <= x <= W and 0 <= y <= H:
            es_area = nombre in ("Picos de Europa", "Estrecho de Gibraltar")
            if not es_area:
                draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(40, 40, 40, 255), outline=(255, 255, 255, 255))
            texto_con_halo(draw, (x + 6, y - 2), nombre, fnt_it if es_area else fnt,
                           color=(70, 70, 70) if es_area else (25, 25, 25), ancla="lm")

    # barra de escala (10 km) y atribución
    km10 = 10_000 / dx_m * escala
    x0, y0 = 18, H - 22
    draw.rectangle([x0 - 6, y0 - 22, x0 + km10 + 6, y0 + 8], fill=(255, 255, 255, 190))
    draw.line([(x0, y0), (x0 + km10, y0)], fill=(20, 20, 20, 255), width=3)
    draw.text((x0 + km10 / 2, y0 - 6), "10 km", font=fuente(12), fill=(20, 20, 20), anchor="mb")
    atrib = "Relieve: AWS Terrain Tiles · Líneas y aerogeneradores: © OpenStreetMap · Índice: máximo mensual"
    fa = fuente(11)
    tw = draw.textlength(atrib, font=fa)
    draw.rectangle([W - tw - 16, H - 22, W, H], fill=(255, 255, 255, 190))
    draw.text((W - 8, H - 5), atrib, font=fa, fill=(50, 50, 50), anchor="rb")

    destino = Path(__file__).resolve().parents[1] / "web" / "img" / f"{region}.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(destino, optimize=True)
    print(destino, img.size)


if __name__ == "__main__":
    for region in sys.argv[1:] or ("cantabria", "estrecho"):
        miniatura(region)
