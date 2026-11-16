"""Independent PCB plate estimate and empirical Steinberg deflection screening."""

import numpy as np

from .config import board_layout
from .vibration import G0, integrate_response, sdof_response


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


def nearest_node(mesh, point):
    distances = np.linalg.norm(mesh.xyz - np.asarray(point, dtype=float), axis=1)
    index = int(np.argmin(distances))
    return index, float(distances[index])


def coupled_board(mesh, modal, config, profile):
    """Board-centre deflection relative to its standoff tops, from the coupled FE modes.

    The enclosure, standoffs and board share one eigenbasis, so the board sees the
    filtered base motion rather than the raw input PSD.
    """
    g, a = config["geometry"], config["analysis"]
    b, layout = g["board"], board_layout(g)
    axis = "xyz".index(a["axis"])
    zeta = a["damping_ratio"]
    centre, snap = nearest_node(
        mesh, (g["length_m"] / 2, g["width_m"] / 2, layout["z_top"])
    )
    supports = [nearest_node(mesh, (x, y, layout["z0"]))[0] for x, y in layout["standoffs"]]
    # Out-of-plane (z) board bending relative to the mean standoff-top motion.
    relative_shape = modal["shapes"][:, centre, 2] - modal["shapes"][:, supports, 2].mean(axis=1)
    coefficients = relative_shape * modal["participation"][:, axis]
    wn = 2 * np.pi * modal["frequencies_hz"]

    def transfer_squared(f):
        w = 2 * np.pi * f
        return abs(G0 * sum(coefficients / (wn**2 - w**2 + 2j * zeta * wn * w))) ** 2

    resonances = [(float(fn), zeta) for fn in modal["frequencies_hz"]]
    rms = integrate_response(profile, transfer_squared, resonances)
    three_sigma = 3 * rms
    # Largest quasi-static contribution |coefficient| / wn^2 to the relative deflection.
    dominant = int(np.argmax(np.abs(coefficients) / wn**2))
    result = {
        "model": "fea_coupled_board_on_standoffs",
        "board_centre_node": int(mesh.node_ids[centre]),
        "board_centre_snap_distance_m": snap,
        "standoff_reference_nodes": [int(mesh.node_ids[i]) for i in supports],
        "dominant_board_mode": dominant + 1,
        "dominant_board_mode_frequency_hz": float(modal["frequencies_hz"][dominant]),
        "relative_deflection_rms_m": rms,
        "relative_deflection_3sigma_m": three_sigma,
        "allowable_3sigma_m": None,
        "margin": None,
        "excitation_assumption": "Base PSD applied at the enclosure mounts; the board responds "
        "through the coupled enclosure, standoff and board modes.",
        "limitations": "Bonded standoff and lid joints, isotropic FR4, smeared component mass, "
        "assumed modal damping, single-axis input. Deflection is relative to the mean "
        "standoff-top motion. No predicted service life or solder-joint stress.",
    }
    s = b.get("steinberg")
    if s:
        allowable = steinberg_allowable_m(
            s["board_edge_parallel_to_component_m"],
            b["thickness_m"],
            s["component_length_m"],
            s["package_constant"],
            s["position_factor"],
        )
        result["allowable_3sigma_m"] = allowable
        result["margin"] = allowable / three_sigma - 1 if three_sigma else None
    return result
