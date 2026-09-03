"""Modelo de riesgo: presencia de la especie × exposición a la infraestructura × factores topográficos.

Para cada especie s y mes m, sobre cada celda de la malla:

  electro[s,m] = P[s,m] · w_electro[s] · apoyos_eq                      (apoyos de distribución ≤66 kV)
  col_lin[s,m] = P[s,m] · w_col_lin[s] · km_linea · (1 + relieve)         (todos los conductores)
  col_aer[s,m] = P[s,m] · w_col_aer[s] · n_aerogeneradores · (1 + cresta)

P es la presencia relativa 0-1 (GBIF/eBird, mezclada con Movebank si hay), apoyos_eq combina los apoyos
mapeados con una estimación a partir de los km de línea de distribución cuando OSM no tiene los apoyos.
Los índices se reescalan a 0-100 por percentil 99 para que sean comparables entre meses y mecanismos.
"""
import numpy as np
import pandas as pd

from . import config

MECANISMOS = ("electro", "col_lin", "col_aer")
APOYOS_POR_KM = 6.0  # apoyos típicos por km en líneas de distribución cuando OSM no los tiene mapeados


def _escala_100(arr, p=99):
    """Reescala para que el percentil `p` de las celdas con valor sea 100. No se recorta: los valores >100
    (el 1 % más alto) mantienen su orden, lo que permite discriminar dentro del ranking; el mapa los pinta saturados."""
    nz = arr[arr > 0]
    if nz.size == 0:
        return np.zeros_like(arr)
    ref = np.percentile(nz, p)
    return arr / max(ref, 1e-12) * 100.0


def exposicion_base(expo):
    apoyos_map = expo["n_apoyos_distribucion"] + 0.5 * expo["n_apoyos_desconocida"]
    apoyos_est = APOYOS_POR_KM * (expo["km_linea_distribucion"] + 0.5 * expo["km_linea_desconocida"])
    return {
        # tope por celda: decenas de apoyos en ~0,2 km² son una subestación, no un tendido más peligroso
        "apoyos_eq": np.minimum(np.maximum(apoyos_map, apoyos_est), config.APOYOS_MAX_CELDA),
        "km_linea": expo["km_linea_total"],
        "aerogeneradores": expo["n_aerogeneradores"],
    }


def calcular(presencias, expo, factores, especies_cfg, confianza=None):
    """presencias: {especie: array (12, ny, nx)}; confianza: {especie: 0-1} (fiabilidad del mapa de la especie).
    Devuelve dict con capas por especie y agregadas."""
    base = exposicion_base(expo)
    relieve, cresta = factores["relieve"], factores["cresta"]
    confianza = confianza or {}
    por_especie = {}
    agregado = {k: np.zeros_like(next(iter(presencias.values()))) for k in MECANISMOS}
    for sp, P in presencias.items():
        cfg = especies_cfg[sp]
        raw = {
            "electro": P * cfg["electro"] * base["apoyos_eq"][None],
            "col_lin": P * cfg["col_lin"] * base["km_linea"][None] * (1 + relieve)[None],
            "col_aer": P * cfg["col_aer"] * base["aerogeneradores"][None] * (1 + cresta)[None],
        }
        por_especie[sp] = {k: _escala_100(v) for k, v in raw.items()}
        for k in MECANISMOS:
            agregado[k] += cfg["estatus"] * confianza.get(sp, 1.0) * raw[k]
    agregado = {k: _escala_100(v) for k, v in agregado.items()}
    pesos = config.PESO_MECANISMO
    total = sum(pesos[k] * agregado[k] for k in MECANISMOS) / sum(pesos.values())
    total = _escala_100(total)
    for sp in por_especie:
        t = sum(pesos[k] * por_especie[sp][k] for k in MECANISMOS) / sum(pesos.values())
        por_especie[sp]["total"] = _escala_100(t)
    return {"por_especie": por_especie, "agregado": agregado, "total": total, "base": base}


def _celda_de(grid, lon, lat):
    row, col = grid.idx(np.array([lon]), np.array([lat]))
    return int(row[0]), int(col[0])


def _especies_dominantes(resultado, mecanismo, r, c, m, n=3):
    contrib = []
    for sp, capas in resultado["por_especie"].items():
        v = capas[mecanismo][m, r, c]
        if v > 0:
            contrib.append((v, sp))
    contrib.sort(reverse=True)
    return ", ".join(f"{config.ESPECIES.get(sp, {}).get('nombre', sp)}" for _, sp in contrib[:n])


def ranking_elementos(resultado, infra, grid):
    """Puntuación de cada apoyo, aerogenerador y tramo de línea a partir de las celdas que ocupa."""
    filas = []
    agg = resultado["agregado"]
    for a in infra["apoyos"]:
        if a["categoria"] == "transporte":
            continue
        r, c = _celda_de(grid, a["lon"], a["lat"])
        if r < 0:
            continue
        # índice de la celda × peligrosidad propia del apoyo (1,0 si OSM no tiene atributos del apoyo)
        pel = a.get("peligro", 1.0)
        serie = agg["electro"][:, r, c] * pel
        m = int(serie.argmax())
        filas.append(dict(tipo="apoyo", osm_id=a["id"], osm_url=f"https://www.openstreetmap.org/node/{a['id']}",
                          lat=a["lat"], lon=a["lon"], mecanismo="electrocucion", categoria=a["categoria"],
                          voltaje=a["voltaje"], detalle=a["tipo"], operador=a["operador"], peligro=pel,
                          riesgo_max=float(serie.max()), riesgo_medio=float(serie.mean()),
                          mes_pico=config.MESES[m], especies=_especies_dominantes(resultado, "electro", r, c, m)))
    for t in infra["aerogeneradores"]:
        r, c = _celda_de(grid, t["lon"], t["lat"])
        if r < 0:
            continue
        serie = agg["col_aer"][:, r, c]
        m = int(serie.argmax())
        filas.append(dict(tipo="aerogenerador", osm_id=t["id"], osm_url=f"https://www.openstreetmap.org/node/{t['id']}",
                          lat=t["lat"], lon=t["lon"], mecanismo="colision_aerogenerador", categoria="eolico",
                          voltaje=None, detalle=t["potencia"], operador=t["operador"],
                          riesgo_max=float(serie.max()), riesgo_medio=float(serie.mean()),
                          mes_pico=config.MESES[m], especies=_especies_dominantes(resultado, "col_aer", r, c, m)))
    for ln in infra["lineas"]:
        lon = np.array([p[0] for p in ln["coords"]])
        lat = np.array([p[1] for p in ln["coords"]])
        row, col = grid.idx(lon, lat)
        ok = row >= 0
        if not ok.any():
            continue
        celdas = np.unique(row[ok] * grid.nx + col[ok])
        serie = agg["col_lin"].reshape(12, -1)[:, celdas].mean(axis=1)
        m = int(serie.argmax())
        peor = int(agg["col_lin"][m].flat[celdas].argmax())
        r, c = divmod(int(celdas[peor]), grid.nx)
        filas.append(dict(tipo="linea", osm_id=ln["id"], osm_url=f"https://www.openstreetmap.org/way/{ln['id']}",
                          lat=float(lat[ok].mean()), lon=float(lon[ok].mean()), mecanismo="colision_linea",
                          categoria=ln["categoria"], voltaje=ln["voltaje"], detalle=ln["nombre"] or ln["power"],
                          operador=ln["operador"], riesgo_max=float(serie.max()), riesgo_medio=float(serie.mean()),
                          mes_pico=config.MESES[m], especies=_especies_dominantes(resultado, "col_lin", r, c, m)))
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    return df.sort_values("riesgo_max", ascending=False).reset_index(drop=True)


def tabla_estacional(resultado):
    """Media del índice total por especie y mes sobre las celdas con infraestructura."""
    filas = {}
    for sp, capas in resultado["por_especie"].items():
        t = capas["total"]
        con_infra = t.reshape(12, -1).max(axis=0) > 0
        filas[config.ESPECIES.get(sp, {}).get("nombre", sp)] = [
            float(t[m].reshape(-1)[con_infra].mean()) if con_infra.any() else 0.0 for m in range(12)]
    tot = resultado["total"]
    con_infra = tot.reshape(12, -1).max(axis=0) > 0
    filas["TOTAL"] = [float(tot[m].reshape(-1)[con_infra].mean()) if con_infra.any() else 0.0 for m in range(12)]
    return pd.DataFrame(filas, index=config.MESES).T
