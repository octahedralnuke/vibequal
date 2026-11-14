"""Tap-test CSV analysis and explicitly synthetic acquisition demonstrations."""

import json
from pathlib import Path

import numpy as np
from scipy.signal import detrend, find_peaks, periodogram


def synthetic_tap(path, frequency_hz, sample_rate_hz=10000, duration_s=3.0, damping=0.012, seed=42):
    if not 0 < frequency_hz < 0.4 * sample_rate_hz or duration_s <= 0 or not 0 < damping < 1:
        raise ValueError("Synthetic signal needs positive duration, 0<damping<1, and f<0.4 fs")
    t = np.arange(int(sample_rate_hz * duration_s)) / sample_rate_hz
    rng = np.random.default_rng(seed)
    delay = 0.12
    tau = np.maximum(t - delay, 0)
    ringdown = np.exp(-damping * 2 * np.pi * frequency_hz * tau) * np.sin(
        2 * np.pi * frequency_hz * np.sqrt(1 - damping**2) * tau
    )
    voltage = 2.5 + 0.8 * ringdown * (t >= delay) + rng.normal(0, 0.003, len(t))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(
        path,
        np.column_stack([t, voltage]),
        delimiter=",",
        header="time_s,voltage_v",
        comments="",
        fmt="%.10g",
    )
    metadata = {
        "provenance": "synthetic",
        "true_undamped_frequency_hz": frequency_hz,
        "damping_ratio": damping,
        "seed": seed,
        "description": "Generated ringdown. This is NOT a physical measurement.",
    }
    path.with_suffix(".meta.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def analyze_tap(path, expected_hz=None, min_hz=20, max_hz=2000, provenance="unverified"):
    path = Path(path)
    data = np.genfromtxt(path, delimiter=",", names=True, encoding="utf-8-sig")
    if not data.dtype.names or not {"time_s", "voltage_v"}.issubset(data.dtype.names):
        raise ValueError("Tap CSV must have time_s,voltage_v columns")
    t, v = np.atleast_1d(data["time_s"]), np.atleast_1d(data["voltage_v"])
    if len(t) < 128 or not np.all(np.isfinite(t)) or not np.all(np.isfinite(v)):
        raise ValueError("Tap CSV needs at least 128 finite time and voltage samples")
    dt = np.diff(t)
    if np.any(dt <= 0) or np.std(dt) / np.mean(dt) > 0.01:
        raise ValueError("Time samples must be increasing and uniform to within 1% jitter")
    fs = 1 / np.mean(dt)
    if not 0 < min_hz < max_hz < fs / 2:
        raise ValueError("Search band must satisfy 0 < min_hz < max_hz < sample_rate/2")
    metadata_path = path.with_suffix(".meta.json")
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("provenance") == "synthetic":
            provenance = "synthetic"  # Never relabel the bundled synthetic data as measured.
    if provenance not in ("synthetic", "physical", "unverified"):
        raise ValueError("Unknown tap provenance")
    y = detrend(v, type="constant")
    if np.std(y) < 1e-9:
        raise ValueError("Tap signal is constant or too small to analyze")
    # Crop immediately after the largest excursion; rectangular window retains fast ringdowns.
    start = max(0, int(np.argmax(abs(y))) - 2)
    if len(y) - start < 128:
        raise ValueError("Not enough post-impact samples; capture a longer ringdown")
    f, spectrum = periodogram(y[start:], fs=fs, window="boxcar", nfft=max(8192, 4 * len(y[start:])))
    band = (f >= min_hz) & (f <= max_hz)
    fb, sb = f[band], spectrum[band]
    peaks, _ = find_peaks(sb)
    if not len(peaks):
        raise ValueError("No interior spectral peak found in the search band")
    strongest = peaks[np.argsort(sb[peaks])[::-1]][:5]
    index = int(strongest[0])
    # Three-point log-parabolic interpolation reduces FFT-bin quantization.
    left, centre, right = np.log(np.maximum(sb[index - 1 : index + 2], np.finfo(float).tiny))
    denominator = left - 2 * centre + right
    offset = float(0.5 * (left - right) / denominator) if denominator else 0.0
    peak_hz = float(fb[index] + np.clip(offset, -0.5, 0.5) * (fb[1] - fb[0]))
    warnings = []
    clipped = float(np.mean((v <= 0.002) | (v >= 4.998)))
    if clipped:
        warnings.append("Samples reach the ADALM1000 0–5 V rails; inspect signal conditioning.")
    if expected_hz is not None and expected_hz <= 0:
        raise ValueError("Expected frequency must be positive")
    difference = None if expected_hz is None else 100 * (peak_hz - expected_hz) / expected_hz
    result = {
        "provenance": provenance,
        "sample_rate_hz": float(fs),
        "samples": len(t),
        "duration_s": float(t[-1] - t[0]),
        "record_resolution_hz": float(fs / (len(y) - start)),
        "dominant_peak_hz": peak_hz,
        "expected_frequency_hz": expected_hz,
        "difference_percent": difference,
        "candidate_peaks_hz": [float(fb[i]) for i in strongest],
        "peak_to_median_spectral_ratio": float(sb[index] / max(np.median(sb), 1e-30)),
        "warnings": warnings,
        "interpretation": "Dominant output-only spectral peak; mode identity is not established. "
        "Check mounting, tap/sensor positions and repeatability. No calibrated acceleration "
        "or input-force frequency-response function is measured.",
    }
    return result, {"time_s": t, "voltage_v": v, "frequency_hz": f, "spectrum_v2_hz": spectrum}
