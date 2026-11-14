#!/usr/bin/env python3
"""Generate the printable evaluation report from recorded run and verification JSON."""

import argparse
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def build(run, verification, output):
    run, verification, output = Path(run), Path(verification), Path(output)
    summary = json.loads((run / "results.json").read_text())
    benchmark = json.loads((verification / "validation.json").read_text())
    refinement = json.loads((verification / "convergence.json").read_text())["rows"]
    r, pcb = summary["response"], summary["pcb"]
    output.parent.mkdir(parents=True, exist_ok=True)
    ink, teal, muted = (colors.HexColor(x) for x in ["#172c3e", "#087d82", "#647b8c"])
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "BodyVQ", fontName="Helvetica", fontSize=10, leading=15, textColor=ink, spaceAfter=10
        )
    )
    styles.add(
        ParagraphStyle(
            "TitleVQ",
            fontName="Helvetica-Bold",
            fontSize=33,
            leading=38,
            textColor=ink,
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            "HeadingVQ",
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=25,
            textColor=ink,
            spaceAfter=15,
        )
    )
    styles.add(
        ParagraphStyle(
            "SmallVQ", fontName="Helvetica", fontSize=8.5, leading=12, textColor=muted, spaceAfter=8
        )
    )
    styles.add(
        ParagraphStyle(
            "KickerVQ",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=14,
            textColor=teal,
            spaceAfter=14,
        )
    )
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=19 * mm,
        rightMargin=19 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title="VibeQual - Automated Vibration Screening",
        author="VibeQual project",
    )
    story = []

    def p(text, style="BodyVQ"):
        return Paragraph(text, styles[style])

    def heading(number, title):
        story.extend([p(f"VIBEQUAL / {number}", "KickerVQ"), p(title, "HeadingVQ")])

    def table(rows, widths=None):
        # Paragraph cells wrap naturally inside fixed column widths.
        rendered = [[p(str(cell), "SmallVQ") for cell in row] for row in rows]
        t = Table(rendered, colWidths=widths, hAlign="LEFT", repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f1ef")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), teal),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce4e7")),
                ]
            )
        )
        return t

    def image(path, width=176 * mm):
        from reportlab.lib.utils import ImageReader

        w, h = ImageReader(str(path)).getSize()
        return Image(str(path), width=width, height=width * h / w)

    story.extend(
        [
            p("ENGINEERING PROJECT / EVALUATION EDITION", "KickerVQ"),
            p("VibeQual", "TitleVQ"),
            p("Automated vibration screening<br/>for electronics enclosures", "HeadingVQ"),
            p("Python - Gmsh - CalculiX", "KickerVQ"),
            p(
                "A working CAD-to-modal pipeline with random-vibration response estimation, "
                "independent PCB deflection screening and a tap-signal comparison workflow."
            ),
            image(run / "figures" / "mesh.png", 150 * mm),
            table(
                [
                    ["First natural frequency", "Illustrative input", "CAD mass"],
                    [
                        f"{r['modes'][0]['frequency_hz']:.3f} Hz",
                        f"{r['input_grms']:.4f} g RMS",
                        f"{summary['mesh']['mass_kg']:.5f} kg",
                    ],
                ],
                [58 * mm] * 3,
            ),
            Spacer(1, 12),
            p(
                "<b>Evidence status:</b> Real finite-element simulation and analytical verification. "
                "The tap demonstration is synthetic; physical correlation remains pending. "
                "The input profile is user-defined and does not establish DO-160 or MIL-STD-810 compliance.",
                "SmallVQ",
            ),
            PageBreak(),
        ]
    )

    heading("01 / OBJECTIVE & METHODS", "A repeatable engineering workflow")
    story.append(
        p(
            "The objective is to reduce manual setup for a small enclosure screening study, "
            "while preserving the model, solver output, assumptions and reproducibility evidence. "
            "The demonstration geometry is a 160 x 100 x 40 mm open aluminium tray with "
            "3 mm walls/base and four mounting holes."
        )
    )
    for title, text in [
        (
            "CAD and boundary conditions",
            "Gmsh OpenCASCADE generates the tray or imports a single-solid "
            "STEP model. Bottom mounting patches are clamped in all three translations. A lid, "
            "payload, bolt preload and contact are omitted. Quadratic tetrahedra are exported as C3D10.",
        ),
        (
            "Modal FEA",
            "CalculiX solves K phi = omega^2 M phi. The parser retains natural frequencies, "
            "mass-normalized shapes, participation factors and translational effective modal masses. "
            "The default run extracts ten modes. Modal damping is assumed as 2.5% of critical.",
        ),
        (
            "Random vibration",
            "The one-sided input acceleration PSD uses g^2/Hz and power-law "
            "interpolation. Its area gives input g RMS. Miles estimates use sqrt[(pi/2) f_n Q S_g(f_n)], "
            "with Q = 1/(2 zeta). This is an approximate dominant-resonance calculation.",
        ),
        (
            "Numerical response",
            "The probe response integrates the squared magnitude of the complex "
            "modal transfer function, including the rigid base acceleration term and common-input "
            "cross terms. Adaptive quadrature resolves resonances and PSD breakpoints. The modal sum "
            "is truncated; omitted modes and damping uncertainty remain material limitations.",
        ),
        (
            "PCB and tap extensions",
            "A separate simply supported isotropic PCB plate estimates "
            "first-mode deflection under direct base excitation. An inch-based Steinberg limit "
            "provides an empirical margin. Tap CSV analysis reports spectral peaks and a frequency "
            "difference, with synthetic/physical provenance kept explicit.",
        ),
    ]:
        story.extend([p(f"<b>{title}</b>"), p(text)])
    story.append(
        p(
            "Full equations, units, derivations and scope: docs/THEORY.md. "
            "Configuration and support-selection details: docs/CONFIGURATION.md.",
            "SmallVQ",
        )
    )
    story.append(PageBreak())

    heading("02 / RECORDED RESULTS", "Simulation output, with its assumptions")
    story.append(
        table(
            [
                ["Mesh / solver", "Recorded value"],
                [
                    "Nodes / quadratic tetrahedra",
                    f"{summary['mesh']['nodes']:,} / {summary['mesh']['elements']:,}",
                ],
                ["Solver / nominal mesh", f"CalculiX {summary['solver']['version']} / 9 mm"],
                ["Probe absolute acceleration", f"{r['absolute_acceleration_grms']:.4f} g RMS"],
                [
                    "Probe relative displacement, 3 sigma",
                    f"{r['relative_displacement_3sigma_m'] * 1000:.5f} mm",
                ],
            ],
            [91 * mm, 83 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(image(run / "figures" / "response_psd.png"))
    story.append(
        p(
            "The first three natural frequencies are "
            + ", ".join(f"{m['frequency_hz']:.3f} Hz" for m in r["modes"][:3])
            + ". The third mode lies close to the 2000 Hz profile upper cutoff, making response "
            "sensitive to small frequency changes. The ten modes capture "
            f"{r['effective_mass_fraction_of_cad'] * 100:.1f}% of full CAD mass in the excitation direction. "
            "Mass coverage and response convergence must be checked before engineering reliance."
        )
    )
    story.append(
        table(
            [
                ["Independent PCB result", "Recorded value"],
                ["Plate first natural frequency", f"{pcb['natural_frequency_hz']:.2f} Hz"],
                [
                    "Predicted / allowable 3-sigma deflection",
                    f"{pcb['relative_deflection_3sigma_m'] * 1000:.4f} / {pcb['allowable_3sigma_m'] * 1000:.4f} mm",
                ],
                ["Empirical deflection margin", f"{pcb['margin']:+.3f}"],
            ],
            [91 * mm, 83 * mm],
        )
    )
    story.append(
        p(
            "A positive PCB margin is only a comparison with the stated empirical limit. "
            "It does not predict service life or establish electronics qualification.",
            "SmallVQ",
        )
    )
    story.append(PageBreak())

    heading("03 / VERIFICATION", "Check the solver, then test sensitivity")
    story.append(
        p(
            "<b>Analytical beam benchmark.</b> A 200 x 20 x 4 mm aluminium cantilever "
            "checks the complete geometry/mesh/deck/solver route against the Euler-Bernoulli "
            "first weak-axis bending solution."
        )
    )
    story.append(
        table(
            [
                ["Analytical", "CalculiX", "Absolute error", "Criterion"],
                [
                    f"{benchmark['analytical_hz']:.4f} Hz",
                    f"{benchmark['calculix_hz']:.4f} Hz",
                    f"{benchmark['absolute_error_percent']:.3f}%",
                    "Below 5%",
                ],
            ],
            [43.5 * mm] * 4,
        )
    )
    story.append(Spacer(1, 10))
    story.append(
        p(
            "<b>Enclosure mesh study.</b> The first frequency becomes more stable under "
            "refinement. Amplitude convergence is weaker and must not be inferred from frequency convergence."
        )
    )
    story.append(
        table(
            [["Mesh", "Nodes", "First frequency", "Probe response"]]
            + [
                [
                    f"{row['size_m'] * 1000:g} mm",
                    f"{row['nodes']:,}",
                    f"{row['first_frequency_hz']:.3f} Hz",
                    f"{row['probe_acceleration_grms']:.4f} g RMS",
                ]
                for row in refinement
            ],
            [30 * mm, 38 * mm, 53 * mm, 53 * mm],
        )
    )
    story.append(image(verification / "convergence.png", 158 * mm))
    story.append(
        p(
            "From 9 to 6 mm, first-frequency change is approximately 0.91% and probe "
            "acceleration increases by about 9.98%. Support discretization, nearest-node "
            "probe selection and the band-edge mode contribute to this sensitivity. "
            "Further amplitude refinement and mode-count studies remain open."
        )
    )
    story.append(
        p(
            "Automated checks cover PSD integrals, SDOF limiting cases, coherent modal "
            "response, unit conversion, tetrahedral ordering, sampling/provenance checks, "
            "the beam benchmark and generated-to-imported STEP analysis. Raw evidence is included.",
            "SmallVQ",
        )
    )
    story.append(PageBreak())

    heading("04 / DEMONSTRATION & LIMITS", "Reproduce, inspect, and extend")
    story.append(
        p(
            "Install the dependencies on Ubuntu or Ubuntu under WSL, activate a Python "
            "virtual environment and run the repository commands below. Use a new output "
            "directory for every run."
        )
    )
    story.append(
        Preformatted(
            "python -m pip install -e '.[dev,report]'\nvibequal doctor\n"
            "vibequal validate --out runs/beam\nvibequal demo --out runs/demo\n"
            "python -m pytest -q",
            styles["Code"],
        )
    )
    story.append(Spacer(1, 12))
    story.append(
        p(
            "Open runs/demo/report.html. Rotate the enclosure, select modes, inspect the "
            "PSD and PCB screen, then compare the synthetic tap spectrum. The complete "
            "solver deck, results, STEP model and run manifest are linked from the report."
        )
    )
    story.append(
        p(
            "<b>Physical correlation remains pending.</b> A future test must reproduce the "
            "mounting, use a properly conditioned sensor and record repeatable tap signals. "
            "The optional ADALM1000 adapter is supplied but has not been hardware-tested. "
            "A resonance match would support the frequency model, not establish response "
            "amplitude, stress or fatigue accuracy."
        )
    )
    story.append(
        p(
            "<b>Scope limits.</b> No lid/payload/contact nonlinearities, measured damping, "
            "coupled enclosure/PCB dynamics, solder stress, cumulative fatigue damage or "
            "standards qualification are included. The demonstration PSD is educational. "
            "The next engineering steps are fixture-aware frequency correlation, damping "
            "estimation, amplitude/mode-count convergence and a coupled PCB model."
        )
    )
    story.append(p("Selected references", "HeadingVQ"))
    refs = [
        ("Gmsh reference manual", "https://gmsh.info/doc/texinfo/gmsh.html"),
        ("CalculiX official documentation", "https://dhondt.de/"),
        (
            "NASA Goddard FEMCI - Miles and random vibration",
            "https://etd.gsfc.nasa.gov/wp-content/uploads/2025/04/FEMCI-The-Book.pdf",
        ),
        (
            "Irvine - Steinberg method and limitations",
            "https://www.vibrationdata.com/tutorials2/electronic_rd_n.pdf",
        ),
        ("Analog Devices libsmu and ADALM1000", "https://github.com/analogdevicesinc/libsmu"),
        (
            "DLA MIL-STD-810 environmental tailoring scope",
            "https://quicksearch.dla.mil/qsDocdetails.aspx?ident_number=35978",
        ),
    ]
    for title, url in refs:
        story.append(p(f'<link href="{url}" color="#087d82">{title}</link>', "SmallVQ"))
    story.append(
        p(
            "Additional sources and complete URLs: docs/REFERENCES.md. "
            "Recorded run timestamp (UTC): " + summary["created_utc"],
            "SmallVQ",
        )
    )

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#dce4e7"))
        canvas.line(19 * mm, 16 * mm, A4[0] - 19 * mm, 16 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(muted)
        canvas.drawString(
            19 * mm, 11 * mm, "VIBEQUAL / SIMULATION AND VERIFICATION / PHYSICAL TEST PENDING"
        )
        canvas.drawRightString(A4[0] - 19 * mm, 11 * mm, f"{document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(output)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=Path("examples/reference_run"))
    p.add_argument("--verification", type=Path, default=Path("examples/verification"))
    p.add_argument("--out", type=Path, default=Path("docs/PROJECT_REPORT.pdf"))
    a = p.parse_args()
    build(a.run, a.verification, a.out)
