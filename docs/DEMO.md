# Demonstration and viva guide

## Five-minute demonstration

1. **State the objective.** “This tool automates a preliminary vibration analysis of one electronics enclosure and keeps the assumptions with the result.”
2. **Show the CAD and configuration.** Identify tray dimensions, aluminium properties, support coordinates, mesh size, damping and the illustrative PSD. Explain that the default has no lid or payload.
3. **Run `vibequal demo --out runs/live_demo`.** Show the real `modal.inp`, `ccx.log` and `modal.dat` outputs. Choose a fresh directory each time.
4. **Open the report.** Rotate the mesh, change mode number, pause animation and explain the amber supports. Mode animation is exaggerated and is not actual response amplitude.
5. **Explain the response plot.** Input is acceleration density; its integrated area gives input g RMS. Resonance can amplify response. The damping is assumed, not extracted by undamped modal FEA.
6. **Show verification.** Beam analytical error is about 0.6%. The first enclosure frequency stabilizes under refinement, but amplitude remains more sensitive.
7. **Show PCB and tap sections.** PCB screening is an independent plate approximation. The tap example is synthetic; real capture analysis is implemented, while physical comparison remains pending.

If installation time is limited, open the included offline reference report and raw solver evidence, then run the short unit tests. Present that as recorded output rather than pretending the solver ran live.

## Questions you should be able to answer

**Why use modal FEA?**
To estimate natural frequencies, deformation patterns and participation under specified supports, stiffness and mass.

**Why are the mode shapes not actual displacements?**
Eigenvectors have a chosen normalization. The physical amplitude depends on the forcing and damping. VibeQual uses mass-normalized shapes and participation in the forced-response calculation.

**What does Miles' equation assume?**
A dominant, lightly damped SDOF resonance and sufficiently broadband excitation near it. A shaped spectrum, a band-edge resonance or several relevant modes can weaken the approximation.

**Why integrate the full transfer function as well?**
To include the actual finite-band spectrum and coherent modal terms. A mode just above the input band can still contribute through its response tail, even when Miles' local PSD value is zero.

**Why do some modes have very little Z participation?**
Their deformation patterns couple weakly to uniform Z-axis base motion. Frequency alone does not identify which mode dominates a particular response location and excitation direction.

**What is the most uncertain input?**
Joint/mounting stiffness and damping are major uncertainties. Density, payload and mesh/probe discretization also matter.

**Does a positive PCB margin mean the electronics qualify?**
No. It means a first-mode plate estimate lies below an empirical deflection threshold under the stated assumptions. Board supports, package applicability, higher modes and enclosure coupling still need investigation.

**What does the tap test validate?**
With a real, repeatable setup it can support a resonance-frequency comparison. It does not validate vibration endurance or all predicted amplitudes. The bundled synthetic signal validates only the software analysis workflow.

**What is original in the project?**
The generated CAD, Python integration, explicit solver deck/mapping, PSD processing, coherent modal response, report/viewer, testing and provenance workflow. Gmsh and CalculiX supply established meshing and FEA capabilities.

**Why not claim DO-160/MIL-STD-810 compliance?**
The applicable installation/category and test program have not been established, the profile is illustrative, and physical qualification testing was not performed.

## Before presenting

Run the commands yourself, inspect one mode shape, change a PSD level and rerun. Multiplying the whole PSD by four should double RMS acceleration and displacement while leaving natural frequencies unchanged. That is a useful demonstration of linear response and a good check that you understand the workflow.
