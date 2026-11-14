# Installation

## Linux or Windows with WSL (recommended)

On Windows, install Ubuntu through WSL using Microsoft's normal setup, then run these commands inside the Ubuntu terminal. Keep the project in the Linux home directory for faster meshing and file output.

```bash
sudo apt-get update
sudo apt-get install -y python3-venv calculix-ccx libglu1-mesa
cd /path/to/vibequal
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,report]'
vibequal doctor
vibequal validate --out runs/beam
vibequal demo --out runs/demo
```

Open the report with a file manager or, from WSL:

```bash
explorer.exe "$(wslpath -w runs/demo/report.html)"
```

To serve the finished report locally instead:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory runs/demo
```

Visit http://127.0.0.1:8000/report.html. The report itself needs neither a server nor Internet access.

## Native Windows

The Python analysis code is portable; the reference run and external solver integration were tested on Linux. WSL is the most reproducible route for this submission. For native Windows:

1. Install 64-bit Python 3.11 or later.
2. Obtain a Windows CalculiX build through links on the [official CalculiX site](https://dhondt.de/), and follow that build's runtime-library instructions.
3. In PowerShell, create a virtual environment and install the project:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,report]"
$env:CCX_BIN = "C:\CalculiX\ccx.exe"
vibequal doctor
vibequal demo --out runs/demo
Start-Process runs/demo/report.html
```

Native Windows hardware drivers and solver packaging were not exercised in this build.

## macOS

Use Python 3.11+, the pip dependencies and an independently installed macOS CalculiX executable. Set `CCX_BIN`. No macOS solver run is claimed in the included evidence.

## What `doctor` does

It checks package versions, loads the Gmsh shared library and finds the configured solver executable. It does not prove that the solver can run. `vibequal validate` executes a real analytical beam benchmark and is the stronger installation check.

## Troubleshooting

| Symptom | Action |
|---|---|
| `libGLU.so.1` is missing | Install `libglu1-mesa` inside Linux/WSL. |
| Solver not found | Install `calculix-ccx`, set `CCX_BIN`, or pass `--ccx /path/to/ccx`. |
| Solver shared-library error | Prefer the distribution's `calculix-ccx` package. Official standalone builds can require older Fortran runtimes. Read `ccx.log`. |
| Output directory is not empty | Choose a new `--out` directory. Results are preserved deliberately. |
| Support patch selects too few nodes | Check STEP units/orientation and support coordinates; refine the mesh if needed. |
| Several solids found | Fuse the intended enclosure to one connected solid, or simplify the CAD. Assemblies and automatic contacts are not supported. |
| STEP import is enormous/tiny | STEP declared units are converted to metres. Check that the originating CAD file declares its physical units correctly; the program does not guess or repair mislabeled inputs. |
| Frequency/response differs from the sample | Compare dependency versions, mesh size, fixed nodes and probe coordinates in the manifest/results. Mesh generation is not bitwise portable. |
| A Matplotlib cache warning appears | Set `MPLCONFIGDIR` to a writable cache directory. It does not affect the physical calculations. |

The application never downloads solver executables, runs `sudo`, or installs packages at runtime.
