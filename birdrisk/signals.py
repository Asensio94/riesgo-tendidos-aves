"""Signals for Estado de las IBA: `output/signals.json`, in the common format of the sibling projects.

Estado de las IBA (https://asensio94.github.io/estado-iba/) gathers what every sibling project knows about each
Natura 2000 site. This project's fact is how many high-risk elements of each modelled region (the top
`HIGH_RISK_SHARE` of risk_max within the region) fall inside each site. Only the counts are published: where each
pylon, span or turbine stands, its OSM id and its species stay in the region's own ranking files.

Version 2 of the common format adds the country of each signal ("ES" or "FR"); the French sites are told apart by
their SITECODE (FR…), and the titles stay in Spanish, the hub's language.
"""
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from shapely import STRtree, box, make_valid, unary_union
from shapely.geometry import Point, shape

from . import config, site_pages

SOURCE = "riesgo-tendidos-aves"
# How the coverage label names each region, in Spanish ("Cantabria y el Estrecho")
SHORT_NAMES = {"estrecho": "el Estrecho", "tarifa": "Tarifa y La Janda", "cantabria": "Cantabria",
               "monfrague": "Monfragüe", "gallocanta": "Gallocanta", "crau": "la Crau", "camargue": "la Camarga",
               "causses": "los Grands Causses", "pyrenees": "el Pirineo francés", "champagne": "la Champaña húmeda"}
NOTE = ("Riesgo de colisión y electrocución de cada aerogenerador, apoyo y tramo de línea de OpenStreetMap (y, en "
        "Francia, de la red de distribución de Enedis), modelado cada mes.")
VERSION = 2
# How a title names each element type of the ranking, wind turbines first: they are the main point.
ELEMENTS = (("turbine", "aerogenerador", "aerogeneradores"), ("pylon", "apoyo", "apoyos"),
            ("line", "tramo de línea", "tramos de línea"))


def polygonal(geometry):
    """A valid areal shape from a GeoJSON geometry.

    Simplified to ~300 m, some rings of the Natura layer cross themselves and some small parts collapse into lines or
    single points. Each part is repaired on its own and only areas are kept: GEOS 3.14 refuses to repair a
    MultiPolygon with a part collapsed into a point, which older versions let through.
    """
    g = shape(geometry)
    fixed = [make_valid(p) for p in getattr(g, "geoms", [g])]
    return unary_union([q for p in fixed for q in getattr(p, "geoms", [p])
                        if q.geom_type in ("Polygon", "MultiPolygon")])


def site_shapes(natura):
    """{SITECODE: shape} of every Natura 2000 site (ZEPA and ZEC) in the layer."""
    return {f["properties"]["codigo"]: polygonal(f["geometry"]) for f in natura["features"]}


def elements(count):
    """A count by element type in one Spanish phrase, wind turbines first: "3 aerogeneradores, 40 apoyos y 1 tramo
    de línea". A type the ranking does not write today still counts, as "otros elementos"."""
    known = [(count.get(t, 0), one, many) for t, one, many in ELEMENTS]
    known.append((sum(count.values()) - sum(n for n, _, _ in known), "otro elemento", "otros elementos"))
    parts = [f"{n} {one if n == 1 else many}" for n, one, many in known if n]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " y " + parts[-1]


def coverage_label(regions):
    """The modelled regions in one Spanish phrase, in key order: "Cantabria y el Estrecho"."""
    names = [SHORT_NAMES.get(k, config.region_name(k, "es")) for k in sorted(regions)]
    label = names[-1] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]
    return label[:1].upper() + label[1:]


def high_risk_inside(regions, shapes, share=config.HIGH_RISK_SHARE):
    """The sites each region's elements could reach and its high-risk elements inside each site.

    High risk is the top `share` of risk_max within the region. Returns (watched site codes, {(region, code): rows});
    the watched sites are every site that touches the bounding box of a region's scored elements.
    """
    codes = list(shapes)
    tree = STRtree([shapes[c] for c in codes])
    watched, inside = set(), {}
    for region, (rows, _day) in sorted(regions.items()):
        rows = [r for r in rows if r.get("risk_max") not in (None, "")]
        if not rows:
            continue
        lons, lats = [float(r["lon"]) for r in rows], [float(r["lat"]) for r in rows]
        watched |= {codes[i] for i in tree.query(box(min(lons), min(lats), max(lons), max(lats)), predicate="intersects")}
        cut = sorted(float(r["risk_max"]) for r in rows)[int(len(rows) * (1 - share))]
        for r in rows:
            if float(r["risk_max"]) >= cut:
                for i in tree.query(Point(float(r["lon"]), float(r["lat"])), predicate="intersects"):
                    inside.setdefault((region, codes[i]), []).append(r)
    return watched, inside


def site_page(region, code, lang=None):
    """Path, under the web root, of the page listing one site's high-risk elements (see `site_pages`); by default
    in the language of the region's country."""
    return f"{region}/sites/{code}.{lang or config.region_langs(region)[0]}.html"


def build(regions, shapes, generated, share=config.HIGH_RISK_SHARE):
    """The signals.json document from {region: (ranking rows, date)} and {SITECODE: shape}.

    Every site holding high-risk elements of a region gets one signal with their count by type, drawn at a point inside the
    site and never at an element. Its link is the site's own page, which shows exactly those elements.
    """
    watched, inside = high_risk_inside(regions, shapes, share)
    signals = []
    for (region, code), rows in inside.items():
        kinds = Counter(r.get("type") for r in rows)
        p = shapes[code].representative_point()  # the count belongs to the site, not to any one pylon
        signals.append({
            "id": f"{region}-{code}", "kind": "power_line", "country": config.region_country(region),
            "date": regions[region][1],
            "title": f"{elements(kinds)} de riesgo alto para las aves dentro del espacio",
            "url": config.WEB_URL + site_page(region, code), "sites": [{"code": code}], "municipalities": [],
            "precision": "punto", "deadline": None, "status": None, "value": {"amount": len(rows), "unit": "elementos"},
            "details": {"region": region, "point": [round(p.x, 4), round(p.y, 4)]}})
    return {"source": SOURCE, "version": VERSION, "generated": generated.strftime("%Y-%m-%dT%H:%MZ"),
            "coverage": {"label": coverage_label(regions), "sites": sorted(watched), "note": NOTE},
            "signals": sorted(signals, key=lambda s: (s["date"], s["id"]))}


def region_rows(folder):
    """Ranking rows of one computed region and the day (UTC) its model output was written."""
    path = Path(folder) / "ranking_elements.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows, datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()


def download_natura(regions=()):
    """The Natura 2000 layer (GeoJSON) as published by Vigía de incendios, plus the French sites around the French
    `regions` straight from the European Environment Agency, with the same properties (codigo, nombre, tipo)."""
    r = requests.get(config.NATURA_URL, headers={"User-Agent": config.USER_AGENT}, timeout=120)
    r.raise_for_status()
    natura = r.json()
    french = [config.REGIONS[k]["bbox"] for k in regions if config.region_country(k) == "FR"]
    if french:
        known = {f["properties"]["codigo"] for f in natura["features"]}
        natura["features"] += [f for f in download_natura_eea(french) if f["properties"]["codigo"] not in known]
    return natura


def download_natura_eea(bboxes):
    """French Natura 2000 sites (SPA, SAC or both) that touch any of the bboxes, simplified to ~300 m. One query
    per bbox and layer: an envelope around all of them would span half of France and hit the server's record cap."""
    feats = {}
    for (lat_min, lon_min, lat_max, lon_max), (layer, kind) in (
            (b, lk) for b in bboxes for lk in config.NATURA_EEA_KIND.items()):
        params = {"where": "SITECODE LIKE 'FR%'", "geometry": f"{lon_min},{lat_min},{lon_max},{lat_max}",
                  "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                  "outFields": "SITECODE,SITENAME", "outSR": 4326, "maxAllowableOffset": 0.003, "f": "geojson"}
        r = requests.get(config.NATURA_EEA_URL.format(layer=layer), params=params,
                         headers={"User-Agent": config.USER_AGENT}, timeout=180)
        r.raise_for_status()
        for f in r.json().get("features", []):
            code = f["properties"]["SITECODE"]
            if f.get("geometry"):
                feats[code] = {"type": "Feature", "geometry": f["geometry"],
                               "properties": {"codigo": code, "nombre": f["properties"].get("SITENAME") or code,
                                              "tipo": kind}}
    return list(feats.values())


def write(output_dir=None, natura=None, now=None):
    """Write `signals.json` at the root of the output folder from every computed region, and the page of each site
    it links to, and return its path.

    The file of an earlier run is removed first, so that a failure (no region, Natura layer unavailable) leaves no
    stale signals behind: without the file, Estado de las IBA reads the published rankings itself.
    """
    out = Path(output_dir or config.OUTPUT_DIR)
    path = out / "signals.json"
    path.unlink(missing_ok=True)
    regions = {k: region_rows(out / k) for k in config.REGIONS
               if (out / k / "ranking_elements.csv").exists()
               and any((out / k / f"map.{lang}.html").exists() for lang in config.region_langs(k))}
    if not regions:
        raise FileNotFoundError(f"no computed region in {out}")
    natura = natura or download_natura(regions)
    shapes = site_shapes(natura)
    doc = build(regions, shapes, now or datetime.now(timezone.utc))
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    site_pages.write(out, high_risk_inside(regions, shapes)[1], natura, regions, site_page)
    return path
