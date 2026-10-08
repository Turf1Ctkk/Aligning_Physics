"""Report complete task comparisons with failure-inclusive and conditional metrics."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from report_squat_tracking import aggregate

ROOT = Path(__file__).resolve().parents[1]
METHODS = {
    "vanilla": "Original",
    "ft_only": "FT only",
    "asap_ft": "ASAP FT",
    "sysid_ft": "Passive SysID",
    "torque_ft": "Common-data torque",
    "active_sysid_ft": "Active SysID",
    "wave_ft": "Excitation torque",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=("CR7", "StepFBL1", "SquatL1"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--horizon", type=float, required=True,
                        help="Recorded evaluation steps / 50, verified from evaluation command")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.horizon < 3:
        parser.error("This report expects the recorded 1s/3s prefix metrics")
    raw = json.loads(args.input.read_text())
    summaries = {}
    for method in METHODS:
        expected = {f"{method}_seed{seed}" for seed in (8101, 8102, 8103)}
        actual = {key for key in raw["results"] if key.startswith(method + "_seed")}
        if actual != expected:
            raise ValueError(f"Incomplete or unexpected evaluation seeds for {method}: {actual}")
        for key in expected:
            trials = raw["results"][key]["trials"]
            if len(trials) != 32 or {t["trial"] for t in trials} != set(range(32)):
                raise ValueError(f"Expected all 32 unique trials: {key}")
            if any(t["survival_s"] > args.horizon + .001 for t in trials):
                raise ValueError(f"Recorded survival exceeds declared horizon: {key}")
            if any(abs(t["survival_s"] - args.horizon) > .001 for t in trials if t["complete"]):
                raise ValueError(f"Complete trials do not match declared horizon: {key}")
        summaries[method] = aggregate(raw["results"], method)
    output = args.output or ROOT / "results/task_extensions" / args.task
    output.mkdir(parents=True, exist_ok=True)
    report = {"task": args.task, "evaluation_horizon_s": args.horizon,
              "source_report_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
              "scope": "One training seed per adapted method; three evaluation seeds,32 trials each; no test checkpoint selection",
              "calibration_scope": "Shared mixed-motion calibrators include this task; not a calibration-motion holdout",
              "error_scope": "Prefix means condition on prefix completion; full-horizon means on full completion",
              "summary": summaries}
    (output / "summary.json").write_text(json.dumps(report, indent=2))
    rows = ["Historical 24-body metrics. Error cells show global / root-relative error and the percentage of trials included.\n",
            "| Policy | Completion (%) | Survival (s) | First second (mm; included %) | First three seconds (mm; included %) | Full motion (mm; included %) |",
            "|---|---:|---:|---|---|---|"]
    def error_pair(body, relative, count):
        return "Unavailable (0.0%)" if not count else f"{body:.2f} / {relative:.2f} ({100 * count / 96:.1f}%)"
    for key, name in METHODS.items():
        row = summaries[key]
        prefixes = [row["prefix_metrics"][str(h)] for h in (1., 3.)]
        cells = [error_pair(p["global_body_mpjpe_mm"], p["root_relative_body_mpjpe_mm"], p["complete_trials"]) for p in prefixes]
        full = error_pair(row["complete_trial_global_body_mpjpe_mm"], row["complete_trial_root_relative_body_mpjpe_mm"], row["complete_trials"])
        rows.append(f"| {name} | {100 * row['completion_rate']:.1f} | {row['mean_survival_s']:.3f} | {cells[0]} | {cells[1]} | {full} |")
    (output / "metrics.md").write_text("\n".join(rows) + "\n")
    names = [name.replace(" ", "\n", 1) for name in METHODS.values()]
    fig, axes = plt.subplots(1, 4, figsize=(16.8, 4.6))
    colors = ("#8796A8", "#DC7F37", "#355C99", "#32836F", "#8958A2", "#A77D30", "#AA5668")
    for panel, ax in enumerate(axes):
        if panel == 0:
            values = [100 * s["completion_rate"] for s in summaries.values()]
            title, ylabel = "Full-reference completion", "Completed trials (%)"
        elif panel == 1:
            values = [s["mean_survival_s"] for s in summaries.values()]
            title, ylabel = "Failure-inclusive survival", "Mean survival (s)"
        else:
            field = "global_body_mpjpe_mm" if panel == 2 else "root_relative_body_mpjpe_mm"
            values = [s["prefix_metrics"]["1.0"][field] for s in summaries.values()]
            title = "First second, valid prefixes"
            ylabel = "Body error (mm)" if panel == 2 else "Root-relative error (mm)"
        bars = ax.bar(names, [v if v is not None else 0 for v in values], color=colors)
        for bar, value in zip(bars, values):
            if value is None:
                bar.set_visible(False)
            ax.annotate("N/A" if value is None else f"{value:.1f}",
                        (bar.get_x() + bar.get_width()/2, value or 0),
                        xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)
        maximum = max(v for v in values if v is not None) if any(v is not None for v in values) else 1
        ax.set(title=title, ylabel=ylabel, ylim=(0, 110 if panel == 0 else maximum * 1.22))
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=7, rotation=25)
    valid = ", ".join(f"{100 * s['prefix_metrics']['1.0']['complete_trials'] / 96:.1f}%" for s in summaries.values())
    fig.text(.5, .015, f"{args.task}: {args.horizon:.2f}s reference • First-second inclusion: {valid}\n"
             "Historical 24-body errors. One training seed; three deployment seeds.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .09, 1, 1))
    fig.savefig(output / "tracking.png", dpi=180)
    print(json.dumps({key: value["complete_trials"] for key, value in summaries.items()}))


if __name__ == "__main__":
    main()
