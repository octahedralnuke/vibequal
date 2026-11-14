"""Reproducible execution, provenance, result export, convergence and validation."""

import copy
import csv
import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import __version__
from .config import load_config
from .geometry import build_mesh
from .pcb import screen_pcb
from .solver import find_ccx, solve
from .tap import analyze_tap, synthetic_tap
from .vibration import PSDProfile, modal_response


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")


def hash_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def csv_rows(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prepare_output(path):
    out = Path(path).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"Output directory is not empty: {out}. Choose a new run directory.")
    out.mkdir(parents=True, exist_ok=True)
    return out


def run(config_path, output, ccx=None, with_synthetic_tap=False, profile_path=None):
    config = load_config(config_path)
    if profile_path is not None:
        profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        PSDProfile.from_config(profile)
        config["profile"] = profile
    executable = find_ccx(ccx)  # Fail before writing outputs if the external solver is absent.
    out = prepare_output(output)
    write_json(out / "config.resolved.json", config)
    print("[1/5] Generating CAD and quadratic tetrahedral mesh…", flush=True)
    mesh = build_mesh(config, out)
    print(f"      {len(mesh.node_ids):,} nodes / {len(mesh.tetra10):,} elements", flush=True)
    print("[2/5] Solving real CalculiX eigenvalue problem…", flush=True)
    modal = solve(mesh, config, out, executable)
    print(f"      First frequency: {modal['frequencies_hz'][0]:.3f} Hz", flush=True)
    print("[3/5] Integrating base-excitation response PSD…", flush=True)
    response, spectra = modal_response(mesh, modal, config)
    profile = PSDProfile.from_config(config["profile"])
    warnings = [
        "Simulation only. No physical qualification or compliance is demonstrated.",
        "Linear elastic model; mounting patches idealize perfectly clamped connections.",
        "Probe response uses a truncated, coherent modal sum for one base-input axis.",
    ]
    if config["profile"].get("standard_reference"):
        warnings.append(
            "A published reference spectrum is used for numerical screening. "
            "Applicability, tailoring and physical test execution are not established."
        )
        warnings.append(config["profile"]["standard_reference"]["limitation"])
    else:
        warnings.append("Input PSD is illustrative unless replaced with a documented requirement.")
    fraction = response.get(
        "effective_mass_fraction_of_solver_total", response["effective_mass_fraction_of_cad"]
    )
    if fraction < 0.9:
        warnings.append(
            f"Extracted directional modal mass is {100 * fraction:.1f}% of the solver's "
            "total effective mass in the excitation direction. Increase mode count "
            "and check response convergence before relying on amplitudes."
        )
    if modal["frequencies_hz"][-1] < profile.frequency[-1]:
        warnings.append(
            "Highest extracted mode lies inside the input band; omitted higher "
            "modes may affect the response."
        )
    pcb = None
    if config.get("pcb", {}).get("enabled"):
        pcb = screen_pcb(config["pcb"], profile)
        warnings.append(
            "PCB result is an independent plate estimate with direct base PSD; "
            "it is not an enclosure-coupled fatigue-life prediction."
        )
    summary = {
        "project": "VibeQual",
        "version": __version__,
        "name": config["name"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": "CalculiX finite-element simulation",
        "physical_validation": "not_performed",
        "qualification_status": "not_assessed",
        "mesh": {
            "nodes": len(mesh.node_ids),
            "elements": len(mesh.tetra10),
            "fixed_nodes": len(mesh.fixed_ids),
            "volume_m3": mesh.volume_m3,
            "mass_kg": mesh.volume_m3 * config["material"]["density_kg_m3"],
            "element_type": "C3D10",
            "target_size_m": config["mesh"]["size_m"],
        },
        "solver": {"name": "CalculiX", "version": modal["solver_version"]},
        "profile": config["profile"],
        "response": response,
        "pcb": pcb,
        "warnings": warnings,
        "tap": None,
    }
    tap_arrays = None
    if with_synthetic_tap:
        first = float(modal["frequencies_hz"][0])
        # Deliberately offset by 3% to demonstrate comparison without suggesting measurement.
        synthetic_tap(
            out / "synthetic_tap.csv", first * 1.03, sample_rate_hz=max(10000, int(10 * first))
        )
        summary["tap"], tap_arrays = analyze_tap(
            out / "synthetic_tap.csv", first, max_hz=max(2000, first * 1.5), provenance="synthetic"
        )
        write_json(out / "tap_results.json", summary["tap"])
    csv_rows(out / "modes.csv", response["modes"])
    np.savetxt(
        out / "response_psd.csv",
        np.column_stack(list(spectra.values())),
        delimiter=",",
        header=",".join(spectra),
        comments="",
    )
    write_json(out / "results.json", summary)
    print("[4/5] Rendering plots and self-contained interactive report…", flush=True)
    from .report import create_report

    create_report(out, summary, mesh, modal, spectra, tap_arrays)
    files = [
        "config.resolved.json",
        "enclosure.step",
        "enclosure.msh",
        "modal.inp",
        "modal.dat",
        "modal.frd",
        "mesh.npz",
        "modes.npz",
        "modes.csv",
        "response_psd.csv",
        "results.json",
    ]
    manifest = {
        "vibequal_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "created_utc": summary["created_utc"],
        "dependencies": {
            p: importlib.metadata.version(p) for p in ["numpy", "scipy", "matplotlib", "gmsh"]
        },
        "solver_version": modal["solver_version"],
        "solver_binary_sha256": hash_file(executable),
        "files_sha256": {f: hash_file(out / f) for f in files},
    }
    if config["geometry"]["type"] == "step":
        manifest["imported_step_sha256"] = hash_file(config["geometry"]["path"])
    write_json(out / "manifest.json", manifest)
    print(f"[5/5] Complete: {out / 'report.html'}", flush=True)
    return summary


def convergence(config_path, output, sizes, ccx=None):
    if len(sizes) < 2 or any(not np.isfinite(s) or s <= 0 for s in sizes):
        raise ValueError("Convergence needs at least two positive finite mesh sizes")
    out = prepare_output(output)
    config = load_config(config_path)
    previous = None
    rows = []
    for i, size in enumerate(sorted(set(sizes), reverse=True)):
        c = copy.deepcopy(config)
        c["mesh"]["size_m"] = float(size)
        directory = out / f"mesh_{i + 1}"
        directory.mkdir()
        print(f"Solving mesh {size * 1000:.2f} mm…", flush=True)
        mesh = build_mesh(c, directory)
        modal = solve(mesh, c, directory, ccx)
        response, _ = modal_response(mesh, modal, c)
        frequencies = modal["frequencies_hz"]
        change = (
            None
            if previous is None
            else 100 * float(np.max(abs(frequencies[:3] - previous[:3]) / frequencies[:3]))
        )
        rows.append(
            {
                "size_m": size,
                "nodes": len(mesh.node_ids),
                "elements": len(mesh.tetra10),
                "first_frequency_hz": float(frequencies[0]),
                "max_first_three_sorted_frequency_change_percent": change,
                "probe_acceleration_grms": response["absolute_acceleration_grms"],
            }
        )
        previous = frequencies
    if len(rows) < 2:
        raise ValueError("Convergence mesh sizes must contain at least two distinct values")
    write_json(
        out / "convergence.json",
        {
            "rows": rows,
            "interpretation": "Sorted frequency "
            "comparison only; inspect mode shapes for swaps. Frequency convergence does "
            "not establish convergence of stresses or response amplitudes.",
        },
    )
    csv_rows(out / "convergence.csv", rows)
    from .report import convergence_plot

    convergence_plot(rows, out / "convergence.png")
    return rows


def validate_beam(output, ccx=None):
    """Independent Euler–Bernoulli cantilever benchmark with 3D solid FEA."""
    out = prepare_output(output)
    config = {
        "geometry": {"type": "beam", "length_m": 0.2, "width_m": 0.02, "height_m": 0.004},
        "material": {"youngs_modulus_pa": 70e9, "poisson_ratio": 0.3, "density_kg_m3": 2700},
        "mesh": {"size_m": 0.005, "order": 2},
        "supports": {"type": "boxes", "bounds_m": [[-1e-8, -1e-8, -1e-8, 1e-8, 0.021, 0.005]]},
        "analysis": {"modes": 4, "solver_timeout_s": 180},
    }
    mesh = build_mesh(config, out)
    modal = solve(mesh, config, out, ccx)
    g, mat = config["geometry"], config["material"]
    theoretical = (
        1.8751040687**2
        / (2 * np.pi * g["length_m"] ** 2)
        * np.sqrt(mat["youngs_modulus_pa"] * g["height_m"] ** 2 / (12 * mat["density_kg_m3"]))
    )
    actual = float(modal["frequencies_hz"][0])
    error = 100 * abs(actual - theoretical) / theoretical
    result = {
        "benchmark": "Cantilever first weak-axis bending frequency",
        "analytical_hz": float(theoretical),
        "calculix_hz": actual,
        "absolute_error_percent": float(error),
        "tolerance_percent": 5.0,
        "passed": bool(error < 5),
        "interpretation": "Euler–Bernoulli theory neglects shear "
        "deformation and 3D clamp effects; this is solver/mesh verification, not validation "
        "of the enclosure against hardware.",
    }
    write_json(out / "validation.json", result)
    return result
