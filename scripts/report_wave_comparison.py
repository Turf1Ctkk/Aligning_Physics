"""Report completed true-rate arms, keeping missing outcomes explicitly absent."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from report_squat_tracking import aggregate

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--unchanged", type=Path, required=True)
    parser.add_argument("--excitation", type=Path)
    parser.add_argument("--baseline", type=Path, default=ROOT / "results/matched_squat/tracking_comparison.json")
    args = parser.parse_args()
    paths = {"unchanged": args.unchanged}
    if args.excitation:
        paths["excitation"] = args.excitation
    report = {}
    for label, directory in paths.items():
        replay = json.loads((directory / "replay_comparison.json").read_text())
        tracking = json.loads((directory / "tracking_comparison.json").read_text())
        report[label] = {"test_replay": replay["torque"]["1.0"],
                         "tracking": aggregate(tracking["results"], "torque_ft"),
                         "selection": json.loads((directory / "torque_selection.json").read_text())}
    baseline = aggregate(json.loads(args.baseline.read_text())["results"], "ft_only")
    output = ROOT / "results/wave_acquisition"
    (output / "comparison_summary.json").write_text(json.dumps({"scope": "Actual 200 Hz target training; matched acquisition arms; one training seed per arm",
        "pending_arms": [] if args.excitation else ["excitation"], "ft_only_baseline": baseline,
        "error_scope": "Prefix errors condition on prefix completion; full-horizon errors condition on full completion; counts remain explicit",
        "results": report}, indent=2))
    labels = ["FT only", "200 Hz\nunchanged"] + (["200 Hz\nexcitation"] if args.excitation else [])
    summaries = [baseline] + [report[key]["tracking"] for key in paths]
    colors = ["#DC7F37", "#355C99", "#32836F"][:len(labels)]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.9))
    for i, ax in enumerate(axes):
        if i == 0:
            values = [100 * row["completion_rate"] for row in summaries]
            title, ylabel = "Full-reference completion", "Completed trials (%)"
        elif i == 1:
            values = [row["mean_survival_s"] for row in summaries]
            title, ylabel = "Failure-inclusive survival", "Mean survival (s)"
        else:
            key = "global_body_mpjpe_mm" if i == 2 else "root_relative_body_mpjpe_mm"
            values = [row["prefix_metrics"]["3.0"][key] for row in summaries]
            title = "First three seconds"
            ylabel = "Body error (mm)" if i == 2 else "Root-relative body error (mm)"
        bars = ax.bar(labels, values, color=colors, width=.65)
        ax.bar_label(bars, labels=[f"{v:.2f}" for v in values], padding=3, fontsize=8)
        ax.set(title=title, ylabel=ylabel, ylim=(0, max(values) * 1.2))
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=8)
    counts = [row["prefix_metrics"]["3.0"]["complete_trials"] for row in summaries]
    note = "Excitation-arm outcomes pending; missing results are not plotted" if not args.excitation else "Matched unchanged/excitation acquisition and optimization budgets"
    fig.text(.5, .015, "Three-second valid trials: " + "/".join(map(str, counts)) + " of 96 each • one training seed per arm\n" + note,
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .08, 1, 1))
    fig.savefig(ROOT / "assets/figures/true_rate_tracking.png", dpi=180)
    print(json.dumps({key: value["tracking"] for key, value in report.items()}, indent=2))


if __name__ == "__main__":
    main()
