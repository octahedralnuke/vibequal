# Calculation methods

## 1. Modal finite-element analysis

The constrained, unloaded linear-elastic model solves:

$$K\phi_j=\omega_j^2 M\phi_j,\qquad f_j=\omega_j/(2\pi).$$

CalculiX supplies mass-normalized modes, $\phi_j^T M\phi_j=1$. For unit rigid translation $r$ along the chosen base-input axis, the participation factor is $\Gamma_j=\phi_j^T M r$. Translational effective modal mass is $\Gamma_j^2$. Only the first three participation/mass columns are interpreted as translation; rotational columns have different dimensions.

Participation is the projection of a unit rigid-base translation into a mode through the mass matrix; squaring it gives effective translational modal mass for a mass-normalized mode. A mode can have a low frequency but weak participation in a chosen input direction. The code reports both available solver mass and full CAD mass denominators.

C3D10 elements use quadratic displacement interpolation, which represents displacement curvature in bending more effectively than a coarse constant-strain four-node tetrahedral mesh. This choice does not remove the need for mesh refinement.

Frequency changes with stiffness, density, boundary conditions, discretization and payload. A plausible eigenfrequency alone does not establish model accuracy.

## 2. PSD integration

The one-sided input acceleration density $S_g(f)$ uses g²/Hz. For each segment, $S_g(f)=S_1(f/f_1)^n$, with $n=\ln(S_2/S_1)/\ln(f_2/f_1)$. Its area is evaluated analytically, including the logarithmic $n=-1$ case:

$$g_{in,rms}=\sqrt{\int_{f_{min}}^{f_{max}}S_g(f)\,df}.$$

The spectrum is zero outside its specified band. The code integrates density, not amplitude spectral density, and does not square input g RMS a second time.

## 3. Miles' approximation

For a lightly damped, dominant SDOF resonance under sufficiently broadband excitation:

$$g_{rms}\approx\sqrt{\frac{\pi}{2}f_n Q S_g(f_n)},\qquad Q=\frac{1}{2\zeta}.$$

This is a unit-participation SDOF estimate. The per-mode probe estimate multiplies it by $|\phi_{pj}\Gamma_j|$. Miles values do not include a complete multimode response. In particular, a resonance just outside the input band can have zero PSD at its natural frequency and still respond to in-band forcing; numerical integration captures that case.

See NASA's FEMCI Miles discussion in [REFERENCES.md](REFERENCES.md).

## 4. Numerical base-excitation response

For a unit input acceleration in the selected axis, define:

$$D_j(\omega)=\omega_j^2-\omega^2+i2\zeta\omega_j\omega,$$

$$H_u(\omega)=-g_0\sum_j\frac{\phi_{pj}\Gamma_j}{D_j(\omega)},\qquad
H_a(\omega)=1+\omega^2\sum_j\frac{\phi_{pj}\Gamma_j}{D_j(\omega)}.$$

$H_u$ is relative displacement in metres per input g; $H_a$ is absolute acceleration in g per input g. The `1` term is rigid base acceleration. The probe response follows:

$$u_{rms}^2=\int |H_u|^2S_g\,df,\qquad a_{rms}^2=\int |H_a|^2S_g\,df.$$

All modes are driven by the **same** base input; summing complex transfer functions before squaring retains modal cross terms. An SRSS sum would impose a different correlation approximation. Quadrature intervals split at PSD breakpoints and around each resonance. The sum is truncated to extracted modes; no residual flexibility or missing-mass correction is applied. Check mode-count convergence and directional mass coverage.

The shown 3-sigma displacement is $3u_{rms}$. It is a statistical amplitude metric, not a guaranteed maximum over a test duration.

## 5. Independent PCB model

For a homogeneous, isotropic, four-edge simply supported plate:

$$D=\frac{Eh^3}{12(1-\nu^2)},\quad \mu=\rho h+\frac{m_{components}}{ab},$$

$$f_{11}=\frac{\pi}{2}\sqrt{\frac{D}{\mu}}\left(\frac{1}{a^2}+\frac{1}{b^2}\right).$$

With $\phi_{11}=\sin(\pi x/a)\sin(\pi y/b)$ normalized to unity at the centre, uniform-base participation is $16/\pi^2$. Numerical SDOF displacement integration uses this participation. This is a separate model with direct application of the input PSD, not a coupled enclosure/PCB model.

The empirical Steinberg limit is calculated using **inches**:

$$Z_{3\sigma,limit}=\frac{0.00022B}{C h r\sqrt{L}}\quad\text{inches}.$$

$B$ is board edge length parallel to the component, $h$ board thickness, $L$ component length, $C$ package factor and $r$ position factor. The result is converted back to metres. Margin is $Z_{limit}/Z_{predicted}-1$. The reference method concerns approximately 20 million stress reversals under its stated assumptions. This implementation gives a deflection screen and **does not calculate service life**, cumulative damage or solder stresses. See the cited Irvine method discussion for applicability limitations.

## 6. Tap signal processing

The CSV contains uniform sample times and sensor voltage. The mean is removed, the record is cropped around its largest excursion, and a zero-padded periodogram is evaluated. An interior spectral peak in the search band is refined with a three-point log-parabolic interpolation. Actual record resolution is based on record duration; zero padding improves interpolation rather than adding physical information.

The reported frequency difference is $100(f_{peak}-f_{FEA})/f_{FEA}$. An output-only dominant peak need not be the first structural mode. Sensor location, excitation location, fixture modes and sensor resonances can change which peak dominates. No force measurement, calibrated acceleration or full experimental modal identification is claimed.

## 7. Band-edge example

The illustrative reference profile ends at 2000 Hz. Mode 3 at 2004.177 Hz has zero PSD at its own resonance, so Miles returns zero. The finite-band unit-participation SDOF integral remains about 16.2 g RMS because in-band forcing excites the resonance tail. That is a unit oscillator result, not an isolated modal contribution to the full probe response. The full transfer includes probe coefficients, the rigid-base term and coherent cross terms. Mesh refinement can move this mode inside the excitation band, helping explain why response amplitude is more sensitive than the first natural frequency.
