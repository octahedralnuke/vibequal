"""CalculiX deck generation, bounded subprocess execution, and modal parsing."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np


def find_ccx(explicit=None):
    candidate = explicit or os.environ.get("CCX_BIN", "ccx")
    found = shutil.which(candidate)
    if found:
        return str(Path(found).resolve())
    raise RuntimeError(
        "CalculiX executable not found. Install calculix-ccx or set CCX_BIN. "
        "See docs/INSTALL.md; no synthetic solver is substituted."
    )


def _material(f, name, youngs, poisson, density):
    f.write(
        f"*MATERIAL, NAME={name}\n*ELASTIC\n{youngs:.12g}, {poisson:.12g}\n"
        f"*DENSITY\n{density:.12g}\n"
    )


def write_deck(mesh, config, path):
    from .config import board_density
    from .geometry import BOARD

    mat = config["material"]
    materials = (
        mesh.element_material
        if len(mesh.element_material)
        else np.zeros(len(mesh.element_ids), dtype=int)
    )
    sets = [("BODY", materials != BOARD), ("BOARD", materials == BOARD)]
    with Path(path).open("w", encoding="ascii") as f:
        f.write("*HEADING\nVibeQual SI units: m, kg, s, N, Pa\n*NODE, NSET=ALLNODES\n")
        for node, xyz in zip(mesh.node_ids, mesh.xyz, strict=True):
            f.write(f"{node}, {xyz[0]:.12g}, {xyz[1]:.12g}, {xyz[2]:.12g}\n")
        for name, selected in sets:
            if not selected.any():
                continue
            f.write(f"*ELEMENT, TYPE=C3D10, ELSET={name}\n")
            for tag, row in zip(mesh.element_ids[selected], mesh.tetra10[selected], strict=True):
                f.write(f"{tag}, " + ", ".join(map(str, row)) + "\n")
        f.write("*NSET, NSET=FIXED\n")
        for i in range(0, len(mesh.fixed_ids), 16):
            f.write(", ".join(map(str, mesh.fixed_ids[i : i + 16])) + "\n")
        _material(f, "MAT", mat["youngs_modulus_pa"], mat["poisson_ratio"], mat["density_kg_m3"])
        f.write("*SOLID SECTION, ELSET=BODY, MATERIAL=MAT\n")
        if sets[1][1].any():
            board = config["geometry"]["board"]
            m = board["material"]
            _material(f, "BOARD", m["youngs_modulus_pa"], m["poisson_ratio"], board_density(board))
            f.write("*SOLID SECTION, ELSET=BOARD, MATERIAL=BOARD\n")
        f.write("*BOUNDARY\nFIXED, 1, 3\n*STEP\n*FREQUENCY\n")
        f.write(
            f"{config['analysis']['modes']}\n*NODE PRINT, NSET=ALLNODES\nU\n"
            "*NODE FILE\nU\n*END STEP\n"
        )


def _number(token):
    return float(token.replace("D", "E").replace("d", "e"))


def parse_dat(path, node_ids, requested_modes):
    """Read real .dat tables. Missing/incomplete results are errors, never demo values."""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    frequencies, participation, effective_mass = [], [], []
    total_effective_mass = None
    displacement_blocks = []
    section = None
    current = None
    for line in lines:
        upper = line.upper()
        compact = re.sub(r"\s+", "", upper)
        if "EIGENVALUEOUTPUT" in compact:
            section = "frequency"
            continue
        if "PARTICIPATIONFACTORS" in compact:
            section = "participation"
            continue
        if "EFFECTIVEMODALMASS" in compact:
            section = "mass"
            continue
        if "TOTALEFFECTIVEMASS" in compact:
            section = "total_mass"
            continue
        if "TOTALMODAL" in compact or "FRACTIONOFTOTALS" in compact:
            section = None
        if "DISPLACEMENTS" in upper and "SET" in upper:
            section = "displacements"
            current = {}
            displacement_blocks.append(current)
            continue
        fields = line.split()
        if section == "total_mass" and len(fields) == 6:
            try:
                total_effective_mass = np.array([_number(x) for x in fields])
                section = None
            except ValueError:
                pass
            continue
        if not fields or not fields[0].isdigit():
            continue
        try:
            numbers = [_number(x) for x in fields]
        except ValueError:
            continue
        if section == "frequency" and len(numbers) >= 4:
            frequencies.append(numbers[3])
        elif section == "participation" and len(numbers) >= 7:
            participation.append(numbers[1:7])
        elif section == "mass" and len(numbers) >= 7:
            effective_mass.append(numbers[1:7])
        elif section == "displacements" and len(numbers) == 4:
            current[int(numbers[0])] = numbers[1:]
    n = requested_modes
    if len(frequencies) != n or len(participation) != n or len(effective_mass) != n:
        raise RuntimeError(
            f"Incomplete CalculiX modal tables: frequencies={len(frequencies)}, "
            f"participation={len(participation)}, masses={len(effective_mass)}; "
            f"expected {n}. Inspect {path}."
        )
    if len(displacement_blocks) != n:
        raise RuntimeError(f"Expected {n} mode-shape blocks, found {len(displacement_blocks)}")
    shapes = np.zeros((n, len(node_ids), 3))
    for i, block in enumerate(displacement_blocks):
        missing = set(map(int, node_ids)) - set(block)
        if missing:
            raise RuntimeError(f"Mode {i + 1} is missing {len(missing)} nodal displacements")
        shapes[i] = [block[int(tag)] for tag in node_ids]
    frequencies = np.array(frequencies)
    if not np.all(np.isfinite(frequencies)) or np.any(frequencies <= 1e-3):
        raise RuntimeError("Nonpositive/rigid-body frequency detected; inspect supports and mesh")
    if total_effective_mass is None or not np.all(np.isfinite(total_effective_mass)):
        raise RuntimeError("CalculiX total effective mass table is missing or invalid")
    if np.any(total_effective_mass[:3] <= 0) or not np.all(np.isfinite(shapes)):
        raise RuntimeError("Invalid translational mass or mode-shape output")
    return {
        "frequencies_hz": frequencies,
        "participation": np.array(participation),
        "effective_mass_kg": np.array(effective_mass),
        "total_effective_mass": total_effective_mass,
        "shapes": shapes,
    }


def solve(mesh, config, directory, ccx=None):
    out = Path(directory).resolve()
    executable = find_ccx(ccx)
    write_deck(mesh, config, out / "modal.inp")
    env = os.environ.copy()
    env.update({"OMP_NUM_THREADS": "1", "CCX_NPROC_RESULTS": "1"})
    try:
        with (out / "ccx.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(
                [executable, "-i", "modal"],
                cwd=out,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=config["analysis"].get("solver_timeout_s", 300),
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "CalculiX timed out; inspect ccx.log or increase solver_timeout_s"
        ) from exc
    output = (out / "ccx.log").read_text(encoding="utf-8", errors="replace")
    if process.returncode or "*ERROR" in output or not (out / "modal.dat").exists():
        raise RuntimeError(
            f"CalculiX failed (exit {process.returncode}); inspect {out / 'ccx.log'}"
        )
    result = parse_dat(out / "modal.dat", mesh.node_ids, config["analysis"]["modes"])
    np.savez_compressed(out / "modes.npz", **result)
    version = re.search(r"Version\s+([\w.]+)", output, re.IGNORECASE)
    result["solver_version"] = version.group(1) if version else "see ccx.log"
    return result
