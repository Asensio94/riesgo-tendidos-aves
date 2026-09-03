"""Download of power lines, pylons and wind turbines from OpenStreetMap (Overpass)."""
import hashlib
import json
import re
import time

import numpy as np
import requests

from . import config

QUERY = """
[out:json][timeout:{timeout}];
(
  way["power"~"^(line|minor_line)$"]({bbox});
  node["power"~"^(tower|pole|portal|insulator)$"]({bbox});
  node["power"="generator"]["generator:source"="wind"]({bbox});
  way["power"="generator"]["generator:source"="wind"]({bbox});
);
out geom;
"""


def _cache_path(bbox):
    h = hashlib.md5(json.dumps(bbox).encode()).hexdigest()[:10]
    return config.CACHE_DIR / "osm" / f"infra_{h}.json"


def download(bbox, force=False):
    """Raw Overpass JSON for the bbox (lat_min, lon_min, lat_max, lon_max)."""
    p = _cache_path(bbox)
    if p.exists() and not force:
        return json.loads(p.read_text(encoding="utf-8"))
    q = QUERY.format(timeout=config.OVERPASS_TIMEOUT, bbox=",".join(f"{v:.5f}" for v in bbox))
    last = None
    for url in config.OVERPASS_URLS:
        for _ in range(2):
            try:
                r = requests.post(url, data={"data": q}, headers={"User-Agent": config.USER_AGENT},
                                  timeout=config.OVERPASS_TIMEOUT + 30)
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                    data = r.json()
                    p.write_text(json.dumps(data), encoding="utf-8")
                    return data
                last = f"{url}: HTTP {r.status_code}"
            except requests.RequestException as e:
                last = f"{url}: {e}"
            time.sleep(3)
    raise RuntimeError(f"Overpass unavailable: {last}")


def parse_voltage(tags):
    """Highest voltage (V) declared in the 'voltage' tag; None when absent."""
    v = tags.get("voltage")
    if not v:
        return None
    vals = [int(float(x)) for x in re.findall(r"\d+(?:\.\d+)?", v)]
    return max(vals) if vals else None


def line_category(tags):
    """'distribution' (≤66 kV, electrocution risk), 'transmission' (>66 kV) or 'unknown'."""
    v = parse_voltage(tags)
    if v is not None:
        return "distribution" if v <= config.ELECTROCUTION_MAX_V else "transmission"
    if tags.get("power") == "minor_line":
        return "distribution"
    return "unknown"


def pylon_hazard(tags):
    """Electrocution hazard factor 0.5-2 from the pylon's OSM tags (criteria of the annex to Spanish Royal
    Decree 1432/2008 and of the Spanish Libro Blanco de la Electrocución). No tags -> 1.0 (unknown)."""
    f = 1.0
    material = (tags.get("material") or "").lower()
    if "wood" in material:
        f *= 0.5  # wood: not earthed, the bird has to bridge two conductors
    elif material:
        f *= 1.1  # steel or reinforced concrete: earthed structure
    attachment = (tags.get("line_attachment") or "").lower()
    if "pin" in attachment:
        f *= 1.5  # pin insulator: conductor above the cross-arm, the deadliest arrangement
    elif "anchor" in attachment:
        f *= 1.3  # anchor: slack jumpers above the cross-arm
    elif "suspension" in attachment:
        f *= 0.9  # suspension: conductor hanging below the cross-arm
    management = (tags.get("line_management") or "").lower()
    if any(k in management for k in ("branch", "split", "transition", "termination", "cross")):
        f *= 1.3  # branches, sectionalisers, transitions to underground, line ends: more live hardware
    design = (tags.get("design") or "").lower()
    if design in ("h-frame", "one-level", "flag", "asymmetric"):
        f *= 1.1  # wide horizontal cross-arms: comfortable perches right next to the conductors
    if tags.get("power") == "portal":
        f *= 1.3
    return round(min(max(f, 0.5), 2.0), 2)


def parse(data):
    """Split the Overpass elements into lines, pylons and wind turbines, with derived attributes."""
    lines, pylons, turbines = [], [], []
    voltage_by_node = {}
    for e in data["elements"]:
        tags = e.get("tags", {})
        if e["type"] == "way" and tags.get("power") in ("line", "minor_line"):
            geom = e.get("geometry") or []
            if len(geom) < 2:
                continue
            cat = line_category(tags)
            v = parse_voltage(tags)
            lines.append({
                "id": e["id"], "power": tags["power"], "voltage": v, "category": cat,
                "operator": tags.get("operator"), "name": tags.get("name"),
                "coords": [(g["lon"], g["lat"]) for g in geom],
            })
            for n in e.get("nodes", []):
                prev = voltage_by_node.get(n)
                if prev is None or (v is not None and (prev[0] is None or v > prev[0])):
                    voltage_by_node[n] = (v, cat)
    for e in data["elements"]:
        tags = e.get("tags", {})
        if tags.get("generator:source") == "wind":
            if e["type"] == "node":
                lat, lon = e["lat"], e["lon"]
            else:
                geom = e.get("geometry") or []
                if not geom:
                    continue
                lat = float(np.mean([g["lat"] for g in geom]))
                lon = float(np.mean([g["lon"] for g in geom]))
            turbines.append({
                "id": e["id"], "lat": lat, "lon": lon,
                "power_output": tags.get("generator:output:electricity"),
                "height": tags.get("height"), "operator": tags.get("operator"), "name": tags.get("name"),
            })
        elif e["type"] == "node" and tags.get("power") in ("tower", "pole", "portal", "insulator"):
            v, cat = voltage_by_node.get(e["id"], (None, None))
            if cat is None:
                cat = "distribution" if tags.get("power") == "pole" else "unknown"
            pylons.append({
                "id": e["id"], "lat": e["lat"], "lon": e["lon"], "type": tags["power"],
                "voltage": v, "category": cat, "material": tags.get("material"),
                "design": tags.get("design"), "operator": tags.get("operator"),
                "hazard": pylon_hazard(tags),
                "tagged": any(k in tags for k in ("material", "line_attachment", "line_management", "design")),
            })
    return {"lines": lines, "pylons": pylons, "turbines": turbines}


def get_infrastructure(bbox, force=False):
    return parse(download(bbox, force=force))


def _densify(coords, step_deg):
    """Points along a polyline every `step_deg` degrees, each with the line length (km) it represents."""
    pts, weights = [], []
    lat0 = np.mean([c[1] for c in coords])
    kx = 111.32 * np.cos(np.radians(lat0))
    ky = 111.32
    for (x1, y1), (x2, y2) in zip(coords[:-1], coords[1:]):
        dkm = np.hypot((x2 - x1) * kx, (y2 - y1) * ky)
        n = max(1, int(np.ceil(np.hypot(x2 - x1, y2 - y1) / step_deg)))
        for i in range(n):
            t = (i + 0.5) / n
            pts.append((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
            weights.append(dkm / n)
    return pts, weights


def exposure_layers(infra, grid):
    """Rasterise the infrastructure onto the grid.

    Returns a dict with km of line per category, number of pylons per category and number of wind turbines.
    """
    step = grid.res / 4
    layers = {k: np.zeros(grid.shape) for k in
              ("line_km_total", "line_km_distribution", "line_km_transmission", "line_km_unknown",
               "n_pylons_total", "n_pylons_distribution", "n_pylons_unknown", "n_turbines")}
    for ln in infra["lines"]:
        pts, weights = _densify(ln["coords"], step)
        if not pts:
            continue
        lon, lat = zip(*pts)
        arr = grid.count(np.array(lon), np.array(lat), np.array(weights))
        layers["line_km_total"] += arr
        layers[f"line_km_{ln['category']}"] += arr
    if infra["pylons"]:
        lon = np.array([a["lon"] for a in infra["pylons"]])
        lat = np.array([a["lat"] for a in infra["pylons"]])
        cat = np.array([a["category"] for a in infra["pylons"]])
        hazard = np.array([a["hazard"] for a in infra["pylons"]])
        layers["n_pylons_total"] = grid.count(lon, lat)
        # weighted by hazard: a wooden suspension pylon counts 0.45; an anchor pylon with a branch, 1.7
        d, u = cat == "distribution", cat == "unknown"
        layers["n_pylons_distribution"] = grid.count(lon[d], lat[d], hazard[d])
        layers["n_pylons_unknown"] = grid.count(lon[u], lat[u], hazard[u])
    if infra["turbines"]:
        lon = np.array([a["lon"] for a in infra["turbines"]])
        lat = np.array([a["lat"] for a in infra["turbines"]])
        layers["n_turbines"] = grid.count(lon, lat)
    return layers


def summary(infra):
    km = {}
    for ln in infra["lines"]:
        _, weights = _densify(ln["coords"], 0.01)
        km[ln["category"]] = km.get(ln["category"], 0) + sum(weights)
    return {
        "lines": len(infra["lines"]),
        "km_by_category": {k: round(float(v), 1) for k, v in km.items()},
        "pylons": len(infra["pylons"]),
        "pylons_distribution": sum(a["category"] == "distribution" for a in infra["pylons"]),
        "pylons_tagged": sum(a["tagged"] for a in infra["pylons"]),
        "turbines": len(infra["turbines"]),
    }
