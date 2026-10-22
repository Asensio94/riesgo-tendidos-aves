"""French infrastructure: Enedis distribution network merged with OSM, clipped to French territory.

OSM is the base everywhere (transmission lines, wind turbines, pylon tags). In France it is completed with the open
data of Enedis, the distribution operator for ~95 % of the mainland: its overhead HTA (medium-voltage) lines and the
position of its poles. The poles file is far from complete (in the Grands Causses about one HTA pole every 160 m of
line, where spans are 80-100 m), so OSM pylons with no Enedis twin fill the gaps; `risk` takes the larger of the
mapped and the estimated number of pylons per cell, so the union never counts a span twice. The merge keeps one copy
of each element:

- an OSM distribution line that runs along Enedis HTA for at least OVERLAP_SHARE of its length is the same line and
  is dropped; the rest (local distributors such as SICAE, or lines Enedis does not have) stays;
- an Enedis pole within HTA_POLE_MAX_M of an HTA line is an HTA pole; the others carry low voltage and are left out;
- an OSM pylon within POLE_MATCH_M of an Enedis pole is the same pylon: the Enedis pole takes its hazard tags and the
  OSM copy is dropped; OSM pylons tagged below 1 kV are low voltage and left out too.

Every element outside the French departments that intersect the region (e.g. the Spanish side of the Pyrenees) is
clipped away, since the Spanish side has no Enedis data and would be undercounted.
"""
import hashlib
import json
import time

import numpy as np
import requests
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely import STRtree, contains_xy, points, prepare
from shapely.geometry import LineString, shape
from shapely.ops import transform, unary_union

from . import config

CACHE = config.CACHE_DIR / "france"
CACHE.mkdir(parents=True, exist_ok=True)


def _cache_path(kind, bbox):
    h = hashlib.md5(json.dumps([kind, bbox]).encode()).hexdigest()[:10]
    return CACHE / f"{kind}_{h}.json"


def _get(url, params=None):
    last = None
    for attempt in range(5):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": config.USER_AGENT}, timeout=120)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def enedis_rows(dataset, bbox, select, force=False):
    """All rows of an Enedis dataset inside the bbox (lat_min, lon_min, lat_max, lon_max), following the cursor."""
    p = _cache_path(dataset, bbox)
    if p.exists() and not force:
        return json.loads(p.read_text(encoding="utf-8"))
    lat_min, lon_min, lat_max, lon_max = bbox
    url = config.ENEDIS_API.format(dataset=dataset)
    params = {"bbox": f"{lon_min},{lat_min},{lon_max},{lat_max}", "size": config.ENEDIS_PAGE, "select": select}
    rows = []
    while url:
        page = _get(url, params)
        rows += page.get("results", [])
        url, params = page.get("next"), None  # `next` carries every parameter plus the cursor
    p.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def territory(bbox, force=False):
    """Union of the French departments (IGN Admin Express) that intersect the bbox, in WGS84."""
    p = _cache_path("departements", bbox)
    if p.exists() and not force:
        data = json.loads(p.read_text(encoding="utf-8"))
    else:
        lat_min, lon_min, lat_max, lon_max = bbox
        data = _get(config.FR_DEPARTMENTS_WFS.format(lon_min=lon_min, lat_min=lat_min, lon_max=lon_max,
                                                     lat_max=lat_max))
        if not data.get("features"):
            raise RuntimeError("IGN returned no department for the bbox")
        p.write_text(json.dumps(data), encoding="utf-8")
    return unary_union([shape(f["geometry"]) for f in data["features"]]).buffer(0)


def _metric(bbox):
    """Projection to metres local to the region (azimuthal equidistant at its centre): forward (lon, lat) -> (x, y)
    and back."""
    lat0 = (bbox[0] + bbox[2]) / 2
    lon0 = (bbox[1] + bbox[3]) / 2
    crs = f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +units=m +ellps=WGS84"
    return (Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform,
            Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform)


def enedis_infrastructure(bbox, force=False):
    """Overhead HTA lines and every pole (HTA and BT) of Enedis inside the bbox."""
    lines = []
    for row in enedis_rows(config.ENEDIS_HTA, bbox, "geometry,_id", force=force):
        geom = row.get("geometry")
        geom = json.loads(geom) if isinstance(geom, str) else geom
        if not geom:
            continue
        parts = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
        for i, coords in enumerate(parts):
            if len(coords) < 2:
                continue
            lines.append({
                "id": f"{row['_id']}" + (f"-{i}" if len(parts) > 1 else ""), "source": "enedis",
                "power": "line", "voltage": None, "category": "distribution", "operator": "Enedis", "name": "HTA",
                "coords": [(float(x), float(y)) for x, y in coords],
            })
    poles = []
    for row in enedis_rows(config.ENEDIS_POLES, bbox, "_geopoint,_id", force=force):
        try:
            lat, lon = (float(v) for v in row["_geopoint"].split(","))
        except (KeyError, ValueError):
            continue
        poles.append({"id": row["_id"], "lat": lat, "lon": lon})
    return lines, poles


def _line_overlap(geom, index, hta, buffer_m):
    """Share of `geom`'s length that lies within `buffer_m` of any HTA line."""
    if geom.length == 0:
        return 0.0
    near = index.query(geom.buffer(buffer_m))
    if len(near) == 0:
        return 0.0
    corridor = unary_union([hta[i] for i in near]).buffer(buffer_m)
    return geom.intersection(corridor).length / geom.length


def merge(osm_infra, enedis_lines, enedis_poles, bbox, land=None):
    """Combine OSM and Enedis as described in the module docstring; `land` (WGS84 polygon) clips everything."""
    to_m, to_deg = _metric(bbox)
    land_m = transform(to_m, land) if land is not None else None
    if land_m is not None:
        prepare(land_m)

    def inside(lon, lat):
        """Mask of the points (arrays of lon, lat) on French territory."""
        if land_m is None:
            return np.ones(len(lon), bool)
        x, y = to_m(np.asarray(lon, float), np.asarray(lat, float))
        return contains_xy(land_m, x, y)

    def clip_line(ln):
        """The line, or the pieces of it on French territory (same id: they are still the same source line)."""
        if land_m is None:
            return [ln]
        g = LineString([to_m(x, y) for x, y in ln["coords"]])
        if land_m.contains(g):
            return [ln]
        cut = g.intersection(land_m)
        parts = [cut] if cut.geom_type == "LineString" else list(getattr(cut, "geoms", []))
        return [{**ln, "coords": [to_deg(x, y) for x, y in p.coords]}
                for p in parts if p.geom_type == "LineString" and len(p.coords) >= 2 and p.length > 0]

    hta_lines = [part for ln in enedis_lines for part in clip_line(ln)]
    hta_m = [LineString([to_m(x, y) for x, y in ln["coords"]]) for ln in hta_lines]
    hta_index = STRtree(hta_m) if hta_m else None

    lines = []
    for ln in osm_infra["lines"]:
        for part in clip_line(ln):
            if part["category"] == "distribution" and hta_index is not None:
                g = LineString([to_m(x, y) for x, y in part["coords"]])
                if _line_overlap(g, hta_index, hta_m, config.OVERLAP_M) >= config.OVERLAP_SHARE:
                    continue  # already in Enedis
            lines.append(part)
    lines += hta_lines

    # Enedis poles on an HTA line; the rest carry low voltage
    pole_xy = np.array([to_m(p["lon"], p["lat"]) for p in enedis_poles]).reshape(-1, 2)
    hta_poles = []
    if len(pole_xy) and hta_index is not None:
        near = hta_index.query(points(pole_xy), predicate="dwithin", distance=config.HTA_POLE_MAX_M)
        on_hta = np.zeros(len(pole_xy), bool)
        on_hta[np.unique(near[0])] = True
        on_hta &= inside([p["lon"] for p in enedis_poles], [p["lat"] for p in enedis_poles])
        hta_poles = [(p, xy) for p, xy, ok in zip(enedis_poles, pole_xy, on_hta) if ok]

    # OSM pylons: hand their tags to the Enedis pole they coincide with, otherwise keep them
    pyl = osm_infra["pylons"]
    osm_pylons = [a for a, ok in zip(pyl, inside([a["lon"] for a in pyl], [a["lat"] for a in pyl])) if ok]
    all_tree = cKDTree(pole_xy) if len(pole_xy) else None
    osm_xy = np.array([to_m(a["lon"], a["lat"]) for a in osm_pylons]).reshape(-1, 2)
    osm_tree = cKDTree(osm_xy) if len(osm_xy) else None
    pylons = []
    for p, xy in hta_poles:
        twin = None
        if osm_tree is not None:
            d, j = osm_tree.query(xy, distance_upper_bound=config.POLE_MATCH_M)
            if np.isfinite(d):
                twin = osm_pylons[j]
        pylons.append({
            "id": p["id"], "source": "enedis", "lat": p["lat"], "lon": p["lon"],
            "type": twin["type"] if twin else "pole", "voltage": None, "category": "distribution",
            "material": twin["material"] if twin else None, "design": twin["design"] if twin else None,
            "operator": "Enedis", "hazard": twin["hazard"] if twin else 1.0,
            "hazard_why": twin.get("hazard_why", "") if twin else "", "tagged": bool(twin and twin["tagged"]),
        })
    for a, xy in zip(osm_pylons, osm_xy):
        if all_tree is not None and np.isfinite(all_tree.query(xy, distance_upper_bound=config.POLE_MATCH_M)[0]):
            continue  # same pylon as an Enedis pole (an HTA one, already kept, or a BT one, left out)
        if a.get("voltage") and a["voltage"] < config.LOW_VOLTAGE_MAX_V:
            continue  # low voltage, left out as Enedis' BT poles are
        pylons.append(a)

    tur = osm_infra["turbines"]
    turbines = [t for t, ok in zip(tur, inside([t["lon"] for t in tur], [t["lat"] for t in tur])) if ok]
    return {"lines": lines, "pylons": pylons, "turbines": turbines,
            "enedis": {"hta_lines": len(hta_lines), "poles": len(enedis_poles), "hta_poles": len(hta_poles)}}


def complete(osm_infra, bbox, force=False):
    """OSM infrastructure of a French region merged with Enedis and clipped to French territory."""
    lines, poles = enedis_infrastructure(bbox, force=force)
    return merge(osm_infra, lines, poles, bbox, land=territory(bbox, force=force))
