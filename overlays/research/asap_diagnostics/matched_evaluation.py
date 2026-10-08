"""Serial fair standalone evaluation and post-hoc structured-SysID diagnostics."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research.asap_diagnostics.controlled_pipeline import launch, write, tracking_overrides
from research.asap_diagnostics.controlled_sampling import hierarchical_weights
from research.asap_diagnostics.sysid_pipeline import make_cases, evaluate_candidates


def run(args):
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    write(work / "status.json", {"status": "waiting", "stage": "preceding_torque_queue"})
    while True:
        state = json.loads(args.wait_for.read_text()) if args.wait_for.exists() else {}
        if state.get("status") == "complete":
            break
        if state.get("status") == "failed":
            raise RuntimeError("Preceding queue failed; inspect before evaluation")
        if time.time() > deadline - 60:
            raise TimeoutError("Cutoff while waiting")
        time.sleep(30)
    plan = json.loads((args.controlled / "plan.json").read_text())
    models = {"vanilla": plan["tasks"]["SquatL1"]["checkpoint"],
              "ft_only": args.controlled / "models/ft_only/model_1000.pt",
              "asap_ft": args.controlled / "models/asap_ft/model_1000.pt",
              "sysid_ft": args.sysid / "models/sysid_ft/model_1000.pt",
              "torque_ft": args.torque / "models/torque_ft/model_1000.pt"}
    write(work / "protocol.json", {"reason": "Original vanilla evaluation inherited observation noise absent from fine-tuned checkpoints",
        "observation_condition": "Zero task actor/history observation noise, common initial-state noise .2, same B dynamics and termination",
        "policy_selection": "Fixed final 1000-update checkpoint; no retraining or evaluation-based selection",
        "seeds": [8101, 8102, 8103], "environments_per_seed": 32})
    tracking = {}
    for label, checkpoint in models.items():
        if not Path(checkpoint).exists():
            raise FileNotFoundError(str(checkpoint))
        for seed in (8101, 8102, 8103):
            name = label + "_seed%d" % seed
            launch(work, "eval", seed, tracking_overrides(work, checkpoint, name, "SquatL1", plan, .2, seed), name, deadline)
            tracking[name] = json.loads((work / "tracking" / (name + ".json")).read_text())
    write(work / "tracking_comparison.json", {"results": tracking, "training_seeds": 1,
        "observation_condition": "Common zero task actor/history observation noise"})
    # Known target parameters enter only a post-hoc diagnostic, never fitting or
    # exploration selection. Do not label this arm as a learned method.
    selected = json.loads((args.controlled / "delta_selection.json").read_text())["checkpoint"]
    fitted = json.loads((args.sysid / "identified.json").read_text())
    candidates = [[20., 20.], [16., 16.], [fitted["ankle_pitch_Kp"], fitted["ankle_roll_Kp"]]]
    cases = make_cases(joblib.load(args.controlled / "datasets/mixed30.pkl"))
    scores = evaluate_candidates(work, cases, hierarchical_weights(cases), candidates, selected,
                                  "sysid_posthoc_known_gain_check", deadline)
    write(work / "sysid_posthoc_diagnostic.json", {"scope": "Known-gain positive control, not training data or parameter selection",
        "labels": ["source20", "known_target16", "passive_fitted"], "scores": scores})
    write(work / "status.json", {"status": "complete", "stage": "matched_evaluation_and_posthoc_check"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("controlled", "sysid", "torque", "work-dir", "wait-for"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--cutoff", default="2026-10-09T09:00:00+00:00")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        write(args.work_dir / "status.json", {"status": "failed", "error": str(error)})
        raise
