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
    result = run(config_path, generated, with_synthetic_tap=True)
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
