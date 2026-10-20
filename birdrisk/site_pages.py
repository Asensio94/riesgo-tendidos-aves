"""One page per Natura 2000 site with high-risk elements: `output/<region>/sites/<SITECODE>.<lang>.html`.

Estado de las IBA counts the high-risk elements inside each site and links here, so the reader lands on exactly
those elements (the region's map only draws the top of the whole region). Each page draws the site's outline and
its high-risk wind turbines, pylons and line segments, and lists them from most to least risk.
"""
import json
from html import escape
from pathlib import Path
from types import SimpleNamespace

from . import config, i18n, report, site

HUB_URL = "https://asensio94.github.io/estado-iba/#/e/"
COLOUR = {"turbine": "#8e44ad", "pylon": "#e74c3c", "line": "#d35400"}  # as in the region's map
ORDER = ("turbine", "pylon", "line")

CSS = site.PAGE_CSS + """
.site-header p.links{margin:0}
main{max-width:1440px;margin:0 auto;padding:0 16px 8px}
main h2{font:700 22px/1.1 var(--font-title);text-transform:uppercase;letter-spacing:.03em;margin:1.4em 0 .5em;
  padding-bottom:4px;border-bottom:1px solid var(--line)}
#map{height:560px;border:1px solid var(--line);background:var(--paper)}
main table{border-collapse:collapse;font-size:13px;width:100%;background:var(--paper)}
main th,main td{border:1px solid var(--line);padding:3px 6px;text-align:left}
main thead th{font:600 13px/1.2 var(--font-title);text-transform:uppercase;letter-spacing:.04em}
main td.n{text-align:right;font-family:var(--font-data)}
tr.on td{background:color-mix(in srgb,var(--accent) 14%,transparent)}
.wrap{overflow-x:auto}
.meta{color:var(--muted);font-size:14.5px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:-1px}
td.why{min-width:320px;font-size:12.5px;line-height:1.4;color:var(--muted)}
@media (max-width:640px){#map{height:62vh}}
"""


def _rows(rows):
    """Ranking rows from most to least risk, with only what the page shows."""
    out = []
    for r in sorted(rows, key=lambda r: -float(r["risk_max"])):
        out.append({"type": r.get("type") or "", "lat": round(float(r["lat"]), 6), "lon": round(float(r["lon"]), 6),
                    "risk": round(float(r["risk_max"])), "mechanism": r.get("mechanism") or "",
                    "month": r.get("peak_month") or "", "species": r.get("species") or "",
                    "category": r.get("category") or "", "voltage": r.get("voltage") or "",
                    "osm": r.get("source_url") or r.get("osm_url") or "", "osm_id": report.osm_id_text(r.get("osm_id")),
                    "source": r.get("source") or "osm", "row": r})
    return out


def _kv(v):
    try:
        return f" · {float(v) / 1000:g} kV" if v and float(v) else ""
    except ValueError:
        return ""


def _source_label(x):
    """What the link of an element says: its OSM id, or "Enedis" for the elements of the Enedis datasets."""
    return "Enedis" if x["source"] == "enedis" else str(x["osm_id"] or "OSM")


def _osm(x):
    if not x["osm"]:
        return ""
    return f'<a href="{escape(x["osm"])}" target="_blank" rel="noopener">{escape(_source_label(x))}</a>'


def page(region, code, props, outline, rows, lang):
    """The HTML of one site's page in one language."""
    langs = config.region_langs(region)
    others = {o: f"{escape(code)}.{o}.html" for o in langs if o != lang}
    name, kind = props.get("nombre") or code, props.get("tipo") or ""
    region_label = config.region_name(region, lang)
    items = _rows(rows)
    counts = {t: sum(1 for x in items if x["type"] == t) for t in ORDER}
    figures = site.figures_html([(i18n.num(n, lang), i18n.element_type_plural(t, lang)) for t, n in counts.items() if n])
    labels = [{"n": i + 1, "type": i18n.element_type(x["type"], lang), "mechanism": i18n.mechanism(x["mechanism"], lang),
               "month": i18n.month_label_from_canonical(x["month"], lang) if x["month"] else "",
               "species": i18n.species_list(x["species"], lang), "colour": COLOUR.get(x["type"], "#7f8c8d"),
               "lat": x["lat"], "lon": x["lon"], "risk": x["risk"], "osm": x["osm"],
               "src": "Enedis" if x["source"] == "enedis" else "OSM"} for i, x in enumerate(items)]
    table = "".join(
        f'<tr id="e{i + 1}"><td class="n">{i + 1}</td>'
        f'<td><span class="dot" style="background:{COLOUR.get(x["type"], "#7f8c8d")}"></span>'
        f'{escape(i18n.element_type(x["type"], lang))}</td>'
        f'<td>{escape(i18n.mechanism(x["mechanism"], lang))}</td><td class="n">{x["risk"]}</td>'
        f'<td>{escape(labels[i]["month"])}</td><td>{escape(labels[i]["species"])}</td>'
        f'<td class="why">{"<br>".join(escape(w) for w in i18n.explain(SimpleNamespace(**x["row"]), lang))}</td>'
        f'<td>{escape(i18n.category(x["category"], lang))}{_kv(x["voltage"])}</td>'
        f'<td>{_osm(x)}</td></tr>'
        for i, x in enumerate(items))
    hub = (f' · <a href="{HUB_URL}{escape(code)}">{escape(i18n.t(lang, "site_hub"))}</a>'
           if "ZEPA" in kind or "ZPS" in kind else "")  # the hub follows the bird sites (SPA)
    data = json.dumps({"outline": outline, "items": labels}, ensure_ascii=False).replace("</", "<\\/")
    title = i18n.t(lang, "site_page_title", site=name)
    return f"""{site.page_head(lang, title, CSS)}
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<body>
<header class="site-header">
 {site.lang_switch(lang, others)}
 <h1>{site.LOGO_SVG}{i18n.t(lang, 'h1_html')}</h1>
 <p class="lede">{escape(i18n.t(lang, 'site_lede', n=len(items), site=name, kind=kind, code=code))}</p>
 <p class="links"><a href="../map.{lang}.html">{escape(i18n.t(lang, 'site_full_map', region=region_label))}</a> ·
  <a href="../report.{lang}.html">{escape(i18n.t(lang, 'site_report', region=region_label))}</a> ·
  <a href="../../regions.{lang}.html">{escape(i18n.t(lang, 'back_to_regions'))}</a>{hub}</p>
 {figures}
</header>
<main>
<p class="meta">{escape(i18n.t(lang, 'site_rule', share=round(config.HIGH_RISK_SHARE * 100), region=region_label))}</p>
<div id="map" role="region" aria-label="{escape(i18n.t(lang, 'site_map_label', site=name))}"></div>
<h2>{escape(i18n.t(lang, 'site_h2_list', n=len(items)))}</h2>
<div class="wrap"><table><thead><tr><th>{escape(i18n.t(lang, 'th_rank'))}</th><th>{escape(i18n.t(lang, 'th_type'))}</th>
<th>{escape(i18n.t(lang, 'th_mechanism'))}</th><th>{escape(i18n.t(lang, 'th_risk_max'))}</th>
<th>{escape(i18n.t(lang, 'th_peak_month'))}</th><th>{escape(i18n.t(lang, 'th_species_list'))}</th>
<th>{escape(i18n.t(lang, 'th_why'))}</th><th>{escape(i18n.t(lang, 'th_category'))}</th>
<th>{escape(i18n.t(lang, 'th_osm'))}</th></tr></thead>
<tbody>{table}</tbody></table></div>
</main>
{site.site_footer(lang, config.region_country(region))}
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D = {data};
const map = L.map("map", {{scrollWheelZoom: false}});
L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{maxZoom: 19, attribution: "© OpenStreetMap"}}).addTo(map);
const esc = s => String(s).replace(/[&<>"]/g, c => ({{"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}}[c]));
const outline = L.geoJSON(D.outline, {{interactive: false, style: {{color: "#8a5a00", weight: 2, fillOpacity: .08}}}});
map.fitBounds(outline.getBounds(), {{padding: [16, 16]}});  // a view first: Leaflet cannot draw paths without one
outline.addTo(map);
for (const x of D.items) {{
  L.circleMarker([x.lat, x.lon], {{radius: 6, color: "#221d1a", weight: 1.2, fillColor: x.colour, fillOpacity: .9}})
    .bindPopup(`<b>#${{x.n}} · ${{esc(x.type)}}</b> (${{esc(x.mechanism)}})<br>{escape(i18n.t(lang, 'th_risk_max'))}: ${{x.risk}}`
      + (x.month ? ` · ${{esc(x.month)}}` : "") + (x.species ? `<br>${{esc(x.species)}}` : "")
      + `<br><a href="#e${{x.n}}">{escape(i18n.t(lang, 'site_in_table'))}</a>`
      + (x.osm ? ` · <a href="${{esc(x.osm)}}" target="_blank" rel="noopener">${{x.src}}</a>` : ""))
    .on("click", () => {{ for (const tr of document.querySelectorAll("tr.on")) tr.classList.remove("on");
                         document.getElementById("e" + x.n)?.classList.add("on"); }})
    .addTo(map);
}}
</script>
</body></html>"""


def write(out, inside, natura, regions, path_of):
    """Write the page of every site with high-risk elements, in each language, and drop the pages of an earlier run.

    `inside` is {(region, SITECODE): ranking rows}; `path_of(region, code, lang)` names each page under `out`.
    """
    out = Path(out)
    feats = {f["properties"]["codigo"]: f for f in natura["features"]}
    for region in regions:
        for old in (out / region / "sites").glob("*.html"):
            old.unlink()
    for (region, code), rows in inside.items():
        f = feats[code]
        outline = {"type": "Feature", "properties": {}, "geometry": f["geometry"]}
        for lang in config.region_langs(region):
            path = out / path_of(region, code, lang)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(page(region, code, f["properties"], outline, rows, lang), encoding="utf-8")
    return len(inside)
