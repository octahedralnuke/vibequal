"""Offline HTML report, scientific plots and machine-readable evidence links."""

import base64
import html
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from . import __version__


def style():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#304155",
            "text.color": "#172b3d",
            "axes.edgecolor": "#b1bcc4",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.17,
        }
    )


def save(fig, path):
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def convergence_plot(rows, path):
    style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    nodes = [r["nodes"] for r in rows]
    axes[0].plot(nodes, [r["first_frequency_hz"] for r in rows], "o-", color="#127c80", lw=2)
    axes[0].set(
        xlabel="Mesh nodes",
        ylabel="First natural frequency (Hz)",
        title="First enclosure mode",
    )
    axes[1].plot(nodes, [r["probe_acceleration_grms"] for r in rows], "o-", color="#b5562b", lw=2)
    axes[1].set(xlabel="Mesh nodes", ylabel="Probe acceleration (g RMS)", title="Probe response")
    save(fig, path)


def create_tap_plot(arrays, result, path):
    style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), constrained_layout=True)
    t = arrays["time_s"]
    # Display first 0.7 s to make the ringdown visible without claiming calibration.
    show = t <= t[0] + min(0.7, t[-1] - t[0])
    axes[0].plot(t[show], arrays["voltage_v"][show], color="#127c80", linewidth=0.7)
    axes[0].set(xlabel="Time (s)", ylabel="Sensor voltage (V)", title="Captured signal")
    f = arrays["frequency_hz"]
    top = min(f[-1], max(2000, result["dominant_peak_hz"] * 1.5))
    keep = (f > 10) & (f < top)
    axes[1].semilogy(f[keep], arrays["spectrum_v2_hz"][keep], color="#536aa1", linewidth=0.9)
    axes[1].axvline(result["dominant_peak_hz"], color="#d78b2c", linestyle="--")
    axes[1].set(xlabel="Frequency (Hz)", ylabel="Voltage PSD (V²/Hz)", title="Output-only spectrum")
    fig.suptitle(f"Tap comparison · {result['provenance'].upper()}", fontsize=12, fontweight="bold")
    save(fig, path)


def board_mode_plot(mesh, modal, summary, path):
    """Top view of the board's dominant mode: out-of-plane shape relative to the standoffs."""
    from .config import board_layout
    from .geometry import BOARD

    board = summary["coupled_pcb"]
    layout = board_layout(summary["geometry"])
    mode = board["dominant_board_mode"] - 1
    nodes = np.unique(mesh.tetra10[mesh.element_material == BOARD])
    index = np.searchsorted(mesh.node_ids, nodes)
    top = np.isclose(mesh.xyz[index, 2], layout["z_top"], atol=1e-7)
    index = index[top]
    references = np.searchsorted(mesh.node_ids, board["standoff_reference_nodes"])
    shape = modal["shapes"][mode, index, 2] - modal["shapes"][mode, references, 2].mean()
    shape = shape / np.max(np.abs(shape))
    style()
    fig, ax = plt.subplots(figsize=(7, 4.4), constrained_layout=True)
    xy = mesh.xyz[index, :2] * 1000
    contour = ax.tricontourf(xy[:, 0], xy[:, 1], shape, levels=21, cmap="RdBu_r", vmin=-1, vmax=1)
    for x, y in layout["standoffs"]:
        ax.plot(x * 1000, y * 1000, "o", color="#172c3e", markersize=7)
    ax.set_aspect("equal")
    ax.set(
        xlabel="x (mm)",
        ylabel="y (mm)",
        title=f"Board mode {mode + 1} · {board['dominant_board_mode_frequency_hz']:.1f} Hz\n"
        "shape relative to the standoffs (dots)",
    )
    fig.colorbar(contour, ax=ax, label="Normalized out-of-plane displacement")
    save(fig, path)


def create_report(out, summary, mesh, modal, spectra, tap_arrays=None):
    out = Path(out)
    figures = out / "figures"
    figures.mkdir(exist_ok=True)
    style()
    r = summary["response"]
    fig, ax = plt.subplots(figsize=(10, 4.2), constrained_layout=True)
    ax.loglog(
        spectra["frequency_hz"],
        spectra["input_psd_g2_hz"],
        color="#6e7e8e",
        label="Base input",
        linewidth=2,
    )
    ax.loglog(
        spectra["frequency_hz"],
        spectra["response_psd_g2_hz"],
        color="#117f82",
        label="Probe absolute response",
        linewidth=1.5,
    )
    ax.set(xlabel="Frequency (Hz)", ylabel="Acceleration PSD (g²/Hz)")
    ax.legend(frameon=False)
    save(fig, figures / "response_psd.png")
    if summary.get("coupled_pcb"):
        board_mode_plot(mesh, modal, summary, figures / "board_mode.png")
    fig, ax = plt.subplots(figsize=(10, 3.2), constrained_layout=True)
    ax.bar(
        [row["mode"] for row in r["modes"]],
        [row["frequency_hz"] for row in r["modes"]],
        color=["#177f82" if row["inside_excitation_band"] else "#b1bdc5" for row in r["modes"]],
    )
    ax.axhspan(
        summary["profile"]["breakpoints_hz_g2_per_hz"][0][0],
        summary["profile"]["breakpoints_hz_g2_per_hz"][-1][0],
        color="#e2a842",
        alpha=0.10,
        label="Excitation band",
    )
    ax.set(xlabel="Mode number", ylabel="Natural frequency (Hz)")
    ax.set_xticks(range(1, len(r["modes"]) + 1, 1 if len(r["modes"]) <= 15 else 5))
    ax.legend(frameon=False)
    save(fig, figures / "frequencies.png")

    indices = {int(tag): i for i, tag in enumerate(mesh.node_ids)}
    tri_indices = np.array([[indices[int(n)] for n in row] for row in mesh.triangles])
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(projection="3d")
    surface = Poly3DCollection(
        mesh.xyz[tri_indices] * 1000,
        facecolors="#4c9ca5",
        edgecolors="#c9e2e3",
        linewidths=0.15,
        alpha=0.8,
    )
    ax.add_collection3d(surface)
    fixed = np.isin(mesh.node_ids, mesh.fixed_ids)
    ax.scatter(*(mesh.xyz[fixed] * 1000).T, s=4, color="#de962a", label="Clamped nodes")
    ax.auto_scale_xyz(*(mesh.xyz * 1000).T)
    ax.set_box_aspect(np.ptp(mesh.xyz, axis=0))
    ax.set(xlabel="x (mm)", ylabel="y (mm)", zlabel="z (mm)")
    ax.view_init(elev=27, azim=-57)
    save(fig, figures / "mesh.png")
    if tap_arrays is not None:
        create_tap_plot(tap_arrays, summary["tap"], figures / "tap.png")

    def embed(name):
        return "data:image/png;base64," + base64.b64encode((figures / name).read_bytes()).decode()

    mode_rows = "".join(
        f"<tr><td>{row['mode']:02d}</td><td>{row['frequency_hz']:.2f}</td>"
        f"<td>{100 * row['effective_mass_fraction_of_cad']:.2f}%</td>"
        f"<td>{row['miles_unit_sdof_grms']:.3f}</td>"
        f"<td>{row['miles_probe_modal_grms']:.3f}</td>"
        f"<td>{'in band' if row['inside_excitation_band'] else 'outside band'}</td></tr>"
        for row in r["modes"]
    )
    # Compact, indexed surface mesh for an offline Canvas viewer. Output shape amplitudes are
    # normalized solely for visualization, and never used as physical deflections.
    used = np.unique(tri_indices)
    remap = {int(old): new for new, old in enumerate(used)}
    viewer_faces = [[remap[int(i)] for i in row] for row in tri_indices]
    shape_data = []
    for shape in modal["shapes"]:
        normalization = float(np.max(np.linalg.norm(shape[used], axis=1)))
        shape_data.append(np.round(shape[used] / max(normalization, 1e-30), 6).tolist())
    viewer = {
        "xyz": np.round(mesh.xyz[used] * 1000, 5).tolist(),
        "faces": viewer_faces,
        "shapes": shape_data,
        "frequencies": modal["frequencies_hz"].tolist(),
        "fixed": [remap[int(i)] for i in np.flatnonzero(fixed) if int(i) in remap],
        "probe": remap.get(indices[r["probe_node"]]),
    }
    replacements = {
        "__VERSION__": __version__,
        "__NAME__": html.escape(summary["name"]),
        "__DATE__": html.escape(summary["created_utc"]),
        "__F1__": f"{r['modes'][0]['frequency_hz']:.1f}",
        "__INPUT__": f"{r['input_grms']:.2f}",
        "__RESPONSE__": f"{r['absolute_acceleration_grms']:.2f}",
        "__MASS__": f"{summary['mesh']['mass_kg']:.3f}",
        "__NODES__": f"{summary['mesh']['nodes']:,}",
        "__ELEMENTS__": f"{summary['mesh']['elements']:,}",
        "__FIXED__": str(summary["mesh"]["fixed_nodes"]),
        "__AXIS__": r["axis"].upper(),
        "__Q__": f"{r['q']:.1f}",
        "__DAMPING__": f"{100 * r['damping_ratio']:.2f}",
        "__DISPLACEMENT__": f"{r['relative_displacement_3sigma_m'] * 1000:.4f}",
        "__COVERAGE__": f"{100 * r['effective_mass_fraction_of_cad']:.1f}",
        "__COVERAGE_FREE__": f"{100 * r.get('effective_mass_fraction_of_solver_total', r['effective_mass_fraction_of_cad']):.2f}",
        "__PROBE__": f"Node {r['probe_node']} · "
        + ", ".join(f"{v * 1000:.2f}" for v in r["probe_xyz_m"])
        + " mm",
        "__PROFILE__": html.escape(summary["profile"]["name"]),
        "__SOURCE__": html.escape(summary["profile"].get("source", "user supplied")),
        "__SOLVER__": html.escape(summary["solver"]["version"]),
        "__WARNINGS__": "".join(f"<li>{html.escape(w)}</li>" for w in summary["warnings"]),
        "__MODE_ROWS__": mode_rows,
        "__MODES_PLOT__": embed("frequencies.png"),
        "__PSD_PLOT__": embed("response_psd.png"),
        "__MESH_PLOT__": embed("mesh.png"),
        "__VIEWER_DATA__": json.dumps(viewer, separators=(",", ":")).replace("<", "\\u003c"),
    }
    pcb = summary["pcb"]
    if pcb:
        result = (
            "Below empirical limit"
            if pcb["margin"] is not None and pcb["margin"] >= 0
            else "Exceeds empirical limit"
        )
        replacements["__PCB__"] = (
            f"<div class='pill amber'>{result} · screening only</div>"
            f"<div class='metric-row'><div><strong>{pcb['natural_frequency_hz']:.1f}<small>Hz</small></strong>Plate first mode</div>"
            f"<div><strong>{pcb['relative_deflection_3sigma_m'] * 1000:.4f}<small>mm</small></strong>Predicted 3σ centre deflection</div>"
            f"<div><strong>{pcb['allowable_3sigma_m'] * 1000:.4f}<small>mm</small></strong>Steinberg 3σ limit</div>"
            f"<div><strong>{pcb['margin']:+.2f}</strong>Deflection margin</div></div>"
            f"<p>{html.escape(pcb['excitation_assumption'])}</p><p class='muted'>{html.escape(pcb['limitations'])}</p>"
        )
    else:
        replacements["__PCB__"] = "<p>PCB screening disabled in this configuration.</p>"
    board = summary.get("coupled_pcb")
    if board:
        if board["margin"] is None:
            verdict, limit = "No Steinberg inputs", "<div><strong>—</strong>Steinberg 3σ limit</div>"
        else:
            verdict = (
                "Below empirical limit" if board["margin"] >= 0 else "Exceeds empirical limit"
            )
            limit = (
                f"<div><strong>{board['allowable_3sigma_m'] * 1000:.4f}<small>mm</small></strong>"
                f"Steinberg 3σ limit</div><div><strong>{board['margin']:+.2f}</strong>"
                "Deflection margin</div>"
            )
        replacements["__PCB__"] += (
            "<h3>Coupled board on standoffs</h3>"
            f"<div class='pill amber'>{verdict} · screening only</div>"
            f"<div class='metric-row'><div><strong>{board['dominant_board_mode_frequency_hz']:.1f}"
            f"<small>Hz</small></strong>Dominant board mode ({board['dominant_board_mode']})</div>"
            f"<div><strong>{board['relative_deflection_3sigma_m'] * 1000:.4f}<small>mm</small>"
            f"</strong>3σ deflection vs standoffs</div>{limit}</div>"
            f"<p>{html.escape(board['excitation_assumption'])}</p>"
            f"<img class='plot' src='{embed('board_mode.png')}' alt='Dominant board mode shape'>"
            f"<p class='muted'>{html.escape(board['limitations'])}</p>"
        )
    tap = summary["tap"]
    if tap:
        replacements["__TAP__"] = (
            f"<div class='pill amber'>{html.escape(tap['provenance']).upper()} DATA · physical test pending</div>"
            f"<div class='metric-row'><div><strong>{tap['dominant_peak_hz']:.2f}<small>Hz</small></strong>Dominant spectral peak</div>"
            f"<div><strong>{tap['difference_percent']:+.2f}<small>%</small></strong>Difference from FEA first mode</div></div>"
            f"<p>This generated ringdown intentionally differs by 3% from the prediction. It verifies "
            f"the analysis workflow; it provides no experimental validation.</p>"
            f"<img class='plot' src='{embed('tap.png')}' alt='Synthetic voltage ringdown and spectrum'>"
        )
    else:
        replacements["__TAP__"] = (
            "<p>No tap data was provided. Use <code>vibequal tap</code> to analyze a CSV capture.</p>"
        )
    template = Path(__file__).parent / "templates" / "report.html"
    rendered = template.read_text(encoding="utf-8")
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    (out / "report.html").write_text(rendered, encoding="utf-8")
    (out / "report.md").write_text(
        f"# VibeQual analysis run\n\n{summary['name']}\n\n"
        f"Simulation: CalculiX {summary['solver']['version']}; C3D10; SI units.\n\n"
        f"- Nodes: {summary['mesh']['nodes']:,}; elements: {summary['mesh']['elements']:,}.\n"
        f"- CAD mass: {summary['mesh']['mass_kg']:.6f} kg.\n"
        f"- First natural frequency: {r['modes'][0]['frequency_hz']:.3f} Hz.\n"
        f"- Base input: {r['input_grms']:.4f} g RMS; axis {r['axis']}; damping {100 * r['damping_ratio']:.2f}%.\n"
        f"- Truncated modal probe acceleration: {r['absolute_acceleration_grms']:.4f} g RMS.\n"
        f"- Probe relative displacement (3σ): {r['relative_displacement_3sigma_m'] * 1000:.5f} mm.\n\n"
        "## Interpretation\n\nThese are simulation outputs, not qualification findings. "
        "See report.html for mode animation, response plots, PCB assumptions and synthetic tap provenance.\n\n"
        "## Limitations\n\n" + "\n".join(f"- {w}" for w in summary["warnings"]) + "\n",
        encoding="utf-8",
    )
