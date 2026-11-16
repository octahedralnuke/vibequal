import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from vibequal.config import load_config
from vibequal.pipeline import run, validate_beam
from vibequal.solver import find_ccx


def solver_available():
    try:
        find_ccx()
        import gmsh

        return bool(gmsh.__version__)
    except (RuntimeError, ImportError, OSError):
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not solver_available(), reason="requires Gmsh and ccx"),
]


def test_analytical_beam_benchmark(tmp_path):
    result = validate_beam(tmp_path / "beam")
    assert result["passed"]
    assert result["absolute_error_percent"] < 5


def test_end_to_end_generated_and_imported_step(tmp_path):
    config_path = Path(__file__).parents[1] / "examples" / "enclosure.json"
    generated = tmp_path / "generated"
    profile_path = Path(__file__).parents[1] / "examples/profiles/mil_std_810h_cat24.json"
    result = run(config_path, generated, with_synthetic_tap=True, profile_path=profile_path)
    assert result["response"]["input_grms"] == pytest.approx(np.sqrt(59.2))
    assert result["profile"]["standard_reference"]["category"] == 24
    import gmsh

    gmsh.initialize()
    try:
        gmsh.option.setString("Geometry.OCCTargetUnit", "M")
        gmsh.model.occ.importShapes(str(generated / "enclosure.step"))
        gmsh.model.occ.synchronize()
        bounds = gmsh.model.getBoundingBox(-1, -1)
        np.testing.assert_allclose(
            np.array(bounds[3:]) - np.array(bounds[:3]), [0.16, 0.10, 0.04], atol=3e-7
        )
    finally:
        gmsh.finalize()
    assert result["response"]["modes"][0]["frequency_hz"] > 100
    assert result["tap"]["provenance"] == "synthetic"
    assert abs(result["tap"]["difference_percent"] - 3) < 0.3
    report = (generated / "report.html").read_text()
    assert "__VIEWER_DATA__" not in report
    assert "SYNTHETIC DATA" in report
    manifest = json.loads((generated / "manifest.json").read_text())
    assert len(manifest["files_sha256"]["modal.inp"]) == 64
    c = load_config(config_path)
    c["geometry"] = {"type": "step", "path": "imported.step"}
    shutil.copy2(generated / "enclosure.step", tmp_path / "imported.step")
    imported_config = tmp_path / "import.json"
    imported_config.write_text(json.dumps(c))
    imported = run(imported_config, tmp_path / "imported")
    np.testing.assert_allclose(
        [m["frequency_hz"] for m in imported["response"]["modes"][:3]],
        [m["frequency_hz"] for m in result["response"]["modes"][:3]],
        rtol=0.025,
    )
    assert imported["physical_validation"] == "not_performed"


def test_assembly_with_lid_and_coupled_board(tmp_path):
    from vibequal.config import board_density

    c = json.loads((Path(__file__).parents[1] / "examples" / "assembly.json").read_text())
    c["mesh"]["size_m"] = 0.009
    c["geometry"]["board"]["mesh_size_m"] = 0.005
    c["analysis"]["modes"] = 10
    config_path = tmp_path / "assembly.json"
    config_path.write_text(json.dumps(c))
    result = run(config_path, tmp_path / "run")
    deck = (tmp_path / "run" / "modal.inp").read_text()
    assert "ELSET=BOARD" in deck and "MATERIAL=BOARD" in deck
    g, b = c["geometry"], c["geometry"]["board"]
    board_volume = b["length_m"] * b["width_m"] * b["thickness_m"]
    tray = (
        g["length_m"] * g["width_m"] * g["height_m"]
        - (g["length_m"] - 0.006) * (g["width_m"] - 0.006) * (g["height_m"] - 0.003)
        - 4 * np.pi * g["hole_radius_m"] ** 2 * 0.003
    )
    lid = g["length_m"] * g["width_m"] * g["lid"]["thickness_m"]
    posts = 4 * np.pi * b["standoff_radius_m"] ** 2 * b["standoff_height_m"]
    expected = (tray + lid + posts) * 2700 + board_volume * board_density(b)
    assert result["mesh"]["mass_kg"] == pytest.approx(expected, rel=1e-6)
    board = result["coupled_pcb"]
    # The board on corner standoffs is the softest part of the assembly.
    assert board["dominant_board_mode"] == 1
    assert 150 < board["dominant_board_mode_frequency_hz"] < 450
    assert board["relative_deflection_3sigma_m"] > 0 and board["margin"] is not None
    assert (tmp_path / "run" / "figures" / "board_mode.png").is_file()
