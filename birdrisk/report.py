"""Outputs: interactive map (folium), HTML report, GeoTIFF, CSV and GeoJSON.

The HTML products are generated once per language (see `i18n`); the data products are language-independent.
"""
import json
from datetime import date
from html import escape

import folium
import numpy as np

from . import config, i18n

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


def build_map(result, infra, ranking, grid, region_label, lang, top=100, start_month=None):
    """Interactive folium map, with every label in `lang`."""
    lat_c, lon_c = grid.lat_centre, 0.5 * (grid.lon_min + grid.lon_max)
    m = folium.Map(location=[lat_c, lon_c], zoom_start=11, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                     attr="© OpenTopoMap (CC-BY-SA), © OpenStreetMap contributors",
                     name=i18n.t(lang, "tile_terrain"), show=False, max_zoom=17).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Imagery", name=i18n.t(lang, "tile_satellite"), show=False).add_to(m)

    month0 = (start_month or date.today().month) - 1
    _overlay(m, result["total"].max(axis=0), grid, i18n.t(lang, "layer_total_annual"), show=False)
    for i in range(12):
        _overlay(m, result["total"][i], grid,
                 i18n.t(lang, "layer_total_month", month=i18n.month_label(i, lang)), show=(i == month0))
    for key, label in (("electro", "layer_electro"), ("col_lin", "layer_col_lin"), ("col_aer", "layer_col_aer")):
        _overlay(m, result["aggregate"][key].max(axis=0), grid, i18n.t(lang, label), show=False)
    for sp, layers in result["by_species"].items():
        _overlay(m, layers["total"].max(axis=0), grid,
                 i18n.t(lang, "layer_species", name=config.species_name(sp, lang)), show=False)

    # one single GeoJSON layer (not thousands of PolyLines): in large regions this takes the HTML
    # from tens of MB down to a few
    lines_gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "LineString", "coordinates": [[round(lo, 5), round(la, 5)] for lo, la in ln["coords"]]},
         "properties": {"category": i18n.category(ln["category"], lang),
                        "voltage": f"{ln['voltage'] / 1000:g} kV" if ln["voltage"]
                                   else i18n.t(lang, "voltage_unknown"),
                        "name": ln["name"] or "",
                        "_cat": ln["category"]}}
        for ln in infra["lines"] if len(ln["coords"]) > 1]}
    folium.GeoJson(
        lines_gj, name=i18n.t(lang, "layer_lines"), show=True,
        style_function=lambda f: {"color": LINE_COLOUR[f["properties"]["_cat"]],
                                  "weight": 2 if f["properties"]["_cat"] == "distribution" else 3, "opacity": 0.8},
        tooltip=folium.GeoJsonTooltip(fields=["category", "voltage", "name"],
                                      aliases=[i18n.t(lang, "tooltip_category"), i18n.t(lang, "tooltip_voltage"),
                                               i18n.t(lang, "tooltip_name")]),
    ).add_to(m)

    fg_turbines = folium.FeatureGroup(name=i18n.t(lang, "layer_turbines"), show=True)
    for t in infra["turbines"]:
        folium.CircleMarker((t["lat"], t["lon"]), radius=3, color="#2c3e50", fill=True, fill_opacity=0.9,
                            tooltip=i18n.t(lang, "tooltip_turbine",
                                           power=t["power_output"] or "")).add_to(fg_turbines)
    fg_turbines.add_to(m)

    pylons = [a for a in infra["pylons"] if a["category"] != "transmission"]
    note = ""
    if len(pylons) > config.MAX_PYLONS_ON_MAP:  # large regions: only the highest index, or the HTML will not load
        ids = set(ranking[ranking.type == "pylon"].head(config.MAX_PYLONS_ON_MAP).osm_id)
        pylons = [a for a in pylons if a["id"] in ids]
        note = i18n.t(lang, "layer_pylons_note", n=config.MAX_PYLONS_ON_MAP)
    fg_pylons = folium.FeatureGroup(name=i18n.t(lang, "layer_pylons", note=note), show=False)
    for a in pylons:
        folium.CircleMarker((a["lat"], a["lon"]), radius=2, color="#e67e22", fill=True, fill_opacity=0.7,
                            tooltip=f"{a['type']} · {i18n.category(a['category'], lang)}").add_to(fg_pylons)
    fg_pylons.add_to(m)

    fg_rank = folium.FeatureGroup(name=i18n.t(lang, "layer_ranking", top=top), show=True)
    ceiling = max(float(ranking.risk_max.max()), 1.0)  # radius (5-10 px) is relative to the first in the ranking
    for i, r in ranking.head(top).iterrows():
        colour = ELEMENT_COLOUR[r.type]
        type_label = i18n.element_type(r.type, lang)
        kv = f" · {r.voltage / 1000:g} kV" if r.voltage == r.voltage and r.voltage else ""
        popup = (f"<b>#{i + 1} · {type_label}</b> ({i18n.mechanism(r.mechanism, lang)})<br>"
                 f"{i18n.t(lang, 'popup_index', max=r.risk_max, mean=r.risk_mean)}<br>"
                 f"{i18n.t(lang, 'popup_peak_month')}: {i18n.month_label_from_canonical(r.peak_month, lang)}<br>"
                 f"{i18n.t(lang, 'popup_species')}: {escape(i18n.species_list(r.species, lang))}<br>"
                 f"{escape(i18n.category(r.category, lang))}{kv}<br>"
                 f"<a href='{r.osm_url}' target='_blank'>{i18n.t(lang, 'popup_osm')}</a>")
        folium.CircleMarker((r.lat, r.lon), radius=5 + 5 * r.risk_max / ceiling, color=colour, weight=2,
                            fill=True, fill_opacity=0.5, popup=folium.Popup(popup, max_width=320),
                            tooltip=f"#{i + 1} {type_label} · {r.risk_max:.0f}").add_to(fg_rank)
    fg_rank.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    legend = f"""
    <div style="position: fixed; bottom: 30px; left: 10px; z-index: 9999; background: white; padding: 10px 12px;
                border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.3); font: 12px sans-serif; max-width: 260px">
      <b>{escape(region_label)}</b><br>{i18n.t(lang, "legend_index")}<br>
      <div style="background: linear-gradient(to right, #000004, #3b0f70, #8c2981, #de4968, #fe9f6d, #fcfdbf);
                  height: 10px; margin: 4px 0"></div>
      <span style="float:left">{i18n.t(lang, "legend_low")}</span>
      <span style="float:right">{i18n.t(lang, "legend_high")}</span><br>
      <span style="color:#e67e22">▬</span> {i18n.t(lang, "legend_distribution")} &nbsp;
      <span style="color:#c0392b">▬</span> {i18n.t(lang, "legend_transmission")} &nbsp;
      <span style="color:#7f8c8d">▬</span> {i18n.t(lang, "legend_unknown")}<br>
      <span style="color:#2c3e50">●</span> {i18n.t(lang, "legend_turbine")} &nbsp;
      <span style="color:#e74c3c">◯</span> {i18n.t(lang, "legend_priority")}
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


def _lang_switch(current, other_href):
    """Small pill switcher linking to the same page in the other language."""
    other = "en" if current == "es" else "es"
    return (f'<p class="lang"><span class="on">{i18n.t(current, "lang_name")}</span> '
            f'<a href="{other_href}" hreflang="{other}">{i18n.t(current, "other_lang_name")}</a></p>')


def report(path, map_rel, region_label, bbox, infra_summary, species_info, table, ranking, lang,
           other_lang_href, top=50, regions_href="../regions.{lang}.html"):
    """Write the HTML report of one region in one language."""
    rows = []
    for i, r in ranking.head(top).iterrows():
        kv = f"{r.voltage / 1000:g} kV" if r.voltage == r.voltage and r.voltage else ""
        rows.append(
            f"<tr><td>{i + 1}</td><td>{escape(i18n.element_type(r.type, lang))}</td>"
            f"<td>{escape(i18n.mechanism(r.mechanism, lang))}</td><td>{r.risk_max:.0f}</td>"
            f"<td>{r.risk_mean:.0f}</td><td>{escape(i18n.month_label_from_canonical(r.peak_month, lang))}</td>"
            f"<td>{escape(i18n.species_list(r.species, lang))}</td>"
            f"<td>{escape(i18n.category(r.category, lang))} {kv}</td><td>{escape(str(r.operator or ''))}</td>"
            f"<td><a href='{r.osm_url}' target='_blank'>{r.osm_id}</a></td></tr>")
    species_rows = "".join(
        f"<tr><td><i>{escape(sp)}</i></td><td>{escape(config.species_name(sp, lang))}</td>"
        f"<td>{info['gbif_records']}</td><td>{info['movebank_fixes']}</td>"
        f"<td>{info.get('confidence', '')}</td>"
        f"<td>{i18n.t(lang, 'yes') if info['included'] else i18n.t(lang, 'no_few_records')}</td></tr>"
        for sp, info in species_info.items())
    html = f"""<!doctype html><html lang="{i18n.t(lang, 'html_lang')}"><head><meta charset="utf-8">
<title>{escape(i18n.t(lang, 'report_title', region=region_label))}</title>
<style>
 body{{font:14px/1.45 system-ui,sans-serif;margin:0;color:#222;background:#fff;color-scheme:light}}
 main{{max-width:1200px;margin:0 auto;padding:16px 24px}}
 h1{{font-size:22px;margin:.2em 0}} h2{{font-size:17px;margin:1.6em 0 .5em;border-bottom:1px solid #ddd}}
 table{{border-collapse:collapse;font-size:12.5px;width:100%}}
 th,td{{border:1px solid #e3e3e3;padding:3px 6px;text-align:left}}
 th{{background:#f5f5f5}} iframe{{width:100%;height:640px;border:1px solid #ccc}} .meta{{color:#666}}
 .wrap{{overflow-x:auto}} code{{background:#f3f3f3;padding:0 3px}}
 .lang{{float:right;margin:0;font-size:12.5px}}
 .lang a,.lang span{{padding:2px 8px;border:1px solid #ddd;border-radius:99px;margin-left:4px;text-decoration:none}}
 .lang .on{{background:#f0f0f0;color:#555}}
</style></head><body><main>
{_lang_switch(lang, other_lang_href)}
<h1>{escape(i18n.t(lang, 'site_title'))}</h1>
<p class="meta">{escape(i18n.t(lang, 'report_meta', region=region_label, bbox=bbox, date=date.today().isoformat()))}
 · <a href="{regions_href.format(lang=lang)}">{escape(i18n.t(lang, 'back_to_regions'))}</a></p>
<iframe src="{map_rel}" loading="lazy"></iframe>
<p>{escape(i18n.t(lang, 'report_intro'))}</p>

<h2>{escape(i18n.t(lang, 'h2_infra'))}</h2>
<ul>
 <li>{escape(i18n.t(lang, 'infra_lines', n=infra_summary['lines'],
                    km=json.dumps(infra_summary['km_by_category'], ensure_ascii=False)))}</li>
 <li>{escape(i18n.t(lang, 'infra_pylons', n=infra_summary['pylons'], dist=infra_summary['pylons_distribution'],
                    tagged=infra_summary.get('pylons_tagged', 0)))}</li>
 <li>{escape(i18n.t(lang, 'infra_turbines', n=infra_summary['turbines']))}</li>
</ul>

<h2>{escape(i18n.t(lang, 'h2_species'))}</h2>
<div class="wrap"><table><thead><tr><th>{escape(i18n.t(lang, 'th_species'))}</th>
<th>{escape(i18n.t(lang, 'th_common_name'))}</th><th>{escape(i18n.t(lang, 'th_gbif'))}</th>
<th>{escape(i18n.t(lang, 'th_movebank'))}</th><th>{escape(i18n.t(lang, 'th_confidence'))}</th>
<th>{escape(i18n.t(lang, 'th_included'))}</th></tr></thead>
<tbody>{species_rows}</tbody></table></div>

<h2>{escape(i18n.t(lang, 'h2_seasonality'))}</h2>
<div class="wrap">{_table_html(table, lang)}</div>

<h2>{escape(i18n.t(lang, 'h2_ranking', top=top))}</h2>
<div class="wrap"><table><thead><tr><th>{escape(i18n.t(lang, 'th_rank'))}</th>
<th>{escape(i18n.t(lang, 'th_type'))}</th><th>{escape(i18n.t(lang, 'th_mechanism'))}</th>
<th>{escape(i18n.t(lang, 'th_risk_max'))}</th><th>{escape(i18n.t(lang, 'th_risk_mean'))}</th>
<th>{escape(i18n.t(lang, 'th_peak_month'))}</th><th>{escape(i18n.t(lang, 'th_species_list'))}</th>
<th>{escape(i18n.t(lang, 'th_category'))}</th><th>{escape(i18n.t(lang, 'th_operator'))}</th>
<th>{escape(i18n.t(lang, 'th_osm'))}</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p>{i18n.t(lang, 'ranking_files')}</p>

<h2>{escape(i18n.t(lang, 'h2_method'))}</h2>
{i18n.method_html(lang)}
</main></body></html>"""
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
