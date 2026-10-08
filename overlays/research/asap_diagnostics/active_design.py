"""Pure CPU command design and local two-gain information criterion."""
from collections import defaultdict

import numpy as np
from scipy.spatial.transform import Rotation

from research.asap_diagnostics.dataset_tools import slice_motion

ANKLES = [4, 5, 10, 11]


def group_windows(motions, frames=54, earliest=False):
    """One central window in the longest segment of each original training group."""
    groups = defaultdict(list)
    for key, motion in motions.items():
        groups[motion["dataset_group"]].append((key, motion))
    result = {}
    for group in sorted(groups):
        eligible = [item for item in groups[group] if len(item[1]["dof"])>=frames]
        if not eligible:
            raise ValueError("Training group has no full command-design window: " + group)
        key, motion = min(eligible, key=lambda item:item[0]) if earliest else max(eligible, key=lambda item: (len(item[1]["dof"]), item[0]))
        start = 0 if earliest else (len(motion["dof"]) - frames) // 2
        if start < 0:
            raise ValueError("Training group has no full command-design window: " + group)
        result[key] = slice_motion(motion, start, start + frames)
    return result


def decode_design(unit):
    unit = np.asarray(unit, dtype=float)
    if unit.shape != (4,) or not np.isfinite(unit).all() or np.any((unit < 0) | (unit > 1)):
        raise ValueError("Design must be four finite coordinates in [0,1]")
    return {"amplitude_rad": (.08 * unit[:2]).tolist(),
            "frequency_hz": (.5 + 2.5 * unit[2:]).tolist(),
            "left_right_phase_rad": float(np.pi), "roll_phase_rad": float(np.pi / 2)}


def excite(motions, design):
    result = {}
    amplitudes = np.asarray(design["amplitude_rad"])
    frequencies = np.asarray(design["frequency_hz"])
    for key, motion in motions.items():
        modified = dict(motion)
        commands = np.asarray(motion["action"]).copy()
        # Post-step convention: a[i+1] acts on s[i]. The starting phase is local.
        times = np.arange(len(commands) - 1) / float(motion["fps"])
        phases = np.array([0., design["roll_phase_rad"]])
        left = amplitudes * np.sin(2 * np.pi * times[:, None] * frequencies + phases)
        right = amplitudes * np.sin(2 * np.pi * times[:, None] * frequencies + phases + design["left_right_phase_rad"])
        commands[1:, ANKLES] += np.concatenate((left, right), axis=1) / .25
        modified["action"] = commands
        result[key] = modified
    return result


def finite_difference_gains(center, step=.5):
    center = np.asarray(center, dtype=float)
    if center.shape != (2,) or step <= 0:
        raise ValueError("Expected two gains and a positive finite-difference step")
    return [center + sign * step * np.eye(2)[axis] for axis in range(2) for sign in (1, -1)]


def valid_trajectory(motion, horizon=1.):
    times = np.asarray(motion["motion_times"]).reshape(-1)
    rows = np.flatnonzero((times > 1e-6) & (times <= horizon + 1e-6))
    if len(rows) != int(round(horizon * float(motion["fps"]))) or np.asarray(motion["terminate"])[rows].any():
        return False
    position = np.asarray(motion["root_trans_offset"])[rows]
    rotation = np.asarray(motion["root_rot"])[rows]
    if not np.isfinite(position).all() or not np.isfinite(rotation).all():
        return False
    gravity = Rotation.from_quat(rotation).inv().apply(np.tile([0., 0., -1.], (len(rows), 1)))
    return bool(np.min(position[:, 2]) >= .35 and np.max(np.abs(gravity[:, :2])) <= .8)


def information_score(predictions, keys, weights, step=.5, noise_rad=.005, ridge=1e-3):
    """A-optimal local design, assuming independent ankle-position observation noise.

    Parameters are two scalar Kp values. Trajectory sensitivities include contact
    dynamics. This noise model is a design assumption, not measured sensor noise.
    """
    count = len(keys)
    fisher = np.zeros((2, 2))
    for index, key in enumerate(keys):
        trajectories = [predictions["motion%d" % (candidate * count + index)] for candidate in range(4)]
        if not all(valid_trajectory(m) for m in trajectories):
            return {"feasible": False, "objective": 1e12, "fisher": None}
        vectors = []
        for motion in trajectories:
            times = np.asarray(motion["motion_times"]).reshape(-1)
            rows = np.flatnonzero((times > 1e-6) & (times <= 1. + 1e-6))
            vectors.append(np.asarray(motion["dof"])[rows][:, ANKLES].reshape(-1))
        jacobian = np.stack(((vectors[0] - vectors[1]) / (2 * step),
                             (vectors[2] - vectors[3]) / (2 * step)), axis=1)
        if not np.isfinite(jacobian).all():
            raise ValueError("Non-finite parameter sensitivity")
        fisher += weights[key] * (jacobian.T @ jacobian) / noise_rad ** 2
    objective = float(np.trace(np.linalg.inv(fisher + ridge * np.eye(2))))
    return {"feasible": True, "objective": objective, "fisher": fisher.tolist(),
            "eigenvalues": np.linalg.eigvalsh(fisher).tolist()}
