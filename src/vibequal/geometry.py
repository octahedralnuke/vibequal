"""Gmsh OpenCASCADE geometry and C3D10 mesh export."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class Mesh:
    node_ids: np.ndarray
    xyz: np.ndarray
    element_ids: np.ndarray
    tetra10: np.ndarray
    triangles: np.ndarray
    fixed_ids: np.ndarray
    volume_m3: float

    def save(self, path):
        np.savez_compressed(path, **vars(self))


def c3d10_order(connectivity, coordinates):
    """Map mid-edge nodes geometrically, avoiding Gmsh/Abaqus ordering ambiguity."""
    edges = [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]
    result = list(connectivity[:4])
    for a, b in edges:
        midpoint = (coordinates[int(connectivity[a])] + coordinates[int(connectivity[b])]) / 2
        distances = [np.linalg.norm(coordinates[int(n)] - midpoint) for n in connectivity[4:]]
        result.append(connectivity[4 + int(np.argmin(distances))])
    if len(set(result)) != 10:
        raise ValueError("Could not map quadratic tetrahedron edge nodes")
    return result


def select_supports(xyz, specification):
    mask = np.zeros(len(xyz), dtype=bool)
    if specification["type"] == "mount_patches":
        plane = np.abs(xyz[:, 2] - specification["plane_z_m"]) <= 1e-7
        for x, y in specification["centres_xy_m"]:
            patch = plane & (
                (xyz[:, 0] - x) ** 2 + (xyz[:, 1] - y) ** 2 <= specification["radius_m"] ** 2
            )
            if np.count_nonzero(patch) < 3:
                raise ValueError(f"Support patch ({x}, {y}) selects fewer than three nodes")
            mask |= patch
    else:
        for bounds in specification["bounds_m"]:
            inside = np.all(
                (xyz >= np.array(bounds[:3]) - 1e-9) & (xyz <= np.array(bounds[3:]) + 1e-9), axis=1
            )
            if np.count_nonzero(inside) < 3:
                raise ValueError("Support box selects fewer than three nodes")
            mask |= inside
    if np.count_nonzero(mask) >= len(xyz) - 4:
        raise ValueError("Support definition constrains essentially the entire model")
    if np.linalg.matrix_rank(xyz[mask] - xyz[mask].mean(axis=0), tol=1e-10) < 2:
        raise ValueError("Clamped support nodes are collinear; rigid rotation remains possible")
    return mask


def build_mesh(config, directory):
    try:
        import gmsh
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Gmsh could not load. On Ubuntu/WSL install libglu1-mesa. See docs/INSTALL.md."
        ) from exc
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        # STEP files have declared units. Convert imported coordinates to metres explicitly.
        gmsh.option.setString("Geometry.OCCTargetUnit", "M")
        gmsh.model.add("vibequal")
        occ = gmsh.model.occ
        g = config["geometry"]
        if g["type"] == "step":
            path = Path(g["path"])
            if not path.is_file():
                raise ValueError(f"STEP file does not exist: {path}")
            occ.importShapes(str(path))
        else:
            length, width, height = (g[k] for k in ["length_m", "width_m", "height_m"])
            outer = occ.addBox(0, 0, 0, length, width, height)
            if g["type"] == "tray":
                t = g["thickness_m"]
                cavity = occ.addBox(t, t, t, length - 2 * t, width - 2 * t, height)
                body, _ = occ.cut([(3, outer)], [(3, cavity)])
                inset = g["mount_inset_m"]
                holes = [
                    occ.addCylinder(x, y, -t, 0, 0, 3 * t, g["hole_radius_m"])
                    for x in (inset, length - inset)
                    for y in (inset, width - inset)
                ]
                occ.cut(body, [(3, tag) for tag in holes])
        occ.synchronize()
        volumes = gmsh.model.getEntities(3)
        if len(volumes) != 1:
            raise ValueError(
                f"Expected one connected solid, found {len(volumes)}. "
                "Fuse or simplify the assembly before importing."
            )
        volume = sum(occ.getMass(dim, tag) for dim, tag in volumes)
        bounds = gmsh.model.getBoundingBox(-1, -1)
        size = config["mesh"]["size_m"]
        if max(bounds[i + 3] - bounds[i] for i in range(3)) / size > 1000:
            raise ValueError(
                "CAD extent / mesh size exceeds 1000. Check STEP length units "
                "and choose a practical mesh size before meshing."
            )
        step_path = out / "enclosure.step"
        # With OCCTargetUnit=M the writer converts our metre coordinates to correctly
        # labeled millimetres in STEP. Importing the asset converts them back to metres.
        gmsh.write(str(step_path))
        gmsh.option.setNumber("Mesh.MeshSizeMax", size)
        gmsh.option.setNumber("Mesh.MeshSizeMin", size * 0.4)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 12)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        gmsh.option.setNumber("Mesh.SecondOrderLinear", 1)
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.optimize("Netgen")
        gmsh.model.mesh.setOrder(2)
        gmsh.write(str(out / "enclosure.msh"))
        tags, flat_xyz, _ = gmsh.model.mesh.getNodes()
        sort = np.argsort(tags)
        tags, xyz = np.asarray(tags, dtype=int)[sort], np.asarray(flat_xyz).reshape(-1, 3)[sort]
        types, element_tags, element_nodes = gmsh.model.mesh.getElements(3)
        if list(types) != [11]:
            raise ValueError(f"Expected Gmsh tetra10 (type 11), found {types}")
        raw = np.asarray(element_nodes[0], dtype=int).reshape(-1, 10)
        lookup = dict(zip(tags, xyz, strict=True))
        tetra = np.array([c3d10_order(row, lookup) for row in raw], dtype=int)
        surface_types, _, surface_nodes = gmsh.model.mesh.getElements(2)
        triangles = []
        for typ, nodes in zip(surface_types, surface_nodes, strict=True):
            if typ == 9:
                triangles.extend(np.asarray(nodes, dtype=int).reshape(-1, 6)[:, :3])
            elif typ == 2:
                triangles.extend(np.asarray(nodes, dtype=int).reshape(-1, 3))
        support_mask = select_supports(xyz, config["supports"])
        mesh = Mesh(
            tags,
            xyz,
            np.asarray(element_tags[0], dtype=int),
            tetra,
            np.asarray(triangles, dtype=int),
            tags[support_mask],
            float(volume),
        )
        mesh.save(out / "mesh.npz")
        (out / "gmsh.log").write_text(
            f"Gmsh {gmsh.__version__}\nNodes: {len(tags)}\nC3D10: {len(tetra)}\n"
            f"Clamped nodes: {len(mesh.fixed_ids)}\nCAD volume: {volume:.12g} m^3\n",
            encoding="utf-8",
        )
        return mesh
    finally:
        gmsh.finalize()
