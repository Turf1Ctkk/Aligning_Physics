"""Render measured equal-task test means, including the same-domain floor."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "results/controlled_squat/replay_comparison.json")
    parser.add_argument("--condition", default="controlled_delta")
    parser.add_argument("--learned-label", default="Learned delta")
    parser.add_argument("--output", type=Path, default=ROOT / "assets/figures/controlled_replay.png")
    args = parser.parse_args()
    evidence = json.loads(args.input.read_text())
    conditions = ("same16_zero", "source20_zero", args.condition)
    labels = ("Same domain\nKp16", "Uncalibrated\nKp20", args.learned_label + "\nKp20")
    colors = ("#808C9C", "#DC7F37", "#355C99")
    fields = (("global_body_mpjpe_mm", "Body position (mm)", "Position improves"),
              ("ankle_rmse_rad", "Ankle position RMSE (rad)", "Ankle position improves"),
              ("joint_velocity_rmse_rad_s", "Joint velocity RMSE (rad/s)", "Velocity worsens"))
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 3.9))
    for ax, (field, ylabel, title) in zip(axes, fields):
        values = [evidence[name]["1.0"]["equal_task_mean"][field] for name in conditions]
        bars = ax.bar(labels, values, color=colors, width=.65)
        ax.set(ylabel=ylabel, title=title, ylim=(0, max(values) * 1.21))
        ax.bar_label(bars, labels=[f"{v:.2f}" if field.endswith("mm") else f"{v:.3f}" for v in values], padding=3, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.18)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=9)
    fig.text(.5, .025, "66 held-out 1-second windows • equal task means • one calibration seed • no uncertainty intervals estimated",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .06, 1, 1))
    fig.savefig(args.output, dpi=180)


if __name__ == "__main__":
    main()
