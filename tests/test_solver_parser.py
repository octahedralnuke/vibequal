import numpy as np
import pytest

from vibequal.solver import parse_dat

TABLES = """
 E I G E N V A L U E   O U T P U T
 1 394784 628.3185 100 0
 P A R T I C I P A T I O N   F A C T O R S
 1 1 2 3 0 0 0
 E F F E C T I V E   M O D A L   M A S S
 1 1 4 9 0 0 0
 T O T A L   E F F E C T I V E   M A S S
 X-COMPONENT Y-COMPONENT Z-COMPONENT X-ROTATION Y-ROTATION Z-ROTATION
 2.0D+00 5.0D+00 1.0D+01 0.1 0.1 0.1
 F R A C T I O N   O F   T O T A L S
 .5 .8 .9 0 0 0
 E I G E N V A L U E    N U M B E R 1
 displacements (vx,vy,vz) for set ALLNODES and time 1
 1 .1 .2 .3
"""


def test_solver_total_mass_is_not_mistaken_for_a_modal_row(tmp_path):
    path = tmp_path / "modal.dat"
    path.write_text(TABLES)
    result = parse_dat(path, np.array([1]), 1)
    np.testing.assert_allclose(result["total_effective_mass"][:3], [2, 5, 10])
    assert result["effective_mass_kg"].shape == (1, 6)
    assert result["frequencies_hz"][0] == 100


def test_missing_total_mass_fails_instead_of_changing_denominator(tmp_path):
    path = tmp_path / "modal.dat"
    path.write_text(TABLES.replace("2.0D+00 5.0D+00 1.0D+01 0.1 0.1 0.1", ""))
    with pytest.raises(RuntimeError, match="total effective mass"):
        parse_dat(path, np.array([1]), 1)
