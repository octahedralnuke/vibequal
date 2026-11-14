# VibeQual analysis run

Aluminium tray - baseline vibration screen

Simulation: CalculiX 2.23; C3D10; SI units.

- Nodes: 10,473; elements: 5,346.
- CAD mass: 0.281355 kg.
- First natural frequency: 1212.265 Hz.
- Base input: 6.0367 g RMS; axis z; damping 2.50%.
- Truncated modal probe acceleration: 19.3777 g RMS.
- Probe relative displacement (3σ): 0.00818 mm.

## Interpretation

These are simulation outputs, not qualification findings. See report.html for mode animation, response plots, PCB assumptions and synthetic tap provenance.

## Limitations

- Simulation only. No physical qualification or compliance is demonstrated.
- Linear elastic model; mounting patches idealize perfectly clamped connections.
- Probe response uses a truncated, coherent modal sum for one base-input axis.
- Input PSD is illustrative unless replaced with a documented requirement.
- PCB result is an independent plate estimate with direct base PSD; it is not an enclosure-coupled fatigue-life prediction.
