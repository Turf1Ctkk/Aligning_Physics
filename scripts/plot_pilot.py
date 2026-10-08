"""Regenerate the descriptive pilot figure from its measured JSON summaries."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, default=root / "results/pilot_multimotion/comparison.json")
    parser.add_argument("--output", type=Path, default=root / "assets/figures/pilot_data_scale.png")
    args = parser.parse_args()
    results = json.loads(args.comparison.read_text())["test"]
    metric = "global_body_mpjpe_mm"
    labels = ("same16_zero", "source20_zero", "balanced1", "balanced10", "balanced_full")
    names = ("Same-domain B", "A: zero delta", "3 groups", "30 groups", "90 groups")
    colors = ("#9ca3af", "#334155", "#84b1b5", "#177e89", "#d48640")
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), gridspec_kw={"width_ratios": [1, 1.25]})
    values = [results[key]["1.0"]["equal_task_mean"][metric] for key in labels[2:]]
    axes[0].plot([3, 30, 90], values, "o-", color=colors[3], lw=2)
    for x, y in zip([3,30,90], values): axes[0].annotate(f"{y:.2f}", (x,y), xytext=(0,8), textcoords="offset points", ha="center")
    for key, name, color, style in zip(labels[:2], names[:2], colors[:2], (":", "--")):
        axes[0].axhline(results[key]["1.0"]["equal_task_mean"][metric], color=color, ls=style, label=name)
    axes[0].set(xscale="log", xticks=[3,30,90], xticklabels=["3","30","90"], xlabel="Original training recording groups", ylabel="Global body MPJPE (mm)", ylim=(0,43))
    axes[0].legend(frameon=False, fontsize=9)
    tasks = ("CR7", "SquatL1", "StepFBL1")
    x = np.arange(3)
    for j, (key, name, color) in enumerate(zip(labels, names, colors)):
        values = [results[key]["1.0"]["per_task"][task][metric] for task in tasks]
        axes[1].bar(x + (j-2)*.15, values, width=.14, label=name, color=color)
    axes[1].set(xticks=x, xticklabels=["CR7", "Squat", "Step"], ylabel="Global body MPJPE (mm)", ylim=(0,58))
    axes[1].legend(frameon=False, fontsize=8, ncol=3)
    for ax in axes: ax.grid(axis="y", alpha=.2); ax.set_axisbelow(True)
    fig.suptitle("Exploratory replay pilot | 1 s | 24 actual rigid bodies", fontsize=14)
    fig.text(.5,.015,"One training seed; correlated held-out windows. Task sampling changes with clip segmentation; no closed-loop result.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.94))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    print(args.output)


if __name__ == "__main__": main()
