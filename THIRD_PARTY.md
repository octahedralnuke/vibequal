# Third-party components

Dependencies are installed from their own distributions; their licenses remain applicable.

| Component | Role | Upstream |
|---|---|---|
| Gmsh | CAD and meshing | https://gmsh.info/ |
| CalculiX | External structural solver | https://dhondt.de/ |
| NumPy | Array calculations | https://numpy.org/ |
| SciPy | Quadrature and spectral analysis | https://scipy.org/ |
| Matplotlib | Scientific plots | https://matplotlib.org/ |
| ReportLab (optional) | Printable report generation | https://www.reportlab.com/ |
| pytest / Ruff / build (development) | Verification and packaging | https://docs.pytest.org/ / https://docs.astral.sh/ruff/ / https://build.pypa.io/ |
| libsmu / pysmu (optional, user installed) | ADALM1000 communication | https://github.com/analogdevicesinc/libsmu |

The generated tray CAD is original to this project. The default PSD is illustrative user-defined data. No RTCA standards text, borrowed CAD, solver binaries or vendor drivers are redistributed here. The optional public DoD Category 24 spectrum is transcribed from the cited original government document with provenance; no DO-160 curve is included. Mathematical methods are cited in docs/REFERENCES.md; the implementations are original project code.
