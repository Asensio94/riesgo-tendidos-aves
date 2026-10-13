"""Signals for Estado de las IBA: `output/signals.json`, in the common format of the sibling projects.

Estado de las IBA (https://asensio94.github.io/estado-iba/) gathers what every sibling project knows about each
Natura 2000 site. This project's fact is how many high-risk elements of each modelled region (the top
`HIGH_RISK_SHARE` of risk_max within the region) fall inside each site. Only the counts are published: where each
pylon, span or turbine stands, its OSM id and its species stay in the region's own ranking files.
"""
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from shapely import STRtree, box, make_valid, unary_union
from shapely.geometry import Point, shape

from . import config

SOURCE = "riesgo-tendidos-aves"
# How the coverage label names each region, in Spanish ("Cantabria y el Estrecho")
SHORT_NAMES = {"estrecho": "el Estrecho", "tarifa": "Tarifa y La Janda", "cantabria": "Cantabria",
               "monfrague": "Monfragüe", "gallocanta": "Gallocanta"}
NOTE = ("Riesgo de colisión y electrocución de cada aerogenerador, apoyo y tramo de línea de OpenStreetMap, "
        "modelado cada mes.")
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


def build(regions, shapes, generated, share=config.HIGH_RISK_SHARE):
    """The signals.json document from {region: (ranking rows, date)} and {SITECODE: shape}.

    Every site holding high-risk elements of a region gets one signal with their count by type, drawn at a point inside the
    site and never at an element. The coverage is every site that touches the bounding box of a region's elements.
    """
    codes = list(shapes)
    tree = STRtree([shapes[c] for c in codes])
    watched, signals = set(), []
    for region, (rows, day) in sorted(regions.items()):
        rows = [r for r in rows if r.get("risk_max") not in (None, "")]
        if not rows:
            continue
        lons, lats = [float(r["lon"]) for r in rows], [float(r["lat"]) for r in rows]
        bounds = box(min(lons), min(lats), max(lons), max(lats))
        watched |= {codes[i] for i in tree.query(bounds, predicate="intersects")}
        cut = sorted(float(r["risk_max"]) for r in rows)[int(len(rows) * (1 - share))]
        count = {}
        for r in rows:
            if float(r["risk_max"]) >= cut:
                for i in tree.query(Point(float(r["lon"]), float(r["lat"])), predicate="intersects"):
                    count.setdefault(codes[i], Counter())[r.get("type")] += 1
        for code, kinds in count.items():
            n = sum(kinds.values())
            p = shapes[code].representative_point()  # the count belongs to the site, not to any one pylon
            signals.append({
                "id": f"{region}-{code}", "kind": "power_line", "date": day,
                "title": f"{elements(kinds)} de riesgo alto para las aves dentro del espacio",
                "url": f"{config.WEB_URL}{region}/map.es.html", "sites": [{"code": code}], "municipalities": [],
                "precision": "punto", "deadline": None, "status": None, "value": {"amount": n, "unit": "elementos"},
                "details": {"region": region, "point": [round(p.x, 4), round(p.y, 4)]}})
    return {"source": SOURCE, "version": 1, "generated": generated.strftime("%Y-%m-%dT%H:%MZ"),
            "coverage": {"label": coverage_label(regions), "sites": sorted(watched), "note": NOTE},
            "signals": sorted(signals, key=lambda s: (s["date"], s["id"]))}


def region_rows(folder):
    """Ranking rows of one computed region and the day (UTC) its model output was written."""
    path = Path(folder) / "ranking_elements.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows, datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()


def download_natura():
    """The Natura 2000 layer (GeoJSON) as published by Vigía de incendios."""
    r = requests.get(config.NATURA_URL, headers={"User-Agent": config.USER_AGENT}, timeout=120)
    r.raise_for_status()
    return r.json()


def write(output_dir=None, natura=None, now=None):
    """Write `signals.json` at the root of the output folder from every computed region and return its path.

    The file of an earlier run is removed first, so that a failure (no region, Natura layer unavailable) leaves no
    stale signals behind: without the file, Estado de las IBA reads the published rankings itself.
    """
    out = Path(output_dir or config.OUTPUT_DIR)
    path = out / "signals.json"
    path.unlink(missing_ok=True)
    regions = {k: region_rows(out / k) for k in config.REGIONS
               if (out / k / "ranking_elements.csv").exists() and (out / k / "map.es.html").exists()}
    if not regions:
        raise FileNotFoundError(f"no computed region in {out}")
    doc = build(regions, site_shapes(natura or download_natura()), now or datetime.now(timezone.utc))
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path
