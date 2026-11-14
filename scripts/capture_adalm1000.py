#!/usr/bin/env python3
"""Optional, hardware-unverified ADALM1000 input-only capture using vendor pysmu."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def capture(path, duration_s=3.0, channel="A"):
    if not 0 < duration_s <= 30 or channel not in ("A", "B"):
        raise ValueError("Use 0 < duration <= 30 seconds and channel A or B")
    path = Path(path)
    if path.exists() or path.with_suffix(".meta.json").exists():
        raise ValueError("Output already exists; choose a new capture path")
    try:
        from pysmu import Mode, Session
    except ImportError as exc:
        raise RuntimeError(
            "Install vendor libsmu/pysmu and USB drivers first; see docs/HARDWARE.md"
        ) from exc
    session = Session(sample_rate=100000)
    if not session.devices:
        raise RuntimeError("No ADALM1000 device is connected or accessible")
    if len(session.devices) != 1:
        raise RuntimeError("Connect exactly one ADALM1000 to avoid capturing the wrong device")
    dev = session.devices[0]
    dev.channels["A"].mode = Mode.HI_Z
    dev.channels["B"].mode = Mode.HI_Z
    dev.ignore_dataflow = False
    fs = float(session.sample_rate)
    count = int(fs * duration_s)
    if count < 128:
        raise ValueError("Capture duration is too short")
    voltages = []
    print("Capturing INPUT ONLY. Tap the mounted enclosure now.", flush=True)
    try:
        session.start(0)
        while len(voltages) < count:
            samples = dev.read(min(1000, count - len(voltages)), 3000)
            if not samples:
                raise RuntimeError("Acquisition timed out; no empty captures are saved")
            voltages.extend(float(sample[0 if channel == "A" else 1][0]) for sample in samples)
    finally:
        session.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    time = np.arange(count) / fs
    np.savetxt(
        path,
        np.column_stack([time, voltages[:count]]),
        delimiter=",",
        header="time_s,voltage_v",
        comments="",
        fmt="%.10g",
    )
    metadata = {
        "provenance": "physical",
        "device": "ADALM1000",
        "serial": str(dev.serial),
        "channel": channel,
        "sample_rate_hz": fs,
        "samples": count,
        "note": "Uncalibrated sensor voltage; fixture and conditioning must be documented.",
    }
    path.with_suffix(".meta.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved {count} samples to {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=3.0)
    parser.add_argument("--channel", choices=["A", "B"], default="A")
    args = parser.parse_args()
    try:
        capture(args.out, args.duration_s, args.channel)
    except (ValueError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2)
