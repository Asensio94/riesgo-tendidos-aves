"""Portada estática que enlaza los informes de todas las regiones calculadas (para publicar output/ tal cual)."""
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd

from . import config


def indice(output_dir=None):
    out = Path(output_dir or config.OUTPUT_DIR)
    tarjetas = []
    for carpeta in sorted(p for p in out.iterdir() if p.is_dir() and (p / "informe.html").exists()):
        nombre = config.REGIONES.get(carpeta.name, {}).get("nombre", carpeta.name)
        fecha = date.fromtimestamp((carpeta / "informe.html").stat().st_mtime).isoformat()
        top = ""
        csv = carpeta / "ranking_elementos.csv"
        if csv.exists():
            df = pd.read_csv(csv)
            resumen = df.groupby("tipo").size().to_dict()
            filas = "".join(
                f"<li>{escape(r.tipo)} · {r.riesgo_max:.0f} · {escape(str(r.mes_pico))} · {escape(str(r.especies))[:70]} "
                f"· <a href='{escape(str(r.osm_url))}' target='_blank'>OSM</a></li>"
                for r in df.drop_duplicates(subset=["tipo", "riesgo_max"]).head(5).itertuples())
            top = (f"<p class='meta'>{len(df)} elementos puntuados: " +
                   ", ".join(f"{v} {k}s" for k, v in resumen.items()) + "</p><ol>" + filas + "</ol>")
        tarjetas.append(f"""
<section>
 <h2>{escape(nombre)}</h2>
 <p class="meta">actualizado el {fecha}</p>
 <p><a href="{carpeta.name}/informe.html">Informe</a> · <a href="{carpeta.name}/mapa.html">Mapa interactivo</a> ·
    <a href="{carpeta.name}/ranking_elementos.csv">Ranking CSV</a> · <a href="{carpeta.name}/ranking_elementos.geojson">GeoJSON</a> ·
    <a href="{carpeta.name}/riesgo_total.tif">GeoTIFF</a></p>
 {top}
</section>""")
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Riesgo de colisión y electrocución de aves · regiones</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;margin:0;color:#222;background:#fff;color-scheme:light}}
 main{{max-width:900px;margin:0 auto;padding:20px 24px}} h1{{font-size:24px}} h2{{font-size:18px;margin:1.4em 0 .2em}}
 .meta{{color:#666;margin:.2em 0}} ol{{font-size:13.5px}} section{{border-top:1px solid #e5e5e5;padding-top:.6em}}
</style></head><body><main>
<h1>Mapa dinámico de riesgo de colisión y electrocución de aves</h1>
<p>Índice relativo (0-100, percentil 99 = 100) por celda de ~500 m, especie y mes, a partir de OpenStreetMap, GBIF/eBird,
Movebank y topografía. Sirve para priorizar qué apoyos, tramos y aerogeneradores corregir primero, no para certificar
mortalidad. Se regenera el día 2 de cada mes. <a href="index.html">Presentación del proyecto</a> ·
<a href="{config.REPO_URL}">código y método</a>.</p>
{''.join(tarjetas) or '<p>No hay regiones calculadas todavía.</p>'}
<p class="meta">Generado el {date.today().isoformat()}.</p>
</main></body></html>"""
    (out / "regiones.html").write_text(html, encoding="utf-8")
    # la portada (index.html) es la presentación estática del proyecto, en web/; se copia si existe
    web = config.ROOT / "web"
    if web.exists():
        import shutil
        for p in web.rglob("*"):
            if p.is_file():
                destino = out / p.relative_to(web)
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, destino)
    return out / "regiones.html"
