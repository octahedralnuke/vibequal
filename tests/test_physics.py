"""Independent limiting cases and dimensional checks for engineering calculations."""

import numpy as np
import pytest

from vibequal.geometry import Mesh, c3d10_order, select_supports
from vibequal.pcb import steinberg_allowable_m
from vibequal.vibration import PSDProfile, miles_grms, modal_response, sdof_response


def test_mil810h_category24_integral_and_reference():
    import json
    from pathlib import Path

    data = json.loads(
        (Path(__file__).parents[1] / "examples/profiles/mil_std_810h_cat24.json").read_text()
    )
    profile = PSDProfile.from_config(data)
    # Plateau area .04*(1000-20) plus f^-2 tail area .04*1000^2*(1/1000-1/2000).
    assert profile.input_grms**2 == pytest.approx(59.2)
    assert round(profile.input_grms, 1) == 7.7
    assert profile.at(2000) == pytest.approx(0.01)
    assert data["duration_s"] == 3600
    assert data["standard_reference"]["figure"] == "514.8E-1"


def test_flat_psd_integral_and_band_limits():
    p = PSDProfile("flat", [20, 2000], [0.04, 0.04])
    assert p.input_grms == pytest.approx(np.sqrt(0.04 * 1980))
    np.testing.assert_allclose(p.at([0, 10, 20, 1000, 2000, 2100]), [0, 0, 0.04, 0.04, 0.04, 0])


def test_power_law_minus_one_is_integrated_analytically():
    p = PSDProfile("minus one", [10, 100], [1, 0.1])
    assert p.input_grms**2 == pytest.approx(10 * np.log(10))
    assert p.at(np.sqrt(1000)) == pytest.approx(1 / np.sqrt(10))


@pytest.mark.parametrize(
    "f,s", [([20, 20], [1, 1]), ([100, 20], [1, 1]), ([20, 100], [1, -1]), ([20, np.nan], [1, 1])]
)
def test_bad_psd_is_rejected(f, s):
    with pytest.raises(ValueError):
        PSDProfile("bad", f, s)


def test_miles_agrees_with_broadband_lightly_damped_sdof():
    p = PSDProfile("wide flat", [0.1, 50000], [0.01, 0.01])
    numeric = sdof_response(p, 500, 0.01)["absolute_acceleration_grms"]
    miles = miles_grms(500, 0.01, 0.01)
    assert abs(numeric / miles - 1) < 0.002


def test_out_of_band_mode_still_has_forced_response():
    p = PSDProfile("low band", [20, 200], [0.01, 0.01])
    r = sdof_response(p, 500, 0.025)
    assert r["miles_unit_participation_grms"] == 0
    assert r["absolute_acceleration_grms"] > p.input_grms


def test_modal_transfer_reduces_to_exact_single_dof():
    mesh = Mesh(
        np.array([1, 2]),
        np.array([[0, 0, 0], [0, 0, 1.0]]),
        np.array([]),
        np.array([]),
        np.array([]),
        np.array([1]),
        1.0,
    )
    modes = {
        "frequencies_hz": np.array([100.0]),
        "participation": np.array([[0, 0, 1.0]]),
        "effective_mass_kg": np.array([[0, 0, 1.0]]),
        "shapes": np.array([[[0, 0, 0], [0, 0, 1.0]]]),
    }
    config = {
        "analysis": {"axis": "z", "probe_xyz_m": [0, 0, 1], "damping_ratio": 0.025},
        "profile": {"breakpoints_hz_g2_per_hz": [[1, 0.01], [1000, 0.01]]},
        "material": {"density_kg_m3": 1.0},
    }
    actual, _ = modal_response(mesh, modes, config)
    reference = sdof_response(PSDProfile.from_config(config["profile"]), 100, 0.025)
    assert actual["absolute_acceleration_grms"] == pytest.approx(
        reference["absolute_acceleration_grms"], rel=1e-7
    )
    assert actual["relative_displacement_rms_m"] == pytest.approx(
        reference["relative_displacement_rms_m"], rel=1e-7
    )


def test_opposite_modal_coefficients_cancel_coherently():
    mesh = Mesh(
        np.array([1, 2]),
        np.array([[0, 0, 0], [0, 0, 1.0]]),
        np.array([]),
        np.array([]),
        np.array([]),
        np.array([1]),
        1.0,
    )
    modes = {
        "frequencies_hz": np.array([100.0, 100.0]),
        "participation": np.array([[0, 0, 1.0], [0, 0, -1.0]]),
        "effective_mass_kg": np.array([[0, 0, 1.0], [0, 0, 1.0]]),
        "shapes": np.array([[[0, 0, 0], [0, 0, 1.0]], [[0, 0, 0], [0, 0, 1.0]]]),
    }
    profile = {"breakpoints_hz_g2_per_hz": [[1, 0.01], [1000, 0.01]]}
    config = {
        "analysis": {"axis": "z", "probe_xyz_m": [0, 0, 1], "damping_ratio": 0.025},
        "profile": profile,
        "material": {"density_kg_m3": 1.0},
    }
    result, _ = modal_response(mesh, modes, config)
    assert result["absolute_acceleration_grms"] == pytest.approx(
        PSDProfile.from_config(profile).input_grms
    )
    assert result["relative_displacement_rms_m"] == 0


def test_steinberg_inch_conversion_known_case():
    # Independent inch calculation: B=6, h=.063, L=.8, C=r=1.
    actual = steinberg_allowable_m(6 * 0.0254, 0.063 * 0.0254, 0.8 * 0.0254, 1, 1)
    assert actual / 0.0254 == pytest.approx(0.02342547455, rel=1e-7)


def test_tetra10_edges_map_from_shuffled_midpoints():
    points = {
        1: np.array([0.0, 0.0, 0.0]),
        2: np.array([1.0, 0.0, 0.0]),
        3: np.array([0.0, 1.0, 0.0]),
        4: np.array([0.0, 0.0, 1.0]),
    }
    for n, (a, b) in enumerate([(1, 2), (2, 3), (3, 1), (1, 4), (2, 4), (3, 4)], 5):
        points[n] = (points[a] + points[b]) / 2
    assert c3d10_order([1, 2, 3, 4, 10, 9, 8, 7, 6, 5], points) == list(range(1, 11))


def test_bad_support_selection_fails_instead_of_free_free_solve():
    xyz = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    with pytest.raises(ValueError, match="fewer than three"):
        select_supports(
            xyz,
            {"type": "mount_patches", "radius_m": 0.01, "plane_z_m": 0, "centres_xy_m": [[10, 10]]},
        )


def single_mode_response(frequency_hz, mass_fraction, coefficient=1.0):
    mesh = Mesh(
        np.array([1, 2]),
        np.array([[0, 0, 0], [0, 0, 1.0]]),
        np.array([]),
        np.array([]),
        np.array([]),
        np.array([1]),
        1.0,
    )
    modes = {
        "frequencies_hz": np.array([frequency_hz]),
        "participation": np.array([[0, 0, 1.0]]),
        "effective_mass_kg": np.array([[0, 0, mass_fraction]]),
        "shapes": np.array([[[0, 0, 0], [0, 0, coefficient]]]),
    }
    config = {
        "analysis": {"axis": "z", "probe_xyz_m": [0, 0, 1], "damping_ratio": 0.025},
        "profile": {"breakpoints_hz_g2_per_hz": [[20, 0.01], [2000, 0.01]]},
        "material": {"density_kg_m3": 1.0},
    }
    return modal_response(mesh, modes, config)[0]


@pytest.mark.parametrize("frequency_hz", [1900.0, 2004.0, 2140.0])
def test_significant_mode_near_profile_edge_is_flagged(frequency_hz):
    # Window is 3 * zeta * fn: 142.5 Hz at 1900 Hz and 160.5 Hz at 2140 Hz.
    result = single_mode_response(frequency_hz, 0.13)
    assert result["modes"][0]["near_band_edge"]
    assert [m["mode"] for m in result["band_edge_modes"]] == [1]
    assert result["band_edge_modes"][0]["edge_hz"] == 2000


@pytest.mark.parametrize("frequency_hz", [1000.0, 1850.0, 2200.0])
def test_mode_clear_of_profile_edges_is_not_flagged(frequency_hz):
    result = single_mode_response(frequency_hz, 0.13)
    assert not result["modes"][0]["near_band_edge"]
    assert result["band_edge_modes"] == []


def test_insignificant_mode_near_edge_is_not_listed():
    result = single_mode_response(2004.0, 1e-5, coefficient=1e-4)
    assert result["modes"][0]["near_band_edge"]
    assert result["band_edge_modes"] == []
