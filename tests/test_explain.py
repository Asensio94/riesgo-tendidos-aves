"""Why an element scores high: the driver columns of the ranking and the sentences built from them."""
from types import SimpleNamespace

import numpy as np

from birdrisk import i18n, osm, risk
from birdrisk.grid import Grid

GRID = Grid.from_bbox((43.0, 0.0, 43.02, 0.02))


def _result():
    """Two species over a grid with distribution pylons everywhere and one busy cell."""
    shape = GRID.shape
    expo = {k: np.zeros(shape) for k in ("n_pylons_distribution", "n_pylons_unknown", "line_km_distribution",
                                         "line_km_unknown", "line_km_total", "n_turbines")}
    expo["n_pylons_distribution"][:] = 2
    expo["n_pylons_distribution"][1, 1] = 12
    presence = {"Gyps fulvus": np.full((12, *shape), 0.1), "Neophron percnopterus": np.full((12, *shape), 0.1)}
    presence["Gyps fulvus"][2, 1, 1] = 0.9  # March, busy cell
    presence["Neophron percnopterus"][2, 1, 1] = 0.3
    cfg = {sp: {"status": 1.0, "electro": 1.0, "col_lin": 1.0, "col_aer": 1.0} for sp in presence}
    factors = {"relief": np.zeros(shape), "ridge": np.zeros(shape)}
    return risk.compute(presence, expo, factors, cfg)


def test_pylon_hazard_reasons_name_the_tags_that_move_the_factor():
    tags = {"power": "pole", "material": "concrete", "line_attachment": "pin"}
    assert osm.pylon_hazard_reasons(tags) == "earthed;pin"
    assert osm.pylon_hazard_reasons({"power": "pole"}) == ""
    assert osm.pylon_hazard_reasons({"power": "portal", "material": "wood"}) == "wood;portal"


def test_ranking_rows_carry_the_drivers_of_their_cell():
    lat, lon = GRID.lat_centres()[1], GRID.lon_centres()[1]
    infra = {"lines": [], "turbines": [],
             "pylons": [{"id": 1, "lat": lat, "lon": lon, "type": "pole", "voltage": None, "category": "distribution",
                         "operator": None, "hazard": 1.65, "hazard_why": "earthed;pin"}]}
    row = risk.rank_elements(_result(), infra, GRID).iloc[0]
    assert row.peak_month == "Mar"
    assert row.species == "Gyps fulvus, Neophron percnopterus" and row.species_share == "75;25"
    n = GRID.ny * GRID.nx  # the busy cell beats every other one
    assert row.exposure == 12 and row.exposure_pct == 100 * (n - 1) // n
    assert row.birds_pct == 100 * (12 * n - 1) // (12 * n)  # and every other cell and month
    assert row.terrain is None and row.hazard_why == "earthed;pin"


def test_the_explanation_reads_the_same_from_pandas_and_from_csv_text():
    values = dict(type="pylon", mechanism="electrocution", risk_max=488.2, peak_month="Mar",
                  species="Gyps fulvus, Neophron percnopterus", species_share="75;25", birds_pct=99, exposure=12.0,
                  exposure_pct=97, terrain=None, hazard=1.65, hazard_why="earthed;pin")
    es = i18n.explain(SimpleNamespace(**values), "es")
    assert es == i18n.explain(SimpleNamespace(**{k: "" if v is None else str(v) for k, v in values.items()}), "es")
    assert es[0].startswith("Índice 488: 4,9 veces")
    assert "muy alta en marzo" in es[1] and "buitre leonado (75 %)" in es[1].lower()
    assert "unos 12 apoyos" in es[2] and "97 %" in es[2]
    assert "aisladores rígidos" in es[3] and "×1,65" in es[3]
    en = i18n.explain(SimpleNamespace(**values), "en")
    assert en[0].startswith("Index 488: 4.9 times") and "very high presence in March" in en[1]
    fr = i18n.explain(SimpleNamespace(**values), "fr")
    assert fr[0].startswith("Indice 488 : 4,9 fois") and "97 %" in fr[2]


def test_old_rankings_only_get_the_sentence_on_the_index():
    old = SimpleNamespace(type="line", mechanism="line_collision", risk_max=80.0, peak_month="Jul", species="x")
    assert i18n.explain(old, "en") == [
        "Index 80 out of 100 (100 = the 99th percentile of the region's cells with this kind of infrastructure; "
        "only 1% are above it)."]
