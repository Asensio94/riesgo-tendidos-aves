"""Display strings for the published languages: Spanish and English for Spain, French and English for France.

Everything that reaches a human eye goes through this module; everything that reaches a file (GeoTIFF band names,
CSV columns and values, GeoJSON properties) stays in the canonical English form defined in `config` and `risk`,
so the data products are language-independent and the HTML pages are generated once per language.

French follows the typography of the sibling project Vigilancia de humedales: a narrow no-break space (U+202F) as
thousands separator and before "%", ";", "!" and "?", and a no-break space before ":". The French strings are written
with plain spaces and `_fr_typography` fixes them once at import.
"""
import re
from html import escape

from . import config

DEFAULT_LANG = "es"

# Localised month labels; the canonical ones (config.MONTHS) are used in the data files.
MONTH_LABELS = {
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    "en": config.MONTHS,
    "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
}

# Full month names, for running text
MONTH_NAMES = {
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
}

# Canonical value -> label, for the columns the ranking writes to disk.
ELEMENT_TYPES = {
    "es": {"pylon": "apoyo", "turbine": "aerogenerador", "line": "línea"},
    "en": {"pylon": "pylon", "turbine": "wind turbine", "line": "power line"},
    "fr": {"pylon": "support", "turbine": "éolienne", "line": "ligne"},
}
ELEMENT_TYPES_PLURAL = {
    "es": {"pylon": "apoyos", "turbine": "aerogeneradores", "line": "líneas"},
    "en": {"pylon": "pylons", "turbine": "wind turbines", "line": "power lines"},
    "fr": {"pylon": "supports", "turbine": "éoliennes", "line": "lignes"},
}
MECHANISMS = {
    "es": {"electrocution": "electrocución", "line_collision": "colisión con línea",
           "turbine_collision": "colisión con aerogenerador"},
    "en": {"electrocution": "electrocution", "line_collision": "line collision",
           "turbine_collision": "turbine collision"},
    "fr": {"electrocution": "électrocution", "line_collision": "collision avec une ligne",
           "turbine_collision": "collision avec une éolienne"},
}
CATEGORIES = {
    "es": {"distribution": "distribución", "transmission": "transporte", "unknown": "desconocida", "wind": "eólico"},
    "en": {"distribution": "distribution", "transmission": "transmission", "unknown": "unknown", "wind": "wind"},
    "fr": {"distribution": "distribution", "transmission": "transport", "unknown": "inconnue", "wind": "éolien"},
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
        "th_why": "Por qué",
        "ranking_why": "La columna «Por qué» desglosa cada índice en los factores del modelo: cuántas aves hay y de qué"
                       " especies, cuánto tendido hay en la celda, el relieve y el tipo de apoyo. Los porcentajes "
                       "comparan con el resto de celdas de la región.",
        "th_category": "Categoría",
        "th_operator": "Operador",
        "th_osm": "OSM",
        "ranking_files": "Ranking completo en <code>ranking_elements.csv</code> y "
                         "<code>ranking_elements.geojson</code>; rásteres mensuales en <code>risk_total.tif</code>.",
        "back_to_regions": "Todas las regiones",
        # ---- one page per Natura 2000 site
        "site_page_title": "{site} · elementos de riesgo alto para las aves",
        "site_lede": "{n} elementos de riesgo alto para las aves dentro de {site} ({kind} {code}).",
        "site_rule": "Riesgo alto: el {share} % de los elementos de {region} con mayor índice máximo. Es el mismo "
                     "recuento que publica Estado de las IBA; un elemento dentro de dos espacios cuenta en los dos.",
        "site_full_map": "Mapa completo de {region}",
        "site_report": "Informe de {region}",
        "site_hub": "Este espacio en Estado de las IBA",
        "site_map_label": "Mapa de los elementos de riesgo alto en {site}",
        "site_h2_list": "Los {n} elementos, de más a menos riesgo",
        "site_in_table": "Ver en la tabla",
        # ---- regions index
        "regions_intro": "Índice relativo (100 = percentil 99: lo que pasa de 100 es el 1 % con más riesgo) por "
                         "celda de ~500 m, especie y mes, a partir de "
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
        "hub_label": "← Terra Aperta: todos los proyectos",
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
        "th_why": "Why",
        "ranking_why": "The “Why” column breaks each index down into the factors of the model: how many birds and of "
                       "which species, how much line there is in the cell, the terrain and the type of pylon. "
                       "Percentages compare with the other cells of the region.",
        "th_category": "Category",
        "th_operator": "Operator",
        "th_osm": "OSM",
        "ranking_files": "Full ranking in <code>ranking_elements.csv</code> and "
                         "<code>ranking_elements.geojson</code>; monthly rasters in <code>risk_total.tif</code>.",
        "back_to_regions": "All regions",
        # ---- one page per Natura 2000 site
        "site_page_title": "{site} · high-risk elements for birds",
        "site_lede": "{n} high-risk elements for birds inside {site} ({kind} {code}).",
        "site_rule": "High risk: the {share} % of the elements of {region} with the highest maximum index. It is the "
                     "same count Estado de las IBA publishes; an element inside two sites counts in both.",
        "site_full_map": "Full map of {region}",
        "site_report": "Report of {region}",
        "site_hub": "This site in Estado de las IBA",
        "site_map_label": "Map of the high-risk elements in {site}",
        "site_h2_list": "The {n} elements, from most to least risk",
        "site_in_table": "See in the table",
        # ---- regions index
        "regions_intro": "Relative index (100 = 99th percentile: anything above 100 is the riskiest 1%) per "
                         "~500 m cell, species and month, built from "
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
        "hub_label": "← Terra Aperta: all projects",
        "footer_sources": "Data: © <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors "
                          "(ODbL) · <a href=\"https://www.gbif.org/\">GBIF</a> and eBird (under each dataset's "
                          "licence) · <a href=\"https://datarepository.movebank.org/\">Movebank Data Repository</a> "
                          "(CC0/CC BY) · AWS Terrain Tiles. Species weights: Bevanger (1998), Janss (2000), Lehman et "
                          "al. (2007), Marques et al. (2014) and Spanish Royal Decree 1432/2008. The index is a "
                          "prioritisation tool, not a measure of mortality. Code under the MIT licence on "
                          "<a href=\"{repo}\">GitHub</a>.",
    },
}


UI["fr"] = {
    "html_lang": "fr",
    "lang_name": "Français",
    "other_lang_name": "English",
    # ---- interactive map
    "tile_terrain": "Relief (OpenTopoMap)",
    "tile_satellite": "Satellite",
    "layer_total_annual": "Risque total · maximum annuel",
    "layer_total_month": "Risque total · {month}",
    "layer_electro": "Électrocution (max. annuel)",
    "layer_col_lin": "Collision avec les lignes (max. annuel)",
    "layer_col_aer": "Collision avec les éoliennes (max. annuel)",
    "layer_species": "Espèce · {name}",
    "layer_lines": "Lignes électriques (OSM et Enedis)",
    "layer_turbines": "Éoliennes (OSM)",
    "layer_pylons": "Supports de distribution (Enedis et OSM){note}",
    "layer_pylons_note": " · les {n} d’indice le plus élevé",
    "layer_ranking": "Les {top} éléments prioritaires",
    "tooltip_category": "Catégorie",
    "tooltip_voltage": "Tension",
    "tooltip_name": "Nom",
    "voltage_unknown": "inconnue",
    "tooltip_turbine": "éolienne {power}",
    "popup_index": "Indice max. : {max:.0f} · moyen : {mean:.0f} (99e centile de la région = 100)",
    "popup_peak_month": "Mois de pointe",
    "popup_species": "Espèces",
    "popup_osm": "Voir sur OSM",
    "popup_enedis": "Jeu de données Enedis",
    "legend_index": "Indice de risque 0-100 (99e centile = 100)",
    "legend_low": "faible",
    "legend_high": "élevé",
    "legend_distribution": "distribution HTA ≤50 kV",
    "legend_transmission": "transport (RTE)",
    "legend_unknown": "inconnue",
    "legend_turbine": "éolienne",
    "legend_priority": "élément prioritaire",
    # ---- report
    "report_title": "Risque de collision et d’électrocution · {region}",
    "site_title": "Carte dynamique du risque de collision et d’électrocution des oiseaux",
    "report_meta": "{region} · bbox {bbox} · généré le {date} · sources : OpenStreetMap (ODbL), Enedis Open Data, "
                   "IGN Admin Express, GBIF/eBird, Movebank Data Repository, AWS Terrain Tiles",
    "report_intro": "Activez une couche mensuelle dans le sélecteur de couches de la carte pour voir la saisonnalité. "
                    "Les cercles sont les éléments à corriger en priorité (supports, éoliennes et tronçons de ligne).",
    "h2_infra": "Infrastructures de la zone (OSM et Enedis, territoire français)",
    "infra_lines": "Lignes : {n} tronçons · km par catégorie : {km}",
    "infra_pylons": "Supports : {n} (de distribution HTA ≤50 kV : {dist} ; avec des attributs de dangerosité "
                    "dans OSM : {tagged})",
    "infra_turbines": "Éoliennes : {n}",
    "h2_species": "Espèces",
    "th_species": "Espèce",
    "th_common_name": "Nom",
    "th_gbif": "Données GBIF",
    "th_movebank": "Positions GPS Movebank",
    "th_confidence": "Confiance (poids dans l’agrégat)",
    "th_included": "Incluse",
    "yes": "oui",
    "no_few_records": "non (trop peu de données)",
    "h2_seasonality": "Saisonnalité du risque (indice moyen des cellules avec infrastructures)",
    "row_total": "TOTAL",
    "h2_ranking": "Les {top} éléments prioritaires",
    "th_rank": "#",
    "th_type": "Type",
    "th_mechanism": "Mécanisme",
    "th_risk_max": "Risque max.",
    "th_risk_mean": "Moyen",
    "th_peak_month": "Mois de pointe",
    "th_species_list": "Espèces",
    "th_why": "Pourquoi",
    "ranking_why": "La colonne « Pourquoi » décompose chaque indice selon les facteurs du modèle : combien d’oiseaux et"
                   " de quelles espèces, combien de réseau dans la maille, le relief et le type de support. Les "
                   "pourcentages comparent avec les autres mailles de la région.",
    "th_category": "Catégorie",
    "th_operator": "Exploitant",
    "th_osm": "Source",
    "ranking_files": "Classement complet dans <code>ranking_elements.csv</code> et "
                     "<code>ranking_elements.geojson</code> ; rasters mensuels dans <code>risk_total.tif</code>.",
    "back_to_regions": "Toutes les régions",
    # ---- one page per Natura 2000 site
    "site_page_title": "{site} · éléments à risque élevé pour les oiseaux",
    "site_lede": "{n} éléments à risque élevé pour les oiseaux dans {site} ({kind} {code}).",
    "site_rule": "Risque élevé : les {share} % des éléments de la région {region} dont l’indice maximal est le plus "
                 "haut. C’est le décompte que publie Estado de las IBA ; un élément situé dans deux sites compte dans "
                 "les deux.",
    "site_full_map": "Carte complète : {region}",
    "site_report": "Rapport : {region}",
    "site_hub": "Ce site dans Estado de las IBA",
    "site_map_label": "Carte des éléments à risque élevé dans {site}",
    "site_h2_list": "Les {n} éléments, du risque le plus élevé au plus faible",
    "site_in_table": "Voir dans le tableau",
    # ---- regions index
    "regions_intro": "Indice relatif (100 = 99e centile : au-delà de 100, le 1 % le plus à risque) par "
                     "cellule d’environ 500 m, espèce et mois, établi à "
                     "partir d’OpenStreetMap, des données ouvertes d’Enedis, de GBIF/eBird, de Movebank et du relief. "
                     "Il sert à choisir quels supports, tronçons et éoliennes corriger en premier, pas à certifier une "
                     "mortalité. Mis à jour le 2 de chaque mois.",
    "regions_project_link": "Présentation du projet",
    "regions_code_link": "code et méthode",
    "regions_updated": "mis à jour le {date}",
    "link_report": "Rapport",
    "link_map": "Carte interactive",
    "link_ranking_csv": "Classement CSV",
    "link_geojson": "GeoJSON",
    "link_geotiff": "GeoTIFF",
    "regions_scored": "{n} éléments notés : {breakdown}",
    "regions_empty": "Aucune région calculée pour l’instant.",
    "generated_on": "Généré le {date}.",
    "country_ES": "Espagne",
    "country_FR": "France",
    # ---- shared page skeleton (header, method, footer)
    "h1_html": "Risque des <span>lignes</span> pour les oiseaux",
    "report_lede": "Indice de risque de collision et d’électrocution des oiseaux pour la région {region}, par cellule "
                   "d’environ 500 m, espèce et mois, établi à partir d’OpenStreetMap, d’Enedis, de GBIF/eBird, de "
                   "Movebank et du relief.",
    "fig_regions": "régions calculées",
    "fig_elements": "éléments notés",
    "fig_line_segments": "tronçons de ligne",
    "fig_pylons": "supports",
    "fig_turbines": "éoliennes",
    "fig_species": "espèces incluses",
    "method_title": "Comment c’est calculé",
    "method_params": "Paramètres",
    "method_validation": "Validation",
    "method_limits": "Limites",
    "method_left_out": "Ce qui reste en dehors, et pourquoi",
    "principle": "Données publiques, règles visibles et chaque chiffre relié à sa source. Des indices, pas des "
                 "verdicts.",
    "siblings_label": "Projets frères",
    "hub_label": "← Terra Aperta : tous les projets",
    "footer_sources": "Données : © contributeurs d’<a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap"
                      "</a> (ODbL) · <a href=\"https://data.enedis.fr/\">Enedis Open Data</a> (lignes HTA : Licence "
                      "Ouverte 2.0 ; supports : ODbL) · IGN Admin Express (Licence Ouverte 2.0) · Natura 2000 : Agence "
                      "européenne pour l’environnement · <a href=\"https://www.gbif.org/\">GBIF</a> et eBird (selon la "
                      "licence de chaque jeu de données) · <a href=\"https://datarepository.movebank.org/\">Movebank "
                      "Data Repository</a> (CC0/CC BY) · AWS Terrain Tiles. Statut : Liste rouge des oiseaux nicheurs "
                      "de France métropolitaine (UICN France, MNHN, LPO, SEOF, ONCFS, 2016). L’indice est un outil de "
                      "priorisation, pas une mesure de la mortalité. Code sous licence MIT sur "
                      "<a href=\"{repo}\">GitHub</a>.",
}
UI["es"].update({"popup_enedis": "Datos de Enedis", "country_ES": "España", "country_FR": "Francia",
                 "method_left_out": "Qué queda fuera y por qué"})
UI["en"].update({"popup_enedis": "Enedis dataset", "country_ES": "Spain", "country_FR": "France",
                 "method_left_out": "What is left out, and why"})

# Strings that change with the country of the page, by country and language. The French pages are only made for
# French regions, so UI["fr"] already speaks of France; the English pages of a French region take these instead.
COUNTRY_UI = {
    "FR": {
        "en": {
            "layer_lines": "Power lines (OSM and Enedis)",
            "layer_pylons": "Distribution pylons (Enedis and OSM){note}",
            "legend_distribution": "distribution (HTA) ≤50 kV",
            "legend_transmission": "transmission (RTE)",
            "report_meta": "{region} · bbox {bbox} · generated on {date} · sources: OpenStreetMap (ODbL), Enedis Open "
                           "Data, IGN Admin Express, GBIF/eBird, Movebank Data Repository, AWS Terrain Tiles",
            "h2_infra": "Infrastructure in the area (OSM and Enedis, French territory only)",
            "infra_pylons": "Pylons: {n} (distribution, HTA ≤50 kV: {dist}; with hazard attributes in OSM: {tagged})",
            "report_lede": "Collision and electrocution risk index for birds in {region}, per ~500 m cell, species and "
                           "month, built from OpenStreetMap, Enedis, GBIF/eBird, Movebank and terrain data.",
            "th_osm": "Source",
            "footer_sources": "Data: © <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> "
                              "contributors (ODbL) · <a href=\"https://data.enedis.fr/\">Enedis Open Data</a> (HTA "
                              "lines: Licence Ouverte 2.0; poles: ODbL) · IGN Admin Express (Licence Ouverte 2.0) · "
                              "Natura 2000: European Environment Agency · <a href=\"https://www.gbif.org/\">GBIF</a> "
                              "and eBird (under each dataset's licence) · <a href=\"https://datarepository.movebank."
                              "org/\">Movebank Data Repository</a> (CC0/CC BY) · AWS Terrain Tiles. Status: Red List "
                              "of the breeding birds of mainland France (UICN France, MNHN, LPO, SEOF, ONCFS, 2016). "
                              "The index is a prioritisation tool, not a measure of mortality. Code under the MIT "
                              "licence on <a href=\"{repo}\">GitHub</a>.",
        },
    },
}


def _fr_typography(text):
    """French spacing written as plain spaces: narrow no-break space before % ; ! ? and no-break space before :."""
    text = re.sub(r" ([%;!?])", " \\1", text)
    return re.sub(r" :(?=\s|$)", " :", text)


UI["fr"] = {k: _fr_typography(v) for k, v in UI["fr"].items()}


def t(lang, key, country=None, **kwargs):
    """Localised string, in the wording of `country` where it has its own; unknown languages fall back to the
    default one."""
    table = UI.get(lang) or UI[DEFAULT_LANG]
    text = COUNTRY_UI.get(country, {}).get(lang, {}).get(key) or table.get(key) or UI[DEFAULT_LANG].get(key, key)
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
    """Number with the thousands and decimal separators of `lang` (Spanish: 20.000 and 0,005; French: 20 000 with a
    narrow no-break space, and 0,005)."""
    text = f"{value:,}"
    if lang == "es":
        return text.translate(str.maketrans(",.", ".,"))
    if lang == "fr":
        return text.replace(",", "\u202f").replace(".", ",")
    return text


def pct(value, lang):
    """A percentage as each language writes it: "50 %" (Spanish), "50\u202f%" (French), "50%" (English)."""
    return {"en": f"{value}%", "fr": f"{value}\u202f%"}.get(lang, f"{value} %")


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


def _method_params_fr(lang):
    """Parameter rows of a French region: the Spanish ones with the French threshold, plus the Enedis merge."""
    c = config

    def n(v):
        return num(v, lang)

    rows = [(k, f"{c.electrocution_max_v('FR') // 1000} kV") if i == 1 else (k, v)
            for i, (k, v) in enumerate(method_params("en" if lang == "en" else "es"))]
    if lang == "en":
        return rows + [
            ("Enedis pole counted as HTA", f"≤{n(c.HTA_POLE_MAX_M)} m from an HTA line"),
            ("OSM pylon and Enedis pole are the same", f"≤{n(c.POLE_MATCH_M)} m apart"),
            ("OSM line duplicated by Enedis",
             f"≥{pct(int(c.OVERLAP_SHARE * 100), lang)} of its length ≤{n(c.OVERLAP_M)} m from HTA"),
        ]
    labels = {
        "Celda de la malla": "Cellule de la grille", "Tensión máxima de distribución": "Tension maximale de distribution",
        "Apoyos estimados donde no hay mapeados": "Supports estimés là où aucun n’est cartographié",
        "Tope de apoyos por celda": "Plafond de supports par cellule",
        "Suavizado de las citas (σ)": "Lissage des données (σ)", "Citas GBIF": "Données GBIF",
        "Citas mínimas para incluir una especie": "Données minimales pour inclure une espèce",
        "Confianza plena": "Confiance pleine", "Peso máximo del GPS (Movebank)": "Poids maximal du GPS (Movebank)",
        "Peso de eBird Status & Trends": "Poids d’eBird Status & Trends",
        "Pendiente que duplica la colisión con líneas": "Pente qui double la collision avec les lignes",
        "Radio de la posición topográfica": "Rayon de la position topographique", "Escala": "Échelle",
    }
    values = [f"{n(c.GRID_RES_DEG)}°", f"{c.electrocution_max_v('FR') // 1000} kV", "6 par km",
              n(c.PYLONS_MAX_PER_CELL), f"{n(c.KDE_SIGMA_M)} m avec ≥{n(c.KDE_N_REF)} données dans le mois",
              f"depuis {c.GBIF_YEAR_FROM}, jusqu’à {n(c.GBIF_MAX_RECORDS)} par espèce", n(c.MIN_RECORDS_PER_SPECIES),
              f"{n(c.RECORDS_FOR_CONFIDENCE)} données ou {n(c.MOVEBANK_N_REF)} positions GPS",
              pct(int(c.MOVEBANK_WEIGHT * 100), lang), pct(int(c.EBIRDST_WEIGHT * 100), lang), "25°",
              f"{n(c.TPI_RADIUS_M)} m", "99e centile = 100"]
    return [(labels[k], v) for (k, _), v in zip(rows, values)] + [
        ("Support Enedis compté comme HTA", f"à ≤{n(c.HTA_POLE_MAX_M)} m d’une ligne HTA"),
        ("Support OSM et support Enedis identiques", f"à ≤{n(c.POLE_MATCH_M)} m l’un de l’autre"),
        ("Ligne OSM en double avec Enedis",
         f"≥{pct(int(c.OVERLAP_SHARE * 100), lang)} de sa longueur à ≤{n(c.OVERLAP_M)} m d’une ligne HTA"),
    ]


def _method_fr(lang):
    """'How it is computed' for the French regions, in French or English."""
    c = config

    def n(v):
        return num(v, lang)

    kv = c.electrocution_max_v("FR") // 1000
    params = "".join(f'<tr><th>{escape(k)}</th><td class="num">{escape(v)}</td></tr>'
                     for k, v in _method_params_fr(lang))
    middle = (f"<h3>{t(lang, 'method_params')}</h3>\n<table class=\"params\"><tbody>{params}</tbody></table>\n"
              f"<h3>{t(lang, 'method_validation')}</h3>\n")
    left_out = f"<h3>{t(lang, 'method_left_out')}</h3>\n"
    limits = f"<h3>{t(lang, 'method_limits')}</h3>\n"
    if lang == "en":
        return f"""<p>The French regions use the same model as the Spanish ones; what changes is where the
 infrastructure comes from, the voltage threshold and the conservation status.</p>
<ol>
 <li><b>Distribution network: Enedis.</b> Enedis, which runs about 95% of mainland France's distribution network,
  publishes every overhead medium-voltage (HTA) line (<a href="https://data.enedis.fr/datasets/{c.ENEDIS_HTA}">réseau
  HTA</a>, Licence Ouverte 2.0) and the position of its poles, HTA or low voltage (<a
  href="https://data.enedis.fr/datasets/{c.ENEDIS_POLES}">poteaux HTA et BT</a>, ODbL). They are downloaded for the
  region's bounding box. The poles file does not say which network each pole belongs to: a pole within
  {n(c.HTA_POLE_MAX_M)} m of an overhead HTA line is counted as an HTA pole. The file is incomplete: it holds about
  half the poles one would expect on the HTA lines, so the pylons mapped in OSM fill the gaps.</li>
 <li><b>Transmission lines and wind turbines: OpenStreetMap.</b> RTE's lines and pylons (63 kV and above) and the
  wind turbines come from OpenStreetMap (Overpass), as in Spain. Lines up to {kv} kV are distribution
  (electrocution and collision); above that, transmission (collision only). In Spain the threshold is 66 kV (Royal
  Decree 1432/2008); in France the HTA network ends at 50 kV and 63 kV is already RTE's.</li>
 <li><b>Merging both sources.</b> An OSM distribution line that runs within {n(c.OVERLAP_M)} m of Enedis HTA for at
  least {pct(int(c.OVERLAP_SHARE * 100), lang)} of its length is the same line and is dropped; the others stay
  (local distributors such as SICAE or régies, which publish no data). An OSM pylon within {n(c.POLE_MATCH_M)} m of
  an Enedis pole is the same pylon: the Enedis pole takes its OSM tags (material, insulators, cross-arm), which
  set its hazard factor, and the OSM copy is dropped. OSM pylons with no Enedis twin are kept (they are the poles
  missing from the Enedis file), except those tagged below 1 kV (low voltage). Where a cell has fewer mapped pylons
  than its line length implies, the model estimates the rest, as in Spain, so nothing is counted twice.</li>
 <li><b>French territory only.</b> Every element outside the French departments that cross the region (IGN Admin
  Express) is clipped away: in the Pyrenees the bounding box takes in part of Spain, where there is no Enedis data
  and the count would be lower for that reason alone. The birds are counted over the whole box, since they fly
  across the border.</li>
 <li><b>Presence, terrain, index and ranking</b> as in Spain: GBIF/eBird records corrected for sampling effort
  (density of the species' records / density of all bird records, smoothed at σ = {n(c.KDE_SIGMA_M)} m), Movebank
  where available, slope and ridges, then a 0-100 index per species, month and {n(c.GRID_RES_DEG)}° cell.
  Electrocution = presence x weight x pylons; line collision = presence x weight x km of line x (1 + relief);
  turbine collision = presence x weight x turbines x (1 + ridge).</li>
 <li><b>Conservation status.</b> Each species weighs according to the Red List of the breeding birds of mainland
  France (UICN France, MNHN, LPO, SEOF, ONCFS, 2016): CR 1, EN 0.9, VU 0.8, NT 0.6, LC 0.4-0.5. Common Crane and
  White-tailed Eagle are weighted as the wintering birds they are in these regions.</li>
 <li><b>Natura 2000 sites</b> come from the European Environment Agency (SPA = ZPS, SAC = ZSC).</li>
</ol>
{middle}<p>Pending, as in Spain: there is no open dataset of birds killed by power lines in France to check the ranking
 against. The LPO and the national action plans keep records that are not open.</p>
{left_out}<ul>
 <li><b>RTE's line routes as RTE publishes them.</b> The ODRÉ portal lists RTE's overhead lines, but without
  geometry since RTE withdrew it for public security reasons; OpenStreetMap is used instead.</li>
 <li><b>Low voltage (BT).</b> Low-voltage lines are mostly twisted insulated cable, which does not electrocute large
  birds, and their poles outnumber HTA ones several times; they would drown the ranking. They are left out.</li>
 <li><b>Local distributors.</b> They publish no network data; only what is mapped in OSM is counted.</li>
 <li><b>Underground lines</b> are no risk to birds and are not counted.</li>
</ul>
{limits}<ul>
 <li>The index is relative to each region and is not a probability of mortality: it is meant for prioritising.</li>
 <li>Enedis does not publish the type of pole or of insulator, so most Enedis poles have a neutral hazard factor
  (1.0) unless OSM describes them.</li>
 <li>The occurrence data carry observer bias (roads, viewpoints, the Camargue's hotspots) even after the effort
  correction; species with few records (e.g. Egyptian Vulture in the Causses) weigh less.</li>
 <li>No species location is published: the ranking places pylons, lines and turbines, never birds.</li>
</ul>"""
    return _fr_typography(f"""<p>Les régions françaises utilisent le même modèle que les espagnoles ; ce qui change, c’est l’origine
 des infrastructures, le seuil de tension et le statut de conservation.</p>
<ol>
 <li><b>Réseau de distribution : Enedis.</b> Enedis, qui exploite environ 95 % du réseau de distribution de France
  métropolitaine, publie toutes ses lignes aériennes HTA (<a href="https://data.enedis.fr/datasets/{c.ENEDIS_HTA}">réseau
  HTA</a>, Licence Ouverte 2.0) et la position de ses supports, HTA ou basse tension (<a
  href="https://data.enedis.fr/datasets/{c.ENEDIS_POLES}">poteaux HTA et BT</a>, ODbL). On les télécharge pour le
  rectangle de la région. Le fichier des supports ne dit pas à quel réseau appartient chacun : un support situé à
  {n(c.HTA_POLE_MAX_M)} m au plus d’une ligne HTA aérienne est compté comme support HTA. Ce fichier est incomplet :
  il contient environ la moitié des supports attendus sur les lignes HTA, et les supports cartographiés dans OSM
  comblent les vides.</li>
 <li><b>Lignes de transport et éoliennes : OpenStreetMap.</b> Les lignes et pylônes de RTE (63 kV et plus) et les
  éoliennes viennent d’OpenStreetMap (Overpass), comme en Espagne. Les lignes jusqu’à {kv} kV sont de distribution
  (électrocution et collision) ; au-delà, de transport (collision seulement). En Espagne le seuil est de 66 kV
  (décret royal 1432/2008) ; en France le réseau HTA s’arrête à 50 kV et le 63 kV relève déjà de RTE.</li>
 <li><b>Fusion des deux sources.</b> Une ligne de distribution d’OSM qui court à {n(c.OVERLAP_M)} m au plus d’une ligne
  HTA d’Enedis sur au moins {pct(int(c.OVERLAP_SHARE * 100), lang)} de sa longueur est la même ligne et on l’écarte ;
  les autres restent (entreprises locales de distribution comme les SICAE ou les régies, qui ne publient pas de
  données). Un support OSM situé à {n(c.POLE_MATCH_M)} m au plus d’un support Enedis est le même : le support Enedis
  reprend ses attributs OSM (matériau, isolateurs, armement), qui fixent sa dangerosité, et la copie OSM est
  écartée. Les supports OSM sans jumeau Enedis sont conservés (ce sont les supports absents du fichier d’Enedis),
  sauf ceux étiquetés sous 1 kV (basse tension). Là où une cellule compte moins de supports cartographiés que ne le
  suppose sa longueur de ligne, le modèle estime le reste, comme en Espagne : rien n’est compté deux fois.</li>
 <li><b>Territoire français seulement.</b> Tout élément situé hors des départements français qui recoupent la région
  (IGN Admin Express) est découpé : dans les Pyrénées, le rectangle englobe une partie de l’Espagne, sans données
  Enedis, où le décompte serait plus faible pour cette seule raison. Les oiseaux, eux, sont comptés sur tout le
  rectangle, car ils traversent la frontière.</li>
 <li><b>Présence, relief, indice et classement</b> comme en Espagne : données GBIF/eBird corrigées de l’effort
  d’observation (densité des données de l’espèce / densité des données de toutes les espèces, lissée à
  σ = {n(c.KDE_SIGMA_M)} m), Movebank s’il existe, pente et crêtes, puis un indice 0-100 par espèce, mois et cellule
  de {n(c.GRID_RES_DEG)}°. Électrocution = présence × poids × supports ; collision avec une ligne = présence × poids ×
  km de ligne × (1 + relief) ; collision avec une éolienne = présence × poids × éoliennes × (1 + crête).</li>
 <li><b>Statut de conservation.</b> Chaque espèce pèse selon la Liste rouge des oiseaux nicheurs de France
  métropolitaine (UICN France, MNHN, LPO, SEOF, ONCFS, 2016) : CR 1, EN 0,9, VU 0,8, NT 0,6, LC 0,4-0,5. La Grue
  cendrée et le Pygargue à queue blanche sont pondérés comme les hivernants qu’ils sont dans ces régions.</li>
 <li><b>Sites Natura 2000</b> : Agence européenne pour l’environnement (ZPS et ZSC).</li>
</ol>
{middle}<p>À faire, comme en Espagne : il n’existe pas de jeu de données ouvert des oiseaux tués par les lignes en
 France pour vérifier le classement. La LPO et les plans nationaux d’actions tiennent des registres qui ne sont pas
 ouverts.</p>
{left_out}<ul>
 <li><b>Le tracé des lignes de RTE tel que RTE le publie.</b> Le portail ODRÉ recense les lignes aériennes de RTE, mais
  sans géométrie depuis que RTE l’a retirée pour des raisons de sécurité publique ; on utilise OpenStreetMap à la
  place.</li>
 <li><b>La basse tension (BT).</b> Les lignes BT sont surtout en câble torsadé isolé, qui n’électrocute pas les grands
  oiseaux, et leurs supports sont plusieurs fois plus nombreux que les HTA : ils noieraient le classement. Ils
  restent en dehors.</li>
 <li><b>Les entreprises locales de distribution.</b> Elles ne publient pas leur réseau ; seul ce qui est cartographié
  dans OSM est compté.</li>
 <li><b>Les lignes souterraines</b> ne présentent pas de risque pour les oiseaux et ne sont pas comptées.</li>
</ul>
{limits}<ul>
 <li>L’indice est relatif à chaque région et n’est pas une probabilité de mortalité : il sert à prioriser.</li>
 <li>Enedis ne publie ni le type de support ni celui des isolateurs : la plupart des supports Enedis ont une
  dangerosité neutre (1,0), sauf si OSM les décrit.</li>
 <li>Les données d’observation gardent un biais d’observateur (routes, points de vue, sites très fréquentés de
  Camargue) malgré la correction ; les espèces avec peu de données (le Vautour percnoptère dans les Causses, par
  exemple) pèsent moins.</li>
 <li>Aucune localisation d’espèce n’est publiée : le classement situe des supports, des lignes et des éoliennes,
  jamais des oiseaux.</li>
</ul>""")


def method_html(lang, country="ES"):
    """Body of the 'How it is computed' section (steps, parameters, validation, limits) for the regions of
    `country`, quoting the live configuration values. The caller wraps it in <section class="method"> with its
    <h2>."""
    if country == "FR":
        return _method_fr(lang)
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


# ---- why an element scores high: one sentence per factor of the model (see risk._Drivers)
# Codes written by osm.pylon_hazard_reasons, in each language
HAZARD_REASONS = {
    "es": {"wood": "de madera (baja el riesgo)", "earthed": "metálico o de hormigón (puesto a tierra)",
           "pin": "aisladores rígidos, con el cable por encima de la cruceta",
           "anchor": "de amarre, con puentes por encima de la cruceta",
           "suspension": "aisladores suspendidos (baja el riesgo)",
           "branch": "derivación, seccionador o fin de línea", "wide_arm": "cruceta horizontal ancha",
           "portal": "pórtico"},
    "en": {"wood": "wooden (lowers the risk)", "earthed": "steel or concrete (earthed)",
           "pin": "pin insulators, conductor above the cross-arm",
           "anchor": "anchor pylon, jumpers above the cross-arm",
           "suspension": "suspension insulators (lowers the risk)",
           "branch": "branch, switch or line end", "wide_arm": "wide horizontal cross-arm", "portal": "portal"},
    "fr": {"wood": "en bois (réduit le risque)", "earthed": "métallique ou en béton (relié à la terre)",
           "pin": "isolateurs rigides, conducteur au-dessus de la traverse",
           "anchor": "support d’ancrage, ponts au-dessus de la traverse",
           "suspension": "isolateurs suspendus (réduit le risque)",
           "branch": "dérivation, interrupteur ou fin de ligne", "wide_arm": "traverse horizontale large",
           "portal": "portique"},
}

EXPLAIN = {
    "es": {
        "level": ((95, "muy alta"), (75, "alta"), (40, "media"), (0, "baja")),
        "birds": "Aves: presencia {level} en {month}, mayor que en el {pct} de las celdas con {where}. "
                 "Las especies que más pesan: {species}.",
        "where": {"electro": "apoyos", "col_lin": "tendido", "col_aer": "aerogeneradores"},
        "expo_electro": "Tendido: unos {n} apoyos de distribución en su celda de 500 m, más que en el {pct} de "
                        "las celdas con apoyos.",
        "expo_col_lin": "Tendido: {n} km de cable en su celda de 500 m, más que en el {pct} de las celdas con "
                        "tendido.",
        "expo_col_aer": "Aerogeneradores: {n} en su celda de 500 m.",
        "terrain_col_lin": "Relieve: multiplica el riesgo por {f}; en laderas y collados el cable queda a la "
                           "altura de vuelo.",
        "terrain_col_aer": "Cresta: multiplica el riesgo por {f}; las aves planeadoras usan las corrientes de "
                           "ladera.",
        "hazard": "Apoyo: {reasons}; peligrosidad ×{f}.",
        "hazard_none": "Apoyo sin datos de material ni armado: se le da peligrosidad media (×1).",
        "index_high": "Índice {v}: {ratio} veces el umbral del 1 % de celdas con más riesgo de la región.",
        "index": "Índice {v} de 100 (100 = umbral del 1 % de celdas con más riesgo de la región).",
    },
    "en": {
        "level": ((95, "very high"), (75, "high"), (40, "medium"), (0, "low")),
        "birds": "Birds: {level} presence in {month}, higher than in {pct} of the cells with {where}. "
                 "Main species: {species}.",
        "where": {"electro": "pylons", "col_lin": "power lines", "col_aer": "wind turbines"},
        "expo_electro": "Network: about {n} distribution pylons in its 500 m cell, more than in {pct} of the cells "
                        "with pylons.",
        "expo_col_lin": "Network: {n} km of wire in its 500 m cell, more than in {pct} of the cells with lines.",
        "expo_col_aer": "Wind turbines: {n} in its 500 m cell.",
        "terrain_col_lin": "Terrain: multiplies the risk by {f}; on slopes and passes the wires sit at flight "
                           "height.",
        "terrain_col_aer": "Ridge: multiplies the risk by {f}; soaring birds ride the slope updraughts.",
        "hazard": "Pylon: {reasons}; hazard ×{f}.",
        "hazard_none": "Pylon with no material or cross-arm data: given an average hazard (×1).",
        "index_high": "Index {v}: {ratio} times the threshold of the region's riskiest 1% of cells.",
        "index": "Index {v} out of 100 (100 = threshold of the region's riskiest 1% of cells).",
    },
    "fr": {
        "level": ((95, "très forte"), (75, "forte"), (40, "moyenne"), (0, "faible")),
        "birds": "Oiseaux : présence {level} en {month}, plus élevée que dans {pct} des mailles avec {where}. "
                 "Espèces principales : {species}.",
        "where": {"electro": "supports", "col_lin": "lignes", "col_aer": "éoliennes"},
        "expo_electro": "Réseau : environ {n} supports de distribution dans sa maille de 500 m, plus que dans "
                        "{pct} des mailles avec supports.",
        "expo_col_lin": "Réseau : {n} km de câble dans sa maille de 500 m, plus que dans {pct} des mailles avec "
                        "lignes.",
        "expo_col_aer": "Éoliennes : {n} dans sa maille de 500 m.",
        "terrain_col_lin": "Relief : multiplie le risque par {f} ; sur les pentes et les cols, les câbles sont à "
                           "hauteur de vol.",
        "terrain_col_aer": "Crête : multiplie le risque par {f} ; les planeurs y profitent des ascendances.",
        "hazard": "Support : {reasons} ; dangerosité ×{f}.",
        "hazard_none": "Support sans données de matériau ni d’armement : dangerosité moyenne (×1).",
        "index_high": "Indice {v} : {ratio} fois le seuil des 1 % de mailles les plus à risque de la région.",
        "index": "Indice {v} sur 100 (100 = seuil des 1 % de mailles les plus à risque de la région).",
    },
}

_MECHANISM_KEY = {"electrocution": "electro", "line_collision": "col_lin", "turbine_collision": "col_aer"}


def _given(value):
    return value is not None and value == value and value != ""  # not None, NaN or empty


def _month_name(canonical, lang):
    try:
        return MONTH_NAMES.get(lang, MONTH_NAMES[DEFAULT_LANG])[config.MONTHS.index(canonical)]
    except ValueError:
        return canonical


def explain(row, lang):
    """Sentences saying why a ranking row scores what it scores, one per factor of the model.

    `row` is a ranking row (any object with its columns as attributes); rankings written before the driver columns
    existed only get the sentence on the index."""
    e = EXPLAIN.get(lang, EXPLAIN[DEFAULT_LANG])
    k = _MECHANISM_KEY.get(getattr(row, "mechanism", None), "electro")
    v = float(row.risk_max)
    out = [e["index_high"].format(v=num(round(v), lang), ratio=num(round(v / 100, 1), lang)) if v > 100
           else e["index"].format(v=num(round(v), lang))]
    birds_pct = getattr(row, "birds_pct", None)  # numbers from pandas, or text from csv.DictReader
    if _given(birds_pct):
        birds_pct = int(float(birds_pct))
        level = next(word for floor, word in e["level"] if birds_pct >= floor)
        names = [s.strip() for s in str(getattr(row, "species", "") or "").split(",") if s.strip()]
        shares = str(getattr(row, "species_share", "") or "").split(";")
        shares += [""] * (len(names) - len(shares))
        species = ", ".join(f"{config.species_name(n, lang)} ({pct(int(float(s)), lang)})" if s
                            else config.species_name(n, lang) for n, s in zip(names, shares))
        out.append(e["birds"].format(level=level, month=_month_name(row.peak_month, lang),
                                     pct=pct(birds_pct, lang), where=e["where"][k], species=species))
    if _given(getattr(row, "exposure", None)):
        n = float(row.exposure)
        n = num(round(n, 1) if k == "col_lin" else int(round(n)), lang)
        expo_pct = getattr(row, "exposure_pct", None)
        out.append(e[f"expo_{k}"].format(n=n, pct=pct(int(float(expo_pct)), lang) if _given(expo_pct) else ""))
    terrain = getattr(row, "terrain", None)
    if _given(terrain) and float(terrain) >= 1.05:
        out.append(e[f"terrain_{k}"].format(f=num(round(float(terrain), 2), lang)))
    if getattr(row, "type", None) == "pylon":
        why = getattr(row, "hazard_why", None)
        if _given(why):
            reasons = HAZARD_REASONS.get(lang, HAZARD_REASONS[DEFAULT_LANG])
            out.append(e["hazard"].format(reasons=", ".join(reasons.get(c, c) for c in str(why).split(";")),
                                          f=num(float(row.hazard), lang)))
        elif _given(getattr(row, "hazard", None)) and float(row.hazard) == 1.0:
            out.append(e["hazard_none"])
    return [_fr_typography(s) for s in out] if lang == "fr" else out
