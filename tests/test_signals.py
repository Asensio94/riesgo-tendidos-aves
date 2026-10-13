import csv
import json
import os
from datetime import datetime, timezone

import pytest
import requests
from shapely.geometry import Point, box, mapping

from birdrisk import config, signals as S

NOW = datetime(2026, 10, 13, 7, 2, 41, tzinfo=timezone.utc)
DAY = datetime(2026, 10, 2, 5, 30, tzinfo=timezone.utc).timestamp()

# Two overlapping sites in Cantabria (a ZEPA and a ZEC), one in the Strait and one far from both regions.
NATURA = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"codigo": code, "nombre": code, "tipo": kind}, "geometry": mapping(g)}
    for code, kind, g in [("ES1", "ZEPA", box(0, 0, 1, 1)), ("ES2", "ZEC", box(0.5, 0, 1.5, 1)),
                          ("ES3", "ZEC y ZEPA", box(10, 10, 11, 11)), ("ES9", "ZEPA", box(50, 50, 51, 51))]]}


def _row(lon, lat, risk, n):
    osm_id = 9_000_000_000 + n  # long enough not to turn up in the output by chance
    return {"type": "pylon", "osm_id": str(osm_id), "osm_url": f"https://www.openstreetmap.org/node/{osm_id}",
            "lon": str(lon), "lat": str(lat), "risk_max": str(risk), "species": "Gyps fulvus"}


# Cantabria: ten scored elements and one without a score. Only the 9 (inside both sites) is in the top tenth;
# the 8 is inside ES1 too, but not high enough. The Strait scores much higher: its top tenth (118 and 119) would
# swallow Cantabria's if the cut were not taken per region.
CANTABRIA = ([_row(0.75, 0.5, 9, 9001), _row(0.25, 0.5, 8, 8001)] + [_row(3, 3, i, 100 + i) for i in range(8)]
             + [_row(0.4, 0.6, "", 7001)])
ESTRECHO = [_row(10.25, 10.75, 118, 1180), _row(10.75, 10.25, 119, 1190)] + [_row(12, 12, 100 + i, 200 + i)
                                                                          for i in range(18)]


def _doc():
    regions = {"estrecho": (ESTRECHO, "2026-10-02"), "cantabria": (CANTABRIA, "2026-10-01")}
    return S.build(regions, S.site_shapes(NATURA), NOW)


def test_counts_the_top_tenth_of_each_region_inside_each_site():
    doc = _doc()
    assert {s["id"]: s["value"]["amount"] for s in doc["signals"]} == {
        "cantabria-ES1": 1, "cantabria-ES2": 1, "estrecho-ES3": 2}
    assert [s["id"] for s in doc["signals"]] == ["cantabria-ES1", "cantabria-ES2", "estrecho-ES3"]  # date, then id
    s = doc["signals"][-1]
    assert s == {"id": "estrecho-ES3", "kind": "power_line", "date": "2026-10-02",
                 "title": "2 apoyos y vanos de riesgo alto para las aves dentro del espacio",
                 "url": "https://asensio94.github.io/riesgo-tendidos-aves/estrecho/map.es.html",
                 "sites": [{"code": "ES3"}], "municipalities": [], "precision": "punto", "deadline": None,
                 "status": None, "value": {"amount": 2, "unit": "elementos"},
                 "details": {"region": "estrecho", "point": s["details"]["point"]}}


def test_coverage_is_every_site_around_the_modelled_elements():
    doc = _doc()
    assert {k: doc[k] for k in ("source", "version", "generated")} == {
        "source": "riesgo-tendidos-aves", "version": 1, "generated": "2026-10-13T07:02Z"}
    assert doc["coverage"] == {
        "label": "Cantabria y el Estrecho", "sites": ["ES1", "ES2", "ES3"],  # ES9 lies outside both regions
        "note": "Riesgo de electrocución y colisión de cada apoyo y vano de OpenStreetMap, modelado cada mes."}


def test_coverage_label_names_the_regions_in_spanish():
    assert S.coverage_label(["estrecho"]) == "El Estrecho"
    assert S.coverage_label(["monfrague", "estrecho", "cantabria"]) == "Cantabria, el Estrecho y Monfragüe"


def test_point_lies_inside_the_site_and_never_on_an_element():
    shapes = S.site_shapes(NATURA)
    elements = {(float(r["lon"]), float(r["lat"])) for r in CANTABRIA + ESTRECHO}
    for s in _doc()["signals"]:
        lon, lat = s["details"]["point"]
        assert shapes[s["sites"][0]["code"]].contains(Point(lon, lat))
        assert (lon, lat) not in elements


def test_no_element_coordinates_ids_or_species_are_published():
    doc = _doc()
    text = json.dumps(doc, ensure_ascii=False)
    assert all(set(s["details"]) == {"region", "point"} for s in doc["signals"])
    for r in CANTABRIA + ESTRECHO:
        assert r["osm_id"] not in text and r["osm_url"] not in text
    assert "Gyps" not in text and "lon" not in text and "lat" not in text
    for lon, lat in ((0.75, 0.5), (10.25, 10.75), (10.75, 10.25)):  # the high-risk elements themselves
        assert [lon, lat] not in [s["details"]["point"] for s in doc["signals"]]


def test_polygonal_keeps_the_areas_of_a_part_collapsed_into_a_point():
    g = {"type": "MultiPolygon", "coordinates": [[[[5, 5], [5, 5], [5, 5], [5, 5]]],
                                                 [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]]}
    s = S.polygonal(g)
    assert s.geom_type == "Polygon" and s.area == 1


def _region(out, name, rows, map_page=True):
    d = out / name
    d.mkdir()
    with (d / "ranking_elements.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    os.utime(d / "ranking_elements.csv", (DAY, DAY))
    if map_page:
        (d / "map.es.html").write_text("", encoding="utf-8")


def test_write_reads_every_computed_region_dated_by_its_output(tmp_path):
    _region(tmp_path, "cantabria", CANTABRIA)
    _region(tmp_path, "estrecho", ESTRECHO)
    _region(tmp_path, "tarifa", ESTRECHO, map_page=False)  # no map to link to: not published, not counted
    (tmp_path / "img").mkdir()
    path = S.write(tmp_path, natura=NATURA, now=NOW)
    assert path == tmp_path / "signals.json"
    doc = json.loads(path.read_bytes().decode("utf-8"))
    assert doc == {**_doc(), "signals": [{**s, "date": "2026-10-02"} for s in _doc()["signals"]]}
    assert "electrocución" in path.read_text(encoding="utf-8")  # UTF-8, not \u escapes


def test_write_leaves_no_stale_file_when_the_natura_layer_is_unavailable(tmp_path, monkeypatch):
    def down(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(S.requests, "get", down)
    _region(tmp_path, "cantabria", CANTABRIA)
    (tmp_path / "signals.json").write_text("{}", encoding="utf-8")
    with pytest.raises(requests.ConnectionError):
        S.write(tmp_path)
    assert not (tmp_path / "signals.json").exists()


def test_index_publishes_the_rest_when_signals_fail(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from birdrisk import cli

    def down(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(S.requests, "get", down)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    _region(tmp_path, "cantabria", CANTABRIA)
    result = CliRunner().invoke(cli.app, ["index"])
    assert result.exit_code == 0, result.output
    assert "signals.json skipped" in result.output
    assert (tmp_path / "regions.es.html").exists() and not (tmp_path / "signals.json").exists()
