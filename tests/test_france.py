"""France: Enedis merged with OSM, clipping to French territory, thresholds, status and French typography."""
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from birdrisk import config, france, i18n, osm, risk
from birdrisk.grid import Grid

# A small box in the Pyrenees: France north of 43.0, Spain south of it. 0.001 deg of latitude is ~111 m.
BBOX = (42.95, -0.10, 43.10, 0.10)
FRANCE = box(-1, 43.0, 1, 44).segmentize(0.001)  # dense, like the real departments
LAT = 43.05


def _osm_line(id, lat, voltage, lon0=-0.05, lon1=0.05):
    tags = {"power": "line", "voltage": str(voltage)}
    return {"id": id, "source": "osm", "power": "line", "voltage": voltage,
            "category": osm.line_category(tags, config.electrocution_max_v("FR")), "operator": None, "name": None,
            "coords": [(lon0, lat), (lon1, lat)]}


def _osm_pylon(id, lat, lon, **tags):
    tags = {"power": "pole", **tags}
    return {"id": id, "source": "osm", "lat": lat, "lon": lon, "type": "pole", "voltage": 20000,
            "category": "distribution", "material": tags.get("material"), "design": tags.get("design"),
            "operator": None, "hazard": osm.pylon_hazard(tags), "tagged": len(tags) > 1}


HTA = [{"id": "hta1", "source": "enedis", "power": "line", "voltage": None, "category": "distribution",
        "operator": "Enedis", "name": "HTA", "coords": [(-0.05, LAT), (0.05, LAT)]}]


def _merge(osm_infra, poles, land=FRANCE):
    return france.merge(osm_infra, HTA, poles, BBOX, land=land)


def test_an_osm_line_along_enedis_hta_is_dropped_and_the_others_stay():
    infra = {"lines": [_osm_line(1, LAT + 0.0001, 20000),      # ~11 m from the HTA: the same line
                       _osm_line(2, LAT + 0.01, 20000),        # ~1.1 km away: a local distributor's line
                       _osm_line(3, LAT + 0.0001, 225000)],    # RTE's line next to it: transmission, kept
             "pylons": [], "turbines": []}
    out = _merge(infra, [])
    ids = sorted(str(ln["id"]) for ln in out["lines"])
    assert ids == ["2", "3", "hta1"]
    assert {ln["id"]: ln["category"] for ln in out["lines"]}[3] == "transmission"


def test_only_enedis_poles_on_an_hta_line_count_and_take_the_tags_of_their_osm_twin():
    poles = [{"id": "p_hta", "lat": LAT + 0.00005, "lon": 0.0},   # ~5 m from the HTA
             {"id": "p_bt", "lat": LAT + 0.002, "lon": 0.0}]      # ~220 m away: low voltage
    infra = {"lines": [], "turbines": [],
             "pylons": [_osm_pylon(10, LAT + 0.00008, 0.00003, material="concrete", line_attachment="pin"),
                        _osm_pylon(11, LAT + 0.002, 0.00005),      # twin of the BT pole: dropped too
                        _osm_pylon(12, LAT + 0.004, 0.02),         # no Enedis pole near: kept
                        {**_osm_pylon(13, LAT + 0.006, 0.03), "voltage": 400}]}  # low voltage: left out
    out = _merge(infra, poles)
    by_id = {str(a["id"]): a for a in out["pylons"]}
    assert set(by_id) == {"p_hta", "12"}
    assert by_id["p_hta"]["source"] == "enedis" and by_id["p_hta"]["tagged"]
    assert by_id["p_hta"]["hazard"] == osm.pylon_hazard({"power": "pole", "material": "concrete",
                                                         "line_attachment": "pin"}) > 1
    assert out["enedis"] == {"hta_lines": 1, "poles": 2, "hta_poles": 1}


def test_everything_outside_french_territory_is_clipped_away():
    infra = {"lines": [_osm_line(5, 42.98, 20000), _osm_line(6, 42.98, 132000, lon0=0.0, lon1=0.0)],
             "pylons": [_osm_pylon(20, 42.98, 0.0)],
             "turbines": [{"id": 30, "source": "osm", "lat": 42.98, "lon": 0.0, "power_output": None, "height": None,
                           "operator": None, "name": None},
                          {"id": 31, "source": "osm", "lat": 43.08, "lon": 0.0, "power_output": None, "height": None,
                           "operator": None, "name": None}]}
    # a line crossing the border keeps only its French half
    infra["lines"].append({**_osm_line(7, 0, 225000), "coords": [(0.08, 42.96), (0.08, 43.06)]})
    out = _merge(infra, [{"id": "es", "lat": 42.98, "lon": -0.05}])
    assert [t["id"] for t in out["turbines"]] == [31]
    assert out["pylons"] == []
    lines = {ln["id"]: ln for ln in out["lines"]}
    assert 5 not in lines and 6 not in lines
    assert min(lat for _, lat in lines[7]["coords"]) == pytest.approx(43.0, abs=1e-5)


def test_the_french_threshold_puts_63_kv_in_transmission_and_spain_keeps_66():
    tags = {"power": "line", "voltage": "63000"}
    assert osm.line_category(tags, config.electrocution_max_v("FR")) == "transmission"
    assert osm.line_category(tags) == "distribution"  # Spain, unchanged
    assert osm.line_category({"power": "line", "voltage": "20000"}, config.electrocution_max_v("FR")) == "distribution"


def test_french_status_follows_the_french_red_list_and_spain_keeps_its_own():
    assert config.species_status("Milvus milvus", "FR") == 0.8
    assert config.species_status("Milvus milvus", "ES") == config.SPECIES["Milvus milvus"]["status"] == 0.9
    assert config.species_status("Otis tarda", "FR") == config.SPECIES["Otis tarda"]["status"]  # not assessed


def test_spanish_regions_without_a_list_keep_the_same_species():
    assert "Tetrax tetrax" not in config.DEFAULT_SPECIES and len(config.DEFAULT_SPECIES) == 21
    for key, reg in config.REGIONS.items():
        for sp in reg.get("species", []):
            assert sp in config.SPECIES, (key, sp)
            assert "fr" in config.SPECIES[sp]["name"]


def test_each_country_publishes_in_its_language_and_english():
    assert config.region_langs("estrecho") == ("es", "en")
    assert config.region_langs("camargue") == ("fr", "en")
    assert config.region_country("pyrenees") == "FR" and config.region_country("cantabria") == "ES"


def test_french_numbers_and_spacing():
    nnbsp = " "
    assert i18n.num(20000, "fr") == f"20{nnbsp}000"
    assert i18n.num(0.005, "fr") == "0,005"
    assert i18n.num(20000, "es") == "20.000" and i18n.num(20000, "en") == "20,000"
    assert i18n.pct(10, "fr") == f"10{nnbsp}%"
    assert f"{nnbsp}%" in i18n.t("fr", "site_rule", share=10, region="Camargue")
    assert " :" in i18n.t("fr", "popup_index", max=1, mean=1)
    assert " %" not in i18n.method_html("fr", "FR") and " ;" not in i18n.method_html("fr", "FR")


def test_english_pages_of_a_french_region_speak_of_france():
    assert "50 kV" in i18n.t("en", "legend_distribution", country="FR")
    assert "66 kV" in i18n.t("en", "legend_distribution")
    assert "Enedis" in i18n.t("en", "footer_sources", country="FR", repo="x")
    assert "RTE" in i18n.method_html("en", "FR") and "Enedis" in i18n.method_html("fr", "FR")


def test_ranking_rows_name_their_source():
    grid = Grid.from_bbox((43.0, 0.0, 43.01, 0.01))
    layer = np.ones((12, *grid.shape))
    result = {"aggregate": {k: layer for k in risk.MECHANISMS}, "by_species": {}}
    infra = {"lines": [], "turbines": [],
             "pylons": [{"id": "abc", "source": "enedis", "lat": 43.005, "lon": 0.005, "type": "pole",
                         "voltage": None, "category": "distribution", "operator": "Enedis", "hazard": 1.0},
                        {"id": 42, "lat": 43.005, "lon": 0.005, "type": "pole", "voltage": None,
                         "category": "distribution", "operator": None, "hazard": 1.0}]}
    df = risk.rank_elements(result, infra, grid).set_index("source_id")
    assert df.loc["abc", "source"] == "enedis" and pd.isna(df.loc["abc", "osm_id"])
    assert df.loc["abc", "source_url"].endswith(config.ENEDIS_POLES)
    assert df.loc["42", "osm_url"] == "https://www.openstreetmap.org/node/42" == df.loc["42", "source_url"]
