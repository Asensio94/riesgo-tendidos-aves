*[English](README.md) · **Español***

# Mapa dinámico de riesgo de colisión y electrocución de aves

Cruza **tendidos eléctricos, apoyos y aerogeneradores** de OpenStreetMap con la **abundancia estacional**
de aves (GBIF, que incluye eBird), el **seguimiento GPS** de Movebank y la **topografía**, para generar
mapas de riesgo por especie y mes y un ranking de los elementos (apoyos, aerogeneradores, tramos) donde
priorizar las correcciones. Pensado para que una eléctrica, una administración o una ONG pueda consultarlo
y actualizarlo sin depender de un estudio puntual.

## Estado

Prototipo v0.1 (septiembre 2026). Funciona sin ninguna clave de API. Movebank es opcional.

**Web:** <https://asensio94.github.io/riesgo-tendidos-aves/> (presentación del proyecto, método, retos y hoja de ruta) ·
[mapas y rankings por región](https://asensio94.github.io/riesgo-tendidos-aves/regions.es.html). Se regenera el día 2 de cada mes
con GitHub Actions. La presentación estática vive en `web/` y las miniaturas se generan con `tools/thumbnails.py`.
Todo se publica en español e inglés: `index.html`/`index.en.html`, `regions.es.html`/`regions.en.html` y, por región,
`report.<lang>.html` y `map.<lang>.html`. El español es la versión por defecto; las URL antiguas (`regiones.html`,
`<region>/informe.html`, `<region>/mapa.html`) redirigen a ella. El código y los datos de salida están en inglés.
La versión en inglés de este fichero es [README.md](README.md).

## Uso

```bash
pip install -r requirements.txt
python -m birdrisk.cli run --region estrecho
```

Genera en `output/<region>/`:

| Fichero | Contenido |
|---|---|
| `report.es.html` / `report.en.html` | informe con mapa embebido, tabla estacional por especie y top de elementos |
| `map.es.html` / `map.en.html` | mapa interactivo (folium): capas mensuales, por mecanismo y por especie, infraestructura y ranking |
| `ranking_elements.csv` / `.geojson` | todos los apoyos, aerogeneradores y tramos con índice máximo, medio, mes pico y especies |
| `risk_total.tif`, `risk_electro.tif`, `risk_col_lin.tif`, `risk_col_aer.tif` | rásteres de 12 bandas (una por mes), EPSG:4326, para QGIS |
| `terrain.tif` | elevación, pendiente y TPI |

Opciones útiles:

```bash
python -m birdrisk.cli regions                       # regiones predefinidas (estrecho, tarifa, cantabria, monfrague, gallocanta)
python -m birdrisk.cli run --region cantabria        # una región puede llevar su propia lista de especies (config.REGIONS[...]["species"])
python -m birdrisk.cli species                       # especies y pesos
python -m birdrisk.cli run --bbox 39.6,-6.3,40.0,-5.7 -s "Aegypius monachus" -s "Ciconia nigra"
python -m birdrisk.cli run --region estrecho --movebank        # añade datasets publicados en Movebank (descargas de cientos de MB)
python -m birdrisk.cli run --region estrecho --study-id 123456 # estudios Movebank concretos (públicos o con MOVEBANK_USER/MOVEBANK_PASSWORD)
python -m birdrisk.cli index                                   # regenera output/regions.es.html y regions.en.html y copia web/ (lo hace también `run`)
python -m birdrisk.cli score --region cantabria --observatory ../observatorio-alegaciones   # índice de riesgo de cada proyecto en información pública
python -m birdrisk.cli score --region cantabria --geojson proyectos.geojson                  # o de cualquier polígono
```

`score` devuelve, por proyecto, el índice medio y máximo, el mes pico, el porcentaje de celdas con infraestructura y el
máximo por mecanismo (`output/<region>/scored_projects.csv`). Con `--observatory` toma los anuncios geolocalizados del
[observatorio de alegaciones](../observatorio-alegaciones) y reutiliza su caché de polígonos municipales.

## Fuentes

| Fuente | Uso | Acceso |
|---|---|---|
| OpenStreetMap vía Overpass | `power=line/minor_line` (voltaje, operador), `power=tower/pole`, `generator:source=wind` | público, sin clave |
| GBIF occurrence API | citas por especie y mes; citas de todas las aves como esfuerzo de muestreo. Incluye el eBird Observation Dataset | público, sin clave |
| AWS Terrain Tiles (terrarium) | elevación ~30 m → pendiente y posición topográfica | público, sin clave |
| Movebank Data Repository | datasets GPS publicados (CC0/CC-BY), búsqueda por especie y descarga de CSV | público, sin clave |
| Movebank API | estudios públicos (`public/json`) o con cuenta (`direct-read`) | opcional |

**eBird Status & Trends** (abundancia semanal modelada a 3 km) es la mejor capa de abundancia, pero exige solicitar
una clave y se distribuye vía R (`ebirdst`). Ya está integrado como opción: descarga los GeoTIFF
`*_abundance_median_3km_*.tif` con `ebirdst_download_status(<código>, pattern = "abundance_median_3km")`, cópialos a
`data/ebirdst/<Genus_species>/` y `birdrisk/ebirdst.py` los reproyecta a la malla, agrega las 52 semanas en meses y los
mezcla con la frecuencia GBIF (70/30, `EBIRDST_WEIGHT`). La especie pasa a confianza 1. Sin ficheros, no cambia nada.

### Datos de mortalidad para calibrar (pendiente)

No hay un dataset abierto nacional de aves electrocutadas o colisionadas. Lo más aprovechable encontrado:

- Gobierno Vasco, *Avifauna y tendidos eléctricos* (líneas con tramos asignados por peligrosidad, shapefile CC BY 4.0):
  <https://www.geo.euskadi.eus/cartografia/DatosDescarga/Medio_Ambiente/Aves_y_Lineas_Electricas/KM_LINEAS_ASIGNADASAvesTendidos.zip>.
  Sirve para validar el ranking en una región `euskadi`: comprobar si los tramos que la administración marcó como
  peligrosos salen arriba en nuestro índice.
- *Libro Blanco de la Electrocución* (Generalitat de Catalunya / Endesa, criterios de peligrosidad por tipo de apoyo):
  <https://mediambient.gencat.cat/web/.content/home/ambits_dactuacio/patrimoni_natural/fauna_autoctona_protegida/Publicacions/llibre_blanc_electrocucio.pdf>.
- RD 1432/2008 (medidas contra electrocución y colisión en líneas de alta tensión):
  <https://www.boe.es/buscar/act.php?id=BOE-A-2008-14914>.
- Programas de seguimiento de SEO/BirdLife y proyectos LIFE (Bonelli, AQUILA a-LIFE) publican cifras agregadas,
  no puntos; habría que solicitarlos.

Cuando haya puntos de mortalidad, el ajuste previsto es una regresión logística del suceso frente a los índices
`electro`/`col_lin` de la celda y los pesos por especie, para reemplazar los pesos bibliográficos por pesos estimados.

## Método

Para cada especie *s*, mes *m* y celda de ~0,5 km:

```
electro[s,m]  = P[s,m] · w_electro[s] · apoyos_eq                 # apoyos de distribución ≤ 66 kV (RD 1432/2008)
col_lin[s,m]  = P[s,m] · w_col_lin[s] · km_línea · (1 + relieve)   # todos los conductores
col_aer[s,m]  = P[s,m] · w_col_aer[s] · n_aerogen · (1 + cresta)
```

- **P** = densidad de citas de la especie / densidad de citas de todas las aves, por mes, suavizada y
  normalizada a 0-1 por especie. El suavizado es adaptativo: σ 1,5 km con ≥300 citas en el mes y más ancho
  (σ·√(300/n)) con menos, para que una cita aislada en un sitio poco visitado no dispare el índice.
  Las citas repetidas en el mismo punto, mes y año pesan √n (un observador que vuelve no es n aves).
  Si hay GPS de Movebank se mezcla con los individuos-día por celda, con peso 0,5·min(1, posiciones/2000): cinco
  posiciones de un ave de paso no mueven el mapa; miles sí.
- En el agregado cada especie pesa **estatus × confianza**, con confianza = max(min(1, citas/500), min(1, posiciones GPS/2000)),
  o 1 si hay modelo de eBird Status & Trends: una especie con 250 citas tiene un mapa poco fiable y no debe dominar el
  ranking, aunque sus capas propias sigan disponibles.
- **apoyos_eq** = apoyos mapeados en OSM o, si faltan, 6 apoyos por km de línea de distribución; tope de 20 por celda
  (más que eso es una subestación). Cada apoyo pesa un **factor de peligrosidad 0,5-2** según sus etiquetas OSM
  (`material` madera 0,5; `line_attachment` pin 1,5 / anchor 1,3 / suspension 0,9; `line_management` derivación,
  seccionamiento, paso a subterráneo o fin de línea 1,3; crucetas horizontales 1,1; pórticos 1,3), con 1,0 si no hay
  etiquetas. El factor escala también el puesto del apoyo en el ranking. En Cantabria unos 5 000 de 46 300 apoyos tienen alguna.
- **relieve** = pendiente/25° (acotado a 1); **cresta** = TPI positivo normalizado (radio 1,5 km).
- Los pesos por especie y el peso de conservación están en `birdrisk/config.py` (síntesis de Bevanger 1998, Janss 2000,
  Lehman et al. 2007, Marques et al. 2014 y el listado del RD 1432/2008). Son un punto de partida ajustable.
- Cada índice se reescala a 0-100 (percentil 99 de la región). El agregado suma especies ponderadas por estatus.
- El ranking de elementos toma el índice de la celda de cada apoyo/aerogenerador y la media a lo largo de cada tramo.

## Pipeline

1. `osm.py`: Overpass (con espejos), clasificación de líneas por voltaje, voltaje heredado por los apoyos, rasterización.
2. `terrain.py`: teselas terrarium → mosaico → pendiente y TPI → muestreo a la malla.
3. `abundance.py`: citas GBIF descargadas por bloques anuales (de reciente a antiguo, hasta `GBIF_MAX_RECORDS` = 20 000 por
   especie) con 3 hilos y reintentos pacientes: el paginado profundo de GBIF es lento y su API devuelve 503 en picos.
   Esfuerzo por tesela de 0,05° y mes con facetas. Cada bloque se cachea para poder reanudar.
4. `movebank.py`: repositorio DSpace (búsqueda, bitstreams, filtro por bbox en streaming; ficheros de hasta
   `MOVEBANK_MAX_MB` = 150 MB), `public/json`, `direct-read`.
5. `risk.py`: modelo, agregación, ranking de elementos, tabla estacional.
6. `report.py`: folium (ImageOverlay por mes), informe HTML, GeoTIFF, GeoJSON.
7. `ebirdst.py` (opcional): GeoTIFF semanales de eBird Status & Trends → meses → mezcla con GBIF.
8. `score.py`: estadísticas del índice sobre polígonos de proyectos (integración con el observatorio de alegaciones).
9. `site.py`: portada `output/index.html`.

Todo se cachea en `data/cache/`.

## Servicio web

`output/` es publicable tal cual (HTML estático + GeoTIFF/CSV) y se sirve en <https://asensio94.github.io/riesgo-tendidos-aves/>.

GitHub Pages está en **modo Actions** (`build_type=workflow`): el sitio lo publica directamente el flujo de trabajo, sin
rama intermedia.

- `.github/workflows/monthly.yml` recalcula todas las regiones el día 2 de cada mes y despliega `output/` con
  `actions/deploy-pages`. También se puede lanzar a mano:

  ```bash
  gh workflow run monthly.yml -R Asensio94/riesgo-tendidos-aves
  ```

- La caché de descargas (GBIF, OSM, terreno) se conserva entre ejecuciones con `actions/cache`, así que una ejecución
  normal solo vuelve a bajar lo que ha cambiado.
- **Movebank queda fuera del flujo de trabajo**: son descargas de cientos de MB con cortes frecuentes, que no encajan en
  un runner. Los resultados que incorporan GPS solo existen si se calculan en local. En el Estrecho Movebank aporta
  ~300 000 posiciones de milano negro y ~65 000 de cigüeña blanca; en Cantabria los datasets publicados no llegan
  (5 posiciones de abejero), así que allí el mapa se apoya solo en citas.
- `tools/publish.sh` empaqueta `output/` y lo sube a la rama `gh-pages`. Solo sirve si se devuelve Pages al modo
  clásico; con el modo Actions activo la rama `gh-pages` se ignora.

## Limitaciones

- La cobertura de OSM de apoyos y voltajes es desigual; por eso se estima el número de apoyos donde no están mapeados.
- Las citas tienen sesgo de observador (carreteras, miradores, hotspots). La corrección por esfuerzo lo atenúa, no lo elimina.
- No hay altura de vuelo en los datos de citas; solo en algunos datasets GPS.
- El índice es relativo a la región analizada, no una probabilidad de mortalidad. Sirve para priorizar, no para certificar.

## Próximos pasos

- Conseguir la clave de eBird Status & Trends y cargar los GeoTIFF de las especies del catálogo (el cargador ya existe).
- Validar el ranking con el shapefile de tendidos peligrosos del Gobierno Vasco (región `euskadi`) y, cuando haya puntos de
  mortalidad, calibrar los pesos por especie.
- Peligrosidad del apoyo con datos de las eléctricas (catastros de armados y aisladores); OSM solo cubre ~11 % de los apoyos.
- Servicio web: región a demanda, descarga por operador y avisos cuando un elemento suba de índice entre meses.
- En el observatorio de alegaciones, mostrar el índice de `score` junto a cada anuncio de eólica o red eléctrica.
