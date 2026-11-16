# VibeQual analysis run

Aluminium enclosure with lid and PCB on standoffs

Simulation: CalculiX 2.21; C3D10; SI units.

- Nodes: 70,013; elements: 35,488.
- CAD mass: 0.421838 kg.
- First natural frequency: 269.761 Hz.
- Base input: 6.0367 g RMS; axis z; damping 2.50%.
- Truncated modal probe acceleration: 38.9424 g RMS.
- Probe relative displacement (3σ): 0.00942 mm.

## Interpretation

These are simulation outputs, not qualification findings. See report.html for mode animation, response plots, PCB assumptions and synthetic tap provenance.

## Limitations

- Simulation only. No physical qualification or compliance is demonstrated.
- Linear elastic model; mounting patches idealize perfectly clamped connections.
- Probe response uses a truncated, coherent modal sum for one base-input axis.
- Input PSD is illustrative unless replaced with a documented requirement.
- PCB result is an independent plate estimate with direct base PSD; it is not an enclosure-coupled fatigue-life prediction.
- The board is coupled to the enclosure through bonded standoffs. Its deflection uses assumed damping and smeared component mass; the Steinberg comparison is an empirical screen, not a fatigue-life prediction.
- The lid is bonded to the wall tops; real screwed lids are less stiff.
