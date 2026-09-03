"""Salidas: mapa interactivo (folium), informe HTML, GeoTIFF, CSV y GeoJSON."""
import json
from datetime import date
from html import escape

import folium
import numpy as np

from . import config

COLOR_LINEA = {"distribucion": "#e67e22", "transporte": "#c0392b", "desconocida": "#7f8c8d"}
# Paleta tipo "magma" (puntos de control 0..1) sin depender de matplotlib
_MAGMA = np.array([
    [0.001, 0.000, 0.014], [0.110, 0.063, 0.276], [0.316, 0.072, 0.485], [0.516, 0.127, 0.507],
    [0.716, 0.215, 0.475], [0.881, 0.351, 0.391], [0.973, 0.539, 0.381], [0.997, 0.734, 0.505],
    [0.987, 0.926, 0.686], [0.987, 0.991, 0.749]])


def _cmap(v):
    """v en 0-1 → RGB 0-1 interpolando la paleta."""
    v = np.clip(v, 0, 1)
    x = np.linspace(0, 1, len(_MAGMA))
    return np.stack([np.interp(v, x, _MAGMA[:, i]) for i in range(3)], axis=-1)


def _rgba(arr):
    """Array 0-100 → imagen RGBA con transparencia proporcional al riesgo (0 = transparente)."""
    rgb = _cmap(arr / 100.0)
    # transparencia creciente con el riesgo; las celdas por debajo de 5/100 no se pintan para no tapar el mapa
    alpha = np.clip(arr / 100.0, 0, 1) ** 0.7 * 0.9
    alpha = np.where(arr >= 5, np.maximum(alpha, 0.2), 0.0)
    return (np.concatenate([rgb, alpha[..., None]], axis=-1) * 255).astype(np.uint8)


def _overlay(m, arr, grid, nombre, show):
    folium.raster_layers.ImageOverlay(
        image=_rgba(arr), bounds=grid.bounds_folium(), origin="upper", mercator_project=True,
        name=nombre, show=show, opacity=1.0, interactive=False, zindex=2,
    ).add_to(m)


def mapa(resultado, infra, ranking, grid, region_nombre, top=100, mes_inicial=None):
    lat_c, lon_c = grid.lat_centro, 0.5 * (grid.lon_min + grid.lon_max)
    m = folium.Map(location=[lat_c, lon_c], zoom_start=11, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                     attr="© OpenTopoMap (CC-BY-SA), © OpenStreetMap contributors", name="Relieve (OpenTopoMap)",
                     show=False, max_zoom=17).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Imagery", name="Satélite", show=False).add_to(m)

    mes0 = (mes_inicial or date.today().month) - 1
    _overlay(m, resultado["total"].max(axis=0), grid, "Riesgo total · máximo anual", show=False)
    for i, mes in enumerate(config.MESES):
        _overlay(m, resultado["total"][i], grid, f"Riesgo total · {mes}", show=(i == mes0))
    for k, nombre in (("electro", "Electrocución (máx. anual)"), ("col_lin", "Colisión líneas (máx. anual)"),
                      ("col_aer", "Colisión aerogeneradores (máx. anual)")):
        _overlay(m, resultado["agregado"][k].max(axis=0), grid, nombre, show=False)
    for sp, capas in resultado["por_especie"].items():
        _overlay(m, capas["total"].max(axis=0), grid, f"Especie · {config.ESPECIES.get(sp, {}).get('nombre', sp)}", show=False)

    # una sola capa GeoJSON (no miles de PolyLine): en regiones grandes el HTML pasa de decenas de MB a unos pocos
    lineas_gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "LineString", "coordinates": [[round(lo, 5), round(la, 5)] for lo, la in ln["coords"]]},
         "properties": {"categoria": ln["categoria"],
                        "tension": f"{ln['voltaje'] / 1000:g} kV" if ln["voltaje"] else "desconocida",
                        "nombre": ln["nombre"] or ""}}
        for ln in infra["lineas"] if len(ln["coords"]) > 1]}
    folium.GeoJson(
        lineas_gj, name="Líneas eléctricas (OSM)", show=True,
        style_function=lambda f: {"color": COLOR_LINEA[f["properties"]["categoria"]],
                                  "weight": 2 if f["properties"]["categoria"] == "distribucion" else 3, "opacity": 0.8},
        tooltip=folium.GeoJsonTooltip(fields=["categoria", "tension", "nombre"], aliases=["Categoría", "Tensión", "Nombre"]),
    ).add_to(m)

    fg_t = folium.FeatureGroup(name="Aerogeneradores (OSM)", show=True)
    for t in infra["aerogeneradores"]:
        folium.CircleMarker((t["lat"], t["lon"]), radius=3, color="#2c3e50", fill=True, fill_opacity=0.9,
                            tooltip=f"aerogenerador {t['potencia'] or ''}").add_to(fg_t)
    fg_t.add_to(m)

    apoyos = [a for a in infra["apoyos"] if a["categoria"] != "transporte"]
    nota = ""
    if len(apoyos) > config.MAX_APOYOS_MAPA:  # regiones grandes: solo los de mayor índice, o el HTML no carga
        ids = set(ranking[ranking.tipo == "apoyo"].head(config.MAX_APOYOS_MAPA).osm_id)
        apoyos = [a for a in apoyos if a["id"] in ids]
        nota = f" · {config.MAX_APOYOS_MAPA} de mayor índice"
    fg_a = folium.FeatureGroup(name=f"Apoyos de distribución (OSM){nota}", show=False)
    for a in apoyos:
        folium.CircleMarker((a["lat"], a["lon"]), radius=2, color="#e67e22", fill=True, fill_opacity=0.7,
                            tooltip=f"{a['tipo']} · {a['categoria']}").add_to(fg_a)
    fg_a.add_to(m)

    fg_r = folium.FeatureGroup(name=f"Top {top} elementos a priorizar", show=True)
    for i, r in ranking.head(top).iterrows():
        col = {"apoyo": "#e74c3c", "aerogenerador": "#8e44ad", "linea": "#d35400"}[r.tipo]
        popup = (f"<b>#{i + 1} · {r.tipo}</b> ({r.mecanismo})<br>"
                 f"Riesgo máx.: {r.riesgo_max:.0f} / 100 · medio: {r.riesgo_medio:.0f}<br>"
                 f"Mes pico: {r.mes_pico}<br>Especies: {escape(str(r.especies))}<br>"
                 f"{escape(str(r.categoria))} {('· ' + str(r.voltaje / 1000) + ' kV') if r.voltaje == r.voltaje and r.voltaje else ''}<br>"
                 f"<a href='{r.osm_url}' target='_blank'>Ver en OSM</a>")
        folium.CircleMarker((r.lat, r.lon), radius=4 + 6 * r.riesgo_max / 100, color=col, weight=2,
                            fill=True, fill_opacity=0.5, popup=folium.Popup(popup, max_width=320),
                            tooltip=f"#{i + 1} {r.tipo} · {r.riesgo_max:.0f}").add_to(fg_r)
    fg_r.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    leyenda = f"""
    <div style="position: fixed; bottom: 30px; left: 10px; z-index: 9999; background: white; padding: 10px 12px;
                border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.3); font: 12px sans-serif; max-width: 260px">
      <b>{escape(region_nombre)}</b><br>Índice de riesgo 0-100 (percentil 99 = 100)<br>
      <div style="background: linear-gradient(to right, #000004, #3b0f70, #8c2981, #de4968, #fe9f6d, #fcfdbf);
                  height: 10px; margin: 4px 0"></div>
      <span style="float:left">bajo</span><span style="float:right">alto</span><br>
      <span style="color:#e67e22">▬</span> distribución ≤66 kV &nbsp;
      <span style="color:#c0392b">▬</span> transporte &nbsp; <span style="color:#7f8c8d">▬</span> desconocida<br>
      <span style="color:#2c3e50">●</span> aerogenerador &nbsp; <span style="color:#e74c3c">◯</span> elemento priorizado
    </div>"""
    m.get_root().html.add_child(folium.Element(leyenda))
    return m


def _tabla_html(df, fmt="{:.0f}"):
    out = ["<table><thead><tr><th></th>" + "".join(f"<th>{c}</th>" for c in df.columns) + "</tr></thead><tbody>"]
    for idx, row in df.iterrows():
        celdas = "".join(f"<td style='background: rgba(222,73,104,{min(v, 100) / 130:.2f})'>{fmt.format(v)}</td>"
                         for v in row.values)
        out.append(f"<tr><th>{escape(str(idx))}</th>{celdas}</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def informe(path, mapa_rel, region_nombre, bbox, resumen_infra, especies_info, tabla, ranking, top=50):
    filas = []
    for i, r in ranking.head(top).iterrows():
        kv = f"{r.voltaje / 1000:g} kV" if r.voltaje == r.voltaje and r.voltaje else ""
        filas.append(f"<tr><td>{i + 1}</td><td>{r.tipo}</td><td>{r.mecanismo}</td><td>{r.riesgo_max:.0f}</td>"
                     f"<td>{r.riesgo_medio:.0f}</td><td>{r.mes_pico}</td><td>{escape(str(r.especies))}</td>"
                     f"<td>{escape(str(r.categoria))} {kv}</td><td>{escape(str(r.operador or ''))}</td>"
                     f"<td><a href='{r.osm_url}' target='_blank'>{r.osm_id}</a></td></tr>")
    sp_rows = "".join(
        f"<tr><td><i>{sp}</i></td><td>{info['nombre']}</td><td>{info['citas_gbif']}</td><td>{info['posiciones_movebank']}</td>"
        f"<td>{info.get('confianza', '')}</td><td>{'sí' if info['incluida'] else 'no (pocas citas)'}</td></tr>"
        for sp, info in especies_info.items())
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Riesgo de colisión y electrocución · {escape(region_nombre)}</title>
<style>
 body{{font:14px/1.45 system-ui,sans-serif;margin:0;color:#222;background:#fff;color-scheme:light}} main{{max-width:1200px;margin:0 auto;padding:16px 24px}}
 h1{{font-size:22px;margin:.2em 0}} h2{{font-size:17px;margin:1.6em 0 .5em;border-bottom:1px solid #ddd}}
 table{{border-collapse:collapse;font-size:12.5px;width:100%}} th,td{{border:1px solid #e3e3e3;padding:3px 6px;text-align:left}}
 th{{background:#f5f5f5}} iframe{{width:100%;height:640px;border:1px solid #ccc}} .meta{{color:#666}}
 .wrap{{overflow-x:auto}} code{{background:#f3f3f3;padding:0 3px}}
</style></head><body><main>
<h1>Mapa dinámico de riesgo de colisión y electrocución de aves</h1>
<p class="meta">{escape(region_nombre)} · bbox {bbox} · generado el {date.today().isoformat()} ·
 fuentes: OpenStreetMap (ODbL), GBIF/eBird, Movebank Data Repository, AWS Terrain Tiles</p>
<iframe src="{mapa_rel}" loading="lazy"></iframe>
<p>Activa una capa mensual en el control de capas del mapa para ver la estacionalidad. Los círculos son los
 elementos con mayor prioridad de corrección (apoyos, aerogeneradores y tramos).</p>

<h2>Infraestructura en la zona (OSM)</h2>
<ul>
 <li>Líneas: {resumen_infra['lineas']} tramos · km por categoría: {escape(json.dumps(resumen_infra['km_por_categoria'], ensure_ascii=False))}</li>
 <li>Apoyos mapeados: {resumen_infra['apoyos']} (de distribución ≤66 kV: {resumen_infra['apoyos_distribucion']};
  con atributos de peligrosidad en OSM: {resumen_infra.get('apoyos_con_atributos', 0)})</li>
 <li>Aerogeneradores: {resumen_infra['aerogeneradores']}</li>
</ul>

<h2>Especies</h2>
<div class="wrap"><table><thead><tr><th>Especie</th><th>Nombre</th><th>Citas GBIF</th><th>Posiciones GPS Movebank</th><th>Confianza (peso en el agregado)</th><th>Incluida</th></tr></thead>
<tbody>{sp_rows}</tbody></table></div>

<h2>Estacionalidad del riesgo (índice medio sobre celdas con infraestructura)</h2>
<div class="wrap">{_tabla_html(tabla)}</div>

<h2>Top {top} elementos a priorizar</h2>
<div class="wrap"><table><thead><tr><th>#</th><th>Tipo</th><th>Mecanismo</th><th>Riesgo máx.</th><th>Medio</th><th>Mes pico</th>
<th>Especies</th><th>Categoría</th><th>Operador</th><th>OSM</th></tr></thead><tbody>{''.join(filas)}</tbody></table></div>
<p>Ranking completo en <code>ranking_elementos.csv</code> y <code>ranking_elementos.geojson</code>; rásteres mensuales en <code>riesgo_total.tif</code>.</p>

<h2>Método y limitaciones</h2>
<ul>
 <li><b>Presencia</b>: frecuencia relativa mensual = densidad de citas de la especie / densidad de citas de todas las aves
  (esfuerzo), suavizada (σ = {config.KDE_SIGMA_M} m con ≥{config.KDE_N_REF} citas en el mes, más ancha con menos).
  Las citas repetidas en el mismo punto, mes y año pesan √n. Datos GBIF desde {config.GBIF_YEAR_FROM}, incluyendo eBird.
  Si hay seguimiento GPS (Movebank) se mezcla con individuos-día por celda con peso hasta el
  {int(config.PESO_MOVEBANK * 100)} %, proporcional al nº de posiciones (pleno desde {config.MOVEBANK_N_REF}).
  Si hay GeoTIFF de eBird Status &amp; Trends en data/ebirdst/ pesan el {int(config.PESO_EBIRDST * 100)} % frente a las citas.
  En el índice agregado cada especie pesa estatus × confianza, con confianza = max(min(1, citas/{config.CITAS_CONFIANZA}),
  min(1, posiciones GPS/{config.MOVEBANK_N_REF})), o 1 con modelo eBird: una especie con pocas citas tiene un mapa poco
  fiable y no debe dominar el ranking.</li>
 <li><b>Exposición</b>: km de línea, apoyos de distribución (≤{config.ELECTROCUCION_MAX_V // 1000} kV, ámbito del RD 1432/2008)
  y aerogeneradores por celda de {config.GRID_RES_DEG}°. Donde OSM no tiene los apoyos se estiman {6} por km de línea de
  distribución; tope de {config.APOYOS_MAX_CELDA} apoyos por celda (más es una subestación). Cada apoyo pesa un factor
  de peligrosidad 0,5-2 derivado de sus etiquetas OSM (material, tipo de aislador, derivaciones, diseño de cruceta;
  criterios del RD 1432/2008), 1,0 si no tiene etiquetas; ese factor también escala su puesto en el ranking.</li>
 <li><b>Topografía</b>: pendiente (colisión con conductores) y posición topográfica a {config.TPI_RADIO_M} m (crestas, aerogeneradores).</li>
 <li><b>Pesos por especie</b> (electrocución / colisión con líneas / colisión con aerogeneradores / estatus) definidos en
  <code>riesgo/config.py</code>, a partir de la bibliografía. Son un punto de partida, no un ajuste con datos de mortalidad.</li>
 <li>El índice es relativo: 100 = percentil 99 de las celdas con infraestructura de la región; los valores por encima de 100
  son el 1 % más alto y conservan su orden para el ranking. No es una probabilidad de mortalidad. La cobertura de OSM es
  incompleta, sobre todo en apoyos y voltajes; los datos de citas tienen sesgo de observador aunque se corrija por esfuerzo.</li>
</ul>
</main></body></html>"""
    path.write_text(html, encoding="utf-8")


def exportar_geotiff(path, arr3d, grid, nombres=None):
    import rasterio

    with rasterio.open(path, "w", driver="GTiff", height=grid.ny, width=grid.nx, count=arr3d.shape[0],
                       dtype="float32", crs="EPSG:4326", transform=grid.transform(), compress="deflate") as dst:
        for i in range(arr3d.shape[0]):
            dst.write(arr3d[i].astype("float32"), i + 1)
            if nombres:
                dst.set_band_description(i + 1, nombres[i])


def exportar_geojson(path, ranking, top=None):
    df = ranking if top is None else ranking.head(top)
    feats = []
    for i, r in df.iterrows():
        props = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items() if k not in ("lat", "lon")}
        props["rank"] = int(i) + 1
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]}, "properties": props})
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, default=str), encoding="utf-8")
