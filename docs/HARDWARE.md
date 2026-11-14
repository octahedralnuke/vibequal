# ADALM1000 tap-test workflow

The software can analyze real captures, but **no ADALM1000 or physical enclosure was available for testing this build**. The optional adapter follows the upstream pysmu API; its hardware path remains unverified. The included ringdown is explicitly synthetic.

## What the test can establish

An output-only tap recording can identify candidate resonances for comparison with FEA. It does not measure a calibrated acceleration response, force-to-response FRF, a full mode shape, random-vibration endurance or fatigue life.

## Suggested setup

- Physical enclosure with dimensions/material close to the CAD.
- Rigid fixture matching the model's mounting patches as closely as practical.
- Lightweight bonded piezo sensor or a suitable conditioned vibration sensor.
- High-input-impedance buffer or charge amplifier, a mid-supply bias, voltage limiting and suitable analog filtering.
- ADALM1000, USB cable and Analog Devices libsmu/pysmu or ALICE acquisition software.

The ADALM1000 measures 0-5 V. A raw piezo can produce bipolar impact transients; do not assume it can be wired directly to the input. Design and check the conditioning circuit against the sensor and device data sheets before connecting it. A passive piezo disc does not need IEPE excitation; a commercial IEPE sensor does, and the ADALM1000 is not an IEPE conditioner.

Conceptual signal chain:

```text
Bonded piezo -> high-impedance conditioning -> 2.5 V-biased,
               amplitude-limited voltage -> ADALM1000 CH A
Fixture and electronics use an appropriate common reference.
```

This is a functional block diagram, not a verified circuit schematic. Component values depend on the chosen sensor, bandwidth, supply and expected impact amplitude. Use real-time sampling and suitable anti-alias filtering; equivalent-time sampling is inappropriate for a nonrepeating ringdown.

## Capture

1. Match the mounting conditions. Bond the sensor lightly and record its position and mass.
2. Acquire a few seconds at 100 kS/s, with time before and after the tap.
3. Tap away from the sensor and mounting fixture. Avoid saturating the conditioning chain.
4. Repeat at least three times and change excitation/sensor position if the predicted mode is weak.
5. Save uniform samples with this exact CSV header:

```csv
time_s,voltage_v
0.00000,2.5001
0.00001,2.4998
```

ALICE/vendor captures can be converted to this two-column format. Timestamps must represent the true sample period, not wall-clock times for each USB chunk.

An optional adapter is included:

```bash
# First install libsmu/pysmu and the vendor USB driver/permissions separately.
python scripts/capture_adalm1000.py --out measurement.csv --duration-s 3 --channel A
vibequal tap measurement.csv --expected-hz 1212.265 --band 20 2000 \
  --provenance physical --out runs/measured_tap
```

The adapter keeps both channels in high impedance, does not source voltage/current, reads in finite chunks and records device metadata. It deliberately fails on missing devices, timeouts or dropped-sample errors. If the adapter/driver is unsuitable on your system, use the vendor GUI and import a correctly formatted CSV.

## Interpretation

Review `tap.png`, candidate peaks and warnings. The strongest peak can belong to the fixture, sensor or another structural mode. The software reports a dominant peak and a difference from the requested reference; it does not automatically label that peak as the enclosure's first mode. Clipping, sensor resonances, mounting differences and short records can bias the estimate.

Record photographs, dimensions, fixture details, sample rate, sensor location and repeatability beside measured results. Never replace the synthetic-data label with a physical-data label without an actual acquisition.
