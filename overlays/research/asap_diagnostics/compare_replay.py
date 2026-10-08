"""Compare post-step replay dumps against a target rollout on its local time axis.

Joint-angle RMSE is in radians and root-position error in mm. These are NOT MPJPE.
No time warping, shift search, or frame-wise spatial alignment is performed.
Stock eval/record discards three rows, so the comparison can start after t=0.
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np


def select(data, key):
    if key is not None:
        return data[key]
    if len(data) != 1:
        raise ValueError("Use --reference-key/--prediction-key for multi-motion files")
    return next(iter(data.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--prediction", required=True, type=Path)
    parser.add_argument("--reference-key")
    parser.add_argument("--prediction-key")
    parser.add_argument("--start-time", type=float, default=0.0,
                        help="Reference-local reset time used by the replay; normally zero")
    parser.add_argument("--horizon", type=float, default=1.0)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if args.horizon <= 0 or args.start_time < 0:
        parser.error("horizon must be positive and start-time nonnegative")
    ref = select(joblib.load(args.reference), args.reference_key)
    pred = select(joblib.load(args.prediction), args.prediction_key)
    n = len(pred["dof"])
    if "motion_times" not in pred:
        parser.error("Prediction needs motion_times from the stock record exporter")
    times = np.asarray(pred["motion_times"]).reshape(-1)
    if times.shape != (n,) or not np.isfinite(times).all():
        parser.error("Invalid prediction motion_times")
    if not np.isclose(float(ref["fps"]), float(pred["fps"])):
        parser.error("Reference and prediction fps differ")
    if "terminate" not in ref or "terminate" not in pred:
        parser.error("Both files need terminate flags to verify episode continuity")
    if np.asarray(ref["terminate"]).any():
        parser.error("Reference contains reset rows; split and remove them first")
    stop = n
    resets = np.flatnonzero(np.asarray(pred["terminate"]).reshape(n, -1).any(axis=1))
    if resets.size:
        stop = int(resets[0])
    fps = float(ref["fps"])
    if not np.isfinite(fps) or fps <= 0:
        parser.error("Invalid reference fps")
    times = times[:stop]
    if times.size > 1 and not np.allclose(np.diff(times), 1 / fps, atol=1e-5, rtol=1e-3):
        parser.error("Prediction contains time jumps: this tool requires one continuous replay")
    duration = (len(ref["dof"]) - 1) / fps
    mask = ((times >= args.start_time - 1e-6)
            & (times <= args.start_time + args.horizon + 1e-6)
            & (times <= duration + 1e-6))
    rows = np.flatnonzero(mask)
    if rows.size == 0:
        parser.error("No samples in the requested replay horizon")
    # Prediction motion_times already includes the reset start-time.
    frame = np.clip(times[rows] * fps, 0, len(ref["dof"]) - 1)
    lo = np.floor(frame).astype(int)
    hi = np.minimum(lo + 1, len(ref["dof"]) - 1)
    w = (frame - lo)[:, None]
    metrics = {}
    for key in ("dof", "root_trans_offset", "dof_vel"):
        if key not in ref or key not in pred:
            continue
        recorded = np.asarray(ref[key])
        simulated = np.asarray(pred[key])
        if recorded.ndim != 2 or simulated.shape[0] != n or recorded.shape[1:] != simulated.shape[1:]:
            parser.error(f"Shape mismatch for {key}")
        expected = (1 - w) * recorded[lo] + w * recorded[hi]
        error = simulated[rows] - expected
        if not np.isfinite(error).all():
            parser.error(f"Non-finite values for {key}")
        if key == "root_trans_offset":
            metrics["root_position_mean_error_mm"] = float(np.linalg.norm(error, axis=1).mean() * 1000)
        else:
            unit = "rad" if key == "dof" else "rad_s"
            metrics[key + "_rmse_" + unit] = float(np.sqrt(np.mean(error ** 2)))
            metrics[key + "_ankle_rmse_" + unit] = float(
                np.sqrt(np.mean(error[:, [4, 5, 10, 11]] ** 2)))
    result = {
        "reference": str(args.reference), "prediction": str(args.prediction),
        "start_time_s": args.start_time, "requested_horizon_s": args.horizon,
        "first_compared_time_s": float(times[rows[0]]),
        "last_compared_time_s": float(times[rows[-1]]), "compared_frames": len(rows),
        "prediction_first_reset_row": int(resets[0]) if resets.size else None,
        "metrics": metrics,
        "scope": "Raw same-origin joint/root comparison; not body MPJPE or closed-loop tracking",
    }
    output = json.dumps(result, indent=2, allow_nan=False)
    print(output)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output + "\n")


if __name__ == "__main__":
    main()
