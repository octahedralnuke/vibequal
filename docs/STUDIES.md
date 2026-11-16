# Geometry and modal studies

## Design question

How much first-frequency gain can a small tray obtain from added material or a different mounting pattern? The comparison keeps the outer dimensions, aluminium properties, nominal 9 mm mesh target, 50 modes, damping and illustrative Z-axis PSD fixed.

`examples/design_variants.json` defines the baseline and three controlled changes. The rib spans the cavity along X, with a 3 mm width and 8 mm height above the base. Its ends meet the walls and the CAD is fused into one solid. Moving the hole pattern also moves the clamped patches; the supports are not left at the old holes.

| Variant | First frequency | Frequency change | Mass change |
|---|---:|---:|---:|
| Baseline 3 mm | 1212.265 Hz | 0% | 0% |
| 4 mm walls/base | 1613.960 Hz | +33.14% | +30.83% |
| Longitudinal rib | 1324.734 Hz | +9.28% | +3.55% |
| Mounts 22 mm inboard | 1379.923 Hz | +13.83% | approximately 0% |

When the mounting interface is fixed, the rib is the more mass-efficient candidate among the tested stiffness changes. It adds 9.98 g rather than 86.74 g for the thicker tray. The mount change needs a different installation interface; it is not a free change to an existing fixture.

The candidate is checked again with 6 mm meshes. The refined rib gives 1310.304 Hz against 1201.373 Hz for the refined baseline: **+9.07%**. The gain survives this refinement, though this is not a complete geometry optimization or experimental validation. First sorted modes can change identity. Higher frequency alone does not guarantee lower vibration response for an arbitrary PSD.

The response amplitudes in the design CSV are exploratory. Geometry changes require remeshing, and nearest probe nodes differ. They are not used as the design ranking metric. The support patches remain ideal clamps and all variants omit the lid, payload and assembly joints.

```bash
vibequal design-study examples/design_variants.json --out runs/designs
vibequal run examples/ribbed_refined.json --out runs/refined-rib
```

## Modal truncation

`mode-study` solves the largest requested basis once, then evaluates prefixes. That holds mesh, supports and response location exactly fixed and isolates modal truncation from remeshing error.

| Modes | Z mass / solver total | Z mass / CAD | Probe g RMS |
|---:|---:|---:|---:|
| 10 | 26.32% | 26.24% | 19.5421 |
| 20 | 62.32% | 62.11% | 19.3455 |
| 30 | 84.38% | 84.10% | 19.3727 |
| 40 | 84.52% | 84.24% | 19.3727 |
| 50 | 90.26% | 89.96% | 19.3777 |

The first denominator is CalculiX's total effective translational mass of the free system. Full CAD mass includes constrained material. Both are recorded so the denominator is explicit. At 50 modes, X/Y capture remains 83.76% / 77.89%; the Z result does not establish adequacy for every input axis.

The Z response changes by 0.0257% from 40 to 50 modes. Mesh refinement is a separate uncertainty: the 9 mm mesh reads 10.7% low against the converged 3.5 mm response because mode 3 sits just outside the 2000 Hz profile limit until the mesh is refined (see VALIDATION.md). No residual-flexibility or missing-mass correction is applied, and the numerical stability does not determine the physical damping.

```bash
vibequal mode-study examples/enclosure.json --counts 10 20 30 40 50 --out runs/mode-count
```

## Evidence retained in the repository

The study folders contain CSV/JSON summaries, plots, input decks, configuration snapshots, console logs, exported CAD and unmodified frequency/participation/mass table excerpts. `solver_tables.txt` stops before the nodal displacement blocks. The manifests hash the complete original runs; large raw `.dat`, `.frd` and mode-array files are omitted from these curated study folders. The commands above regenerate complete raw files. The main reference run retains its full modal results.
