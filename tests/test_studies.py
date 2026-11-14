import copy
from pathlib import Path

import numpy as np
import pytest

from vibequal.config import load_config, validate_config
from vibequal.studies import checked_counts, mass_fractions, modal_prefix, variant_config


def test_mass_coverage_uses_solver_and_cad_denominators_separately():
    modal = {
        "effective_mass_kg": np.array([[1.0, 2.0, 3.0], [2.0, 3.0, 4.0]]),
        "total_effective_mass": np.array([6.0, 10.0, 14.0, 1.0, 1.0, 1.0]),
    }
    fractions = mass_fractions(modal, 20.0)
    assert fractions["z_mass_fraction_of_solver_total"] == 0.5
    assert fractions["z_mass_fraction_of_cad"] == 0.35


def test_prefix_retains_common_denominator_and_order():
    modal = {
        "frequencies_hz": np.array([100.0, 200.0, 300.0]),
        "participation": np.ones((3, 6)),
        "effective_mass_kg": np.ones((3, 6)),
        "shapes": np.ones((3, 4, 3)),
        "total_effective_mass": np.ones(6) * 10,
    }
    subset = modal_prefix(modal, 2)
    np.testing.assert_array_equal(subset["frequencies_hz"], [100, 200])
    assert subset["shapes"].shape == (2, 4, 3)
    np.testing.assert_array_equal(subset["total_effective_mass"], modal["total_effective_mass"])
    assert len(modal["frequencies_hz"]) == 3


@pytest.mark.parametrize("counts", [[10], [10, 10], [0, 10], [10, 101], [10, True], [1.0, 10]])
def test_invalid_truncation_counts_are_rejected(counts):
    with pytest.raises(ValueError):
        checked_counts(counts)


def test_mount_variant_moves_holes_and_clamped_patches_together():
    base = load_config(Path(__file__).parents[1] / "examples/enclosure.json")
    original = copy.deepcopy(base)
    result = variant_config(base, {"label": "moved", "geometry": {"mount_inset_m": 0.022}}, 50)
    assert result["geometry"]["mount_inset_m"] == 0.022
    np.testing.assert_allclose(
        result["supports"]["centres_xy_m"],
        [[0.022, 0.022], [0.022, 0.078], [0.138, 0.022], [0.138, 0.078]],
    )
    assert result["analysis"]["modes"] == 50
    assert result["material"] == base["material"]
    assert result["profile"] == base["profile"]
    assert base == original


def test_rib_must_fit_cavity():
    base = load_config(Path(__file__).parents[1] / "examples/enclosure.json")
    base["geometry"]["rib"] = {"width_m": 0.2, "height_m": 0.008}
    with pytest.raises(ValueError, match="fit inside"):
        validate_config(base)
