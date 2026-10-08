"""Bounded 200 Hz excitations and audit of genuinely measured target records."""
import numpy as np

ANKLES = [4, 5, 10, 11]


def wave_tables(windows, seed=7601, frames=220):
    rng = np.random.RandomState(seed)
    tables, metadata = {}, {}
    counters = {}
    for key, motion in windows.items():
        task = motion["dataset_task"]
        index = counters.get(task, 0)
        counters[task] = index + 1
        kind = ("sine", "square", "bounded_gaussian")[index % 3]
        frequency = rng.uniform(1., 3., 4)
        phase = rng.uniform(0., 2 * np.pi, 4)
        time = np.arange(frames)[:, None] / 200.
        if kind == "sine":
            values = .04 * np.sin(2 * np.pi * time * frequency + phase)
        elif kind == "square":
            values = .04 * np.sign(np.sin(2 * np.pi * time * frequency + phase))
        else:
            values = np.clip(rng.normal(0., .02, (frames, 4)), -.04, .04)
        tables[key] = values.astype(np.float32)
        metadata[key] = {"type": kind, "frequency_hz": frequency.tolist() if kind != "bounded_gaussian" else None,
                         "phase_rad": phase.tolist() if kind != "bounded_gaussian" else None,
                         "max_position_offset_rad": .04, "group": motion["dataset_group"], "task": task}
    return tables, metadata


def audit_record(reference, record, table):
    n = len(record["dof"])
    times = np.asarray(record["motion_times"]).reshape(-1)
    if n != 208 or not np.isclose(record["fps"], 200.) or not np.allclose(np.diff(times), .005, atol=2e-6):
        raise ValueError("Expected 208 genuinely recorded, continuous 5ms states")
    if np.asarray(record["terminate"]).any():
        raise ValueError("Target acquisition terminated; do not discard failed groups silently")
    # The stored post-step command was executed at the preceding 5ms instant.
    source_frame = np.floor(np.arange(n) * 50 / 200 + 1e-5).astype(int) + 1
    expected = np.asarray(reference["action"])[source_frame].copy()
    expected[:, ANKLES] += table[:n] / .25
    error = float(np.max(np.abs(np.asarray(record["action"]) - expected)))
    if error > 2e-5:
        raise ValueError("Executed command recording mismatch: %g" % error)
    for key in ("dof", "dof_vel", "root_trans_offset", "root_rot", "root_lin_vel", "root_ang_vel", "body_pos"):
        if not np.isfinite(record[key]).all():
            raise ValueError("Non-finite acquired state: " + key)
    return {"frames": n, "transitions": n-1, "recorded_fps": float(record["fps"]),
            "command_max_absolute_error": error}


def actuator_features(record):
    """Descriptive regimes, using the same next-transition action convention."""
    q = np.asarray(record["dof"])
    actions = np.asarray(record["action"])
    velocity = np.asarray(record["dof_vel"])[:-1, ANKLES]
    error = np.array([-.2, 0., -.2, 0.]) + .25 * actions[1:, ANKLES] - q[:-1, ANKLES]
    torque = 20 * error - np.array([.2, .1, .2, .1]) * velocity
    return {"mean_ankle_range_rad": float(np.ptp(q[:, ANKLES], axis=0).mean()),
            "servo_error_rms_rad": float(np.sqrt(np.mean(error**2))),
            "ankle_velocity_rms_rad_s": float(np.sqrt(np.mean(velocity**2))),
            "command_change_rms_rad": float(np.sqrt(np.mean((.25*np.diff(actions[1:, ANKLES], axis=0))**2))),
            "source_nominal_saturation_fraction": float(np.mean(np.abs(torque)>=50))}
