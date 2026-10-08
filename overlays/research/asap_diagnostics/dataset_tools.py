"""Pure CPU dataset splitting and replay metrics; trusted local joblib inputs."""
import hashlib
import math

import numpy as np


FRAME_FIELDS = ("pose_aa", "root_trans_offset", "root_rot", "dof", "action",
                "dof_vel", "root_lin_vel", "root_ang_vel", "body_pos", "terminate", "motion_times")


def slice_motion(motion, start, stop):
    result = dict(motion)
    for key in FRAME_FIELDS:
        if key in motion:
            result[key] = np.asarray(motion[key])[start:stop].copy()
    n = stop - start
    result["motion_times"] = np.arange(n, dtype=np.float32) / float(motion["fps"])
    result["terminate"] = np.zeros(n, dtype=bool)
    return result


def continuous_segments(motion, horizon=1.0):
    fps = float(motion["fps"])
    if not np.isclose(fps, 50):
        raise ValueError("Expected 50 Hz recorded data")
    n = len(motion["dof"])
    expected = {"action": (n, 23), "dof": (n, 23), "dof_vel": (n, 23),
                "root_trans_offset": (n, 3), "root_rot": (n, 4),
                "root_lin_vel": (n, 3), "root_ang_vel": (n, 3), "body_pos": (n, 24, 3)}
    for key, shape in expected.items():
        arr = np.asarray(motion[key])
        if arr.shape != shape or not np.isfinite(arr).all():
            raise ValueError("Invalid shape or values: " + key)
    times = np.asarray(motion["motion_times"]).reshape(n)
    if not np.isfinite(times).all() or not np.isfinite(np.asarray(motion["pose_aa"])).all():
        raise ValueError("Invalid pose/time values")
    reset = np.asarray(motion["terminate"]).reshape(n, -1).any(axis=1)
    minimum = int(math.ceil(horizon * fps)) + 2
    result, rejected = [], []
    begin = None
    def finish(end):
        if begin is not None:
            if end - begin >= minimum:
                result.append((begin, end, slice_motion(motion, begin, end)))
            else:
                rejected.append({"start": begin, "end": end, "reason": "shorter_than_full_horizon"})
    for i in range(n):
        if reset[i]:
            finish(i)
            begin = None
            continue
        if begin is not None and not np.isclose(times[i] - times[i-1], 1/fps, atol=1e-5, rtol=1e-3):
            finish(i)
            begin = None
        if begin is None:
            begin = i
    finish(n)
    return result, {"reset_rows": np.flatnonzero(reset).tolist(), "rejected_segments": rejected}


def fingerprint(motion):
    digest = hashlib.sha256()
    for key in ("dof", "dof_vel", "action"):
        digest.update(np.asarray(motion[key], dtype=np.float32).tobytes())
    return digest.hexdigest()


def replay_metrics(reference, prediction, horizon):
    times = np.asarray(prediction["motion_times"]).reshape(-1)
    n = len(times)
    resets = np.flatnonzero(np.asarray(prediction["terminate"]).reshape(n, -1).any(axis=1))
    stop = int(resets[0]) if len(resets) else n
    times = times[:stop]
    fps = float(reference["fps"])
    if not np.isclose(fps, float(prediction["fps"])):
        raise ValueError("FPS mismatch")
    if len(times) > 1 and not np.allclose(np.diff(times), 1/fps, atol=1e-5, rtol=1e-3):
        raise ValueError("Replay has time discontinuities")
    rows = np.flatnonzero((times >= 1e-6) & (times <= horizon + 1e-6))
    frames = times[rows] * fps
    lo = np.floor(frames).astype(int)
    hi = np.minimum(lo + 1, len(reference["dof"]) - 1)
    if len(rows) == 0 or np.any(lo >= len(reference["dof"])):
        raise ValueError("No valid replay samples")
    weights = frames - lo
    errors = {}
    for key in ("dof", "dof_vel", "root_trans_offset", "body_pos"):
        a, b = np.asarray(reference[key]), np.asarray(prediction[key])
        if a.shape[1:] != b.shape[1:]:
            raise ValueError("Shape mismatch: " + key)
        w = weights.reshape((-1,) + (1,) * (a.ndim - 1))
        errors[key] = b[rows] - ((1-w)*a[lo] + w*a[hi])
        if not np.isfinite(errors[key]).all():
            raise ValueError("Non-finite replay error: " + key)
    if reference["body_names"] != prediction["body_names"]:
        raise ValueError("Rigid-body order mismatch")
    q, qv = errors["dof"], errors["dof_vel"]
    body = errors["body_pos"]
    rel_body = body - errors["root_trans_offset"][:, None]
    feet = [reference["body_names"].index(name) for name in ("left_ankle_roll_link", "right_ankle_roll_link")]
    return {
        "frames": len(rows), "expected_frames": int(np.floor(horizon * fps + 1e-5)),
        "complete": bool(len(rows) == int(np.floor(horizon * fps + 1e-5))),
        "first_reset_row": int(resets[0]) if len(resets) else None,
        "ankle_rmse_rad": float(np.sqrt((q[:, [4,5,10,11]]**2).mean())),
        "all_joint_rmse_rad": float(np.sqrt((q**2).mean())),
        "joint_velocity_rmse_rad_s": float(np.sqrt((qv**2).mean())),
        "root_position_mean_error_mm": float(np.linalg.norm(errors["root_trans_offset"], axis=-1).mean()*1000),
        "global_body_mpjpe_mm": float(np.linalg.norm(body, axis=-1).mean()*1000),
        "root_relative_body_mpjpe_mm": float(np.linalg.norm(rel_body, axis=-1).mean()*1000),
        "feet_position_mean_error_mm": float(np.linalg.norm(body[:, feet], axis=-1).mean()*1000),
    }
