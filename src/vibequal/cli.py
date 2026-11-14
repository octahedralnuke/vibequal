"""Command-line entry point; no network access or global setup is performed at runtime."""

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path

from . import __version__


def parser():
    p = argparse.ArgumentParser(prog="vibequal", description="CAD-to-modal vibration screening")
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Check Python dependencies and the external solver")
    doctor.add_argument("--ccx")
    for name, help_text in [
        ("run", "Run an enclosure configuration"),
        ("demo", "Run the bundled enclosure with a SYNTHETIC tap comparison"),
    ]:
        cmd = commands.add_parser(name, help=help_text)
        if name == "run":
            cmd.add_argument("config", type=Path)
            cmd.add_argument("--synthetic-tap", action="store_true")
        cmd.add_argument("--out", type=Path, default=Path("runs/demo"))
        cmd.add_argument("--ccx", help="CalculiX executable path, or use CCX_BIN")
    convergence = commands.add_parser("converge", help="Run a mesh refinement study")
    convergence.add_argument("config", type=Path)
    convergence.add_argument("--out", type=Path, default=Path("runs/convergence"))
    convergence.add_argument("--sizes", type=float, nargs="+", default=[0.012, 0.009, 0.006])
    convergence.add_argument("--ccx")
    benchmark = commands.add_parser("validate", help="Verify against an analytical cantilever")
    benchmark.add_argument("--out", type=Path, default=Path("runs/validation"))
    benchmark.add_argument("--ccx")
    tap = commands.add_parser("tap", help="Analyze a time_s,voltage_v CSV ringdown")
    tap.add_argument("csv", type=Path)
    tap.add_argument("--expected-hz", type=float)
    tap.add_argument("--band", type=float, nargs=2, default=[20.0, 2000.0])
    tap.add_argument(
        "--provenance", choices=["unverified", "physical", "synthetic"], default="unverified"
    )
    tap.add_argument("--out", type=Path, default=Path("runs/tap"))
    synthetic = commands.add_parser("make-tap", help="Generate an explicitly synthetic CSV")
    synthetic.add_argument("--frequency-hz", type=float, required=True)
    synthetic.add_argument("--sample-rate-hz", type=float, default=10000)
    synthetic.add_argument("--out", type=Path, default=Path("synthetic_tap.csv"))
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            from .solver import find_ccx

            for package in ["numpy", "scipy", "matplotlib", "gmsh"]:
                print(f"{package}: {importlib.metadata.version(package)}")
            try:
                import gmsh

                gmsh.initialize()
                gmsh.finalize()
            except (ImportError, OSError) as exc:
                raise RuntimeError(
                    "Gmsh could not load; install libglu1-mesa on Ubuntu/WSL"
                ) from exc
            print(f"CalculiX: {find_ccx(args.ccx)}")
            print(
                "Dependency checks passed. Run 'vibequal validate' to execute a solver benchmark."
            )
        elif args.command in ("run", "demo"):
            from .pipeline import run

            config = (
                args.config
                if args.command == "run"
                else Path(__file__).parent / "data" / "enclosure.json"
            )
            run(
                config,
                args.out,
                args.ccx,
                with_synthetic_tap=args.command == "demo" or args.synthetic_tap,
            )
        elif args.command == "converge":
            from .pipeline import convergence

            result = convergence(args.config, args.out, args.sizes, args.ccx)
            print(json.dumps(result, indent=2))
        elif args.command == "validate":
            from .pipeline import validate_beam

            result = validate_beam(args.out, args.ccx)
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 1
        elif args.command == "tap":
            from .pipeline import prepare_output, write_json
            from .report import create_tap_plot
            from .tap import analyze_tap

            result, arrays = analyze_tap(args.csv, args.expected_hz, *args.band, args.provenance)
            out = prepare_output(args.out)
            write_json(out / "tap_results.json", result)
            create_tap_plot(arrays, result, out / "tap.png")
            print(json.dumps(result, indent=2))
            print(f"Plot: {out / 'tap.png'}")
        elif args.command == "make-tap":
            from .tap import synthetic_tap

            if args.out.exists() or args.out.with_suffix(".meta.json").exists():
                raise ValueError("Synthetic output path already exists; choose a new file")
            synthetic_tap(args.out, args.frequency_hz, sample_rate_hz=args.sample_rate_hz)
            print(f"SYNTHETIC data: {args.out}")
    except (
        ValueError,
        RuntimeError,
        KeyError,
        FileNotFoundError,
        ImportError,
        importlib.metadata.PackageNotFoundError,
    ) as exc:
        print(f"vibequal: {exc}", file=sys.stderr)
        return 2
    return 0
