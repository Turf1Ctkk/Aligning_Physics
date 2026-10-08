"""Plot the completed matched acquisition arms; no policy benefit is inferred."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "results/wave_acquisition"


def main():
    unchanged = json.loads((DIRECTORY / "unchanged_replay_comparison.json").read_text())
    excitation = json.loads((DIRECTORY / "excitation_replay_comparison.json").read_text())
    for condition in ("same16_zero", "source20_zero"):
        if unchanged[condition] != excitation[condition]:
            raise ValueError("Acquisition arms do not share actual test baselines")
    rows = [unchanged["source20_zero"]["1.0"], unchanged["torque"]["1.0"], excitation["torque"]["1.0"]]
    if any(row["complete_cases"] != 66 for row in rows):
        raise ValueError("All 66 cases required for this completed-window plot")
    names = ("Zero\ncorrection", "200 Hz\nunchanged", "200 Hz\nexcitation")
    fields = ("global_body_mpjpe_mm", "ankle_rmse_rad", "joint_velocity_rmse_rad_s")
    units = ("Body MPJPE (mm)", "Ankle RMSE (rad)", "Joint-velocity RMSE (rad/s)")
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.9))
    for ax, field, unit in zip(axes, fields, units):
        values = [row["equal_task_mean"][field] for row in rows]
        bars = ax.bar(names, values, color=("#808C9C", "#355C99", "#32836F"), width=.65)
        digits = 2 if field.endswith("mm") else 3
        ax.bar_label(bars, labels=[f"{value:.{digits}f}" for value in values], padding=3, fontsize=9)
        ax.set(ylabel=unit, ylim=(0, max(values) * 1.2))
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(.5, .015, "Matched 30-parent / 6210-transition acquisition arms • validation selects 1000/500 updates\nAll 66 correlated test windows complete • equal task/group means • one training seed per arm",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .08, 1, 1))
    fig.savefig(ROOT / "assets/figures/true_rate_replay.png", dpi=180)


if __name__ == "__main__":
    main()
