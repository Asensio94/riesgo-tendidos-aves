"""Static front pages linking the reports of every computed region, one per language.

The whole `output/` folder is published as-is on GitHub Pages, so this module also copies `web/` (the project
presentation) into it and leaves small redirects behind for the URLs the site used before it became bilingual.

It also holds the pieces every generated page shares with the sibling projects: the common stylesheet
(`common.css`, copied verbatim from the shared style guide and inlined in each page), this project's accent colour,
the web fonts and the common footer.
"""
import shutil
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd

from . import config, i18n
from .logo import LOGO_SVG, favicon_link

# Shared stylesheet of the sibling projects: copied verbatim, never edited here; inlined before each page's own CSS.
COMMON_CSS = Path(__file__).with_name("common.css").read_text(encoding="utf-8").strip()
FAVICON = favicon_link("#8a5a00", "#e3a93c")
ACCENT_CSS = ":root{--accent:#8a5a00;--accent-dark:#e3a93c}"
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700'
         '&amp;family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&amp;family=IBM+Plex+Mono:wght@400;500'
         '&amp;display=swap">')
SELF_SLUG = "riesgo-tendidos-aves"
# Sibling projects in the order of the style guide; the names are proper names and stay in Spanish.
SIBLINGS = [
    ("observatorio-alegaciones", "Observatorio de alegaciones"),
    ("vigia-incendios", "Vigía de incendios"),
    ("centinela-natura", "Centinela Natura"),
    ("vigilancia-humedales", "Vigilancia de humedales"),
    ("sub-nocte", "Sub Nocte"),
    ("riesgo-tendidos-aves", "Riesgo de tendidos para aves"),
    ("grafo-promotores", "Grafo de promotores"),
    ("cartera-cotizadas", "Cartera de las cotizadas"),
    ("cuaderno-campo", "Cuaderno de campo"),
]

REDIRECT = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={target}"><link rel="canonical" href="{target}">
<title>{target}</title></head><body><p><a href="{target}">{target}</a></p></body></html>"""


def page_head(lang, title, own_css):
    """Document start up to </head>: fonts, then the common stylesheet, the accent and the page's own CSS."""
    return f"""<!doctype html><html lang="{i18n.t(lang, 'html_lang')}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
{FAVICON}
{FONTS}
<style>
{COMMON_CSS}
{ACCENT_CSS}
{own_css}
</style></head>"""


def site_footer(lang):
    """Common footer: the shared principle, this project's sources and licences, and the sibling projects."""
    current = ' aria-current="page"'
    items = "\n".join(
        f"    <li{current if slug == SELF_SLUG else ''}>"
        f'<a href="https://asensio94.github.io/{slug}/">{escape(name)}</a></li>'
        for slug, name in SIBLINGS)
    return f"""<footer class="site-footer">
  <p class="principle">{escape(i18n.t(lang, 'principle'))}</p>
  <p>{i18n.t(lang, 'footer_sources', repo=config.REPO_URL)}</p>
  <nav aria-label="{escape(i18n.t(lang, 'siblings_label'))}"><ul class="siblings">
{items}
  </ul></nav>
</footer>"""


def figures_html(pairs):
    """`.figures` block from (value, label) pairs."""
    return '<div class="figures">' + "".join(
        f"<div><b>{escape(str(value))}</b><span>{escape(label)}</span></div>" for value, label in pairs) + "</div>"


def method_section(lang):
    """The 'How it is computed' section shared by the regions page and the reports."""
    return (f'<section class="method" id="method">\n<h2>{escape(i18n.t(lang, "method_title"))}</h2>\n'
            f"{i18n.method_html(lang)}\n</section>")


def write_redirect(path, target, lang="es"):
    """Leave an old URL pointing at its new location."""
    Path(path).write_text(REDIRECT.format(target=target, lang=lang), encoding="utf-8")


def region_redirects(region_dir):
    """Keep the pre-bilingual per-region URLs alive, pointing at the Spanish pages."""
    region_dir = Path(region_dir)
    write_redirect(region_dir / "informe.html", "report.es.html")
    write_redirect(region_dir / "mapa.html", "map.es.html")


def _card(folder, lang):
    """Card of one region and the number of elements it scored."""
    name = config.region_name(folder.name, lang)
    updated = date.fromtimestamp((folder / f"report.{lang}.html").stat().st_mtime).isoformat()
    top = ""
    scored = 0
    csv = folder / "ranking_elements.csv"
    if csv.exists():
        df = pd.read_csv(csv)
        scored = len(df)
        counts = df.groupby("type").size().to_dict()
        items = "".join(
            f"<li>{escape(i18n.element_type(r.type, lang))} · {r.risk_max:.0f} · "
            f"{escape(i18n.month_label_from_canonical(r.peak_month, lang))} · "
            f"{escape(i18n.species_list(r.species, lang))[:70]} "
            f"· <a href='{escape(str(r.osm_url))}' target='_blank'>OSM</a></li>"
            for r in df.drop_duplicates(subset=["type", "risk_max"]).head(5).itertuples())
        breakdown = ", ".join(f"{i18n.num(v, lang)} {i18n.element_type_plural(k, lang)}" for k, v in counts.items())
        top = (f"<p class='meta'>{escape(i18n.t(lang, 'regions_scored', n=i18n.num(scored, lang), breakdown=breakdown))}"
               f"</p><ol>{items}</ol>")
    return f"""
<section class="region">
 <h2>{escape(name)}</h2>
 <p class="meta">{escape(i18n.t(lang, "regions_updated", date=updated))}</p>
 <p><a href="{folder.name}/report.{lang}.html">{escape(i18n.t(lang, "link_report"))}</a> ·
    <a href="{folder.name}/map.{lang}.html">{escape(i18n.t(lang, "link_map"))}</a> ·
    <a href="{folder.name}/ranking_elements.csv">{escape(i18n.t(lang, "link_ranking_csv"))}</a> ·
    <a href="{folder.name}/ranking_elements.geojson">{escape(i18n.t(lang, "link_geojson"))}</a> ·
    <a href="{folder.name}/risk_total.tif">{escape(i18n.t(lang, "link_geotiff"))}</a></p>
 {top}
</section>""", scored


# Rules shared by the generated pages: the language switcher at the top right of the header, and parameter
# names that wrap on a phone instead of widening the page.
PAGE_CSS = """
.lang{justify-self:end;margin:0;font:600 13px/1 var(--font-title);text-transform:uppercase;letter-spacing:.06em}
.lang a,.lang span{padding:4px 9px 3px;border:1px solid var(--line);margin-left:4px;text-decoration:none;color:var(--muted)}
.lang .on{color:var(--accent);border-color:var(--accent)}
@media (max-width:640px){table.params th{white-space:normal}}
"""
REGIONS_CSS = PAGE_CSS + """
.site-header p.links{margin:0}
main{max-width:1440px;margin:0 auto;padding:0 16px 8px}
main h2{font:700 24px/1.1 var(--font-title);text-transform:uppercase;letter-spacing:.03em;margin:1.2em 0 .2em}
.meta{color:var(--muted);margin:.2em 0;font-size:14.5px}
main ol{font-size:14.5px}
section.region{border-top:1px solid var(--line);padding-top:.4em}
.method code{font-family:var(--font-data);font-size:.9em}
"""


def _regions_page(out, lang):
    cards = [_card(folder, lang) for folder in sorted(p for p in out.iterdir()
                                                      if p.is_dir() and (p / f"report.{lang}.html").exists())]
    other = "en" if lang == "es" else "es"
    home = "index.html" if lang == "es" else "index.en.html"
    figures = figures_html([(i18n.num(len(cards), lang), i18n.t(lang, "fig_regions")),
                            (i18n.num(sum(n for _, n in cards), lang), i18n.t(lang, "fig_elements"))])
    html = f"""{page_head(lang, i18n.t(lang, 'site_title'), REGIONS_CSS)}<body>
<header class="site-header">
 <p class="lang"><span class="on">{i18n.t(lang, "lang_name")}</span>
  <a href="regions.{other}.html" hreflang="{other}">{i18n.t(lang, "other_lang_name")}</a></p>
 <h1>{LOGO_SVG}{i18n.t(lang, 'h1_html')}</h1>
 <p class="lede">{escape(i18n.t(lang, 'regions_intro'))}</p>
 <p class="links"><a href="{home}">{escape(i18n.t(lang, 'regions_project_link'))}</a> ·
  <a href="{config.REPO_URL}">{escape(i18n.t(lang, 'regions_code_link'))}</a></p>
 {figures}
</header>
<main>
{''.join(html for html, _ in cards) or f'<p>{escape(i18n.t(lang, "regions_empty"))}</p>'}
<p class="meta">{escape(i18n.t(lang, 'generated_on', date=date.today().isoformat()))}</p>
</main>
{method_section(lang)}
{site_footer(lang)}
</body></html>"""
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
