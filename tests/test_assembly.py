"""Lid/board configuration, mass bookkeeping and coupled board deflection."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from vibequal.config import board_density, board_layout, validate_config
from vibequal.geometry import BOARD, BODY, Mesh, model_mass_kg
from vibequal.pcb import coupled_board
from vibequal.vibration import PSDProfile, sdof_response

ASSEMBLY = Path(__file__).parents[1] / "examples" / "assembly.json"


def assembly():
    return json.loads(ASSEMBLY.read_text())


def test_assembly_example_is_valid_and_board_is_centred():
    c = validate_config(assembly())
    layout = board_layout(c["geometry"])
    assert layout["x0"] == pytest.approx(0.02)
    assert layout["y0"] == pytest.approx(0.0125)
    assert layout["z0"] == pytest.approx(0.011)
    assert layout["z_top"] == pytest.approx(0.0126)
    assert layout["standoffs"][0] == pytest.approx((0.025, 0.0175))


def test_smeared_component_mass_raises_board_density():
    b = assembly()["geometry"]["board"]
    volume = 0.12 * 0.075 * 0.0016
    assert board_density(b) == pytest.approx(1850 + 0.025 / volume)


@pytest.mark.parametrize(
    "change,message",
    [
        ({"length_m": 0.155}, "inside the tray walls"),
        ({"standoff_height_m": 0.04}, "below the top"),
        ({"standoff_inset_m": 0.002}, "wholly under"),
        ({"thickness_m": 0}, "greater than zero"),
        ({"smeared_component_mass_kg": -1}, "nonnegative"),
    ],
)
def test_invalid_board_is_rejected(change, message):
    c = assembly()
    c["geometry"]["board"].update(change)
    with pytest.raises(ValueError, match=message):
        validate_config(c)


def test_board_standoff_cannot_hit_a_mounting_hole():
    c = assembly()
    c["geometry"]["board"].update({"length_m": 0.148, "width_m": 0.088, "standoff_inset_m": 0.006})
    with pytest.raises(ValueError, match="mounting hole"):
        validate_config(c)


def test_board_and_lid_need_a_tray():
    c = assembly()
    c["geometry"] = {"type": "beam", "length_m": 0.2, "width_m": 0.02, "height_m": 0.004,
                     "lid": {"thickness_m": 0.002}}
    with pytest.raises(ValueError, match="require geometry.type tray"):
        validate_config(c)


def test_model_mass_uses_each_material_density():
    c = assembly()
    mesh = Mesh(*[np.array([])] * 6, 1e-4, np.array([BODY, BOARD]), 1.44e-5)
    expected = (1e-4 - 1.44e-5) * 2700 + 1.44e-5 * board_density(c["geometry"]["board"])
    assert model_mass_kg(mesh, c) == pytest.approx(expected)


def board_model(centre_z, standoff_z):
    c = validate_config(assembly())
    layout = board_layout(c["geometry"])
    points = [(0.08, 0.05, layout["z_top"])] + [(x, y, layout["z0"]) for x, y in layout["standoffs"]]
    points.append((0.012, 0.012, 0.0))
    mesh = Mesh(np.arange(1, 7), np.array(points), *[np.array([])] * 3, np.array([6]), 1.0)
    shapes = np.zeros((1, 6, 3))
    shapes[0, 0, 2], shapes[0, 1:5, 2] = centre_z, standoff_z
    modal = {
        "frequencies_hz": np.array([300.0]),
        "participation": np.array([[0, 0, 1.0]]),
        "effective_mass_kg": np.array([[0, 0, 1.0]]),
        "shapes": shapes,
    }
    return mesh, modal, c


def test_board_bending_mode_reduces_to_single_dof_relative_displacement():
    mesh, modal, c = board_model(1.0, 0.0)
    profile = PSDProfile.from_config(c["profile"])
    result = coupled_board(mesh, modal, c, profile)
    zeta = c["analysis"]["damping_ratio"]
    reference = sdof_response(profile, 300.0, zeta)["relative_displacement_rms_m"]
    assert result["relative_deflection_rms_m"] == pytest.approx(reference, rel=1e-7)
    assert result["relative_deflection_3sigma_m"] == pytest.approx(3 * reference, rel=1e-7)
    assert result["dominant_board_mode"] == 1
    assert result["margin"] == pytest.approx(result["allowable_3sigma_m"] / (3 * reference) - 1)


def test_rigid_board_motion_produces_no_bending():
    mesh, modal, c = board_model(0.7, 0.7)
    result = coupled_board(mesh, modal, c, PSDProfile.from_config(c["profile"]))
    assert result["relative_deflection_rms_m"] == 0
    assert result["margin"] is None


def test_steinberg_inputs_are_optional():
    mesh, modal, c = board_model(1.0, 0.0)
    c = copy.deepcopy(c)
    del c["geometry"]["board"]["steinberg"]
    result = coupled_board(mesh, modal, c, PSDProfile.from_config(c["profile"]))
    assert result["allowable_3sigma_m"] is None and result["margin"] is None
