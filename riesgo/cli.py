"""CLI: python -m riesgo.cli run --region estrecho"""
from typing import Optional

import numpy as np
import typer
from rich.console import Console
from rich.table import Table

from . import abundance, config, ebirdst, movebank, osm, report, risk, site, terrain
from . import puntuar as puntuar_mod
from .grid import Grid

app = typer.Typer(add_completion=False, help="Mapa dinámico de riesgo de colisión y electrocución de aves.")
console = Console()
log = console.print


def _bbox(region: Optional[str], bbox: Optional[str]):
    if bbox:
        vals = tuple(float(v) for v in bbox.split(","))
        if len(vals) != 4:
            raise typer.BadParameter("bbox debe ser lat_min,lon_min,lat_max,lon_max")
        return vals, f"bbox {bbox}", None
    reg = config.REGIONES.get(region or "estrecho")
    if not reg:
        raise typer.BadParameter(f"región desconocida; usa una de {list(config.REGIONES)} o --bbox")
    return tuple(reg["bbox"]), reg["nombre"], reg.get("especies")


@app.command()
def regiones():
    """Lista las regiones predefinidas."""
    for k, v in config.REGIONES.items():
        log(f"[bold]{k}[/]: {v['nombre']} {v['bbox']}")


@app.command()
def especies():
    """Lista las especies y sus pesos."""
    t = Table("Especie", "Nombre", "Electrocución", "Col. líneas", "Col. aerogen.", "Estatus")
    for sp, c in config.ESPECIES.items():
        t.add_row(sp, c["nombre"], str(c["electro"]), str(c["col_lin"]), str(c["col_aer"]), str(c["estatus"]))
    console.print(t)


@app.command()
def run(
    region: Optional[str] = typer.Option("estrecho", help="Región predefinida (ver `regiones`)."),
    bbox: Optional[str] = typer.Option(None, help="lat_min,lon_min,lat_max,lon_max (sustituye a --region)."),
    especie: Optional[list[str]] = typer.Option(None, "--especie", "-e", help="Nombre científico; repetible. Por defecto todas."),
    con_movebank: bool = typer.Option(False, "--movebank", help="Descargar seguimiento GPS del Movebank Data Repository (ficheros grandes)."),
    study_id: Optional[list[int]] = typer.Option(None, help="IDs de estudios Movebank a incluir (públicos o con credenciales)."),
    top: int = typer.Option(100, help="Nº de elementos en el ranking del mapa."),
    mes: Optional[int] = typer.Option(None, help="Mes (1-12) mostrado por defecto en el mapa."),
    force_osm: bool = typer.Option(False, help="Volver a descargar OSM ignorando la caché."),
    salida: Optional[str] = typer.Option(None, help="Carpeta de salida (por defecto output/<region>)."),
):
    """Genera el mapa de riesgo, el informe y las exportaciones para una región."""
    box, nombre, especies_region = _bbox(region, bbox)
    grid = Grid.from_bbox(box)
    out = config.OUTPUT_DIR / (salida or (region if not bbox else "bbox"))
    out.mkdir(parents=True, exist_ok=True)
    log(f"[bold]{nombre}[/] · malla {grid.ny}×{grid.nx} celdas de {grid.res}° (~{grid.dx_m:.0f}×{grid.dy_m:.0f} m)")

    log("[cyan]1/5[/] Infraestructura OSM (Overpass)…")
    infra = osm.obtener_infraestructura(box, force=force_osm)
    res_infra = osm.resumen(infra)
    log(f"  {res_infra}")
    expo = osm.capas_exposicion(infra, grid)

    log("[cyan]2/5[/] Topografía (AWS Terrain Tiles)…")
    topo = terrain.capas_topografia(box, grid)
    factores = terrain.factores_topograficos(topo)
    log(f"  elevación {topo['elevacion'].min():.0f}-{topo['elevacion'].max():.0f} m, pendiente media {topo['pendiente'].mean():.1f}°")

    log("[cyan]3/5[/] Abundancia estacional (GBIF/eBird)…")
    esf = abundance.esfuerzo_mensual(box, log=log)
    esf_r = abundance.raster_esfuerzo(esf, grid)
    lista = especie or especies_region or config.ESPECIES_DEFECTO
    presencias, info = {}, {}
    for sp in lista:
        if sp not in config.ESPECIES:
            log(f"  [yellow]{sp} no está en config.ESPECIES; se usan pesos neutros 0.5[/]")
            config.ESPECIES[sp] = dict(nombre=sp, electro=0.5, col_lin=0.5, col_aer=0.5, estatus=0.5)
        P, n = abundance.presencia_mensual(sp, box, grid, esf_r, log=log)
        S = ebirdst.presencia_mensual(sp, grid, log=log)  # None si no hay GeoTIFF de eBird Status & Trends
        if S is not None:
            P = S if P is None else (1 - config.PESO_EBIRDST) * P + config.PESO_EBIRDST * S
        info[sp] = dict(nombre=config.ESPECIES[sp]["nombre"], citas_gbif=n, posiciones_movebank=0,
                        ebirdst=S is not None, incluida=P is not None)
        if P is not None:
            presencias[sp] = P
    if not presencias:
        log("[red]Ninguna especie con datos suficientes en la zona.[/]")
        raise typer.Exit(1)

    log("[cyan]4/5[/] Seguimiento GPS (Movebank)…" if (con_movebank or study_id) else "[cyan]4/5[/] Movebank omitido (usa --movebank o --study-id)")
    if con_movebank or study_id:
        for sp in list(presencias):
            U, n = movebank.seguimiento_especie(sp, box, grid, usar_repo=con_movebank, study_ids=study_id or (), log=log)
            info[sp]["posiciones_movebank"] = n
            if U is not None:
                # el peso del GPS crece con el nº de posiciones: 5 posiciones de paso no deben mover el mapa
                w = config.PESO_MOVEBANK * min(1.0, n / config.MOVEBANK_N_REF)
                presencias[sp] = (1 - w) * presencias[sp] + w * U
                log(f"  {sp}: {n} posiciones GPS en la zona, mezcladas al {int(w * 100)} %")

    log("[cyan]5/5[/] Modelo de riesgo y salidas…")
    confianza = {sp: 1.0 if info[sp].get("ebirdst") else
                 max(min(1.0, info[sp]["citas_gbif"] / config.CITAS_CONFIANZA),
                     min(1.0, info[sp]["posiciones_movebank"] / config.MOVEBANK_N_REF))
                 for sp in presencias}
    for sp in presencias:
        info[sp]["confianza"] = round(confianza[sp], 2)
    resultado = risk.calcular(presencias, expo, factores, config.ESPECIES, confianza=confianza)
    ranking = risk.ranking_elementos(resultado, infra, grid)
    tabla = risk.tabla_estacional(resultado)

    m = report.mapa(resultado, infra, ranking, grid, nombre, top=top, mes_inicial=mes)
    m.save(str(out / "mapa.html"))
    ranking.to_csv(out / "ranking_elementos.csv", index=False, encoding="utf-8")
    report.exportar_geojson(out / "ranking_elementos.geojson", ranking)
    report.exportar_geotiff(out / "riesgo_total.tif", resultado["total"], grid, config.MESES)
    for k in risk.MECANISMOS:
        report.exportar_geotiff(out / f"riesgo_{k}.tif", resultado["agregado"][k], grid, config.MESES)
    report.exportar_geotiff(out / "topografia.tif", np.stack([topo["elevacion"], topo["pendiente"], topo["tpi"]]), grid,
                            ["elevacion_m", "pendiente_deg", "tpi_m"])
    report.informe(out / "informe.html", "mapa.html", nombre, box, res_infra, info, tabla, ranking)
    site.indice(config.OUTPUT_DIR)

    console.print(tabla.round(0).astype(int))
    if not ranking.empty:
        t = Table("#", "tipo", "mecanismo", "riesgo", "mes", "especies", "OSM")
        for i, r in ranking.head(15).iterrows():
            t.add_row(str(i + 1), r.tipo, r.mecanismo, f"{r.riesgo_max:.0f}", r.mes_pico, str(r.especies)[:60], str(r.osm_id))
        console.print(t)
    log(f"[green]Listo:[/] {out / 'informe.html'}")


@app.command()
def indice():
    """Regenera output/index.html con enlaces a todas las regiones calculadas (portada del servicio web)."""
    log(f"[green]Portada:[/] {site.indice(config.OUTPUT_DIR)}")


@app.command()
def puntuar(
    region: str = typer.Option("cantabria", help="Región cuyos rásteres (output/<region>/riesgo_*.tif) se usan."),
    geojson: Optional[str] = typer.Option(None, help="FeatureCollection GeoJSON de polígonos (proyectos) a puntuar."),
    observatorio: Optional[str] = typer.Option(None, help="Raíz del observatorio de alegaciones: usa data/estado.json y su caché de municipios."),
    categoria: Optional[list[str]] = typer.Option(None, help="Filtrar anuncios del observatorio por categoría (eolica, red_electrica…); repetible."),
    salida: Optional[str] = typer.Option(None, help="CSV de salida (por defecto output/<region>/proyectos_puntuados.csv)."),
):
    """Asigna el índice de riesgo a proyectos (polígonos): media y máximo mensual sobre los rásteres de una región."""
    import json
    from pathlib import Path

    carpeta = config.OUTPUT_DIR / region
    if not (carpeta / "riesgo_total.tif").exists():
        raise typer.BadParameter(f"no hay rásteres en {carpeta}; ejecuta antes `run --region {region}`")
    if geojson:
        feats = json.loads(Path(geojson).read_text(encoding="utf-8"))
    elif observatorio:
        raiz = Path(observatorio)
        feats = puntuar_mod.features_observatorio(raiz / "data" / "estado.json", raiz / "data" / "cache" / "geo",
                                                  categorias=categoria or None)
        log(f"  {len(feats['features'])} anuncios geolocalizados con polígono")
    else:
        raise typer.BadParameter("indica --geojson o --observatorio")
    df = puntuar_mod.puntuar(feats, carpeta)
    destino = Path(salida) if salida else carpeta / "proyectos_puntuados.csv"
    df.to_csv(destino, index=False, encoding="utf-8")
    t = Table("proyecto", "categoría", "km²", "riesgo medio", "riesgo máx", "mes pico", "% celdas con infra")
    for r in df.itertuples():
        t.add_row(str(getattr(r, "titulo", getattr(r, "id", "")))[:70], str(getattr(r, "categoria", "")),
                  str(getattr(r, "area_km2", "")), str(r.riesgo_medio), str(r.riesgo_max), str(r.mes_pico),
                  str(r.pct_celdas_con_infra))
    console.print(t)
    log(f"[green]Guardado:[/] {destino}")


if __name__ == "__main__":
    app()
