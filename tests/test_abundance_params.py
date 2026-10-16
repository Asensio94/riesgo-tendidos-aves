"""GBIF query parameters."""
import numpy as np

from birdrisk.abundance import _bbox_params


def test_a_tile_edge_on_the_greenwich_meridian_is_not_written_in_scientific_notation():
    lons = np.arange(-0.10, 0.05, 0.05)  # the last edge is ~1e-15, not 0
    p = _bbox_params((42.75, lons[1], 42.8, lons[2]))
    assert "e" not in p["decimalLongitude"].lower()
    assert p["decimalLongitude"] == "-0.05,0.0"


def test_ordinary_coordinates_are_written_as_before():
    p = _bbox_params((36.0, -5.95, 36.05000000000001, -5.9))
    assert p["decimalLatitude"] == "36.0,36.05000000000001" and p["decimalLongitude"] == "-5.95,-5.9"
