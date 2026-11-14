import json

import numpy as np
import pytest

from vibequal.tap import analyze_tap, synthetic_tap


def test_synthetic_frequency_recovery_and_provenance(tmp_path):
    path = tmp_path / "tap.csv"
    synthetic_tap(path, 613.7)
    result, _ = analyze_tap(path, 600, provenance="physical")
    assert abs(result["dominant_peak_hz"] - 613.7) / 613.7 < 0.002
    assert result["provenance"] == "synthetic"
    assert result["difference_percent"] == pytest.approx(
        100 * (result["dominant_peak_hz"] - 600) / 600
    )
    assert json.loads(path.with_suffix(".meta.json").read_text())["provenance"] == "synthetic"


def test_irregular_sampling_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    t = np.arange(1000) / 10000
    t[500:] += 0.1
    np.savetxt(
        path,
        np.column_stack([t, np.sin(2 * np.pi * 100 * t)]),
        delimiter=",",
        header="time_s,voltage_v",
        comments="",
    )
    with pytest.raises(ValueError, match="uniform"):
        analyze_tap(path)


def test_constant_signal_rejected(tmp_path):
    path = tmp_path / "constant.csv"
    np.savetxt(
        path,
        np.column_stack([np.arange(1000) / 10000, np.ones(1000) * 2.5]),
        delimiter=",",
        header="time_s,voltage_v",
        comments="",
    )
    with pytest.raises(ValueError, match="constant"):
        analyze_tap(path)


def test_nyquist_constraint(tmp_path):
    path = tmp_path / "tap.csv"
    synthetic_tap(path, 200, sample_rate_hz=1000)
    with pytest.raises(ValueError, match="sample_rate/2"):
        analyze_tap(path, max_hz=600)
