"""Outputs: interactive map (folium), HTML report, GeoTIFF, CSV and GeoJSON.

The HTML products are generated once per language (see `i18n`); the data products are language-independent.
"""
import json
from datetime import date
from html import escape

import folium
import numpy as np

from . import config, i18n, site

LINE_COLOUR = {"distribution": "#e67e22", "transmission": "#c0392b", "unknown": "#7f8c8d"}
ELEMENT_COLOUR = {"pylon": "#e74c3c", "turbine": "#8e44ad", "line": "#d35400"}
# "magma"-like palette (control points 0..1) without depending on matplotlib
_MAGMA = np.array([
    [0.001, 0.000, 0.014], [0.110, 0.063, 0.276], [0.316, 0.072, 0.485], [0.516, 0.127, 0.507],
    [0.716, 0.215, 0.475], [0.881, 0.351, 0.391], [0.973, 0.539, 0.381], [0.997, 0.734, 0.505],
    [0.987, 0.926, 0.686], [0.987, 0.991, 0.749]])


def _cmap(v):
    """v in 0-1 -> RGB 0-1 by interpolating the palette."""
    v = np.clip(v, 0, 1)
    x = np.linspace(0, 1, len(_MAGMA))
    return np.stack([np.interp(v, x, _MAGMA[:, i]) for i in range(3)], axis=-1)


def _rgba(arr):
    """Array 0-100 -> RGBA image with transparency proportional to the risk (0 = transparent)."""
    rgb = _cmap(arr / 100.0)
    # opacity grows with the risk; cells below 5/100 are not painted so they do not hide the base map
    alpha = np.clip(arr / 100.0, 0, 1) ** 0.7 * 0.9
    alpha = np.where(arr >= 5, np.maximum(alpha, 0.2), 0.0)
    return (np.concatenate([rgb, alpha[..., None]], axis=-1) * 255).astype(np.uint8)


def _overlay(m, arr, grid, name, show):
    folium.raster_layers.ImageOverlay(
        image=_rgba(arr), bounds=grid.bounds_folium(), origin="upper", mercator_project=True,
        name=name, show=show, opacity=1.0, interactive=False, zindex=2,
    ).add_to(m)


def build_map(result, infra, ranking, grid, region_label, lang, top=100, start_month=None, country="ES"):
    """Interactive folium map, with every label in `lang` (and in the wording of `country`)."""

    def tt(key, **kw):
        return i18n.t(lang, key, country=country, **kw)

    lat_c, lon_c = grid.lat_centre, 0.5 * (grid.lon_min + grid.lon_max)
    m = folium.Map(location=[lat_c, lon_c], zoom_start=11, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                     attr="© OpenTopoMap (CC-BY-SA), © OpenStreetMap contributors",
                     name=tt("tile_terrain"), show=False, max_zoom=17).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Imagery", name=tt("tile_satellite"), show=False).add_to(m)

    month0 = (start_month or date.today().month) - 1
    _overlay(m, result["total"].max(axis=0), grid, tt("layer_total_annual"), show=False)
    for i in range(12):
        _overlay(m, result["total"][i], grid,
                 tt("layer_total_month", month=i18n.month_label(i, lang)), show=(i == month0))
    for key, label in (("electro", "layer_electro"), ("col_lin", "layer_col_lin"), ("col_aer", "layer_col_aer")):
        _overlay(m, result["aggregate"][key].max(axis=0), grid, tt(label), show=False)
    for sp, layers in result["by_species"].items():
        _overlay(m, layers["total"].max(axis=0), grid,
                 tt("layer_species", name=config.species_name(sp, lang)), show=False)

    # one single GeoJSON layer (not thousands of PolyLines): in large regions this takes the HTML
    # from tens of MB down to a few
    lines_gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "LineString", "coordinates": [[round(lo, 5), round(la, 5)] for lo, la in ln["coords"]]},
         "properties": {"category": i18n.category(ln["category"], lang),
                        "voltage": f"{ln['voltage'] / 1000:g} kV" if ln["voltage"]
                                   else tt("voltage_unknown"),
                        "name": ln["name"] or "",
                        "_cat": ln["category"]}}
        for ln in infra["lines"] if len(ln["coords"]) > 1]}
    folium.GeoJson(
        lines_gj, name=tt("layer_lines"), show=True,
        style_function=lambda f: {"color": LINE_COLOUR[f["properties"]["_cat"]],
                                  "weight": 2 if f["properties"]["_cat"] == "distribution" else 3, "opacity": 0.8},
        tooltip=folium.GeoJsonTooltip(fields=["category", "voltage", "name"],
                                      aliases=[tt("tooltip_category"), tt("tooltip_voltage"),
                                               tt("tooltip_name")]),
    ).add_to(m)

    fg_turbines = folium.FeatureGroup(name=tt("layer_turbines"), show=True)
    for t in infra["turbines"]:
        folium.CircleMarker((t["lat"], t["lon"]), radius=3, color="#2c3e50", fill=True, fill_opacity=0.9,
                            tooltip=tt("tooltip_turbine",
                                           power=t["power_output"] or "")).add_to(fg_turbines)
    fg_turbines.add_to(m)

    pylons = [a for a in infra["pylons"] if a["category"] != "transmission"]
    note = ""
    if len(pylons) > config.MAX_PYLONS_ON_MAP:  # large regions: only the highest index, or the HTML will not load
        ids = set(ranking[ranking.type == "pylon"].head(config.MAX_PYLONS_ON_MAP).source_id.astype(str))
        pylons = [a for a in pylons if str(a["id"]) in ids]
        note = tt("layer_pylons_note", n=config.MAX_PYLONS_ON_MAP)
    fg_pylons = folium.FeatureGroup(name=tt("layer_pylons", note=note), show=False)
    for a in pylons:
        folium.CircleMarker((a["lat"], a["lon"]), radius=2, color="#e67e22", fill=True, fill_opacity=0.7,
                            tooltip=f"{a['type']} · {i18n.category(a['category'], lang)}").add_to(fg_pylons)
    fg_pylons.add_to(m)

    fg_rank = folium.FeatureGroup(name=tt("layer_ranking", top=top), show=True)
    ceiling = max(float(ranking.risk_max.max()), 1.0)  # radius (5-10 px) is relative to the first in the ranking
    for i, r in ranking.head(top).iterrows():
        colour = ELEMENT_COLOUR[r.type]
        type_label = i18n.element_type(r.type, lang)
        kv = f" · {r.voltage / 1000:g} kV" if r.voltage == r.voltage and r.voltage else ""
        popup = (f"<b>#{i + 1} · {type_label}</b> ({i18n.mechanism(r.mechanism, lang)})<br>"
                 f"{tt('popup_index', max=r.risk_max, mean=r.risk_mean)}<br>"
                 f"{tt('popup_peak_month')}: {i18n.month_label_from_canonical(r.peak_month, lang)}<br>"
                 f"{tt('popup_species')}: {escape(i18n.species_list(r.species, lang))}<br>"
                 f"{escape(i18n.category(r.category, lang))}{kv}<br>"
                 f"{source_link(r, lang, tt('popup_osm'))}")
        folium.CircleMarker((r.lat, r.lon), radius=5 + 5 * r.risk_max / ceiling, color=colour, weight=2,
                            fill=True, fill_opacity=0.5, popup=folium.Popup(popup, max_width=320),
                            tooltip=f"#{i + 1} {type_label} · {r.risk_max:.0f}").add_to(fg_rank)
    fg_rank.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    legend = f"""
    <div style="position: fixed; bottom: 30px; left: 10px; z-index: 9999; background: white; padding: 10px 12px;
                border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.3); font: 12px sans-serif; max-width: 260px">
      <b>{escape(region_label)}</b><br>{tt("legend_index")}<br>
      <div style="background: linear-gradient(to right, #000004, #3b0f70, #8c2981, #de4968, #fe9f6d, #fcfdbf);
                  height: 10px; margin: 4px 0"></div>
      <span style="float:left">{tt("legend_low")}</span>
      <span style="float:right">{tt("legend_high")}</span><br>
      <span style="color:#e67e22">▬</span> {tt("legend_distribution")} &nbsp;
      <span style="color:#c0392b">▬</span> {tt("legend_transmission")} &nbsp;
      <span style="color:#7f8c8d">▬</span> {tt("legend_unknown")}<br>
      <span style="color:#2c3e50">●</span> {tt("legend_turbine")} &nbsp;
      <span style="color:#e74c3c">◯</span> {tt("legend_priority")}
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))
    return m


def _table_html(df, lang, fmt="{:.0f}"):
    """Seasonality table: scientific names become common names, canonical months become localised labels."""
    header = "".join(f"<th>{escape(i18n.month_label_from_canonical(c, lang))}</th>" for c in df.columns)
    out = [f"<table><thead><tr><th></th>{header}</tr></thead><tbody>"]
    for idx, row in df.iterrows():
        label = i18n.t(lang, "row_total") if idx == "TOTAL" else config.species_name(str(idx), lang)
        cells = "".join(f"<td style='background: rgba(222,73,104,{min(v, 100) / 130:.2f})'>{fmt.format(v)}</td>"
                        for v in row.values)
        out.append(f"<tr><th>{escape(label)}</th>{cells}</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def osm_id_text(value):
    """An OSM id as written: pandas reads the column as float when Enedis rows leave it empty (1409.0 -> "1409")."""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError, OverflowError):  # None, "", NaN
        return "" if value is None or value != value else str(value)


def source_link(r, lang, osm_label=None):
    """Link of a ranking row to where the element comes from: its OSM page, or the Enedis dataset."""
    url = getattr(r, "source_url", None)
    if not isinstance(url, str) or not url:
        url = r.osm_url  # rankings written before the source columns existed
    if getattr(r, "source", "osm") == "enedis":
        label = i18n.t(lang, "popup_enedis")
    else:
        label = osm_label or osm_id_text(r.osm_id)
    return f"<a href='{escape(str(url))}' target='_blank'>{escape(label)}</a>"


REPORT_CSS = site.PAGE_CSS + """
.site-header .meta{margin:0}
main{max-width:1440px;margin:0 auto;padding:0 16px 8px}
main h2{font:700 22px/1.1 var(--font-title);text-transform:uppercase;letter-spacing:.03em;margin:1.6em 0 .5em;
  padding-bottom:4px;border-bottom:1px solid var(--line)}
main table{border-collapse:collapse;font-size:13px;width:100%;background:var(--paper)}
main th,main td{border:1px solid var(--line);padding:3px 6px;text-align:left}
main thead th{font:600 13px/1.2 var(--font-title);text-transform:uppercase;letter-spacing:.04em}
iframe{display:block;width:100%;height:640px;border:1px solid var(--line);background:var(--paper)}
.meta{color:var(--muted);font-size:14.5px}
.wrap{overflow-x:auto}
code{font-family:var(--font-data);font-size:.9em}
@media (max-width:640px){iframe{height:70vh}}
"""


def report(path, map_rel, region_label, bbox, infra_summary, species_info, table, ranking, lang,
           other_lang_href, top=50, regions_href="../regions.{lang}.html", country="ES", other_lang=None):
    """Write the HTML report of one region in one language; `other_lang_href` is the same report in
    `other_lang` (English, or the country's own language on the English page)."""

    def tt(key, **kw):
        return i18n.t(lang, key, country=country, **kw)

    other_lang = other_lang or ("en" if lang != "en" else config.COUNTRY_LANGS[country][0])
    rows = []
    for i, r in ranking.head(top).iterrows():
        kv = f"{r.voltage / 1000:g} kV" if r.voltage == r.voltage and r.voltage else ""
        rows.append(
            f"<tr><td>{i + 1}</td><td>{escape(i18n.element_type(r.type, lang))}</td>"
            f"<td>{escape(i18n.mechanism(r.mechanism, lang))}</td><td>{r.risk_max:.0f}</td>"
            f"<td>{r.risk_mean:.0f}</td><td>{escape(i18n.month_label_from_canonical(r.peak_month, lang))}</td>"
            f"<td>{escape(i18n.species_list(r.species, lang))}</td>"
            f"<td>{escape(i18n.category(r.category, lang))} {kv}</td><td>{escape(str(r.operator or ''))}</td>"
            f"<td>{source_link(r, lang)}</td></tr>")
    species_rows = "".join(
        f"<tr><td><i>{escape(sp)}</i></td><td>{escape(config.species_name(sp, lang))}</td>"
        f"<td>{i18n.num(info['gbif_records'], lang)}</td><td>{i18n.num(info['movebank_fixes'], lang)}</td>"
        f"<td>{i18n.num(info['confidence'], lang) if 'confidence' in info else ''}</td>"
        f"<td>{tt('yes') if info['included'] else tt('no_few_records')}</td></tr>"
        for sp, info in species_info.items())
    included = sum(1 for info in species_info.values() if info["included"])
    figures = site.figures_html([
        (i18n.num(infra_summary["lines"], lang), tt("fig_line_segments")),
        (i18n.num(infra_summary["pylons"], lang), tt("fig_pylons")),
        (i18n.num(infra_summary["turbines"], lang), tt("fig_turbines")),
        (i18n.num(included, lang), tt("fig_species")),
    ])
    km = " · ".join(f"{i18n.category(k, lang)} {i18n.num(round(v, 1), lang)}"
                    for k, v in infra_summary["km_by_category"].items())
    html = f"""{site.page_head(lang, tt('report_title', region=region_label), REPORT_CSS)}<body>
<header class="site-header">
{site.lang_switch(lang, {other_lang: other_lang_href})}
<h1>{site.LOGO_SVG}{tt('h1_html')}</h1>
<p class="lede">{escape(tt('report_lede', region=region_label))}</p>
<p class="meta">{escape(tt('report_meta', region=region_label, bbox=bbox, date=date.today().isoformat()))}
 · <a href="{regions_href.format(lang=lang)}">{escape(tt('back_to_regions'))}</a></p>
{figures}
</header>
<main>
<p class="meta">{escape(tt('report_meta', region=region_label, bbox=bbox, date=date.today().isoformat()))}
 · <a href="{regions_href.format(lang=lang)}">{escape(tt('back_to_regions'))}</a></p>
<iframe src="{map_rel}" loading="lazy"></iframe>
<p>{escape(tt('report_intro'))}</p>

<h2>{escape(tt('h2_infra'))}</h2>
<ul>
 <li>{escape(tt('infra_lines', n=i18n.num(infra_summary['lines'], lang), km=km))}</li>
 <li>{escape(tt('infra_pylons', n=i18n.num(infra_summary['pylons'], lang),
                    dist=i18n.num(infra_summary['pylons_distribution'], lang),
                    tagged=i18n.num(infra_summary.get('pylons_tagged', 0), lang)))}</li>
 <li>{escape(tt('infra_turbines', n=i18n.num(infra_summary['turbines'], lang)))}</li>
</ul>

<h2>{escape(tt('h2_species'))}</h2>
<div class="wrap"><table><thead><tr><th>{escape(tt('th_species'))}</th>
<th>{escape(tt('th_common_name'))}</th><th>{escape(tt('th_gbif'))}</th>
<th>{escape(tt('th_movebank'))}</th><th>{escape(tt('th_confidence'))}</th>
<th>{escape(tt('th_included'))}</th></tr></thead>
<tbody>{species_rows}</tbody></table></div>

<h2>{escape(tt('h2_seasonality'))}</h2>
<div class="wrap">{_table_html(table, lang)}</div>

<h2>{escape(tt('h2_ranking', top=top))}</h2>
<div class="wrap"><table><thead><tr><th>{escape(tt('th_rank'))}</th>
<th>{escape(tt('th_type'))}</th><th>{escape(tt('th_mechanism'))}</th>
<th>{escape(tt('th_risk_max'))}</th><th>{escape(tt('th_risk_mean'))}</th>
<th>{escape(tt('th_peak_month'))}</th><th>{escape(tt('th_species_list'))}</th>
<th>{escape(tt('th_category'))}</th><th>{escape(tt('th_operator'))}</th>
<th>{escape(tt('th_osm'))}</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p>{tt('ranking_files')}</p>
</main>
{site.method_section(lang, (country,))}
{site.site_footer(lang, country)}
</body></html>"""
    path.write_text(html, encoding="utf-8")


def export_geotiff(path, arr3d, grid, names=None):
    import rasterio

    with rasterio.open(path, "w", driver="GTiff", height=grid.ny, width=grid.nx, count=arr3d.shape[0],
                       dtype="float32", crs="EPSG:4326", transform=grid.transform(), compress="deflate") as dst:
        for i in range(arr3d.shape[0]):
            dst.write(arr3d[i].astype("float32"), i + 1)
            if names:
                dst.set_band_description(i + 1, names[i])


def export_geojson(path, ranking, top=None):
    df = ranking if top is None else ranking.head(top)
    feats = []
    for i, r in df.iterrows():
        props = {k: (None if (isinstance(v, float) and np.isnan(v)) else v)
                 for k, v in r.items() if k not in ("lat", "lon")}
        props["rank"] = int(i) + 1
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                      "properties": props})
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, default=str),
                    encoding="utf-8")
