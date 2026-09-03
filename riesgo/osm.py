"""Descarga de tendidos eléctricos, apoyos y aerogeneradores desde OpenStreetMap (Overpass)."""
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


def descargar(bbox, force=False):
    """Devuelve el JSON crudo de Overpass para la bbox (lat_min, lon_min, lat_max, lon_max)."""
    p = _cache_path(bbox)
    if p.exists() and not force:
        return json.loads(p.read_text(encoding="utf-8"))
    q = QUERY.format(timeout=config.OVERPASS_TIMEOUT, bbox=",".join(f"{v:.5f}" for v in bbox))
    ultimo = None
    for url in config.OVERPASS_URLS:
        for _ in range(2):
            try:
                r = requests.post(url, data={"data": q}, headers={"User-Agent": config.USER_AGENT},
                                  timeout=config.OVERPASS_TIMEOUT + 30)
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                    data = r.json()
                    p.write_text(json.dumps(data), encoding="utf-8")
                    return data
                ultimo = f"{url}: HTTP {r.status_code}"
            except requests.RequestException as e:
                ultimo = f"{url}: {e}"
            time.sleep(3)
    raise RuntimeError(f"Overpass no disponible: {ultimo}")


def parse_voltaje(tags):
    """Voltaje máximo (V) declarado en la etiqueta 'voltage'; None si no hay."""
    v = tags.get("voltage")
    if not v:
        return None
    vals = [int(float(x)) for x in re.findall(r"\d+(?:\.\d+)?", v)]
    return max(vals) if vals else None


def categoria_linea(tags):
    """'distribucion' (≤66 kV, riesgo de electrocución), 'transporte' (>66 kV) o 'desconocida'."""
    v = parse_voltaje(tags)
    if v is not None:
        return "distribucion" if v <= config.ELECTROCUCION_MAX_V else "transporte"
    if tags.get("power") == "minor_line":
        return "distribucion"
    return "desconocida"


def peligrosidad_apoyo(tags):
    """Factor 0,5-2 de peligrosidad de electrocución según las etiquetas OSM del apoyo (criterios del anexo del
    RD 1432/2008 y del Libro Blanco de la Electrocución). Sin etiquetas → 1,0 (desconocido)."""
    f = 1.0
    mat = (tags.get("material") or "").lower()
    if "wood" in mat:
        f *= 0.5  # madera: sin puesta a tierra, hace falta tocar dos conductores
    elif mat:
        f *= 1.1  # metal u hormigón armado: estructura puesta a tierra
    att = (tags.get("line_attachment") or "").lower()
    if "pin" in att:
        f *= 1.5  # aislador rígido: conductor sobre la cruceta, el caso más letal
    elif "anchor" in att:
        f *= 1.3  # amarre: puentes flojos por encima de la cruceta
    elif "suspension" in att:
        f *= 0.9  # suspensión: conductor colgado bajo la cruceta
    man = (tags.get("line_management") or "").lower()
    if any(k in man for k in ("branch", "split", "transition", "termination", "cross")):
        f *= 1.3  # derivaciones, seccionamientos, paso a subterráneo, fin de línea: más herrajes en tensión
    des = (tags.get("design") or "").lower()
    if des in ("h-frame", "one-level", "flag", "asymmetric"):
        f *= 1.1  # crucetas horizontales anchas: posaderos cómodos junto a los conductores
    if tags.get("power") == "portal":
        f *= 1.3
    return round(min(max(f, 0.5), 2.0), 2)


def procesar(data):
    """Separa elementos en líneas, apoyos y aerogeneradores con atributos derivados."""
    lineas, apoyos, aerogeneradores = [], [], []
    voltaje_por_nodo = {}
    for e in data["elements"]:
        tags = e.get("tags", {})
        if e["type"] == "way" and tags.get("power") in ("line", "minor_line"):
            geom = e.get("geometry") or []
            if len(geom) < 2:
                continue
            cat = categoria_linea(tags)
            v = parse_voltaje(tags)
            lineas.append({
                "id": e["id"], "power": tags["power"], "voltaje": v, "categoria": cat,
                "operador": tags.get("operator"), "nombre": tags.get("name"),
                "coords": [(g["lon"], g["lat"]) for g in geom],
            })
            for n in e.get("nodes", []):
                prev = voltaje_por_nodo.get(n)
                if prev is None or (v is not None and (prev[0] is None or v > prev[0])):
                    voltaje_por_nodo[n] = (v, cat)
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
            aerogeneradores.append({
                "id": e["id"], "lat": lat, "lon": lon,
                "potencia": tags.get("generator:output:electricity"),
                "altura": tags.get("height"), "operador": tags.get("operator"), "nombre": tags.get("name"),
            })
        elif e["type"] == "node" and tags.get("power") in ("tower", "pole", "portal", "insulator"):
            v, cat = voltaje_por_nodo.get(e["id"], (None, None))
            if cat is None:
                cat = "distribucion" if tags.get("power") == "pole" else "desconocida"
            apoyos.append({
                "id": e["id"], "lat": e["lat"], "lon": e["lon"], "tipo": tags["power"],
                "voltaje": v, "categoria": cat, "material": tags.get("material"),
                "diseno": tags.get("design"), "operador": tags.get("operator"),
                "peligro": peligrosidad_apoyo(tags),
                "etiquetado": any(k in tags for k in ("material", "line_attachment", "line_management", "design")),
            })
    return {"lineas": lineas, "apoyos": apoyos, "aerogeneradores": aerogeneradores}


def obtener_infraestructura(bbox, force=False):
    return procesar(descargar(bbox, force=force))


def _densificar(coords, paso_deg):
    """Puntos a lo largo de una polilínea cada `paso_deg` grados, con la longitud (km) que representa cada uno."""
    pts, pesos = [], []
    lat0 = np.mean([c[1] for c in coords])
    kx = 111.32 * np.cos(np.radians(lat0))
    ky = 111.32
    for (x1, y1), (x2, y2) in zip(coords[:-1], coords[1:]):
        dkm = np.hypot((x2 - x1) * kx, (y2 - y1) * ky)
        n = max(1, int(np.ceil(np.hypot(x2 - x1, y2 - y1) / paso_deg)))
        for i in range(n):
            t = (i + 0.5) / n
            pts.append((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
            pesos.append(dkm / n)
    return pts, pesos


def capas_exposicion(infra, grid):
    """Rasteriza la infraestructura en la malla.

    Devuelve dict con km de línea por categoría, nº de apoyos por categoría y nº de aerogeneradores.
    """
    paso = grid.res / 4
    capas = {k: np.zeros(grid.shape) for k in
             ("km_linea_total", "km_linea_distribucion", "km_linea_transporte", "km_linea_desconocida",
              "n_apoyos_total", "n_apoyos_distribucion", "n_apoyos_desconocida", "n_aerogeneradores")}
    for ln in infra["lineas"]:
        pts, pesos = _densificar(ln["coords"], paso)
        if not pts:
            continue
        lon, lat = zip(*pts)
        arr = grid.contar(np.array(lon), np.array(lat), np.array(pesos))
        capas["km_linea_total"] += arr
        capas[f"km_linea_{ln['categoria']}"] += arr
    if infra["apoyos"]:
        lon = np.array([a["lon"] for a in infra["apoyos"]])
        lat = np.array([a["lat"] for a in infra["apoyos"]])
        cat = np.array([a["categoria"] for a in infra["apoyos"]])
        pel = np.array([a["peligro"] for a in infra["apoyos"]])
        capas["n_apoyos_total"] = grid.contar(lon, lat)
        # ponderados por peligrosidad: un apoyo de madera en suspensión cuenta 0,45; uno de amarre con derivación, 1,7
        d, u = cat == "distribucion", cat == "desconocida"
        capas["n_apoyos_distribucion"] = grid.contar(lon[d], lat[d], pel[d])
        capas["n_apoyos_desconocida"] = grid.contar(lon[u], lat[u], pel[u])
    if infra["aerogeneradores"]:
        lon = np.array([a["lon"] for a in infra["aerogeneradores"]])
        lat = np.array([a["lat"] for a in infra["aerogeneradores"]])
        capas["n_aerogeneradores"] = grid.contar(lon, lat)
    return capas


def resumen(infra):
    km = {}
    for ln in infra["lineas"]:
        _, pesos = _densificar(ln["coords"], 0.01)
        km[ln["categoria"]] = km.get(ln["categoria"], 0) + sum(pesos)
    return {
        "lineas": len(infra["lineas"]),
        "km_por_categoria": {k: round(float(v), 1) for k, v in km.items()},
        "apoyos": len(infra["apoyos"]),
        "apoyos_distribucion": sum(a["categoria"] == "distribucion" for a in infra["apoyos"]),
        "apoyos_con_atributos": sum(a["etiquetado"] for a in infra["apoyos"]),
        "aerogeneradores": len(infra["aerogeneradores"]),
    }
