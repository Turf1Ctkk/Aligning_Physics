"""Descriptive actuator features from trusted, post-step G1 target recordings."""
import argparse
import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ANKLES = [4, 5, 10, 11]
DEFAULT = np.array([-.2, 0., -.2, 0.])
TASKS = ("CR7", "SquatL1", "StepFBL1")
COLORS = ("#355C99", "#DC7F37", "#32836F")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    motions = joblib.load(args.dataset)
    rows, samples = [], {}
    for key, motion in motions.items():
        q = np.asarray(motion["dof"])
        # s[i] -- a[i+1] --> s[i+1], not a[i] paired with s[i].
        e = DEFAULT + .25 * np.asarray(motion["action"])[1:, ANKLES] - q[:-1, ANKLES]
        velocity = np.asarray(motion["dof_vel"])[ :-1, ANKLES]
        nominal_source_torque = 20. * e - np.array([.2, .1, .2, .1]) * velocity
        if not np.isfinite(e).all() or np.asarray(motion["terminate"]).any():
            raise ValueError("Invalid/noncontinuous calibration clip")
        row = {"clip": key, "task": motion["dataset_task"], "group": motion["dataset_group"],
               "transitions": len(e), "mean_ankle_range_rad": float(np.ptp(q[:, ANKLES], axis=0).mean()),
               "servo_error_rms_rad": float(np.sqrt(np.mean(e ** 2))),
               "ankle_velocity_rms_rad_s": float(np.sqrt(np.mean(velocity ** 2))),
               "source_nominal_saturation_fraction": float(np.mean(np.abs(nominal_source_torque) >= 50.))}
        rows.append(row)
        samples[key] = e
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.1))
    summary = {}
    limit = float(np.ceil(max(np.abs(e).max() for e in samples.values())))
    bins = np.linspace(-limit, limit, 101)
    for task, color in zip(TASKS, COLORS):
        selected = [r for r in rows if r["task"] == task]
        groups = sorted({r["group"] for r in selected})
        correlations = np.corrcoef([r["mean_ankle_range_rad"] for r in selected],
                                  [r["servo_error_rms_rad"] for r in selected])[0, 1]
        values, weights = [], []
        for row in selected:
            e = samples[row["clip"]].ravel()
            segments = sum(r["group"] == row["group"] for r in selected)
            values.extend(e)
            weights.extend(np.full(len(e), 1 / (len(groups) * segments * len(e))))
        density, edges = np.histogram(values, bins=bins, weights=weights)
        axes[0].plot((edges[1:] + edges[:-1]) / 2, density / np.diff(edges), label=task, color=color)
        axes[1].scatter([r["mean_ankle_range_rad"] for r in selected], [r["servo_error_rms_rad"] for r in selected],
                        label=task, color=color, alpha=.7, s=26)
        summary[task] = {"recording_groups": len(groups), "continuous_clips": len(selected),
                         "transitions": sum(r["transitions"] for r in selected),
                         "unweighted_clip_rom_servo_error_correlation": float(correlations),
                         "source_nominal_saturation_fraction": float(np.mean([
                             np.mean([r["source_nominal_saturation_fraction"] for r in selected if r["group"] == group]) for group in groups]))}
    axes[0].set(xlabel="Next-command servo error (rad)", ylabel="Weighted density", title="Command-state regimes\ndiffer across tasks")
    axes[0].legend(frameon=False)
    axes[1].set(xlabel="Mean ankle range within clip (rad)", ylabel="Ankle servo-error RMS (rad)", title="Range and servo error\nare distinct features")
    axes[2].bar(TASKS, [100 * summary[t]["source_nominal_saturation_fraction"] for t in TASKS], color=COLORS)
    axes[2].set(ylabel="Saturated ankle commands (%)", title="Source torque clipping\nlimits local excitation")
    axes[2].tick_params(axis="x", labelsize=9)
    for ax in axes:
        ax.grid(alpha=.2)
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(.5, .015, "Target training pool only • descriptive features, not a data-selection outcome • each dot is one continuous clip",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .045, 1, 1))
    output = ROOT / "assets/figures/calibration_features.png"
    fig.savefig(output, dpi=180)
    directory = ROOT / "results/calibration_features"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(json.dumps({"scope": "Training-pool descriptive analysis; no model-performance or causal conclusion",
        "formula": "e[i] = ankle_default + 0.25 * a[i+1] - q[i]", "default_ankle_positions_rad": DEFAULT.tolist(),
        "saturation_test": "abs(20*e - Kd*qdot) >= 50 Nm; source-model diagnostic at recorded target states, not measured target torque",
        "density_weights": "equal groups within each task, equal continuous clips within group, equal transitions within clip",
        "summary": summary, "clips": rows}, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
