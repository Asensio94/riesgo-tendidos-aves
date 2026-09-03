"""PNG thumbnails of the annual index (monthly maximum) per region, for the project website.

Background: shaded relief with a hypsometric tint and sea, computed from output/<region>/terrain.tif (AWS Terrain
Tiles, already downloaded by the pipeline); on top of it the risk index, the OSM power lines and wind turbines,
the top 40 of the ranking and a few place names for reference.

Usage: .venv/Scripts/python.exe tools/thumbnails.py [region ...]  -> web/img/<region>.png (Spanish caption)
                                                                     web/img/<region>.en.png (English caption)
Only PIL + rasterio + numpy; no matplotlib and no external tiles.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from birdrisk import config, osm  # noqa: E402

TARGET_WIDTH = 1400  # px
# index palette (yellow -> dark red), values 0-150
RISK_PALETTE = [(255, 237, 160), (254, 178, 76), (240, 90, 40), (200, 20, 30), (110, 0, 40)]
# hypsometric tint (m -> colour)
HYPSO = [(0, (214, 226, 190)), (250, (190, 208, 160)), (700, (204, 190, 145)), (1300, (176, 150, 112)),
         (2000, (150, 130, 110)), (2700, (235, 232, 228))]
SEA = (168, 200, 222)
# reference place names per region: (name, lat, lon)
PLACE_NAMES = {
    "cantabria": [("Santander", 43.462, -3.810), ("Torrelavega", 43.353, -4.048), ("Castro Urdiales", 43.384, -3.219),
                  ("Laredo", 43.411, -3.410), ("Reinosa", 43.001, -4.138), ("Potes", 43.154, -4.623),
                  ("Cabezón de la Sal", 43.308, -4.235), ("Aguilar de Campoo", 42.793, -4.259),
                  ("Medina de Pomar", 42.929, -3.487), ("Villarcayo", 42.940, -3.573),
                  ("Espinosa de los Monteros", 43.078, -3.560), ("Ramales", 43.256, -3.462),
                  ("San Vicente de la Barquera", 43.385, -4.399), ("Picos de Europa", 43.19, -4.85),
                  ("Cervera de Pisuerga", 42.868, -4.500)],
    "estrecho": [("Tarifa", 36.013, -5.606), ("Algeciras", 36.128, -5.453), ("La Línea", 36.168, -5.348),
                 ("Los Barrios", 36.185, -5.490), ("Facinas", 36.137, -5.693), ("Castellar", 36.317, -5.452),
                 ("Jimena de la Frontera", 36.434, -5.454), ("Zahara de los Atunes", 36.134, -5.847),
                 ("Bolonia", 36.089, -5.773), ("San Roque", 36.210, -5.384), ("Estrecho de Gibraltar", 35.99, -5.55)],
}
# names drawn as an area label (italic, no dot)
AREA_LABELS = ("Picos de Europa", "Estrecho de Gibraltar")
ATTRIBUTION = {
    "es": "Relieve: AWS Terrain Tiles · Líneas y aerogeneradores: © OpenStreetMap · Índice: máximo mensual",
    "en": "Relief: AWS Terrain Tiles · Lines and turbines: © OpenStreetMap · Index: monthly maximum",
}


def interp_colour(v, table):
    if v <= table[0][0]:
        return table[0][1]
    for (v0, c0), (v1, c1) in zip(table[:-1], table[1:]):
        if v <= v1:
            f = (v - v0) / (v1 - v0)
            return tuple(int(a + (b - a) * f) for a, b in zip(c0, c1))
    return table[-1][1]


def risk_colour(v, vmax=150.0):
    t = float(np.clip(v / vmax, 0, 1)) * (len(RISK_PALETTE) - 1)
    i = min(int(t), len(RISK_PALETTE) - 2)
    f = t - i
    return tuple(int(a + (b - a) * f) for a, b in zip(RISK_PALETTE[i], RISK_PALETTE[i + 1]))


def relief_background(elev, dx_m, dy_m, scale):
    """RGB image of the shaded relief with a hypsometric tint and sea, already upscaled."""
    ny, nx = elev.shape
    z = np.nan_to_num(elev, nan=0.0)
    # hillshade (azimuth 315 deg, altitude 45 deg, vertical exaggeration x2)
    gy, gx = np.gradient(z * 2.0, dy_m, dx_m)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(45)
    shade = np.cos(alt) * np.cos(slope) + np.sin(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(shade, 0, 1)
    rgb = np.zeros((ny, nx, 3), dtype=np.float64)
    table_v = np.array([v for v, _ in HYPSO], dtype=float)
    table_c = np.array([c for _, c in HYPSO], dtype=float)
    for k in range(3):
        rgb[..., k] = np.interp(z, table_v, table_c[:, k])
    rgb *= (0.5 + 0.5 * shade)[..., None]
    rgb[z <= 0] = SEA
    img = Image.fromarray(np.clip(rgb, 0, 255).astype("uint8"))
    return img.resize((nx * scale, ny * scale), Image.BICUBIC)


def risk_layer(annual, scale):
    """RGBA layer of the index: colour by value, growing alpha; cells without infrastructure stay transparent."""
    ny, nx = annual.shape
    rgba = np.zeros((ny, nx, 4), dtype="uint8")
    for r in range(ny):
        for c in range(nx):
            v = annual[r, c]
            if np.isfinite(v) and v > 3:
                rgba[r, c, :3] = risk_colour(v)
                rgba[r, c, 3] = int(np.clip(120 + v * 1.2, 120, 235))
    img = Image.fromarray(rgba, "RGBA")
    return img.resize((nx * scale, ny * scale), Image.BILINEAR)


def font(size, bold=False):
    names = ("segoeuib.ttf" if bold else "segoeui.ttf", "arialbd.ttf" if bold else "arial.ttf",
             "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    for name in names:
        for folder in ("C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", ""):
            try:
                return ImageFont.truetype(folder + name, size)
            except OSError:
                continue
    return ImageFont.load_default()


def haloed_text(draw, xy, text, fnt, colour=(30, 30, 30), halo=(255, 255, 255), anchor="la"):
    x, y = xy
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                draw.text((x + dx, y + dy), text, font=fnt, fill=halo, anchor=anchor)
    draw.text((x, y), text, font=fnt, fill=colour, anchor=anchor)


def thumbnail(region, langs=config.LANGS):
    """Render one thumbnail per language (only the attribution line differs)."""
    reg = config.REGIONS[region]
    folder = config.OUTPUT_DIR / region
    with rasterio.open(folder / "risk_total.tif") as src:
        arr = src.read()
        transform = src.transform
        nx = src.width
    with rasterio.open(folder / "terrain.tif") as src:
        elev = src.read(1).astype("float64")
    annual = np.nanmax(arr, axis=0)
    scale = max(4, TARGET_WIDTH // nx)
    lat0 = (reg["bbox"][0] + reg["bbox"][2]) / 2
    dx_m = abs(transform.a) * 111_320 * np.cos(np.radians(lat0))
    dy_m = abs(transform.e) * 111_320

    base = relief_background(elev, dx_m, dy_m, scale).convert("RGBA")
    base.alpha_composite(risk_layer(annual, scale))
    W, H = base.size

    def xy(lon, lat):
        col, row = ~transform * (lon, lat)
        return col * scale, row * scale

    draw = ImageDraw.Draw(base, "RGBA")
    infra = osm.get_infrastructure(tuple(reg["bbox"]))
    for ln in infra["lines"]:
        pts = [xy(lo, la) for lo, la in ln["coords"]]
        if len(pts) > 1:
            width = 2 if ln.get("category") == "transmission" else 1
            draw.line(pts, fill=(40, 40, 40, 150), width=width)
    for t in infra["turbines"]:
        x, y = xy(t["lon"], t["lat"])
        draw.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=(20, 20, 20, 230), outline=(255, 255, 255, 200))
    ranking = pd.read_csv(folder / "ranking_elements.csv").head(40)
    for r in ranking.itertuples():
        x, y = xy(r.lon, r.lat)
        draw.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(255, 255, 255, 240), width=3)
        draw.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(15, 15, 15, 255), width=2)

    fnt = font(max(13, W // 95))
    fnt_area = font(max(12, W // 105))
    for name, lat, lon in PLACE_NAMES.get(region, []):
        x, y = xy(lon, lat)
        if 0 <= x <= W and 0 <= y <= H:
            is_area = name in AREA_LABELS
            if not is_area:
                draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(40, 40, 40, 255), outline=(255, 255, 255, 255))
            haloed_text(draw, (x + 6, y - 2), name, fnt_area if is_area else fnt,
                        colour=(70, 70, 70) if is_area else (25, 25, 25), anchor="lm")

    # scale bar (10 km)
    km10 = 10_000 / dx_m * scale
    x0, y0 = 18, H - 22
    draw.rectangle([x0 - 6, y0 - 22, x0 + km10 + 6, y0 + 8], fill=(255, 255, 255, 190))
    draw.line([(x0, y0), (x0 + km10, y0)], fill=(20, 20, 20, 255), width=3)
    draw.text((x0 + km10 / 2, y0 - 6), "10 km", font=font(12), fill=(20, 20, 20), anchor="mb")

    target_dir = Path(__file__).resolve().parents[1] / "web" / "img"
    target_dir.mkdir(parents=True, exist_ok=True)
    small = font(11)
    for lang in langs:
        img = base.copy()
        d = ImageDraw.Draw(img, "RGBA")
        text = ATTRIBUTION[lang]
        tw = d.textlength(text, font=small)
        d.rectangle([W - tw - 16, H - 22, W, H], fill=(255, 255, 255, 190))
        d.text((W - 8, H - 5), text, font=small, fill=(50, 50, 50), anchor="rb")
        # Spanish keeps the historical file name so existing links do not break
        target = target_dir / (f"{region}.png" if lang == "es" else f"{region}.{lang}.png")
        img.convert("RGB").save(target, optimize=True)
        print(target, img.size)


if __name__ == "__main__":
    for region in sys.argv[1:] or ("cantabria", "estrecho"):
        thumbnail(region)
