"""Report the five final checkpoints under explicit common evaluation settings."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from report_squat_tracking import aggregate

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True)
    args=parser.parse_args()
    raw=json.loads(args.input.read_text())
    labels=("vanilla","ft_only","asap_ft","sysid_ft","torque_ft")
    names=("Original","FT only","ASAP FT","Passive\nSysID FT","Torque FT")
    summary={label:aggregate(raw["results"],label) for label in labels}
    directory=ROOT/"results/matched_squat"
    directory.mkdir(parents=True,exist_ok=True)
    (directory/"tracking_comparison.json").write_text(json.dumps(raw,indent=2))
    (directory/"summary.json").write_text(json.dumps({"summary":summary,
        "scope":"Explicit zero task-observation noise; shared termination and initialization settings; one training seed per method",
        "error_scope":"First-second completion counts accompany prefix errors; full-horizon errors condition on completion"},indent=2))
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    colors=("#808C9C","#DC7F37","#355C99","#32836F","#8D56A0")
    for i,ax in enumerate(axes):
        if i==0:
            values=[100*summary[k]["completion_rate"] for k in labels]
            title,ylabel="Full 5.22-second completion","Completed trials (%)"
        else:
            field="global_body_mpjpe_mm" if i==1 else "root_relative_body_mpjpe_mm"
            values=[summary[k]["prefix_metrics"]["1.0"][field] for k in labels]
            title="First-second tracking"
            ylabel="Body error (mm)" if i==1 else "Root-relative body error (mm)"
        bars=ax.bar(names,values,color=colors,width=.7)
        ax.bar_label(bars,labels=[f"{v:.1f}" for v in values],padding=3,fontsize=8)
        ax.set(title=title,ylabel=ylabel,ylim=(0,max(values)*1.2))
        ax.tick_params(axis="x",labelsize=8)
        ax.spines[["top","right"]].set_visible(False)
        ax.grid(axis="y",alpha=.18)
        ax.set_axisbelow(True)
    counts=[summary[k]["prefix_metrics"]["1.0"]["complete_trials"] for k in labels]
    fig.text(.5,.015,"Three evaluation seeds × 32 trials • first-second valid counts: "+"/".join(map(str,counts))+" of 96 each\nOne trained policy per condition; evaluation seeds do not estimate training variance",ha="center",fontsize=8)
    fig.tight_layout(rect=(0,.075,1,1))
    fig.savefig(ROOT/"assets/figures/matched_squat_tracking.png",dpi=180)
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
