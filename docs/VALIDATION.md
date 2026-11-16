# Verification and current confidence

The included evidence was produced by executing the code with Gmsh 4.15.2 and CalculiX 2.23 on Linux. `examples/reference_run/manifest.json` records Python/library versions and hashes of the main inputs and outputs. Numerical results can differ slightly with mesher/solver versions. Hardware validation has **not** been performed.

## Independent mathematical checks

The automated tests check flat and inverse-frequency PSD integrals, finite-band behavior, Miles versus broadband SDOF integration, reduction of the modal transfer to an exact single oscillator, coherent cancellation, inch-to-metre conversion, tetrahedron node ordering, support selection, synthetic frequency recovery, sampling checks and provenance protection.

These tests use independent limiting cases rather than merely restating implementation details.

```bash
python -m pytest -m 'not integration' -q
```

## Solver benchmark

The benchmark is a 200 × 20 × 4 mm aluminium cantilever, clamped at x = 0. It compares 3D C3D10 FEA with the Euler-Bernoulli first weak-axis bending solution:

$$f_1=\frac{1.8751040687^2}{2\pi L^2}\sqrt{\frac{EI}{\rho A}}.$$

| Result | Frequency |
|---|---:|
| Analytical | 82.2522 Hz |
| CalculiX | 82.7396 Hz |
| Absolute relative error | 0.5926% |
| Benchmark acceptance | Below 5% |

The 5% criterion allows 3D clamp effects, shear effects and mesh error relative to ideal beam theory. Passing verifies the solver/deck/mesh route for a known problem. It does not establish accuracy for a bolted enclosure.

Recorded data: `examples/verification/validation.json`.

## Enclosure mesh refinement

| Target mesh size | Nodes | Elements | First frequency | Mode 3 | Probe acceleration | Change from previous |
|---:|---:|---:|---:|---:|---:|---:|
| 12 mm | 6,870 | 3,525 | 1235.798 Hz | 2073.9 Hz | 17.1719 g RMS | — |
| 9 mm | 10,473 | 5,346 | 1212.265 Hz | 2004.2 Hz | 19.3777 g RMS | 11.38% |
| 6 mm | 19,214 | 9,757 | 1201.373 Hz | 1957.3 Hz | 21.3585 g RMS | 9.27% |
| 4.5 mm | 32,713 | 16,527 | 1197.377 Hz | 1946.2 Hz | 21.6608 g RMS | 1.40% |
| 3.5 mm | 51,074 | 25,706 | 1196.747 Hz | 1944.2 Hz | 21.7058 g RMS | 0.21% |

All runs use 50 modes. The first frequency changes by 0.05% and the probe response by 0.21% between the two finest meshes, so both are converged for this model.

**Why the coarse meshes under-predict.** Mode 3 carries 13.5% of the Z effective mass and has the largest probe coefficient. Coarse quadratic tetrahedra make it too stiff, placing it at 2074 Hz and 2004 Hz, just outside the 2000 Hz profile limit, where it receives almost no input. Refinement lowers it to 1944 Hz, inside the band. The response therefore rises sharply until mode 3 settles. The 9 mm screening mesh used by the reference run reads **10.7% low** against the 3.5 mm result; 6 mm is 1.6% low and 4.5 mm is 0.2% low.

Mode 3 remains within three half-power half-bandwidths (3ζf) of the 2000 Hz limit even when converged. Every run now lists such modes in `band_edge_modes` and adds a warning, because real hardware frequencies differing by a few percent would change the in-band response noticeably. Use a 4.5 mm or finer mesh for amplitudes on this geometry.

A separate fixed-mesh 10-to-50-mode study captures 90.26% of the solver's available Z mass at 50 modes; probe acceleration changes by 0.0257% from 40 to 50 modes. This is modal-truncation evidence, separate from mesh convergence. X/Y mass capture is 83.76% / 77.89%; those axes need further study. See STUDIES.md.

Sorted mode comparison is not modal assurance criterion (MAC) tracking; modes can swap order. Stress convergence is outside the current implementation.

Recorded data: `examples/verification/convergence.json`, `.csv` and `.png`.

## End-to-end tests

```bash
python -m pytest -m integration -q
```

These execute the beam benchmark, a generated tray using the cited Category 24 spectrum, synthetic tap processing, report generation, the hash manifest and STEP export/reimport. Additional mathematical tests check the spectrum integral and solver-total mass denominator. The STEP test requires the first three frequencies to agree within 2.5%, accounting for remeshing.

GitHub Actions includes unit checks on Linux/Windows and a Linux CalculiX integration job. CI is configured, but a remote workflow run is not claimed until it has actually executed on GitHub.

## Physical work still pending

- Fabricate or obtain an enclosure matching the CAD, material and mounting.
- Acquire at least three repeatable tap records under the same boundary conditions.
- Check candidate mode identity by changing sensor/tap position.
- Compare measured resonance frequency with prediction; document differences without tuning material values solely to force agreement.
- Measure/estimate damping independently before relying on response amplitudes.

Synthetic data verifies the analysis code path, not the structural model. A frequency comparison alone does not validate stresses, fatigue or standards compliance.
