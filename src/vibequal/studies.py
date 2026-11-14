"""Controlled geometry comparisons and fixed-mesh modal truncation studies."""

import copy
import importlib.metadata
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import __version__
from .config import load_config, validate_config
from .geometry import build_mesh
from .pipeline import csv_rows, hash_file, prepare_output, write_json
from .solver import find_ccx, solve
from .vibration import modal_response


def checked_counts(counts):
    if not counts or any(
        isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 100 for n in counts
    ):
        raise ValueError("Mode counts must be integers from 1 to 100")
    counts = sorted(set(counts))
    if len(counts) < 2:
        raise ValueError("A truncation study requires at least two distinct mode counts")
    return counts


def modal_prefix(modal, count):
    """Subset one eigenbasis; mesh, constraints and probe remain identical."""
    if not 1 <= count <= len(modal["frequencies_hz"]):
        raise ValueError("Requested modal prefix is outside the solved basis")
    result = dict(modal)
    for key in ["frequencies_hz", "participation", "effective_mass_kg", "shapes"]:
        result[key] = modal[key][:count]
    return result


def mass_fractions(modal, cad_mass_kg):
    captured = np.sum(modal["effective_mass_kg"][:, :3], axis=0)
    return {
        f"{axis}_mass_fraction_of_solver_total": float(
            captured[i] / modal["total_effective_mass"][i]
        )
        for i, axis in enumerate("xyz")
    } | {
        f"{axis}_mass_fraction_of_cad": float(captured[i] / cad_mass_kg)
        for i, axis in enumerate("xyz")
    }


def solver_evidence(directory, executable):
    directory = Path(directory)
    text = (directory / "modal.dat").read_text(encoding="utf-8")
    # Preserve the original frequency, participation and mass tables without the large
    # nodal displacement blocks. The full .dat remains in the run directory.
    tables = re.split(r"\n\s*E I G E N V A L U E\s+N U M B E R", text, maxsplit=1)[0]
    (directory / "solver_tables.txt").write_text(tables, encoding="utf-8")
    hashes = {
        p.name: hash_file(p)
        for p in directory.iterdir()
        if p.is_file() and p.name != "manifest.json"
    }
    write_json(
        directory / "manifest.json",
        {
            "version": __version__,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "dependencies": {p: importlib.metadata.version(p) for p in ["numpy", "scipy", "gmsh"]},
            "solver_binary_sha256": hash_file(executable),
            "files_sha256": hashes,
            "archive_note": "The repository may retain selected evidence files only. Re-running "
            "the study produces all raw files. Hashes describe the original complete run.",
        },
    )


def mode_study(config_path, output, counts=(10, 20, 30, 40, 50), ccx=None):
    counts = checked_counts(list(counts))
    c = load_config(config_path)
    c["analysis"]["modes"] = max(counts)
    executable = find_ccx(ccx)
    out = prepare_output(output)
    raw = out / "raw"
    raw.mkdir()
    write_json(raw / "config.resolved.json", c)
    print(f"Solving {max(counts)} modes once on an unchanged mesh…", flush=True)
    mesh = build_mesh(c, raw)
    modal = solve(mesh, c, raw, executable)
    cad_mass = mesh.volume_m3 * c["material"]["density_kg_m3"]
    rows, previous = [], None
    for n in counts:
        subset = modal_prefix(modal, n)
        response, _ = modal_response(mesh, subset, c)
        acceleration = response["absolute_acceleration_grms"]
        row = {
            "modes": n,
            "highest_frequency_hz": float(subset["frequencies_hz"][-1]),
            **mass_fractions(subset, cad_mass),
            "probe_acceleration_grms": acceleration,
            "probe_relative_3sigma_m": response["relative_displacement_3sigma_m"],
            "acceleration_change_from_previous_percent": None
            if previous is None
            else 100 * (acceleration / previous - 1),
        }
        rows.append(row)
        previous = acceleration
    csv_rows(out / "mode_count.csv", rows)
    csv_rows(raw / "modes.csv", modal_response(mesh, modal, c)[0]["modes"])
    result = {
        "study": "modal_truncation",
        "rows": rows,
        "axis": c["analysis"]["axis"],
        "profile": c["profile"],
        "cad_mass_kg": cad_mass,
        "solver_total_effective_mass_xyz_kg": modal["total_effective_mass"][:3].tolist(),
        "nodes": len(mesh.node_ids),
        "elements": len(mesh.tetra10),
        "solver_version": modal["solver_version"],
        "probe_node": response["probe_node"],
        "probe_xyz_m": response["probe_xyz_m"],
        "interpretation": "Prefixes of the same solved eigenbasis. This isolates modal "
        "truncation from remeshing, support changes and probe snapping. Translational "
        "mass fractions use both the CalculiX total effective mass of free DOFs and full "
        "CAD mass. No residual/missing-mass correction is applied.",
    }
    write_json(out / "mode_count.json", result)
    solver_evidence(raw, executable)
    plot_mode_study(result, out / "mode_count.png")
    return result


def variant_config(base, specification, modes):
    c = copy.deepcopy(base)
    for section in ("geometry", "supports"):
        c[section].update(specification.get(section, {}))
    g, s = c["geometry"], c["supports"]
    # Move the idealized mounting patches together with the mounting-hole pattern.
    if g["type"] == "tray" and s["type"] == "mount_patches" and "supports" not in specification:
        inset = g["mount_inset_m"]
        s["centres_xy_m"] = [
            [x, y] for x in (inset, g["length_m"] - inset) for y in (inset, g["width_m"] - inset)
        ]
    c["analysis"]["modes"] = modes
    c["name"] = specification["label"]
    return validate_config(c)


def design_study(specification_path, output, ccx=None):
    path = Path(specification_path).resolve()
    spec = json.loads(path.read_text(encoding="utf-8"))
    base = load_config(path.parent / spec["base_config"])
    modes = spec.get("modes", 50)
    variants = spec["variants"]
    ids = [v["id"] for v in variants]
    if (
        len(variants) < 2
        or len(set(ids)) != len(ids)
        or any(not re.fullmatch(r"[a-z0-9_-]+", name) for name in ids)
    ):
        raise ValueError("Use at least two variants with unique lowercase filename-safe IDs")
    configurations = [variant_config(base, v, modes) for v in variants]
    executable = find_ccx(ccx)
    out = prepare_output(output)
    write_json(out / "study.resolved.json", spec)
    rows = []
    for v, c in zip(variants, configurations, strict=True):
        print(f"Solving design: {v['label']} ({modes} modes)…", flush=True)
        raw = out / v["id"]
        raw.mkdir()
        write_json(raw / "config.resolved.json", c)
        mesh = build_mesh(c, raw)
        modal = solve(mesh, c, raw, executable)
        response, _ = modal_response(mesh, modal, c)
        mass = mesh.volume_m3 * c["material"]["density_kg_m3"]
        row = {
            "variant": v["id"],
            "label": v["label"],
            "mass_kg": mass,
            "nodes": len(mesh.node_ids),
            "elements": len(mesh.tetra10),
            "modes": modes,
            "first_frequency_hz": float(modal["frequencies_hz"][0]),
            "frequency_change_from_baseline_percent": 0.0
            if not rows
            else 100 * (modal["frequencies_hz"][0] / rows[0]["first_frequency_hz"] - 1),
            "mass_change_from_baseline_percent": 0.0
            if not rows
            else 100 * (mass / rows[0]["mass_kg"] - 1),
            **mass_fractions(modal, mass),
            "probe_acceleration_grms": response["absolute_acceleration_grms"],
            "probe_snap_distance_m": response["probe_snap_distance_m"],
        }
        rows.append(row)
        csv_rows(raw / "modes.csv", response["modes"])
        write_json(raw / "response.json", response)
        solver_evidence(raw, executable)
    result = {
        "study": "geometry_comparison",
        "rows": rows,
        "profile": base["profile"],
        "controlled": {
            "mesh_target_m": base["mesh"]["size_m"],
            "modes": modes,
            "damping_ratio": base["analysis"]["damping_ratio"],
            "material": base["material"],
            "axis": base["analysis"]["axis"],
        },
        "interpretation": "First-frequency and mass tradeoff for one specified tray. "
        "Variant modes are sorted by frequency, not matched by mode-shape identity. "
        "All variants retain idealized clamps and omit a lid and payload. Probe responses "
        "are exploratory because meshes and nearest probe nodes differ; amplitudes are "
        "not used to rank designs. Frequency increase alone is not qualification.",
    }
    write_json(out / "design_comparison.json", result)
    csv_rows(out / "design_comparison.csv", rows)
    plot_design_study(result, out / "design_comparison.png")
    return result


def plot_mode_study(result, path):
    import matplotlib.pyplot as plt

    from .report import save, style

    style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    n = [r["modes"] for r in result["rows"]]
    for axis in "xyz":
        axes[0].plot(
            n,
            [100 * r[f"{axis}_mass_fraction_of_solver_total"] for r in result["rows"]],
            "o-",
            label=axis.upper(),
        )
    axes[0].axhline(90, color="#91a1aa", linestyle="--", linewidth=0.8)
    axes[0].set(xlabel="Retained modes", ylabel="Effective mass / solver total (%)", ylim=(0, 105))
    axes[0].legend(frameon=False)
    axes[1].plot(n, [r["probe_acceleration_grms"] for r in result["rows"]], "o-", color="#127c80")
    axes[1].set(xlabel="Retained modes", ylabel="Probe absolute acceleration (g RMS)")
    save(fig, path)


def plot_design_study(result, path):
    import matplotlib.pyplot as plt

    from .report import save, style

    style()
    fig, ax = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
    rows = result["rows"]
    labels = [r["label"] for r in rows]
    bars = ax.barh(labels, [r["first_frequency_hz"] for r in rows], color="#127c80")
    ax.invert_yaxis()
    ax.set(xlabel="First natural frequency (Hz)", title="Controlled tray design comparison")
    ax.set_xlim(0, max(r["first_frequency_hz"] for r in rows) * 1.35)
    for bar, row in zip(bars, rows, strict=True):
        ax.text(
            bar.get_width() + 15,
            bar.get_y() + bar.get_height() / 2,
            f"{row['frequency_change_from_baseline_percent']:+.1f}% · {row['mass_kg']:.3f} kg",
            va="center",
            fontsize=9,
        )
    save(fig, path)
