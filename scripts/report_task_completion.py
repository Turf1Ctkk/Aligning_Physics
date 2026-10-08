"""Show task dependence without pooling tasks or claiming training replication."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from report_squat_tracking import aggregate

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("vanilla", "ft_only", "asap_ft", "sysid_ft", "torque_ft", "active_sysid_ft", "wave_ft")
NAMES = ("Original", "FT only", "ASAP", "Passive SysID", "Common torque", "Active SysID", "Excitation torque")


def main():
    inputs = {"squat": ROOT / "results/matched_squat/tracking_comparison.json",
              "wave": ROOT / "results/wave_acquisition/comparison_summary.json",
              **{task: ROOT / f"results/task_extensions/{task}/summary.json" for task in ("CR7", "StepFBL1")}}
    records = {key: json.loads(path.read_text()) for key, path in inputs.items()}
    squat = {m: aggregate(records["squat"]["results"], m) for m in METHODS[:-1]}
    squat["wave_ft"] = records["wave"]["results"]["excitation"]["tracking"]
    rows = {"SquatL1": squat, **{task: records[task]["summary"] for task in ("CR7", "StepFBL1")}}
    counts = []
    for task, row in rows.items():
        if set(row) != set(METHODS) or any(row[m]["total_trials"] != 96 for m in METHODS):
            raise ValueError("Require complete seven-controller96-trial reports per task")
        counts.append([row[m]["complete_trials"] for m in METHODS])
    output = ROOT / "results/task_extensions"
    evidence = {"scope": "Descriptive completion within each task; one task-training seed per adapted method; same frozen mixed-motion calibrators, all tasks seen in calibration",
                "limits": "Task horizons and source policies differ. Do not pool tasks or rank methods across tasks;96 evaluations are not96 trained policies.",
                "horizons_s": {"SquatL1": 5.22, "CR7": 3.92, "StepFBL1": 3.92},
                "methods": list(METHODS), "completion_counts": {task: count for task, count in zip(rows, counts)},
                "source_sha256": {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in inputs.items()}}
    (output / "completion_summary.json").write_text(json.dumps(evidence, indent=2) + "\n")
    values = np.asarray(counts)
    fig, ax = plt.subplots(figsize=(11.6, 3.7))
    ax.imshow(values / 96, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(METHODS)), NAMES, rotation=18, ha="right")
    ax.set_yticks(range(3), ["SquatL1 (5.22s)", "CR7 (3.92s)", "StepFBL1 (3.92s)"])
    for i in range(3):
        for j in range(len(METHODS)):
            ax.text(j, i, f"{100 * values[i,j] / 96:.1f}%", ha="center", va="center",
                    color="white" if values[i,j] > 55 else "#163552", fontsize=11)
    ax.set_title("Completion by task", pad=12)
    ax.spines[:].set_visible(False)
    fig.text(.5, .02, "Each task has its own horizon and starting policy. One training seed per method.\n"
             "All three motions occur in calibration.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .12, 1, 1))
    fig.savefig(output / "completion.png", dpi=180)
    print(json.dumps(evidence["completion_counts"]))


if __name__ == "__main__":
    main()
