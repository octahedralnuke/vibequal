# Configuration

Copy `examples/enclosure.json`, edit it, then run:

```bash
vibequal run examples/my_enclosure.json --out runs/my_enclosure
```

All geometry lengths are **metres**. Elastic modulus is Pa; density is kg/m³. Excitation frequency is Hz; acceleration spectral density is **g²/Hz**, not g/√Hz. Internally `g0 = 9.80665 m/s²` converts acceleration to displacement units.

## CAD and mesh

`geometry.type = "tray"` generates an open enclosure with a uniform wall/base thickness and four cylindrical mounting holes. The default is 160 × 100 × 40 mm, with 3 mm thickness, 2.2 mm hole radius and mounting centres 12 mm from each side.

To import a single solid:

```json
"geometry": {"type": "step", "path": "cad/enclosure.step"}
```

The path resolves relative to the JSON configuration. Gmsh converts the STEP file's declared length units into metres. Support/probe coordinates remain metres; mounting faces are not discovered automatically. The exporter writes corresponding millimetre coordinates with a millimetre STEP length context, making the 0.16 m tray physically 160 mm in external CAD. A ready example is provided as `examples/import_step.json`.

`mesh.size_m` is the nominal maximum mesh size. Curvature and geometric constraints can create smaller elements. Only quadratic tetrahedra are accepted; the six mid-edge nodes are mapped into CalculiX C3D10 ordering explicitly.

Meshing is rejected when CAD maximum extent divided by target mesh size exceeds 1000. This catches gross unit mistakes and impractically fine inputs before mesh generation; simplify the model or increase the target size.

## Supports

The default clamps all three translational DOFs at nodes on the bottom plane and inside four circular mounting patches. Hole interiors contain no nodes. Every patch must select at least three nodes; the combined support set must not be collinear.

For different geometry, use axis-aligned coordinate boxes:

```json
"supports": {
  "type": "boxes",
  "bounds_m": [[-0.000001, 0, 0, 0.000001, 0.1, 0.04]]
}
```

Each box is `[xmin,ymin,zmin,xmax,ymax,zmax]`. Supports are ideal clamps, not bolt/contact models. Check `fixed_nodes`, the plotted amber support markers, and the generated `*BOUNDARY` card.

## Modal and response settings

- `analysis.modes`: number of eigenmodes, integer 1–100.
- `analysis.damping_ratio`: critical damping fraction, e.g. `0.025` means 2.5%. Modal FEA does not identify this value.
- `analysis.axis`: `x`, `y` or `z`; both input and reported probe acceleration use this axis.
- `analysis.probe_xyz_m`: desired response location. The nearest FE node is used. Its actual coordinate and snap distance are saved. Clamped probe nodes are rejected.
- `analysis.solver_timeout_s`: maximum external solver runtime.

Mesh changes can move the nearest probe node and slightly alter the discretized support area. Compare the saved coordinates as part of a convergence study. Mode visualization gain has no effect on the calculation.

## Excitation

`profile.breakpoints_hz_g2_per_hz` contains strictly increasing, positive `[Hz, g²/Hz]` pairs. Interpolation is linear in log-frequency/log-density space, so each segment is a power law. Density is zero outside the provided band. Zero-density internal points and discontinuities are not represented by this format.

`profile.name` and `profile.source` must describe the actual origin of a profile. The default is deliberately educational. If you use a standards-derived profile, record its actual revision, section, category, aircraft/installation, axis and tailoring rationale. Do not simply rename the demonstration profile.

`duration_s` records intended exposure duration. Stationary RMS response does not depend on exposure duration, and this project does not turn it into predicted fatigue life.

## PCB

The supported model is `independent_simply_supported_isotropic_plate`. Set `enabled` to false to omit it. Modulus and density are equivalent homogeneous properties; component mass is smeared over the board. All four edges are simply supported. The first plate mode and its base participation are used for centre deflection.

`board_edge_parallel_to_component_m`, `component_length_m`, `package_constant` and `position_factor` feed the empirical Steinberg limit. The reference `C=1`, `r=1` is illustrative of a centred component with an applicable package factor; it is not universal. The inch-based coefficient is evaluated in inches, then converted to metres.

The PCB sees the input profile directly at its supports. The program does not automatically substitute the enclosure probe spectrum, which would require a defensible board-support/coupling model.
