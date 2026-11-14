# Submission checklist

- Read README, THEORY, VALIDATION and DEMO.
- Open `examples/reference_run/report.html` and `docs/PROJECT_REPORT.pdf`.
- Install on the demonstration machine and run `vibequal doctor` and `vibequal validate`.
- Run the unit tests; run all tests if CalculiX is installed.
- Rehearse a fresh `vibequal demo --out runs/rehearsal`.
- Include the source repository, CAD, configuration, report, recorded verification and raw example solver output.
- Keep tap data labeled synthetic unless you have acquired a real measurement.
- Describe the project as a vibration screening prototype. Record actual completed work and any required assistance disclosure under your evaluation rules.
- Add your name/roll number only where your institution requires them; no identity fields or dates of earlier work have been fabricated.

## A defensible project description

> Implemented a Python pipeline using Gmsh and CalculiX to generate/import enclosure CAD, mesh quadratic solids, extract modal frequencies and estimate random-vibration response from specified acceleration PSDs. Verified the solver workflow against an analytical beam benchmark and examined mesh sensitivity. Added an independent Steinberg-based PCB deflection screen and a tap-signal analysis workflow demonstrated with explicitly synthetic data; physical frequency correlation remains pending.

## Publishing

The directory is ready to be a Git repository. Once GitHub CLI is installed and authenticated, `scripts/publish_github.sh` creates a private repository named `vibequal` by default and pushes the local commit. The script does not authenticate automatically and never asks you to paste a token into source code. See its `--help` output. A public evaluation repository can be selected explicitly if appropriate.
