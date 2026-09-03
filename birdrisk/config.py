import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = ROOT / "output"

for d in (CACHE_DIR / "osm", CACHE_DIR / "terrain", CACHE_DIR / "gbif", CACHE_DIR / "movebank", OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

USER_AGENT = "birdrisk/0.2 (open conservation project)"
REPO_URL = "https://github.com/Asensio94/riesgo-tendidos-aves"
WEB_URL = "https://asensio94.github.io/riesgo-tendidos-aves/"

LANGS = ("es", "en")

# ---------------------------------------------------------------- regions
# bbox = (lat_min, lon_min, lat_max, lon_max)
# Region keys are part of the published URLs and of the observatory integration: do not rename them.
REGIONS = {
    "estrecho": {
        "name": {"es": "Estrecho de Gibraltar / Campo de Gibraltar (Cádiz)",
                 "en": "Strait of Gibraltar / Campo de Gibraltar (Cádiz, Spain)"},
        "bbox": (36.00, -5.95, 36.45, -5.30),
        "species": ["Gyps fulvus", "Aegypius monachus", "Neophron percnopterus", "Aquila adalberti", "Aquila fasciata",
                    "Aquila chrysaetos", "Circaetus gallicus", "Hieraaetus pennatus", "Pernis apivorus",
                    "Milvus migrans", "Milvus milvus", "Falco peregrinus", "Ciconia ciconia", "Ciconia nigra",
                    "Grus grus", "Bubo bubo"],
    },
    "tarifa": {
        "name": {"es": "Tarifa y La Janda (Cádiz)", "en": "Tarifa and La Janda (Cádiz, Spain)"},
        "bbox": (36.00, -6.05, 36.30, -5.55),
    },
    "cantabria": {
        "name": {"es": "Cantabria y su entorno", "en": "Cantabria and surroundings (Spain)"},
        "bbox": (42.75, -4.90, 43.55, -3.10),
        # own list: no Mediterranean or steppe species, plus the sensitive Cantabrian ones
        "species": ["Gyps fulvus", "Neophron percnopterus", "Aegypius monachus", "Gypaetus barbatus",
                    "Aquila chrysaetos", "Circaetus gallicus", "Hieraaetus pennatus", "Pernis apivorus",
                    "Milvus migrans", "Milvus milvus", "Falco peregrinus", "Ciconia ciconia", "Ciconia nigra",
                    "Grus grus", "Bubo bubo", "Pyrrhocorax pyrrhocorax", "Platalea leucorodia", "Ardea cinerea"],
    },
    "monfrague": {
        "name": {"es": "Monfragüe y entorno (Cáceres)", "en": "Monfragüe and surroundings (Cáceres, Spain)"},
        "bbox": (39.65, -6.30, 40.00, -5.70),
    },
    "gallocanta": {
        "name": {"es": "Gallocanta y Campo de Daroca (Zaragoza/Teruel)",
                 "en": "Gallocanta and Campo de Daroca (Zaragoza/Teruel, Spain)"},
        "bbox": (40.85, -1.75, 41.15, -1.30),
    },
}

# Analysis grid resolution in degrees (~0.005 deg is 550 m in latitude, ~450 m in longitude at 36 N)
GRID_RES_DEG = 0.005

# ---------------------------------------------------------------- OSM / Overpass
OVERPASS_URLS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_TIMEOUT = 180
# Voltage threshold (V) separating distribution (electrocution risk) from transmission (collision only).
# Spanish Royal Decree 1432/2008: anti-electrocution measures apply to 1 kV - 66 kV lines.
ELECTROCUTION_MAX_V = 66_000

# ---------------------------------------------------------------- Terrain (AWS Terrain Tiles, terrarium format)
TERRAIN_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TERRAIN_ZOOM = 12  # ~38 m/pixel at the equator, ~31 m at 36 N
TPI_RADIUS_M = 1500  # radius for the topographic position index (ridges / valley bottoms)

# ---------------------------------------------------------------- GBIF (includes the eBird Observation Dataset)
GBIF_OCC_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_YEAR_FROM = 2010
AVES_TAXON_KEY = 212
EBIRD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
GBIF_PAGE = 300
GBIF_MAX_OFFSET = 100_000  # search API limit
GBIF_THREADS = 3  # pages downloaded in parallel (GBIF throttles per IP)
GBIF_RETRIES = 10  # exponential backoff up to 2 min (GBIF returns 503 under load)
GBIF_MAX_RECORDS = 20_000  # cap of records per species and region (most recent years first)
EFFORT_TILE_DEG = 0.05  # tile size for the sampling effort layer (all birds)
KDE_SIGMA_M = 1500  # smoothing of the record density
# With few records in a month the smoothing widens: sigma * sqrt(KDE_N_REF / n). This keeps an isolated record
# in a rarely visited place from spiking the index (e.g. a migrating Black Stork next to a substation).
KDE_N_REF = 300
# A species enters the aggregate index with weight status * min(1, records / RECORDS_FOR_CONFIDENCE): with few
# records its map is unreliable and must not dominate the ranking. With GPS tracking in the area confidence is 1.
RECORDS_FOR_CONFIDENCE = 500
# Maximum number of pylons counted in one grid cell (more than that is usually a substation, not a power line)
PYLONS_MAX_PER_CELL = 20
# Maximum number of pylons drawn on the map (highest index first); more markers make the HTML unusable
MAX_PYLONS_ON_MAP = 4000
# Minimum number of records of a species in the region for it to be considered
MIN_RECORDS_PER_SPECIES = 30

# ---------------------------------------------------------------- eBird Status & Trends (optional, needs a key)
# Folder with the weekly abundance GeoTIFFs (52 bands) downloaded with the R package `ebirdst`
# (ebirdst_download_status(species, pattern = "abundance_median_3km")). Looked up in EBIRDST_DIR/<Genus_species>/*.tif
# or in any file whose name contains the eBird species code.
EBIRDST_DIR = DATA_DIR / "ebirdst"
EBIRDST_WEIGHT = 0.7  # weight of the eBird model against the GBIF frequency when both are available

# ---------------------------------------------------------------- Movebank
MOVEBANK_PUBLIC_JSON = "https://www.movebank.org/movebank/service/public/json"
MOVEBANK_DIRECT_READ = "https://www.movebank.org/movebank/service/direct-read"
MOVEBANK_REPO_SEARCH = "https://datarepository.movebank.org/server/api/discover/search/objects"
MOVEBANK_REPO_ITEM = "https://datarepository.movebank.org/server/api/core/items/{uuid}"
MOVEBANK_USER = os.environ.get("MOVEBANK_USER")
MOVEBANK_PASSWORD = os.environ.get("MOVEBANK_PASSWORD")
MOVEBANK_MAX_MB = 150  # do not download repository files larger than this (some exceed 1 GB)
# IDs of public Movebank studies to always include (optional)
MOVEBANK_STUDY_IDS: list[int] = []
# Flight height (m above ground) below which a GPS fix counts as being inside the risk envelope
MOVEBANK_RISK_HEIGHT_M = 150
# Maximum weight of the tracking data against the GBIF abundance when both exist; the actual weight is
# MOVEBANK_WEIGHT * min(1, fixes / MOVEBANK_N_REF), so that a handful of passing fixes cannot move the map
MOVEBANK_WEIGHT = 0.5
MOVEBANK_N_REF = 2000

# ---------------------------------------------------------------- Species
# Weights 0-1 per mechanism (synthesis of Bevanger 1998, Janss 2000, Lehman et al. 2007, Martin & Shaw 2010,
# Marques et al. 2014 and the species lists of Spanish Royal Decree 1432/2008). User-adjustable.
#   electro: electrocution on distribution pylons (large birds that perch on pylons)
#   col_lin: collision with conductors (poor manoeuvrability, flocking, crepuscular flight)
#   col_aer: collision with wind turbines (soaring birds that use ridges and thermals)
#   status: conservation weight (Spanish Catalogue of Threatened Species / Red Book)
SPECIES = {
    "Gyps fulvus": dict(name={"es": "Buitre leonado", "en": "Griffon Vulture"},
                        electro=0.8, col_lin=0.5, col_aer=1.0, status=0.5),
    "Aegypius monachus": dict(name={"es": "Buitre negro", "en": "Cinereous Vulture"},
                              electro=0.7, col_lin=0.5, col_aer=0.9, status=0.9),
    "Neophron percnopterus": dict(name={"es": "Alimoche", "en": "Egyptian Vulture"},
                                  electro=0.6, col_lin=0.4, col_aer=0.8, status=0.9),
    "Aquila adalberti": dict(name={"es": "Águila imperial ibérica", "en": "Spanish Imperial Eagle"},
                             electro=1.0, col_lin=0.4, col_aer=0.7, status=1.0),
    "Aquila fasciata": dict(name={"es": "Águila perdicera", "en": "Bonelli’s Eagle"},
                            electro=0.9, col_lin=0.4, col_aer=0.7, status=0.9),
    "Aquila chrysaetos": dict(name={"es": "Águila real", "en": "Golden Eagle"},
                              electro=0.8, col_lin=0.4, col_aer=0.8, status=0.7),
    "Circaetus gallicus": dict(name={"es": "Culebrera europea", "en": "Short-toed Snake Eagle"},
                               electro=0.6, col_lin=0.3, col_aer=0.6, status=0.5),
    "Hieraaetus pennatus": dict(name={"es": "Águila calzada", "en": "Booted Eagle"},
                                electro=0.5, col_lin=0.3, col_aer=0.5, status=0.5),
    "Milvus migrans": dict(name={"es": "Milano negro", "en": "Black Kite"},
                           electro=0.5, col_lin=0.4, col_aer=0.7, status=0.4),
    "Milvus milvus": dict(name={"es": "Milano real", "en": "Red Kite"},
                          electro=0.6, col_lin=0.4, col_aer=0.8, status=0.9),
    "Ciconia ciconia": dict(name={"es": "Cigüeña blanca", "en": "White Stork"},
                            electro=0.9, col_lin=0.9, col_aer=0.6, status=0.4),
    "Ciconia nigra": dict(name={"es": "Cigüeña negra", "en": "Black Stork"},
                          electro=0.7, col_lin=0.8, col_aer=0.5, status=0.9),
    "Grus grus": dict(name={"es": "Grulla común", "en": "Common Crane"},
                      electro=0.1, col_lin=1.0, col_aer=0.4, status=0.5),
    "Otis tarda": dict(name={"es": "Avutarda", "en": "Great Bustard"},
                       electro=0.0, col_lin=1.0, col_aer=0.5, status=0.9),
    "Bubo bubo": dict(name={"es": "Búho real", "en": "Eurasian Eagle-Owl"},
                      electro=0.9, col_lin=0.2, col_aer=0.2, status=0.6),
    # Cantabrian / Atlantic
    "Gypaetus barbatus": dict(name={"es": "Quebrantahuesos", "en": "Bearded Vulture"},
                              electro=0.6, col_lin=0.5, col_aer=0.9, status=1.0),
    "Pernis apivorus": dict(name={"es": "Abejero europeo", "en": "European Honey Buzzard"},
                            electro=0.4, col_lin=0.3, col_aer=0.6, status=0.4),
    "Falco peregrinus": dict(name={"es": "Halcón peregrino", "en": "Peregrine Falcon"},
                             electro=0.6, col_lin=0.3, col_aer=0.5, status=0.6),
    "Pyrrhocorax pyrrhocorax": dict(name={"es": "Chova piquirroja", "en": "Red-billed Chough"},
                                    electro=0.4, col_lin=0.3, col_aer=0.5, status=0.6),
    "Platalea leucorodia": dict(name={"es": "Espátula común", "en": "Eurasian Spoonbill"},
                                electro=0.2, col_lin=0.9, col_aer=0.4, status=0.7),
    "Ardea cinerea": dict(name={"es": "Garza real", "en": "Grey Heron"},
                          electro=0.3, col_lin=0.7, col_aer=0.3, status=0.3),
}
DEFAULT_SPECIES = list(SPECIES)

# Relative weights of the three mechanisms in the combined index
MECHANISM_WEIGHT = {"electro": 1.0, "col_lin": 1.0, "col_aer": 1.0}

# Canonical month labels used in data outputs (GeoTIFF band names, CSV columns).
# Localised labels for display live in i18n.py.
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _localised(value, lang, fallback):
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or fallback
    return value or fallback


def region_name(key, lang="en"):
    """Display name of a region in the requested language, falling back to the key."""
    reg = REGIONS.get(key)
    return _localised(reg["name"], lang, key) if reg else key


def species_name(scientific, lang="en"):
    """Common name of a species in the requested language, falling back to the scientific name."""
    cfg = SPECIES.get(scientific)
    return _localised(cfg["name"], lang, scientific) if cfg else scientific
