"""Independent PCB plate estimate and empirical Steinberg deflection screening."""

import numpy as np

from .vibration import sdof_response


def steinberg_allowable_m(
    edge_parallel_m, thickness_m, component_length_m, package_constant, position_factor
):
    # The coefficient 0.00022 is empirical and MUST be evaluated with all lengths in inches.
    values = [edge_parallel_m, thickness_m, component_length_m, package_constant, position_factor]
    if not all(np.isfinite(x) and x > 0 for x in values):
        raise ValueError("Steinberg inputs must be positive and finite")
    inch = 0.0254
    b, h, length = edge_parallel_m / inch, thickness_m / inch, component_length_m / inch
    return float(inch * 0.00022 * b / (package_constant * h * position_factor * np.sqrt(length)))


def screen_pcb(p, profile):
    length, width, h = p["length_m"], p["width_m"], p["thickness_m"]
    rigidity = p["youngs_modulus_pa"] * h**3 / (12 * (1 - p["poisson_ratio"] ** 2))
    areal_mass = p["density_kg_m3"] * h + p.get("smeared_component_mass_kg", 0) / (length * width)
    fn = np.pi / 2 * np.sqrt(rigidity / areal_mass) * (1 / length**2 + 1 / width**2)
    # phi_11=sin(pi*x/a)sin(pi*y/b), normalized to unity at centre.
    # Uniform base acceleration participation = integral(phi)/integral(phi^2)=16/pi^2.
    gamma = 16 / np.pi**2
    response = sdof_response(profile, float(fn), p["damping_ratio"], participation=gamma)
    three_sigma = 3 * response["relative_displacement_rms_m"]
    allowable = steinberg_allowable_m(
        p["board_edge_parallel_to_component_m"],
        h,
        p["component_length_m"],
        p["package_constant"],
        p["position_factor"],
    )
    margin = allowable / three_sigma - 1 if three_sigma else None
    return {
        "model": p["model"],
        "natural_frequency_hz": float(fn),
        "first_mode_participation": float(gamma),
        "relative_deflection_3sigma_m": three_sigma,
        "allowable_3sigma_m": allowable,
        "margin": margin,
        "screening_result": "below_empirical_limit"
        if three_sigma <= allowable
        else "exceeds_empirical_limit",
        "nominal_reference_stress_reversals": 20000000,
        "excitation_assumption": "Direct application of the input PSD to independent PCB supports; "
        "enclosure-to-PCB coupling is NOT modeled.",
        "limitations": "Isotropic, four-edge simply supported, first plate mode, smeared component "
        "mass, empirical package factor. No predicted service life or solder-joint stress.",
    }
