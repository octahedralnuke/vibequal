"""Strict configuration checks; all mechanical dimensions use SI units."""

import copy
import json
import math
from pathlib import Path


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and greater than zero")
    return float(value)


def board_layout(g):
    """Board origin, top z and standoff centres for a board centred in the tray."""
    b, t = g["board"], g["thickness_m"]
    x0, y0 = (g["length_m"] - b["length_m"]) / 2, (g["width_m"] - b["width_m"]) / 2
    z0 = t + b["standoff_height_m"]
    i = b["standoff_inset_m"]
    centres = [
        (x, y)
        for x in (x0 + i, x0 + b["length_m"] - i)
        for y in (y0 + i, y0 + b["width_m"] - i)
    ]
    return {"x0": x0, "y0": y0, "z0": z0, "z_top": z0 + b["thickness_m"], "standoffs": centres}


def board_density(b):
    """FR4 density with the component mass smeared uniformly over the board volume."""
    volume = b["length_m"] * b["width_m"] * b["thickness_m"]
    return b["material"]["density_kg_m3"] + b.get("smeared_component_mass_kg", 0) / volume


def validate_board(g):
    b, t = g["board"], g["thickness_m"]
    for k in [
        "length_m",
        "width_m",
        "thickness_m",
        "standoff_height_m",
        "standoff_radius_m",
        "standoff_inset_m",
    ]:
        positive(b[k], f"geometry.board.{k}")
    if g.get("rib"):
        raise ValueError("geometry.board cannot be combined with geometry.rib")
    m = b["material"]
    for k in ["youngs_modulus_pa", "density_kg_m3"]:
        positive(m[k], f"geometry.board.material.{k}")
    if not -1 < m["poisson_ratio"] < 0.5:
        raise ValueError("geometry.board.material.poisson_ratio must lie between -1 and 0.5")
    mass = b.get("smeared_component_mass_kg", 0)
    if isinstance(mass, bool) or not math.isfinite(mass) or mass < 0:
        raise ValueError("geometry.board.smeared_component_mass_kg must be finite and nonnegative")
    if "mesh_size_m" in b:
        positive(b["mesh_size_m"], "geometry.board.mesh_size_m")
    layout = board_layout(g)
    if b["length_m"] >= g["length_m"] - 2 * t or b["width_m"] >= g["width_m"] - 2 * t:
        raise ValueError("The board must fit inside the tray walls")
    if layout["z_top"] >= g["height_m"]:
        raise ValueError("Board and standoffs must fit below the top of the walls")
    if b["standoff_inset_m"] <= b["standoff_radius_m"]:
        raise ValueError("Standoffs must lie wholly under the board")
    inset, length, width = g["mount_inset_m"], g["length_m"], g["width_m"]
    holes = [(x, y) for x in (inset, length - inset) for y in (inset, width - inset)]
    for sx, sy in layout["standoffs"]:
        for hx, hy in holes:
            if math.hypot(sx - hx, sy - hy) <= b["standoff_radius_m"] + g["hole_radius_m"]:
                raise ValueError("A board standoff intersects a mounting hole")
    s = b.get("steinberg")
    if s:
        for k in ["component_length_m", "package_constant", "board_edge_parallel_to_component_m"]:
            positive(s[k], f"geometry.board.steinberg.{k}")
        if not 0 < s["position_factor"] <= 1:
            raise ValueError("geometry.board.steinberg.position_factor must lie in (0,1]")


def validate_config(config):
    c = copy.deepcopy(config)
    for key in ["geometry", "material", "mesh", "supports", "analysis", "profile"]:
        if key not in c or not isinstance(c[key], dict):
            raise ValueError(f"Missing configuration object: {key}")
    g, mat, mesh, a = c["geometry"], c["material"], c["mesh"], c["analysis"]
    if g.get("type") not in ("tray", "step", "beam"):
        raise ValueError("geometry.type must be tray, step, or beam")
    if g["type"] != "step":
        for k in ["length_m", "width_m", "height_m"]:
            positive(g[k], f"geometry.{k}")
    elif not g.get("path"):
        raise ValueError("geometry.path is required for STEP import")
    if g["type"] == "tray":
        t = positive(g["thickness_m"], "geometry.thickness_m")
        if 2 * t >= min(g["length_m"], g["width_m"]) or t >= g["height_m"]:
            raise ValueError("Tray thickness leaves no interior cavity")
        r = positive(g["hole_radius_m"], "geometry.hole_radius_m")
        inset = positive(g["mount_inset_m"], "geometry.mount_inset_m")
        if inset - r <= t or 2 * (inset + r) >= min(g["length_m"], g["width_m"]):
            raise ValueError("Mounting holes must lie inside the base, clear of the walls")
        if g.get("rib"):
            rib = g["rib"]
            positive(rib["width_m"], "geometry.rib.width_m")
            positive(rib["height_m"], "geometry.rib.height_m")
            if rib["width_m"] >= g["width_m"] - 2 * t or rib["height_m"] >= g["height_m"] - t:
                raise ValueError("The longitudinal rib must fit inside the tray cavity")
            if abs(inset - g["width_m"] / 2) <= rib["width_m"] / 2 + r:
                raise ValueError("The longitudinal rib intersects a mounting hole")
        if g.get("lid"):
            positive(g["lid"]["thickness_m"], "geometry.lid.thickness_m")
        if g.get("board"):
            validate_board(g)
    elif g.get("lid") or g.get("board"):
        raise ValueError("geometry.lid and geometry.board require geometry.type tray")
    for k in ["youngs_modulus_pa", "density_kg_m3"]:
        positive(mat[k], f"material.{k}")
    if not -1 < mat["poisson_ratio"] < 0.5:
        raise ValueError("material.poisson_ratio must lie between -1 and 0.5")
    positive(mesh["size_m"], "mesh.size_m")
    if mesh.get("order", 2) != 2:
        raise ValueError("Only quadratic tetrahedra (order=2) are supported")
    modes = a["modes"]
    if isinstance(modes, bool) or not isinstance(modes, int) or not 1 <= modes <= 100:
        raise ValueError("analysis.modes must be an integer from 1 to 100")
    if not 0 < a["damping_ratio"] <= 0.2:
        raise ValueError("analysis.damping_ratio must lie in (0, 0.2]")
    if a["axis"] not in ("x", "y", "z"):
        raise ValueError("analysis.axis must be x, y, or z")
    probe = a["probe_xyz_m"]
    if len(probe) != 3 or not all(math.isfinite(x) for x in probe):
        raise ValueError("analysis.probe_xyz_m must contain three finite coordinates")
    positive(a.get("solver_timeout_s", 300), "analysis.solver_timeout_s")
    s = c["supports"]
    if s.get("type") == "mount_patches":
        positive(s["radius_m"], "supports.radius_m")
        if not math.isfinite(s["plane_z_m"]) or not s.get("centres_xy_m"):
            raise ValueError("Support patches need a plane and at least one centre")
        if any(len(p) != 2 or not all(math.isfinite(x) for x in p) for p in s["centres_xy_m"]):
            raise ValueError("Support centres must be finite x,y pairs")
    elif s.get("type") == "boxes":
        if not s.get("bounds_m"):
            raise ValueError("supports.bounds_m cannot be empty")
        for b in s["bounds_m"]:
            if len(b) != 6 or not all(math.isfinite(x) for x in b):
                raise ValueError("Each support box is [xmin,ymin,zmin,xmax,ymax,zmax]")
            if any(b[i] > b[i + 3] for i in range(3)):
                raise ValueError("Support box lower bounds exceed upper bounds")
    else:
        raise ValueError("supports.type must be mount_patches or boxes")
    from .vibration import PSDProfile

    PSDProfile.from_config(c["profile"])
    if c.get("pcb", {}).get("enabled"):
        p = c["pcb"]
        if p.get("model") != "independent_simply_supported_isotropic_plate":
            raise ValueError("Unsupported PCB model")
        for k in [
            "length_m",
            "width_m",
            "thickness_m",
            "youngs_modulus_pa",
            "density_kg_m3",
            "component_length_m",
            "package_constant",
            "position_factor",
            "board_edge_parallel_to_component_m",
            "damping_ratio",
        ]:
            positive(p[k], f"pcb.{k}")
        if not 0 < p["damping_ratio"] <= 0.2 or not -1 < p["poisson_ratio"] < 0.5:
            raise ValueError("Invalid PCB damping or Poisson ratio")
        mass = p.get("smeared_component_mass_kg", 0)
        if not math.isfinite(mass) or mass < 0:
            raise ValueError("PCB smeared component mass must be finite and nonnegative")
        if not 0 < p["position_factor"] <= 1:
            raise ValueError("PCB position_factor must lie in (0,1]")
    return c


def load_config(path):
    path = Path(path).resolve()
    with path.open(encoding="utf-8") as stream:
        config = validate_config(json.load(stream))
    if config["geometry"]["type"] == "step":
        p = Path(config["geometry"]["path"])
        config["geometry"]["path"] = str((path.parent / p).resolve())
    return config
