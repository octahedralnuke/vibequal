# References and provenance

1. **Gmsh reference manual**, OpenCASCADE import, Python API and mesh generation: https://gmsh.info/doc/texinfo/gmsh.html
2. **CalculiX official distribution and manual**, frequency analysis, mass-normalized modes and participation: https://dhondt.de/ (solver documentation PDF: https://dhondt.de/ccx_2.23.pdf).
3. **NASA Goddard FEMCI - The Book**, sections on Miles' equation, random vibration, unit consistency and model checks: https://etd.gsfc.nasa.gov/wp-content/uploads/2025/04/FEMCI-The-Book.pdf
4. **NASA MSFC-STD-3676B**, relationship between modal frequency, Q and response under an input spectrum: https://standards.nasa.gov/sites/default/files/standards/MSFC/B/0/msfc-std-3676b.pdf
5. **Dave S. Steinberg, Vibration Analysis for Electronic Equipment**, Wiley, third edition. Publisher overview: https://www.wiley.com/en-nl/vibration-analysis-for-electronic-equipment-3rd-edition-p-9780471376859
6. **Tom Irvine, Extending Steinberg's Fatigue Analysis of Electronics Equipment Methodology to a Full Relative Displacement vs. Cycles Curve**, Revision C, 2013. Empirical limit, inch units and limitations: https://www.vibrationdata.com/tutorials2/electronic_rd_n.pdf
7. **Analog Devices ADALM1000 documentation**, 100 kS/s, 16-bit, 0-5 V input: https://www.analog.com/media/en/technical-documentation/evaluation-documentation/eval_adalm1000_documentation_active_learning_module.pdf
8. **Analog Devices, Amplifier Provides Signal Conditioning for Piezofilm Sensor**, high-impedance sensor conditioning: https://www.analog.com/en/resources/technical-articles/amplifier-provides-signal-conditioning-for-piezofilm-sensor.html
9. **Analog Devices libsmu**, ADALM1000 Python communication API and upstream examples: https://github.com/analogdevicesinc/libsmu / https://analogdevicesinc.github.io/libsmu/
10. **RTCA DO-160 overview**, environmental conditions and test procedures: https://www.rtca.org/do-160/
11. **DLA ASSIST, MIL-STD-810 document scope**, environmental tailoring rather than a universal design/test specification: https://quicksearch.dla.mil/qsDocdetails.aspx?ident_number=35978

The equations are implemented in original Python code; third-party tutorial source code is not copied into this project. The default PSD breakpoints are illustrative values selected for this demonstration. No applicable aircraft category or qualification environment has been established. No standards profile or proprietary standard text is reproduced.
