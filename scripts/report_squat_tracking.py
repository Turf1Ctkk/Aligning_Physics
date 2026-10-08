"""Aggregate recorded trials without hiding failures or selecting a best seed."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def aggregate(results, label):
    reports = [r for key, r in results.items() if key.startswith(label + "_seed")]
    trials = [trial for report in reports for trial in report["trials"]]
    if len(reports) != 3 or len(trials) != 96:
        raise ValueError("Expected three fixed evaluation seeds and 96 trials")
    complete = [trial for trial in trials if trial["complete"]]
    prefixes = {}
    for horizon in (1., 3.):
        valid = [trial["prefix_metrics"][str(horizon)] for trial in trials
                 if trial["prefix_metrics"][str(horizon)]["complete"]]
        prefixes[str(horizon)] = {"complete_trials": len(valid), "total_trials": len(trials),
            "global_body_mpjpe_mm": float(np.mean([t["global_body_mpjpe_mm"] for t in valid])) if valid else None,
            "root_relative_body_mpjpe_mm": float(np.mean([t["root_relative_body_mpjpe_mm"] for t in valid])) if valid else None}
    return {"complete_trials": len(complete), "total_trials": len(trials), "completion_rate": len(complete)/len(trials),
        "mean_survival_s": float(np.mean([t["survival_s"] for t in trials])),
        "complete_trial_global_body_mpjpe_mm": float(np.mean([t["global_body_mpjpe_mm"] for t in complete])) if complete else None,
        "complete_trial_root_relative_body_mpjpe_mm": float(np.mean([t["root_relative_body_mpjpe_mm"] for t in complete])) if complete else None,
        "prefix_metrics": prefixes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--sysid", type=Path, required=True)
    args = parser.parse_args()
    primary, sysid = json.loads(args.main.read_text()), json.loads(args.sysid.read_text())
    results = dict(primary["results"], **sysid["results"])
    labels = ("ft_only", "asap_ft", "sysid_ft")
    summaries = {label: aggregate(results, label) for label in labels}
    output = ROOT / "results/controlled_squat"
    evidence = {"scope": "Standalone B evaluation; one training seed per method and three deployment seeds, 32 trials each",
        "setting_audit": {"vanilla": "Inherited nonzero actor observation noise; excluded from the matched comparison below",
            "fine_tuned_conditions": "Common zero task observation noise, initial noise .2, common original Squat termination settings",
            "reevaluation": "Full explicit common-noise reevaluation queued; original recordings retained"},
        "results": results}
    (output / "tracking_comparison_initial.json").write_text(json.dumps(evidence, indent=2))
    (output / "tracking_summary.json").write_text(json.dumps({"summary": summaries,
        "error_scope": "Full-horizon means condition on completion; first-second means cover all 96 trials",
        "inference_limit": "Evaluation seeds are not independent training replications"}, indent=2))
    fig, axes = plt.subplots(1, 4, figsize=(13.4, 3.7))
    names, colors = ("FT only", "ASAP FT", "Passive\nSysID FT"), ("#DC7F37", "#355C99", "#32836F")
    for panel, ax in enumerate(axes):
        if panel == 0:
            values = [100*summaries[l]["completion_rate"] for l in labels]
            ylabel, title = "Completed trials (%)", "Full 5.22-second horizon"
        elif panel == 1:
            values = [summaries[l]["mean_survival_s"] for l in labels]
            ylabel, title = "Mean survival (s)", "Failures remain in the mean"
        else:
            field = "global_body_mpjpe_mm" if panel == 2 else "root_relative_body_mpjpe_mm"
            values = [summaries[l]["prefix_metrics"]["1.0"][field] for l in labels]
            ylabel = "Body error (mm)" if panel == 2 else "Root-relative body error (mm)"
            title = "First second: all 96 trials"
        bars = ax.bar(names, values, color=colors, width=.65)
        ax.bar_label(bars, labels=[f"{v:.1f}" for v in values], padding=3, fontsize=8)
        ax.set(ylabel=ylabel, title=title, ylim=(0, max(values)*1.2))
        ax.tick_params(axis="x", labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.18)
        ax.set_axisbelow(True)
    fig.text(.5, .015, "One policy-training seed per condition • same pretrained Squat and 1000 additional updates • no training-variance estimate",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(ROOT / "assets/figures/squat_tracking_initial.png", dpi=180)
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
