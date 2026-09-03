"""Static front pages linking the reports of every computed region, one per language.

The whole `output/` folder is published as-is on GitHub Pages, so this module also copies `web/` (the project
presentation) into it and leaves small redirects behind for the URLs the site used before it became bilingual.
"""
import shutil
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd

from . import config, i18n

REDIRECT = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={target}"><link rel="canonical" href="{target}">
<title>{target}</title></head><body><p><a href="{target}">{target}</a></p></body></html>"""


def write_redirect(path, target, lang="es"):
    """Leave an old URL pointing at its new location."""
    Path(path).write_text(REDIRECT.format(target=target, lang=lang), encoding="utf-8")


def region_redirects(region_dir):
    """Keep the pre-bilingual per-region URLs alive, pointing at the Spanish pages."""
    region_dir = Path(region_dir)
    write_redirect(region_dir / "informe.html", "report.es.html")
    write_redirect(region_dir / "mapa.html", "map.es.html")


def _card(folder, lang):
    name = config.region_name(folder.name, lang)
    updated = date.fromtimestamp((folder / f"report.{lang}.html").stat().st_mtime).isoformat()
    top = ""
    csv = folder / "ranking_elements.csv"
    if csv.exists():
        df = pd.read_csv(csv)
        counts = df.groupby("type").size().to_dict()
        items = "".join(
            f"<li>{escape(i18n.element_type(r.type, lang))} · {r.risk_max:.0f} · "
            f"{escape(i18n.month_label_from_canonical(r.peak_month, lang))} · "
            f"{escape(i18n.species_list(r.species, lang))[:70]} "
            f"· <a href='{escape(str(r.osm_url))}' target='_blank'>OSM</a></li>"
            for r in df.drop_duplicates(subset=["type", "risk_max"]).head(5).itertuples())
        breakdown = ", ".join(f"{v} {i18n.element_type_plural(k, lang)}" for k, v in counts.items())
        top = (f"<p class='meta'>{escape(i18n.t(lang, 'regions_scored', n=len(df), breakdown=breakdown))}</p>"
               f"<ol>{items}</ol>")
    return f"""
<section>
 <h2>{escape(name)}</h2>
 <p class="meta">{escape(i18n.t(lang, "regions_updated", date=updated))}</p>
 <p><a href="{folder.name}/report.{lang}.html">{escape(i18n.t(lang, "link_report"))}</a> ·
    <a href="{folder.name}/map.{lang}.html">{escape(i18n.t(lang, "link_map"))}</a> ·
    <a href="{folder.name}/ranking_elements.csv">{escape(i18n.t(lang, "link_ranking_csv"))}</a> ·
    <a href="{folder.name}/ranking_elements.geojson">{escape(i18n.t(lang, "link_geojson"))}</a> ·
    <a href="{folder.name}/risk_total.tif">{escape(i18n.t(lang, "link_geotiff"))}</a></p>
 {top}
</section>"""


def _regions_page(out, lang):
    cards = [_card(folder, lang) for folder in sorted(p for p in out.iterdir()
                                                      if p.is_dir() and (p / f"report.{lang}.html").exists())]
    other = "en" if lang == "es" else "es"
    home = "index.html" if lang == "es" else "index.en.html"
    html = f"""<!doctype html><html lang="{i18n.t(lang, 'html_lang')}"><head><meta charset="utf-8">
<title>{escape(i18n.t(lang, 'site_title'))}</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;margin:0;color:#222;background:#fff;color-scheme:light}}
 main{{max-width:900px;margin:0 auto;padding:20px 24px}} h1{{font-size:24px}}
 h2{{font-size:18px;margin:1.4em 0 .2em}}
 .meta{{color:#666;margin:.2em 0}} ol{{font-size:13.5px}} section{{border-top:1px solid #e5e5e5;padding-top:.6em}}
 .lang{{float:right;margin:0;font-size:13px}}
 .lang a,.lang span{{padding:2px 8px;border:1px solid #ddd;border-radius:99px;margin-left:4px;text-decoration:none}}
 .lang .on{{background:#f0f0f0;color:#555}}
</style></head><body><main>
<p class="lang"><span class="on">{i18n.t(lang, "lang_name")}</span>
 <a href="regions.{other}.html" hreflang="{other}">{i18n.t(lang, "other_lang_name")}</a></p>
<h1>{escape(i18n.t(lang, 'site_title'))}</h1>
<p>{escape(i18n.t(lang, 'regions_intro'))}
 <a href="{home}">{escape(i18n.t(lang, 'regions_project_link'))}</a> ·
 <a href="{config.REPO_URL}">{escape(i18n.t(lang, 'regions_code_link'))}</a>.</p>
{''.join(cards) or f'<p>{escape(i18n.t(lang, "regions_empty"))}</p>'}
<p class="meta">{escape(i18n.t(lang, 'generated_on', date=date.today().isoformat()))}</p>
</main></body></html>"""
    path = out / f"regions.{lang}.html"
    path.write_text(html, encoding="utf-8")
    return path


def index(output_dir=None):
    """Rebuild the regions pages in both languages, the legacy redirects and the copy of `web/`."""
    out = Path(output_dir or config.OUTPUT_DIR)
    paths = [_regions_page(out, lang) for lang in config.LANGS]
    write_redirect(out / "regiones.html", "regions.es.html")  # pre-bilingual URL
    # the front page (index.html) is the static project presentation kept in web/; copied verbatim if present
    web = config.ROOT / "web"
    if web.exists():
        for p in web.rglob("*"):
            if p.is_file():
                target = out / p.relative_to(web)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
    return paths[0]
