"""Command line interface: python -m birdrisk.cli run --region estrecho"""
from typing import Optional

import numpy as np
import typer
from rich.console import Console
from rich.table import Table

from . import abundance, config, ebirdst, movebank, osm, report, risk, score as score_mod, site, terrain
from .grid import Grid

app = typer.Typer(add_completion=False, help="Dynamic collision and electrocution risk map for birds.")
console = Console()
log = console.print


def _bbox(region: Optional[str], bbox: Optional[str]):
    """Resolve the area of interest into (bbox, region key, species list)."""
    if bbox:
        vals = tuple(float(v) for v in bbox.split(","))
        if len(vals) != 4:
            raise typer.BadParameter("bbox must be lat_min,lon_min,lat_max,lon_max")
        return vals, None, None
    key = region or "estrecho"
    reg = config.REGIONS.get(key)
    if not reg:
        raise typer.BadParameter(f"unknown region; use one of {list(config.REGIONS)} or --bbox")
    return tuple(reg["bbox"]), key, reg.get("species")


@app.command()
def regions():
    """List the predefined regions."""
    for k, v in config.REGIONS.items():
        log(f"[bold]{k}[/]: {config.region_name(k, 'en')} {v['bbox']}")


@app.command()
def species():
    """List the species and their weights."""
    t = Table("Scientific name", "Common name", "Electrocution", "Line collision", "Turbine collision", "Status")
    for sp, c in config.SPECIES.items():
        t.add_row(sp, config.species_name(sp, "en"), str(c["electro"]), str(c["col_lin"]), str(c["col_aer"]),
                  str(c["status"]))
    console.print(t)


@app.command()
def run(
    region: Optional[str] = typer.Option("estrecho", help="Predefined region (see `regions`)."),
    bbox: Optional[str] = typer.Option(None, help="lat_min,lon_min,lat_max,lon_max (replaces --region)."),
    species_name: Optional[list[str]] = typer.Option(None, "--species", "-s",
                                                     help="Scientific name; repeatable. Defaults to all."),
    with_movebank: bool = typer.Option(False, "--movebank",
                                       help="Download GPS tracking from the Movebank Data Repository (large files)."),
    study_id: Optional[list[int]] = typer.Option(None, help="Movebank study IDs to include (public or with credentials)."),
    top: int = typer.Option(100, help="Number of elements in the map ranking."),
    month: Optional[int] = typer.Option(None, help="Month (1-12) shown by default on the map."),
    force_osm: bool = typer.Option(False, help="Download OSM again, ignoring the cache."),
    out: Optional[str] = typer.Option(None, help="Output folder (defaults to output/<region>)."),
):
    """Build the risk map, the reports and the exports for one region, in both languages."""
    box, region_key, region_species = _bbox(region, bbox)
    grid = Grid.from_bbox(box)
    folder = config.OUTPUT_DIR / (out or (region_key or "bbox"))
    folder.mkdir(parents=True, exist_ok=True)
    log(f"[bold]{config.region_name(region_key, 'en') if region_key else f'bbox {bbox}'}[/] · grid "
        f"{grid.ny}x{grid.nx} cells of {grid.res} deg (~{grid.dx_m:.0f}x{grid.dy_m:.0f} m)")

    log("[cyan]1/5[/] OSM infrastructure (Overpass)...")
    infra = osm.get_infrastructure(box, force=force_osm)
    infra_summary = osm.summary(infra)
    log(f"  {infra_summary}")
    expo = osm.exposure_layers(infra, grid)

    log("[cyan]2/5[/] Terrain (AWS Terrain Tiles)...")
    topo = terrain.terrain_layers(box, grid)
    factors = terrain.terrain_factors(topo)
    log(f"  elevation {topo['elevation'].min():.0f}-{topo['elevation'].max():.0f} m, "
        f"mean slope {topo['slope'].mean():.1f} deg")

    log("[cyan]3/5[/] Seasonal abundance (GBIF/eBird)...")
    effort = abundance.monthly_effort(box, log=log)
    effort_raster = abundance.effort_raster(effort, grid)
    wanted = species_name or region_species or config.DEFAULT_SPECIES
    presences, info = {}, {}
    for sp in wanted:
        if sp not in config.SPECIES:
            log(f"  [yellow]{sp} is not in config.SPECIES; neutral weights of 0.5 are used[/]")
            config.SPECIES[sp] = dict(name={"es": sp, "en": sp}, electro=0.5, col_lin=0.5, col_aer=0.5, status=0.5)
        P, n = abundance.monthly_presence(sp, box, grid, effort_raster, log=log)
        S = ebirdst.monthly_presence(sp, grid, log=log)  # None when there is no eBird Status & Trends GeoTIFF
        if S is not None:
            P = S if P is None else (1 - config.EBIRDST_WEIGHT) * P + config.EBIRDST_WEIGHT * S
        info[sp] = dict(gbif_records=n, movebank_fixes=0, ebirdst=S is not None, included=P is not None)
        if P is not None:
            presences[sp] = P
    if not presences:
        log("[red]No species has enough data in the area.[/]")
        raise typer.Exit(1)

    log("[cyan]4/5[/] GPS tracking (Movebank)..." if (with_movebank or study_id)
        else "[cyan]4/5[/] Movebank skipped (use --movebank or --study-id)")
    if with_movebank or study_id:
        for sp in list(presences):
            U, n = movebank.species_tracking(sp, box, grid, use_repo=with_movebank,
                                             study_ids=study_id or (), log=log)
            info[sp]["movebank_fixes"] = n
            if U is not None:
                # the weight of the GPS data grows with the number of fixes: 5 passing fixes must not move the map
                w = config.MOVEBANK_WEIGHT * min(1.0, n / config.MOVEBANK_N_REF)
                presences[sp] = (1 - w) * presences[sp] + w * U
                log(f"  {sp}: {n} GPS fixes in the area, blended at {int(w * 100)}%")

    log("[cyan]5/5[/] Risk model and outputs...")
    confidence = {sp: 1.0 if info[sp].get("ebirdst") else
                  max(min(1.0, info[sp]["gbif_records"] / config.RECORDS_FOR_CONFIDENCE),
                      min(1.0, info[sp]["movebank_fixes"] / config.MOVEBANK_N_REF))
                  for sp in presences}
    for sp in presences:
        info[sp]["confidence"] = round(confidence[sp], 2)
    result = risk.compute(presences, expo, factors, config.SPECIES, confidence=confidence)
    ranking = risk.rank_elements(result, infra, grid)
    table = risk.seasonal_table(result)

    ranking.to_csv(folder / "ranking_elements.csv", index=False, encoding="utf-8")
    report.export_geojson(folder / "ranking_elements.geojson", ranking)
    report.export_geotiff(folder / "risk_total.tif", result["total"], grid, config.MONTHS)
    for k in risk.MECHANISMS:
        report.export_geotiff(folder / f"risk_{k}.tif", result["aggregate"][k], grid, config.MONTHS)
    report.export_geotiff(folder / "terrain.tif",
                          np.stack([topo["elevation"], topo["slope"], topo["tpi"]]), grid,
                          ["elevation_m", "slope_deg", "tpi_m"])

    label = config.region_name(region_key, "en") if region_key else f"bbox {bbox}"
    for lang in config.LANGS:
        region_label = config.region_name(region_key, lang) if region_key else label
        m = report.build_map(result, infra, ranking, grid, region_label, lang, top=top, start_month=month)
        m.save(str(folder / f"map.{lang}.html"))
        other = "en" if lang == "es" else "es"
        report.report(folder / f"report.{lang}.html", f"map.{lang}.html", region_label, box, infra_summary,
                      info, table, ranking, lang, other_lang_href=f"report.{other}.html")
    site.region_redirects(folder)
    site.index(config.OUTPUT_DIR)

    console.print(table.round(0).astype(int))
    if not ranking.empty:
        t = Table("#", "type", "mechanism", "risk", "month", "species", "OSM")
        for i, r in ranking.head(15).iterrows():
            t.add_row(str(i + 1), r.type, r.mechanism, f"{r.risk_max:.0f}", r.peak_month,
                      str(r.species)[:60], str(r.osm_id))
        console.print(t)
    log(f"[green]Done:[/] {folder / 'report.en.html'}")


@app.command()
def index():
    """Rebuild output/regions.<lang>.html with links to every computed region (the web service front page)."""
    log(f"[green]Front page:[/] {site.index(config.OUTPUT_DIR)}")


@app.command()
def score(
    region: str = typer.Option("cantabria", help="Region whose rasters (output/<region>/risk_*.tif) are used."),
    geojson: Optional[str] = typer.Option(None, help="GeoJSON FeatureCollection of polygons (projects) to score."),
    observatory: Optional[str] = typer.Option(None, help="Root of the public consultation observatory: uses its "
                                                         "data/estado.json and its municipality cache."),
    category: Optional[list[str]] = typer.Option(None, help="Filter observatory notices by category "
                                                            "(eolica, red_electrica...); repeatable."),
    out: Optional[str] = typer.Option(None, help="Output CSV (defaults to output/<region>/scored_projects.csv)."),
):
    """Assign the risk index to projects (polygons): monthly mean and maximum over a region's rasters."""
    import json
    from pathlib import Path

    folder = config.OUTPUT_DIR / region
    if not (folder / "risk_total.tif").exists():
        raise typer.BadParameter(f"no rasters in {folder}; run `run --region {region}` first")
    if geojson:
        feats = json.loads(Path(geojson).read_text(encoding="utf-8"))
    elif observatory:
        root = Path(observatory)
        feats = score_mod.observatory_features(root / "data" / "estado.json", root / "data" / "cache" / "geo",
                                               categories=category or None)
        log(f"  {len(feats['features'])} geolocated notices with a polygon")
    else:
        raise typer.BadParameter("pass --geojson or --observatory")
    df = score_mod.score(feats, folder)
    target = Path(out) if out else folder / "scored_projects.csv"
    df.to_csv(target, index=False, encoding="utf-8")
    t = Table("project", "category", "km2", "mean risk", "max risk", "peak month", "% cells with infrastructure")
    for r in df.itertuples():
        t.add_row(str(getattr(r, "title", getattr(r, "id", "")))[:70], str(getattr(r, "category", "")),
                  str(getattr(r, "area_km2", "")), str(r.risk_mean), str(r.risk_max), str(r.peak_month),
                  str(r.pct_cells_with_infra))
    console.print(t)
    log(f"[green]Saved:[/] {target}")


if __name__ == "__main__":
    app()
