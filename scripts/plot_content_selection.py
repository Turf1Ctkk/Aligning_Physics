"""Plot separately reported fixed-data training runs without pooling seeds."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

METHODS = ("uniform", "coverage", "joint_range")
NAMES = ("Uniform", "Actuator\ncoverage", "Joint range")
COLORS = ("#888888", "#355C99", "#C4882F")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--run", choices=("primary", "repeat"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.summary.read_text())
    run = report["runs"][args.run]
    results = run["results"]
    if set(results) != set(METHODS):
        raise ValueError("Require all three prespecified selectors")
    baselines = (run["shared_test_baselines"] if args.run == "primary"
                 else run.get("fresh_seed_matched_baselines"))
    zero = baselines["source20_zero"]["equal_task_mean"] if baselines else None
    panels = [
        ([results[m]["test_replay"]["equal_task_mean"]["global_body_mpjpe_mm"] for m in METHODS],
         "Held-out body replay", "Body MPJPE (mm)", zero["global_body_mpjpe_mm"] if zero else None),
        ([results[m]["test_replay"]["equal_task_mean"]["joint_velocity_rmse_rad_s"] for m in METHODS],
         "Held-out joint velocity", "RMSE (rad/s)", zero["joint_velocity_rmse_rad_s"] if zero else None),
        ([results[m]["tracking"]["complete_trials"] for m in METHODS],
         "Standalone B:5.22s", "Completed trials /96", None),
        ([results[m]["tracking"]["mean_survival_s"] for m in METHODS],
         "All96 deployment trials", "Mean survival (s)", None),
        ([results[m]["tracking"]["prefix_metrics"]["1.0"]["global_body_mpjpe_mm"] for m in METHODS],
         "First-second global tracking", "Body MPJPE (mm)", None),
        ([results[m]["tracking"]["prefix_metrics"]["1.0"]["root_relative_body_mpjpe_mm"] for m in METHODS],
         "First-second relative tracking", "Root-relative MPJPE (mm)", None),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12.2, 7.2))
    replay_counts = [results[m]["test_replay"]["complete_cases"] for m in METHODS]
    prefix_counts = [results[m]["tracking"]["prefix_metrics"]["1.0"]["complete_trials"] for m in METHODS]
    for i, (ax, (values, title, ylabel, reference)) in enumerate(zip(axes.flat, panels)):
        if any(v is None for v in values):
            raise ValueError("A prefix with no valid trials requires an unavailable-data plot")
        bars = ax.bar(NAMES, values, color=COLORS, width=.65)
        labels = [str(int(v)) if i == 2 else f"{v:.3f}" if i in (1, 3) else f"{v:.2f}" for v in values]
        ax.bar_label(bars, labels=labels, padding=3, fontsize=9)
        if reference is not None:
            ax.axhline(reference, color="#555555", linestyle="--", linewidth=1.2,
                       label="Seed-matched zero correction")
            ax.legend(fontsize=7, loc="upper left")
        top = max(values + ([reference] if reference is not None else [])) * 1.24
        if i == 2:
            top = 96
        elif i == 3:
            top = 5.22 * 1.18
        ax.set(title=title, ylabel=ylabel, ylim=(0, top))
        ax.tick_params(axis="x", labelsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.18)
        ax.set_axisbelow(True)
    fig.suptitle(f"Fixed-budget content selection: {args.run} training seed", fontsize=13)
    fig.text(.5, .015,
             f"Same18 parents /954 selected transitions • replay complete counts:{replay_counts}/66 • first1s valid counts:{prefix_counts}/96\n"
             "One calibration/policy training seed in this figure; deployment trials are not training replications. No floor subtraction or composite ranking.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .065, 1, .96))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=170)
    args.output.with_suffix(".json").write_text(json.dumps({
        "scope": "Separate metrics from one fixed-data training run; no pooled-seed population ranking",
        "summary": str(args.summary), "run": args.run,
        "calibration_seed": run["calibration_seed"], "policy_seed": run["policy_seed"],
        "replay_complete_counts": replay_counts, "first_second_valid_counts": prefix_counts,
        "zero_reference": "Seed-matched controls" if zero else "No seed-matched control available; no zero line displayed",
    }, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
