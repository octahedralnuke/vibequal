# Analysis workflow

The JSON configuration defines geometry, elastic properties, density, supports, mesh size, modal damping, response location and the input acceleration PSD. All mechanical dimensions use metres.

## Running a model

```bash
vibequal doctor
vibequal run examples/enclosure.json --out runs/tray
```

`doctor` checks dependencies. The analysis command creates CAD and a mesh, writes a CalculiX deck, executes the eigenvalue solve, reads the modal results and calculates vibration response. Each run uses a new output directory to preserve the earlier evidence.

`vibequal demo --out runs/demo` uses the bundled configuration and additionally generates an explicitly synthetic tap signal. That signal exercises the processing path; it is not experimental correlation.

## Inspecting a result

- `report.html`: offline report with mode selection, rotation, response plots and model assumptions.
- `modal.inp`, `modal.dat`, `modal.frd`, `ccx.log`: solver input, numerical output, mode visualization data and execution log.
- `enclosure.step`, `enclosure.msh`: exported CAD and mesh.
- `modes.csv`: frequencies, directional mass fractions and per-mode response estimates.
- `response_psd.csv`: input and probe acceleration spectra.
- `results.json`: numerical summary and interpretation limits.
- `manifest.json`: dependency versions and hashes of primary artifacts.

The animated eigenvectors are scaled for display. Their plotted amplitudes are not physical deflections. Physical response uses the excitation, damping, mass-normalized mode shapes and participation factors.

## Verification and sensitivity

```bash
vibequal validate --out runs/beam
vibequal converge examples/enclosure.json --sizes .012 .009 .006 --out runs/mesh-study
python -m pytest -q
```

The beam benchmark checks a known bending frequency. Mesh refinement tests discretization sensitivity. Neither establishes the stiffness or damping of a real mounted enclosure; that requires physical measurements.

## Measured tap data

`vibequal tap` accepts uniformly sampled `time_s,voltage_v` CSV records. The dominant spectral peak is compared with a supplied FEA frequency. Sensor and tap positions, fixture stiffness and repeatability must be assessed before identifying the peak as a particular mode. See [HARDWARE.md](HARDWARE.md) for acquisition requirements.
