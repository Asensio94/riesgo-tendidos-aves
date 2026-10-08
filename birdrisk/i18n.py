"""Display strings for the two published languages (Spanish and English).

Everything that reaches a human eye goes through this module; everything that reaches a file (GeoTIFF band names,
CSV columns and values, GeoJSON properties) stays in the canonical English form defined in `config` and `risk`,
so the data products are language-independent and the HTML pages are generated once per language.
"""
from html import escape

from . import config

DEFAULT_LANG = "es"

# Localised month labels; the canonical ones (config.MONTHS) are used in the data files.
MONTH_LABELS = {
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    "en": config.MONTHS,
}

# Canonical value -> label, for the columns the ranking writes to disk.
ELEMENT_TYPES = {
    "es": {"pylon": "apoyo", "turbine": "aerogenerador", "line": "línea"},
    "en": {"pylon": "pylon", "turbine": "wind turbine", "line": "power line"},
}
ELEMENT_TYPES_PLURAL = {
    "es": {"pylon": "apoyos", "turbine": "aerogeneradores", "line": "líneas"},
    "en": {"pylon": "pylons", "turbine": "wind turbines", "line": "power lines"},
}
MECHANISMS = {
    "es": {"electrocution": "electrocución", "line_collision": "colisión con línea",
           "turbine_collision": "colisión con aerogenerador"},
    "en": {"electrocution": "electrocution", "line_collision": "line collision",
           "turbine_collision": "turbine collision"},
}
CATEGORIES = {
    "es": {"distribution": "distribución", "transmission": "transporte", "unknown": "desconocida", "wind": "eólico"},
    "en": {"distribution": "distribution", "transmission": "transmission", "unknown": "unknown", "wind": "wind"},
}

UI = {
    "es": {
        "html_lang": "es",
        "lang_name": "Español",
        "other_lang_name": "English",
        # ---- interactive map
        "tile_terrain": "Relieve (OpenTopoMap)",
        "tile_satellite": "Satélite",
        "layer_total_annual": "Riesgo total · máximo anual",
        "layer_total_month": "Riesgo total · {month}",
        "layer_electro": "Electrocución (máx. anual)",
        "layer_col_lin": "Colisión con líneas (máx. anual)",
        "layer_col_aer": "Colisión con aerogeneradores (máx. anual)",
        "layer_species": "Especie · {name}",
        "layer_lines": "Líneas eléctricas (OSM)",
        "layer_turbines": "Aerogeneradores (OSM)",
        "layer_pylons": "Apoyos de distribución (OSM){note}",
        "layer_pylons_note": " · {n} de mayor índice",
        "layer_ranking": "Top {top} elementos a priorizar",
        "tooltip_category": "Categoría",
        "tooltip_voltage": "Tensión",
        "tooltip_name": "Nombre",
        "voltage_unknown": "desconocida",
        "tooltip_turbine": "aerogenerador {power}",
        "popup_index": "Índice máx.: {max:.0f} · medio: {mean:.0f} (percentil 99 de la región = 100)",
        "popup_peak_month": "Mes pico",
        "popup_species": "Especies",
        "popup_osm": "Ver en OSM",
        "legend_index": "Índice de riesgo 0-100 (percentil 99 = 100)",
        "legend_low": "bajo",
        "legend_high": "alto",
        "legend_distribution": "distribución ≤66 kV",
        "legend_transmission": "transporte",
        "legend_unknown": "desconocida",
        "legend_turbine": "aerogenerador",
        "legend_priority": "elemento priorizado",
        # ---- report
        "report_title": "Riesgo de colisión y electrocución · {region}",
        "site_title": "Mapa dinámico de riesgo de colisión y electrocución de aves",
        "report_meta": "{region} · bbox {bbox} · generado el {date} · fuentes: OpenStreetMap (ODbL), GBIF/eBird, "
                       "Movebank Data Repository, AWS Terrain Tiles",
        "report_intro": "Activa una capa mensual en el control de capas del mapa para ver la estacionalidad. "
                        "Los círculos son los elementos con mayor prioridad de corrección (apoyos, aerogeneradores "
                        "y tramos de línea).",
        "h2_infra": "Infraestructura en la zona (OSM)",
        "infra_lines": "Líneas: {n} tramos · km por categoría: {km}",
        "infra_pylons": "Apoyos mapeados: {n} (de distribución ≤66 kV: {dist}; con atributos de peligrosidad "
                        "en OSM: {tagged})",
        "infra_turbines": "Aerogeneradores: {n}",
        "h2_species": "Especies",
        "th_species": "Especie",
        "th_common_name": "Nombre",
        "th_gbif": "Citas GBIF",
        "th_movebank": "Posiciones GPS Movebank",
        "th_confidence": "Confianza (peso en el agregado)",
        "th_included": "Incluida",
        "yes": "sí",
        "no_few_records": "no (pocas citas)",
        "h2_seasonality": "Estacionalidad del riesgo (índice medio sobre celdas con infraestructura)",
        "row_total": "TOTAL",
        "h2_ranking": "Top {top} elementos a priorizar",
        "th_rank": "#",
        "th_type": "Tipo",
        "th_mechanism": "Mecanismo",
        "th_risk_max": "Riesgo máx.",
        "th_risk_mean": "Medio",
        "th_peak_month": "Mes pico",
        "th_species_list": "Especies",
        "th_category": "Categoría",
        "th_operator": "Operador",
        "th_osm": "OSM",
        "ranking_files": "Ranking completo en <code>ranking_elements.csv</code> y "
                         "<code>ranking_elements.geojson</code>; rásteres mensuales en <code>risk_total.tif</code>.",
        "back_to_regions": "Todas las regiones",
        # ---- regions index
        "regions_intro": "Índice relativo (0-100, percentil 99 = 100) por celda de ~500 m, especie y mes, a partir de "
                         "OpenStreetMap, GBIF/eBird, Movebank y topografía. Sirve para priorizar qué apoyos, tramos y "
                         "aerogeneradores corregir primero, no para certificar mortalidad. Se regenera el día 2 de "
                         "cada mes.",
        "regions_project_link": "Presentación del proyecto",
        "regions_code_link": "código y método",
        "regions_updated": "actualizado el {date}",
        "link_report": "Informe",
        "link_map": "Mapa interactivo",
        "link_ranking_csv": "Ranking CSV",
        "link_geojson": "GeoJSON",
        "link_geotiff": "GeoTIFF",
        "regions_scored": "{n} elementos puntuados: {breakdown}",
        "regions_empty": "No hay regiones calculadas todavía.",
        "generated_on": "Generado el {date}.",
        # ---- shared page skeleton (header, method, footer)
        "h1_html": "Riesgo de <span>tendidos</span> para aves",
        "report_lede": "Índice de riesgo de colisión y electrocución de aves en {region}, por celda de ~500 m, especie "
                       "y mes, a partir de OpenStreetMap, GBIF/eBird, Movebank y el relieve.",
        "fig_regions": "regiones calculadas",
        "fig_elements": "elementos puntuados",
        "fig_line_segments": "tramos de línea",
        "fig_pylons": "apoyos mapeados",
        "fig_turbines": "aerogeneradores",
        "fig_species": "especies incluidas",
        "method_title": "Cómo se calcula",
        "method_params": "Parámetros",
        "method_validation": "Validación",
        "method_limits": "Límites",
        "principle": "Datos públicos, reglas a la vista y cada cifra enlazada a su fuente. Indicios, no veredictos.",
        "siblings_label": "Proyectos hermanos",
        "footer_sources": "Datos: © colaboradores de <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> "
                          "(ODbL) · <a href=\"https://www.gbif.org/\">GBIF</a> y eBird (según la licencia de cada "
                          "dataset) · <a href=\"https://datarepository.movebank.org/\">Movebank Data Repository</a> "
                          "(CC0/CC BY) · AWS Terrain Tiles. Pesos por especie: Bevanger (1998), Janss (2000), Lehman et "
                          "al. (2007), Marques et al. (2014) y RD 1432/2008. El índice es una herramienta de "
                          "priorización, no una medida de mortalidad. Código bajo licencia MIT en "
                          "<a href=\"{repo}\">GitHub</a>.",
    },
    "en": {
        "html_lang": "en",
        "lang_name": "English",
        "other_lang_name": "Español",
        # ---- interactive map
        "tile_terrain": "Terrain (OpenTopoMap)",
        "tile_satellite": "Satellite",
        "layer_total_annual": "Total risk · annual maximum",
        "layer_total_month": "Total risk · {month}",
        "layer_electro": "Electrocution (annual max.)",
        "layer_col_lin": "Line collision (annual max.)",
        "layer_col_aer": "Turbine collision (annual max.)",
        "layer_species": "Species · {name}",
        "layer_lines": "Power lines (OSM)",
        "layer_turbines": "Wind turbines (OSM)",
        "layer_pylons": "Distribution pylons (OSM){note}",
        "layer_pylons_note": " · top {n} by index",
        "layer_ranking": "Top {top} elements to prioritise",
        "tooltip_category": "Category",
        "tooltip_voltage": "Voltage",
        "tooltip_name": "Name",
        "voltage_unknown": "unknown",
        "tooltip_turbine": "wind turbine {power}",
        "popup_index": "Index max.: {max:.0f} · mean: {mean:.0f} (99th percentile of the region = 100)",
        "popup_peak_month": "Peak month",
        "popup_species": "Species",
        "popup_osm": "View on OSM",
        "legend_index": "Risk index 0-100 (99th percentile = 100)",
        "legend_low": "low",
        "legend_high": "high",
        "legend_distribution": "distribution ≤66 kV",
        "legend_transmission": "transmission",
        "legend_unknown": "unknown",
        "legend_turbine": "wind turbine",
        "legend_priority": "prioritised element",
        # ---- report
        "report_title": "Collision and electrocution risk · {region}",
        "site_title": "Dynamic collision and electrocution risk map for birds",
        "report_meta": "{region} · bbox {bbox} · generated on {date} · sources: OpenStreetMap (ODbL), GBIF/eBird, "
                       "Movebank Data Repository, AWS Terrain Tiles",
        "report_intro": "Switch on a monthly layer in the map's layer control to see the seasonality. The circles are "
                        "the elements with the highest correction priority (pylons, wind turbines and line segments).",
        "h2_infra": "Infrastructure in the area (OSM)",
        "infra_lines": "Power lines: {n} segments · km by category: {km}",
        "infra_pylons": "Mapped pylons: {n} (distribution ≤66 kV: {dist}; with hazard attributes in OSM: {tagged})",
        "infra_turbines": "Wind turbines: {n}",
        "h2_species": "Species",
        "th_species": "Species",
        "th_common_name": "Common name",
        "th_gbif": "GBIF records",
        "th_movebank": "Movebank GPS fixes",
        "th_confidence": "Confidence (weight in the aggregate)",
        "th_included": "Included",
        "yes": "yes",
        "no_few_records": "no (too few records)",
        "h2_seasonality": "Seasonality of the risk (mean index over cells with infrastructure)",
        "row_total": "TOTAL",
        "h2_ranking": "Top {top} elements to prioritise",
        "th_rank": "#",
        "th_type": "Type",
        "th_mechanism": "Mechanism",
        "th_risk_max": "Risk max.",
        "th_risk_mean": "Mean",
        "th_peak_month": "Peak month",
        "th_species_list": "Species",
        "th_category": "Category",
        "th_operator": "Operator",
        "th_osm": "OSM",
        "ranking_files": "Full ranking in <code>ranking_elements.csv</code> and "
                         "<code>ranking_elements.geojson</code>; monthly rasters in <code>risk_total.tif</code>.",
        "back_to_regions": "All regions",
        # ---- regions index
        "regions_intro": "Relative index (0-100, 99th percentile = 100) per ~500 m cell, species and month, built from "
                         "OpenStreetMap, GBIF/eBird, Movebank and terrain data. It ranks which pylons, line segments "
                         "and wind turbines to fix first; it does not certify mortality. Rebuilt on the 2nd of every "
                         "month.",
        "regions_project_link": "Project overview",
        "regions_code_link": "code and method",
        "regions_updated": "updated on {date}",
        "link_report": "Report",
        "link_map": "Interactive map",
        "link_ranking_csv": "Ranking CSV",
        "link_geojson": "GeoJSON",
        "link_geotiff": "GeoTIFF",
        "regions_scored": "{n} elements scored: {breakdown}",
        "regions_empty": "No regions computed yet.",
        "generated_on": "Generated on {date}.",
        # ---- shared page skeleton (header, method, footer)
        "h1_html": "<span>Power-line</span> risk for birds",
        "report_lede": "Collision and electrocution risk index for birds in {region}, per ~500 m cell, species and "
                       "month, built from OpenStreetMap, GBIF/eBird, Movebank and terrain data.",
        "fig_regions": "regions computed",
        "fig_elements": "elements scored",
        "fig_line_segments": "line segments",
        "fig_pylons": "mapped pylons",
        "fig_turbines": "wind turbines",
        "fig_species": "species included",
        "method_title": "How it is computed",
        "method_params": "Parameters",
        "method_validation": "Validation",
        "method_limits": "Limits",
        "principle": "Public data, rules in plain sight and every figure linked to its source. Leads, not verdicts.",
        "siblings_label": "Sibling projects",
        "footer_sources": "Data: © <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors "
                          "(ODbL) · <a href=\"https://www.gbif.org/\">GBIF</a> and eBird (under each dataset's "
                          "licence) · <a href=\"https://datarepository.movebank.org/\">Movebank Data Repository</a> "
                          "(CC0/CC BY) · AWS Terrain Tiles. Species weights: Bevanger (1998), Janss (2000), Lehman et "
                          "al. (2007), Marques et al. (2014) and Spanish Royal Decree 1432/2008. The index is a "
                          "prioritisation tool, not a measure of mortality. Code under the MIT licence on "
                          "<a href=\"{repo}\">GitHub</a>.",
    },
}


def t(lang, key, **kwargs):
    """Localised string; unknown languages fall back to the default one."""
    table = UI.get(lang) or UI[DEFAULT_LANG]
    text = table.get(key) or UI[DEFAULT_LANG].get(key, key)
    return text.format(**kwargs) if kwargs else text


def month_label(index, lang):
    """Label of month `index` (0-11) in the requested language."""
    return MONTH_LABELS.get(lang, MONTH_LABELS[DEFAULT_LANG])[index]


def month_label_from_canonical(name, lang):
    """Translate a canonical month name ('Jan') as written in the data files."""
    try:
        return month_label(config.MONTHS.index(name), lang)
    except (ValueError, TypeError):
        return name


def element_type(value, lang):
    return ELEMENT_TYPES.get(lang, ELEMENT_TYPES[DEFAULT_LANG]).get(value, value)


def element_type_plural(value, lang):
    return ELEMENT_TYPES_PLURAL.get(lang, ELEMENT_TYPES_PLURAL[DEFAULT_LANG]).get(value, value)


def mechanism(value, lang):
    return MECHANISMS.get(lang, MECHANISMS[DEFAULT_LANG]).get(value, value)


def category(value, lang):
    return CATEGORIES.get(lang, CATEGORIES[DEFAULT_LANG]).get(value, value)


def species_list(value, lang):
    """Translate a comma-separated list of scientific names into common names."""
    if not value or value != value:  # NaN-safe
        return ""
    return ", ".join(config.species_name(s.strip(), lang) for s in str(value).split(",") if s.strip())


def num(value, lang):
    """Number with the thousands and decimal separators of `lang` (Spanish: 20.000 and 0,005)."""
    text = f"{value:,}"
    return text.translate(str.maketrans(",.", ".,")) if lang == "es" else text


def method_params(lang):
    """(label, value) rows of the parameters table, read from the live configuration."""
    c = config

    def n(v):
        return num(v, lang)

    if lang == "en":
        return [
            ("Grid cell", f"{n(c.GRID_RES_DEG)}°"),
            ("Maximum distribution voltage", f"{c.ELECTROCUTION_MAX_V // 1000} kV"),
            ("Pylons assumed where none are mapped", "6 per km"),
            ("Pylon cap per cell", n(c.PYLONS_MAX_PER_CELL)),
            ("Record smoothing (σ)", f"{n(c.KDE_SIGMA_M)} m with ≥{n(c.KDE_N_REF)} records in the month"),
            ("GBIF records", f"from {c.GBIF_YEAR_FROM}, up to {n(c.GBIF_MAX_RECORDS)} per species"),
            ("Minimum records to include a species", n(c.MIN_RECORDS_PER_SPECIES)),
            ("Full confidence", f"{n(c.RECORDS_FOR_CONFIDENCE)} records or {n(c.MOVEBANK_N_REF)} GPS fixes"),
            ("Maximum GPS weight (Movebank)", f"{int(c.MOVEBANK_WEIGHT * 100)}%"),
            ("eBird Status & Trends weight", f"{int(c.EBIRDST_WEIGHT * 100)}%"),
            ("Slope at which line collision doubles", "25°"),
            ("Topographic position radius", f"{n(c.TPI_RADIUS_M)} m"),
            ("Scale", "99th percentile = 100"),
        ]
    return [
        ("Celda de la malla", f"{n(c.GRID_RES_DEG)}°"),
        ("Tensión máxima de distribución", f"{c.ELECTROCUTION_MAX_V // 1000} kV"),
        ("Apoyos estimados donde no hay mapeados", "6 por km"),
        ("Tope de apoyos por celda", n(c.PYLONS_MAX_PER_CELL)),
        ("Suavizado de las citas (σ)", f"{n(c.KDE_SIGMA_M)} m con ≥{n(c.KDE_N_REF)} citas en el mes"),
        ("Citas GBIF", f"desde {c.GBIF_YEAR_FROM}, hasta {n(c.GBIF_MAX_RECORDS)} por especie"),
        ("Citas mínimas para incluir una especie", n(c.MIN_RECORDS_PER_SPECIES)),
        ("Confianza plena", f"{n(c.RECORDS_FOR_CONFIDENCE)} citas o {n(c.MOVEBANK_N_REF)} posiciones GPS"),
        ("Peso máximo del GPS (Movebank)", f"{int(c.MOVEBANK_WEIGHT * 100)} %"),
        ("Peso de eBird Status & Trends", f"{int(c.EBIRDST_WEIGHT * 100)} %"),
        ("Pendiente que duplica la colisión con líneas", "25°"),
        ("Radio de la posición topográfica", f"{n(c.TPI_RADIUS_M)} m"),
        ("Escala", "percentil 99 = 100"),
    ]


def method_html(lang):
    """Body of the 'How it is computed' section (steps, parameters, validation, limits), quoting the live
    configuration values. The caller wraps it in <section class="method"> with its <h2>."""
    c = config

    def n(v):
        return num(v, lang)

    params = "".join(f'<tr><th>{escape(k)}</th><td class="num">{escape(v)}</td></tr>' for k, v in method_params(lang))
    middle = (f"<h3>{t(lang, 'method_params')}</h3>\n<table class=\"params\"><tbody>{params}</tbody></table>\n"
              f"<h3>{t(lang, 'method_validation')}</h3>\n")
    limits = f"<h3>{t(lang, 'method_limits')}</h3>\n"
    if lang == "en":
        return f"""<ol>
 <li><b>Infrastructure.</b> Power lines, pylons and wind turbines are downloaded from OpenStreetMap (Overpass). Lines
  up to {c.ELECTROCUTION_MAX_V // 1000} kV are distribution (electrocution risk, the scope of Spanish Royal Decree
  1432/2008); above that they only count for collision. Pylons inherit the voltage of their line. Each
  {n(c.GRID_RES_DEG)}° cell gets km of line, distribution pylons and wind turbines. Where OSM has no pylons mapped,
  6 per km of distribution line are assumed; the count is capped at {c.PYLONS_MAX_PER_CELL} pylons per cell (more
  than that is a substation).</li>
 <li><b>Pylon hazard.</b> Each pylon carries a hazard factor of 0.5-2 derived from its OSM tags (material, insulator
  type, branch connections, cross-arm design; criteria of Royal Decree 1432/2008), or 1.0 when it has no tags; that
  factor also scales its position in the ranking.</li>
 <li><b>Presence.</b> Monthly relative frequency = density of records of the species / density of records of all
  birds (sampling effort), smoothed (σ = {n(c.KDE_SIGMA_M)} m with at least {c.KDE_N_REF} records in the month,
  wider with fewer). Records repeated at the same spot, month and year are weighted by the square root of their
  count. GBIF data from {c.GBIF_YEAR_FROM} onwards, eBird included. Where GPS tracking (Movebank) is available it
  is blended in as individual-days per cell with a weight of up to {int(c.MOVEBANK_WEIGHT * 100)}%, proportional
  to the number of fixes (full weight from {n(c.MOVEBANK_N_REF)} on). Where eBird Status &amp; Trends GeoTIFFs are
  present in data/ebirdst/ they carry {int(c.EBIRDST_WEIGHT * 100)}% against the GBIF frequency.</li>
 <li><b>Terrain.</b> Slope (collision with conductors) and topographic position at {n(c.TPI_RADIUS_M)} m (ridges,
  wind turbines).</li>
 <li><b>Species weights</b> (electrocution / line collision / turbine collision / conservation status) are defined
  in <code>birdrisk/config.py</code>, drawn from the literature. They are a starting point, not a fit to mortality
  data. In the aggregate index each species is weighted by status x confidence, with confidence =
  max(min(1, records/{c.RECORDS_FOR_CONFIDENCE}), min(1, GPS fixes/{c.MOVEBANK_N_REF})), or 1 with an eBird model:
  a species with few records has an unreliable map and must not dominate the ranking.</li>
 <li><b>Index and ranking.</b> Per species, month and cell: electrocution = presence x weight x equivalent pylons;
  line collision = presence x weight x km of line x (1 + relief); turbine collision = presence x weight x turbines x
  (1 + ridge). Each index is rescaled so that the 99th percentile of the cells with infrastructure in the region is
  100, without clipping the maxima. Each pylon takes the electrocution index of its cell times its hazard factor;
  each line segment, the mean along its route; each wind turbine, the index of its cell. The peak month and the
  species that contribute most are kept.</li>
</ol>
{middle}<p>Pending. The ranking has not yet been checked against real mortality: there is no open dataset of
 electrocuted or collided birds in Spain. The first planned check is against the Basque Government's shapefile of
 hazardous power lines (region <code>euskadi</code>); once mortality points are available, the species weights will
 be fitted with a logistic regression.</p>
{limits}<ul>
 <li>The index is relative: 100 is the 99th percentile of the cells with infrastructure in the region, and values
  above 100 are the top 1% and keep their order for the ranking. It is not a probability of mortality: it is meant
  for prioritising, not for certifying.</li>
 <li>OSM coverage is incomplete, especially for pylons and voltages.</li>
 <li>The occurrence data carry observer bias (roads, viewpoints, hotspots) even after the effort correction, and
  carry no flight height; only some GPS datasets do.</li>
</ul>"""
    return f"""<ol>
 <li><b>Infraestructura.</b> Se descargan de OpenStreetMap (Overpass) las líneas, los apoyos y los aerogeneradores.
  Las líneas de hasta {c.ELECTROCUTION_MAX_V // 1000} kV son de distribución (riesgo de electrocución, ámbito del
  RD 1432/2008); por encima solo cuentan para la colisión. Los apoyos heredan la tensión de su línea. Cada celda de
  {n(c.GRID_RES_DEG)}° recibe km de línea, apoyos de distribución y aerogeneradores. Donde OSM no tiene los apoyos se
  estiman 6 por km de línea de distribución; tope de {c.PYLONS_MAX_PER_CELL} apoyos por celda (más es una
  subestación).</li>
 <li><b>Peligrosidad de cada apoyo.</b> Un factor 0,5-2 derivado de sus etiquetas OSM (material, tipo de aislador,
  derivaciones, diseño de cruceta; criterios del RD 1432/2008), 1,0 si no tiene etiquetas; ese factor también escala
  su puesto en el ranking.</li>
 <li><b>Presencia.</b> Frecuencia relativa mensual = densidad de citas de la especie / densidad de citas de todas
  las aves (esfuerzo), suavizada (σ = {n(c.KDE_SIGMA_M)} m con ≥{c.KDE_N_REF} citas en el mes, más ancha con menos).
  Las citas repetidas en el mismo punto, mes y año pesan √n. Datos GBIF desde {c.GBIF_YEAR_FROM}, incluyendo eBird.
  Si hay seguimiento GPS (Movebank) se mezcla con individuos-día por celda con peso hasta el
  {int(c.MOVEBANK_WEIGHT * 100)} %, proporcional al nº de posiciones (pleno desde {n(c.MOVEBANK_N_REF)}).
  Si hay GeoTIFF de eBird Status &amp; Trends en data/ebirdst/ pesan el {int(c.EBIRDST_WEIGHT * 100)} % frente a
  las citas.</li>
 <li><b>Relieve.</b> Pendiente (colisión con conductores) y posición topográfica a {n(c.TPI_RADIUS_M)} m (crestas,
  aerogeneradores).</li>
 <li><b>Pesos por especie</b> (electrocución / colisión con líneas / colisión con aerogeneradores / estatus)
  definidos en <code>birdrisk/config.py</code>, a partir de la bibliografía. Son un punto de partida, no un ajuste
  con datos de mortalidad. En el índice agregado cada especie pesa estatus × confianza, con confianza =
  max(min(1, citas/{c.RECORDS_FOR_CONFIDENCE}), min(1, posiciones GPS/{c.MOVEBANK_N_REF})), o 1 con modelo eBird:
  una especie con pocas citas tiene un mapa poco fiable y no debe dominar el ranking.</li>
 <li><b>Índice y ranking.</b> Por especie, mes y celda: electrocución = presencia × peso × apoyos equivalentes;
  colisión con línea = presencia × peso × km de línea × (1 + relieve); colisión con aerogenerador = presencia ×
  peso × aerogeneradores × (1 + cresta). Cada índice se reescala para que el percentil 99 de las celdas con
  infraestructura de la región valga 100, sin recortar los máximos. Cada apoyo toma el índice de electrocución de su
  celda multiplicado por su peligrosidad; cada tramo, la media a lo largo de su recorrido; cada aerogenerador, el de
  su celda. Se guardan el mes pico y las especies que más aportan.</li>
</ol>
{middle}<p>Pendiente. El ranking aún no se ha contrastado con mortalidad real: no hay un dato abierto de aves
 electrocutadas o colisionadas en España. El primer contraste previsto es con el shapefile de tendidos peligrosos del
 Gobierno Vasco (región <code>euskadi</code>); cuando haya puntos de mortalidad, los pesos por especie se ajustarán con
 una regresión logística.</p>
{limits}<ul>
 <li>El índice es relativo: 100 = percentil 99 de las celdas con infraestructura de la región; los valores por
  encima de 100 son el 1 % más alto y conservan su orden para el ranking. No es una probabilidad de mortalidad: sirve
  para priorizar, no para certificar.</li>
 <li>La cobertura de OSM es incompleta, sobre todo en apoyos y voltajes.</li>
 <li>Las citas tienen sesgo de observador (carreteras, miradores, hotspots) aunque se corrija por esfuerzo, y no
  dicen a qué altura volaba el ave; solo algunos datasets GPS lo hacen.</li>
</ul>"""
