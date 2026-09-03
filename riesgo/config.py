import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = ROOT / "output"

for d in (CACHE_DIR / "osm", CACHE_DIR / "terrain", CACHE_DIR / "gbif", CACHE_DIR / "movebank", OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

USER_AGENT = "riesgo-tendidos-aves/0.1 (proyecto abierto de conservacion)"
REPO_URL = "https://github.com/Asensio94/riesgo-tendidos-aves"
WEB_URL = "https://asensio94.github.io/riesgo-tendidos-aves/"

# ---------------------------------------------------------------- regiones
# bbox = (lat_min, lon_min, lat_max, lon_max)
REGIONES = {
    "estrecho": {
        "nombre": "Estrecho de Gibraltar / Campo de Gibraltar (Cádiz)",
        "bbox": (36.00, -5.95, 36.45, -5.30),
        "especies": ["Gyps fulvus", "Aegypius monachus", "Neophron percnopterus", "Aquila adalberti", "Aquila fasciata",
                     "Aquila chrysaetos", "Circaetus gallicus", "Hieraaetus pennatus", "Pernis apivorus", "Milvus migrans",
                     "Milvus milvus", "Falco peregrinus", "Ciconia ciconia", "Ciconia nigra", "Grus grus", "Bubo bubo"],
    },
    "tarifa": {
        "nombre": "Tarifa y La Janda (Cádiz)",
        "bbox": (36.00, -6.05, 36.30, -5.55),
    },
    "cantabria": {
        "nombre": "Cantabria y su entorno",
        "bbox": (42.75, -4.90, 43.55, -3.10),
        # lista propia: sin las especies mediterráneas/esteparias y con las cantábricas sensibles
        "especies": ["Gyps fulvus", "Neophron percnopterus", "Aegypius monachus", "Gypaetus barbatus",
                     "Aquila chrysaetos", "Circaetus gallicus", "Hieraaetus pennatus", "Pernis apivorus",
                     "Milvus migrans", "Milvus milvus", "Falco peregrinus", "Ciconia ciconia", "Ciconia nigra",
                     "Grus grus", "Bubo bubo", "Pyrrhocorax pyrrhocorax", "Platalea leucorodia", "Ardea cinerea"],
    },
    "monfrague": {
        "nombre": "Monfragüe y entorno (Cáceres)",
        "bbox": (39.65, -6.30, 40.00, -5.70),
    },
    "gallocanta": {
        "nombre": "Gallocanta y Campo de Daroca (Zaragoza/Teruel)",
        "bbox": (40.85, -1.75, 41.15, -1.30),
    },
}

# Resolución de la malla de análisis en grados (~0.005° ≈ 550 m en latitud, ~450 m en longitud a 36°N)
GRID_RES_DEG = 0.005

# ---------------------------------------------------------------- OSM / Overpass
OVERPASS_URLS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_TIMEOUT = 180
# Umbral (V) que separa distribución (riesgo de electrocución) de transporte (solo colisión).
# RD 1432/2008: medidas anti-electrocución para líneas de 2ª y 3ª categoría (1 kV - 66 kV).
ELECTROCUCION_MAX_V = 66_000

# ---------------------------------------------------------------- Topografía (AWS Terrain Tiles, formato terrarium)
TERRAIN_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TERRAIN_ZOOM = 12  # ~38 m/píxel en el ecuador, ~31 m a 36°N
TPI_RADIO_M = 1500  # radio para el índice de posición topográfica (crestas / vaguadas)

# ---------------------------------------------------------------- GBIF (incluye el eBird Observation Dataset)
GBIF_OCC_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_YEAR_FROM = 2010
AVES_TAXON_KEY = 212
EBIRD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
GBIF_PAGE = 300
GBIF_MAX_OFFSET = 100_000  # límite de la API de búsqueda
GBIF_HILOS = 3  # páginas descargadas en paralelo (GBIF limita por IP)
GBIF_REINTENTOS = 10  # con espera exponencial hasta 2 min (GBIF devuelve 503 en picos)
GBIF_MAX_CITAS = 20_000  # tope de citas por especie y región (se toman los años más recientes)
EFFORT_TILE_DEG = 0.05  # tesela para el esfuerzo de muestreo (todas las aves)
KDE_SIGMA_M = 1500  # suavizado de la densidad de citas
# Con pocas citas en un mes el suavizado se ensancha: sigma · sqrt(KDE_N_REF / n). Evita que una cita aislada
# en un sitio poco visitado dispare el índice (p. ej. una cigüeña negra de paso junto a una subestación).
KDE_N_REF = 300
# Una especie entra en el índice agregado con peso estatus · min(1, citas / CITAS_CONFIANZA): con pocas citas su
# mapa es poco fiable y no debe dominar el ranking. Con seguimiento GPS en la zona la confianza es 1.
CITAS_CONFIANZA = 500
# Nº máximo de apoyos que cuentan en una celda (más que eso suele ser una subestación, no un tendido)
APOYOS_MAX_CELDA = 20
# Máximo de apoyos dibujados en el mapa (los de mayor índice); más marcadores hacen el HTML inmanejable
MAX_APOYOS_MAPA = 4000
# Umbral mínimo de citas de la especie en la región para considerarla
MIN_CITAS_ESPECIE = 30

# ---------------------------------------------------------------- eBird Status & Trends (opcional, requiere clave)
# Carpeta con los GeoTIFF semanales de abundancia (52 bandas) descargados con el paquete R `ebirdst`
# (ebirdst_download_status(species, pattern = "abundance_median_3km")). Se buscan en EBIRDST_DIR/<Genus_species>/*.tif
# o cualquier fichero cuyo nombre contenga el código eBird de la especie.
EBIRDST_DIR = DATA_DIR / "ebirdst"
PESO_EBIRDST = 0.7  # peso del modelo eBird frente a la frecuencia GBIF cuando hay ambos

# ---------------------------------------------------------------- Movebank
MOVEBANK_PUBLIC_JSON = "https://www.movebank.org/movebank/service/public/json"
MOVEBANK_DIRECT_READ = "https://www.movebank.org/movebank/service/direct-read"
MOVEBANK_REPO_SEARCH = "https://datarepository.movebank.org/server/api/discover/search/objects"
MOVEBANK_REPO_ITEM = "https://datarepository.movebank.org/server/api/core/items/{uuid}"
MOVEBANK_USER = os.environ.get("MOVEBANK_USER")
MOVEBANK_PASSWORD = os.environ.get("MOVEBANK_PASSWORD")
MOVEBANK_MAX_MB = 150  # no descargar ficheros del repositorio mayores que esto (algunos superan 1 GB)
# IDs de estudios públicos de Movebank que se quieran incluir siempre (opcional)
MOVEBANK_STUDY_IDS: list[int] = []
# Altura de vuelo (m sobre el suelo) por debajo de la cual una posición GPS cuenta como "en zona de riesgo"
MOVEBANK_ALTURA_RIESGO_M = 150
# Peso máximo del dato de seguimiento frente a la abundancia GBIF cuando hay ambos; el peso real es
# PESO_MOVEBANK · min(1, posiciones / MOVEBANK_N_REF), para que unas pocas posiciones de paso no muevan el mapa
PESO_MOVEBANK = 0.5
MOVEBANK_N_REF = 2000

# ---------------------------------------------------------------- Especies
# Pesos 0-1 por mecanismo (síntesis de Bevanger 1998, Janss 2000, Lehman et al. 2007, Martin & Shaw 2010,
# Marques et al. 2014 y listados del RD 1432/2008). Ajustables por el usuario.
#   electro: electrocución en apoyos de distribución (aves grandes que se posan en apoyos)
#   col_lin: colisión con conductores (vuelo poco maniobrable, bandos, vuelo crepuscular)
#   col_aer: colisión con aerogeneradores (planeadoras que usan crestas y térmicas)
#   estatus: peso de conservación (Catálogo Español de Especies Amenazadas / Libro Rojo)
ESPECIES = {
    "Gyps fulvus":            dict(nombre="Buitre leonado",     electro=0.8, col_lin=0.5, col_aer=1.0, estatus=0.5),
    "Aegypius monachus":      dict(nombre="Buitre negro",       electro=0.7, col_lin=0.5, col_aer=0.9, estatus=0.9),
    "Neophron percnopterus":  dict(nombre="Alimoche",           electro=0.6, col_lin=0.4, col_aer=0.8, estatus=0.9),
    "Aquila adalberti":       dict(nombre="Águila imperial ibérica", electro=1.0, col_lin=0.4, col_aer=0.7, estatus=1.0),
    "Aquila fasciata":        dict(nombre="Águila perdicera",   electro=0.9, col_lin=0.4, col_aer=0.7, estatus=0.9),
    "Aquila chrysaetos":      dict(nombre="Águila real",        electro=0.8, col_lin=0.4, col_aer=0.8, estatus=0.7),
    "Circaetus gallicus":     dict(nombre="Culebrera europea",  electro=0.6, col_lin=0.3, col_aer=0.6, estatus=0.5),
    "Hieraaetus pennatus":    dict(nombre="Águila calzada",     electro=0.5, col_lin=0.3, col_aer=0.5, estatus=0.5),
    "Milvus migrans":         dict(nombre="Milano negro",       electro=0.5, col_lin=0.4, col_aer=0.7, estatus=0.4),
    "Milvus milvus":          dict(nombre="Milano real",        electro=0.6, col_lin=0.4, col_aer=0.8, estatus=0.9),
    "Ciconia ciconia":        dict(nombre="Cigüeña blanca",     electro=0.9, col_lin=0.9, col_aer=0.6, estatus=0.4),
    "Ciconia nigra":          dict(nombre="Cigüeña negra",      electro=0.7, col_lin=0.8, col_aer=0.5, estatus=0.9),
    "Grus grus":              dict(nombre="Grulla común",       electro=0.1, col_lin=1.0, col_aer=0.4, estatus=0.5),
    "Otis tarda":             dict(nombre="Avutarda",           electro=0.0, col_lin=1.0, col_aer=0.5, estatus=0.9),
    "Bubo bubo":              dict(nombre="Búho real",          electro=0.9, col_lin=0.2, col_aer=0.2, estatus=0.6),
    # cantábricas / atlánticas
    "Gypaetus barbatus":      dict(nombre="Quebrantahuesos",    electro=0.6, col_lin=0.5, col_aer=0.9, estatus=1.0),
    "Pernis apivorus":        dict(nombre="Abejero europeo",    electro=0.4, col_lin=0.3, col_aer=0.6, estatus=0.4),
    "Falco peregrinus":       dict(nombre="Halcón peregrino",   electro=0.6, col_lin=0.3, col_aer=0.5, estatus=0.6),
    "Pyrrhocorax pyrrhocorax": dict(nombre="Chova piquirroja",  electro=0.4, col_lin=0.3, col_aer=0.5, estatus=0.6),
    "Platalea leucorodia":    dict(nombre="Espátula común",     electro=0.2, col_lin=0.9, col_aer=0.4, estatus=0.7),
    "Ardea cinerea":          dict(nombre="Garza real",         electro=0.3, col_lin=0.7, col_aer=0.3, estatus=0.3),
}
ESPECIES_DEFECTO = list(ESPECIES)

# Pesos relativos de los tres mecanismos en el índice combinado
PESO_MECANISMO = {"electro": 1.0, "col_lin": 1.0, "col_aer": 1.0}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
