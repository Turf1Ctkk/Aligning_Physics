"""Descriptive target-policy actuator support; no utility labels or model fitting."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
ANKLES = [4, 5, 10, 11]
LABELS = ("vanilla", "ft_only", "asap_ft", "sysid_ft", "torque_ft")


def transition_features(record):
    q, v, a = [np.asarray(record[key]) for key in ("dof", "dof_vel", "action")]
    error = np.array([-.2, 0., -.2, 0.]) + .25 * a[1:, ANKLES] - q[:-1, ANKLES]
    velocity = v[:-1, ANKLES]
    change = .25 * (a[1:, ANKLES] - a[:-1, ANKLES])
    vector = np.concatenate((error, velocity, change), axis=1)
    if not np.isfinite(vector).all():
        raise ValueError("Non-finite actuator features")
    return vector


def weighted_quantile(values, weights, quantile):
    order = np.argsort(values)
    x, w = values[order], weights[order]
    grid = (np.cumsum(w) - .5 * w) / np.sum(w)
    return float(np.interp(quantile, grid, x))


def load_evaluations(path):
    if path.is_file():
        return joblib.load(path)
    output = {}
    for label in LABELS:
        cases = []
        for seed in (8101, 8102, 8103):
            records = joblib.load(path / (label + "_seed%d.pkl" % seed))
            for trial in range(32):
                record = records["motion%d" % trial]
                if not np.isclose(record["fps"], 50) or len(record["dof"]) < 50 or np.asarray(record["terminate"])[:50].any():
                    raise ValueError("Every matched trial must complete the first50 stored states at50Hz")
                case = {key: np.asarray(record[key])[:50].copy()
                        for key in ("dof", "dof_vel", "action", "motion_times")}
                case.update(seed=seed, trial=trial, fps=float(record["fps"]))
                cases.append(case)
        output[label] = cases
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--evaluations", type=Path, required=True)
    args = parser.parse_args()
    motions = joblib.load(args.calibration)
    task_groups, counts = defaultdict(set), Counter()
    for motion in motions.values():
        task, group = motion["dataset_task"], motion["dataset_group"]
        task_groups[task].add(group)
        counts[task, group] += 1
    features, weights, groups = [], [], []
    for motion in motions.values():
        values = transition_features(motion)
        task, group = motion["dataset_task"], motion["dataset_group"]
        clip_weight = 1 / len(task_groups) / len(task_groups[task]) / counts[task, group]
        features.append(values)
        weights.extend(np.full(len(values), clip_weight / len(values)))
        groups.extend([group] * len(values))
    matrix, weights, groups = np.concatenate(features), np.asarray(weights), np.asarray(groups)
    if len(matrix) != 6198 or not np.isclose(weights.sum(), 1):
        raise ValueError("Expected confirmed mixed30 calibration pool and normalized hierarchy")
    center = np.array([weighted_quantile(matrix[:, j], weights, .5) for j in range(12)])
    scale = np.array([weighted_quantile(matrix[:, j], weights, .75)
                      - weighted_quantile(matrix[:, j], weights, .25) for j in range(12)])
    scale[scale < 1e-6] = 1
    normalized = (matrix - center) / scale
    # A descriptive reference: query each training transition against all other
    # original parents, so its nearest distance cannot be its own exact record.
    leave_parent_out = np.empty(len(matrix))
    for group in np.unique(groups):
        selected = groups == group
        leave_parent_out[selected] = cKDTree(normalized[~selected]).query(normalized[selected], workers=1)[0]
    threshold = weighted_quantile(leave_parent_out, weights, .95)
    tree = cKDTree(normalized)
    evaluations = load_evaluations(args.evaluations)
    summary = {}
    for label in LABELS:
        rows = []
        if len(evaluations[label]) != 96:
            raise ValueError("Expected all 96 matched trials")
        for record in evaluations[label]:
            if len(record["dof"]) != 50:
                raise ValueError("Expected fixed first 50 stored states, without survivor filtering")
            values = transition_features(record)
            distances = tree.query((values - center) / scale, workers=1)[0]
            nominal_torque = 20 * values[:, :4] - np.array([.2, .1, .2, .1]) * values[:, 4:8]
            rows.append({"seed": record["seed"], "trial": record["trial"], "transitions": len(values),
                "nearest_distance_mean": float(distances.mean()),
                "nearest_distance_median": float(np.median(distances)),
                "above_reference_p95_fraction": float(np.mean(distances > threshold)),
                "source_nominal_saturation_fraction": float(np.mean(np.abs(nominal_torque) >= 50)),
                "servo_error_rms_rad": float(np.sqrt(np.mean(values[:, :4] ** 2))),
                "ankle_velocity_rms_rad_s": float(np.sqrt(np.mean(values[:, 4:8] ** 2))),
                "command_change_rms_rad": float(np.sqrt(np.mean(values[:, 8:12] ** 2)))})
        summary[label] = {"trials": len(rows), "transitions": sum(r["transitions"] for r in rows),
            "mean_trial_metrics": {key: float(np.mean([r[key] for r in rows]))
                for key in rows[0] if key not in ("seed", "trial", "transitions")}, "trial_metrics": rows}
    output = ROOT / "results/policy_regimes"
    output.mkdir(parents=True, exist_ok=True)
    report = {"scope": "Descriptive B-deployment feature support against mixed30 B calibration; not causal evidence or A-training occupancy",
        "feature_order": "Four joints each: next-command servo error, current joint velocity, position-command change from preceding command",
        "features": "e[i]=default+.25*a[i+1]-q[i]; v[i]; .25*(a[i+1]-a[i])",
        "calibration": {"clips": len(motions), "parents": len(np.unique(groups)), "transitions": len(matrix),
            "sha256": hashlib.sha256(args.calibration.read_bytes()).hexdigest(),
            "weighting": "Equal task, original parent within task, continuous clip within parent, transition within clip",
            "weighted_median": center.tolist(), "weighted_iqr": scale.tolist()},
        "reference": {"metric": "Euclidean nearest-neighbor distance in 12 robustly scaled actuator features",
            "leave_parent_out_weighted_p95": threshold,
            "interpretation": "Descriptive threshold from within-training inter-parent variation; not a calibrated OOD probability or confidence bound"},
        "evaluation": {"seeds": [8101, 8102, 8103], "frames_per_trial": 50,
            "transitions_per_trial": 49, "window": "First50 post-step states, nominally .02–1.00s; no reset within window",
            "training_seeds_per_method": 1, "extraction": "All 96 matched trials per method; not selected for task outcome"},
        "summary": summary}
    (output / "summary.json").write_text(json.dumps(report, indent=2))
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4))
    names = ("Original", "FT only", "ASAP FT", "Passive\nSysID FT", "Torque FT")
    metrics = ("nearest_distance_mean", "above_reference_p95_fraction", "servo_error_rms_rad")
    titles = ("Distance to calibration support", "Above inter-parent reference", "Observed actuator error")
    ylabels = ("Robust feature distance", "Transitions above reference p95 (%)", "Ankle servo-error RMS (rad)")
    colors = ("#808C9C", "#DC7F37", "#355C99", "#32836F", "#8D56A0")
    for ax, key, title, ylabel in zip(axes, metrics, titles, ylabels):
        values = [summary[label]["mean_trial_metrics"][key] for label in LABELS]
        if "fraction" in key:
            values = [100 * value for value in values]
        bars = ax.bar(names, values, color=colors)
        ax.bar_label(bars, labels=[f"{value:.3f}" for value in values], padding=3, fontsize=8)
        ax.set(title=title, ylabel=ylabel, ylim=(0, max(values) * 1.25))
        ax.tick_params(axis="x", labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(.5, .015, "All 96 target trials per policy • first 49 recorded transitions • one trained policy per condition\nTraining-only feature scale and reference • descriptive support, not a utility or causal test", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .075, 1, 1))
    fig.savefig(ROOT / "assets/figures/policy_regimes.png", dpi=180)
    print(json.dumps({label: row["mean_trial_metrics"] for label, row in summary.items()}, indent=2))


if __name__ == "__main__":
    main()
