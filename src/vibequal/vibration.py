"""One-sided PSDs, Miles estimates and coherent modal base-excitation response."""

from dataclasses import dataclass

import numpy as np
from scipy.integrate import quad

G0 = 9.80665


@dataclass(frozen=True)
class PSDProfile:
    name: str
    frequency: np.ndarray
    density: np.ndarray
    source: str = "user supplied"
    duration_s: float = 60.0

    def __post_init__(self):
        f, s = np.asarray(self.frequency, dtype=float), np.asarray(self.density, dtype=float)
        if (
            f.ndim != 1
            or s.shape != f.shape
            or len(f) < 2
            or not np.all(np.isfinite(f))
            or not np.all(np.isfinite(s))
            or np.any(f <= 0)
            or np.any(s <= 0)
            or np.any(np.diff(f) <= 0)
        ):
            raise ValueError(
                "PSD needs at least two strictly increasing positive frequencies "
                "and positive finite densities in g^2/Hz"
            )
        if not np.isfinite(self.duration_s) or self.duration_s <= 0:
            raise ValueError("Profile duration_s must be positive and finite")
        object.__setattr__(self, "frequency", f)
        object.__setattr__(self, "density", s)

    @classmethod
    def from_config(cls, config):
        points = np.asarray(config["breakpoints_hz_g2_per_hz"], dtype=float)
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("PSD breakpoints must be [frequency_hz, density_g2_per_hz] pairs")
        return cls(
            config.get("name", "User-defined PSD"),
            points[:, 0],
            points[:, 1],
            config.get("source", "user supplied"),
            config.get("duration_s", 60.0),
        )

    def at(self, frequency):
        f = np.asarray(frequency, dtype=float)
        safe = np.maximum(f, np.finfo(float).tiny)
        values = np.exp(np.interp(np.log(safe), np.log(self.frequency), np.log(self.density)))
        return np.where((f >= self.frequency[0]) & (f <= self.frequency[-1]), values, 0.0)

    @property
    def input_grms(self):
        total = 0.0
        for f1, f2, s1, s2 in zip(
            self.frequency[:-1],
            self.frequency[1:],
            self.density[:-1],
            self.density[1:],
            strict=True,
        ):
            slope = np.log(s2 / s1) / np.log(f2 / f1)
            if abs(slope + 1) < 1e-10:
                total += s1 * f1 * np.log(f2 / f1)
            else:
                total += s1 * f1 * np.expm1((slope + 1) * np.log(f2 / f1)) / (slope + 1)
        return float(np.sqrt(total))


def miles_grms(frequency_hz, damping_ratio, psd_at_resonance):
    if frequency_hz <= 0 or not 0 < damping_ratio <= 0.2 or psd_at_resonance < 0:
        raise ValueError("Miles calculation needs f>0, 0<damping<=0.2, and PSD>=0")
    return float(np.sqrt(np.pi / 2 * frequency_hz / (2 * damping_ratio) * psd_at_resonance))


def integrate_response(profile, transfer_squared, resonances=()):
    # Split at PSD breakpoints and around resonances; adaptive quadrature resolves narrow peaks.
    points = set(map(float, profile.frequency))
    for fn, zeta in resonances:
        for multiple in [-10, -3, -1, 0, 1, 3, 10]:
            p = fn * (1 + multiple * zeta)
            if profile.frequency[0] < p < profile.frequency[-1]:
                points.add(float(p))
    ordered = sorted(points)
    result = 0.0
    for lower, upper in zip(ordered[:-1], ordered[1:], strict=True):
        value, _ = quad(
            lambda f: float(profile.at(f)) * float(transfer_squared(f)),
            lower,
            upper,
            epsabs=1e-16,
            epsrel=2e-6,
            limit=150,
        )
        result += value
    return float(np.sqrt(max(0.0, result)))


def sdof_response(profile, frequency_hz, damping_ratio, participation=1.0):
    wn = 2 * np.pi * frequency_hz

    def denominator(f):
        w = 2 * np.pi * f
        return wn**2 - w**2 + 2j * damping_ratio * wn * w

    accel = integrate_response(
        profile,
        lambda f: abs((wn**2 + 2j * damping_ratio * wn * 2 * np.pi * f) / denominator(f)) ** 2,
        [(frequency_hz, damping_ratio)],
    )
    relative = integrate_response(
        profile,
        lambda f: abs(participation * G0 / denominator(f)) ** 2,
        [(frequency_hz, damping_ratio)],
    )
    return {
        "absolute_acceleration_grms": accel,
        "relative_displacement_rms_m": relative,
        "miles_unit_participation_grms": miles_grms(
            frequency_hz, damping_ratio, float(profile.at(frequency_hz))
        ),
    }


def modal_response(mesh, modal, config):
    profile = PSDProfile.from_config(config["profile"])
    a = config["analysis"]
    axis = "xyz".index(a["axis"])
    distances = np.linalg.norm(mesh.xyz - np.asarray(a["probe_xyz_m"]), axis=1)
    probe = int(np.argmin(distances))
    if int(mesh.node_ids[probe]) in set(map(int, mesh.fixed_ids)):
        raise ValueError("Probe selects a clamped node; choose an unconstrained response location")
    fns = modal["frequencies_hz"]
    wn = 2 * np.pi * fns
    zeta = a["damping_ratio"]
    coefficients = modal["shapes"][:, probe, axis] * modal["participation"][:, axis]

    def transfers(f):
        w = 2 * np.pi * f
        terms = coefficients / (wn**2 - w**2 + 2j * zeta * wn * w)
        relative = -sum(terms) * G0  # m/g; one coherent base input drives all modes
        absolute = 1 + w**2 * sum(terms)  # g/g, including the rigid base contribution
        return absolute, relative

    resonances = [(float(fn), zeta) for fn in fns]
    accel = integrate_response(profile, lambda f: abs(transfers(f)[0]) ** 2, resonances)
    displacement = integrate_response(profile, lambda f: abs(transfers(f)[1]) ** 2, resonances)
    mass = mesh.volume_m3 * config["material"]["density_kg_m3"]
    rows = []
    for i, fn in enumerate(fns):
        sdof = sdof_response(profile, float(fn), zeta)
        rows.append(
            {
                "mode": i + 1,
                "frequency_hz": float(fn),
                "effective_mass_kg": float(modal["effective_mass_kg"][i, axis]),
                "effective_mass_fraction_of_cad": float(modal["effective_mass_kg"][i, axis] / mass),
                "probe_coefficient": float(coefficients[i]),
                "miles_unit_sdof_grms": sdof["miles_unit_participation_grms"],
                "miles_probe_modal_grms": abs(float(coefficients[i]))
                * sdof["miles_unit_participation_grms"],
                "integrated_unit_sdof_grms": sdof["absolute_acceleration_grms"],
                "inside_excitation_band": bool(profile.frequency[0] <= fn <= profile.frequency[-1]),
            }
        )
    grid = np.unique(
        np.concatenate(
            [np.geomspace(profile.frequency[0], profile.frequency[-1], 1500)]
            + [
                fn * np.linspace(max(0.05, 1 - 8 * zeta), 1 + 8 * zeta, 180)
                for fn in fns
                if profile.frequency[0] <= fn <= profile.frequency[-1]
            ]
        )
    )
    grid = grid[(grid >= profile.frequency[0]) & (grid <= profile.frequency[-1])]
    transfer = np.array([transfers(f)[0] for f in grid])
    result = {
        "input_grms": profile.input_grms,
        "damping_ratio": zeta,
        "q": 1 / (2 * zeta),
        "axis": a["axis"],
        "probe_node": int(mesh.node_ids[probe]),
        "probe_xyz_m": mesh.xyz[probe].tolist(),
        "probe_snap_distance_m": float(distances[probe]),
        "absolute_acceleration_grms": accel,
        "relative_displacement_rms_m": displacement,
        "relative_displacement_3sigma_m": 3 * displacement,
        "effective_mass_fraction_of_cad": float(modal["effective_mass_kg"][:, axis].sum() / mass),
        "modes": rows,
    }
    if "total_effective_mass" in modal:
        total = float(modal["total_effective_mass"][axis])
        result["total_effective_mass_kg"] = total
        result["effective_mass_fraction_of_solver_total"] = float(
            modal["effective_mass_kg"][:, axis].sum() / total
        )
    return result, {
        "frequency_hz": grid,
        "input_psd_g2_hz": profile.at(grid),
        "response_psd_g2_hz": profile.at(grid) * np.abs(transfer) ** 2,
    }
