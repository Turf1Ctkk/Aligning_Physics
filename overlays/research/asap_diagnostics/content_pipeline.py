"""Optional serialized equal-budget data-content test on one fixed parent set."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
import time

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research.asap_diagnostics.controlled_pipeline import launch, write, delta_overrides, fine_overrides, tracking_overrides
from research.asap_diagnostics.controlled_sampling import hierarchical_weights
from research.asap_diagnostics.select_content import select


def run(args):
    import research.asap_diagnostics.multi_motion_pipeline as replay
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    if (work / "selection_manifest.json").exists():
        raise RuntimeError("Content experiment already exists; inspect rather than silently restarting")
    write(work / "status.json", {"status": "waiting", "stage": "preceding_task_extensions"})
    while True:
        state = json.loads(args.wait_for.read_text()) if args.wait_for.exists() else {}
        if state.get("status") == "complete":
            break
        if state.get("status") == "failed":
            raise RuntimeError("Preceding extension failed; inspect before hypothesis test")
        if time.time() > deadline-60:
            raise TimeoutError("Cutoff while waiting")
        time.sleep(30)
    if deadline-time.time()<5*3600:
        write(work / "status.json", {"status": "skipped", "stage": "insufficient_cutoff_margin", "minimum_margin_hours": 5})
        return
    selections, manifest = select(joblib.load(args.pool))
    write(work / "selection_manifest.json", manifest)
    plan = json.loads((args.controlled / "plan.json").read_text())
    plan["training_seed"] += 4000
    plan["protocol"] = "Fixed18 parent groups,954 unique transitions, uniform/coverage/joint-range windows"
    write(work / "plan.json", plan)
    original_delta = json.loads((args.controlled / "delta_selection.json").read_text())["checkpoint"]
    replay.launch = lambda w, mode, seed, command, log: launch(w, mode, seed, command, log.stem, deadline)
    all_results = {}
    for method, data in selections.items():
        directory = work / method
        (directory / "datasets").mkdir(parents=True, exist_ok=True)
        write(work / "status.json", {"status": "running", "stage": method + "_calibration_and_policy"})
        joblib.dump(data, directory / "datasets/mixed30.pkl")
        joblib.dump(data, directory / "datasets/train_check_cases.pkl")
        for split in ("val", "test"):
            shutil.copy2(args.controlled / "datasets" / (split+"_cases.pkl"), directory / "datasets" / (split+"_cases.pkl"))
        write(directory / "sampling_manifest.json", {"weights": hierarchical_weights(data),
              "metadata": {key: {"task": m["dataset_task"], "group": m["dataset_group"]} for key,m in data.items()}})
        # Report the replay floor of each selected subset; do not use it to
        # replace selected windows after seeing their physics error.
        floor = replay.evaluate_batch(directory, plan, original_delta, "train_check", "same16_zero", kp=16, zero=True)["summary"]
        write(directory / "selected_subset_replay_floor.json", floor)
        launch(directory, "train", plan["training_seed"], delta_overrides(directory, plan, args.iterations), "train_delta", deadline)
        candidates = []
        for iteration in (args.iterations//2, args.iterations):
            checkpoint = directory / "models/delta" / ("model_%d.pt"%iteration)
            summary = replay.evaluate_batch(directory, plan, checkpoint, "val", "delta_%d"%iteration)["summary"]["1.0"]
            if summary["complete_cases"] != summary["total_cases"]:
                raise RuntimeError("Incomplete content-test validation")
            candidates.append((summary["equal_task_mean"]["global_body_mpjpe_mm"], checkpoint))
        score, selected = min(candidates, key=lambda item:item[0])
        write(directory / "delta_selection.json", {"checkpoint": str(selected), "validation_body_mpjpe_mm": score})
        test = replay.evaluate_batch(directory, plan, selected, "test", "learned")["summary"]
        if method == "uniform":
            baselines = {label: replay.evaluate_batch(directory, plan, selected, "test", label, kp=kp, zero=True)["summary"]
                         for label,kp in (("same16_zero",16),("source20_zero",20))}
            write(work / "shared_test_baselines.json", baselines)
        launch(directory, "train", plan["training_seed"]+1000,
               fine_overrides(directory, plan, selected, "asap_ft", "SquatL1", args.iterations), "train_asap_ft", deadline)
        final = directory / "models/asap_ft" / ("model_%d.pt"%args.iterations)
        tracking = {}
        for seed in (8101,8102,8103):
            label = "asap_ft_seed%d"%seed
            launch(directory,"eval",seed,tracking_overrides(directory,final,label,"SquatL1",plan,.2,seed),label,deadline)
            tracking[label]=json.loads((directory/"tracking"/(label+".json")).read_text())
        all_results[method]={"test_replay":test,"tracking":{"results":tracking,"training_seeds":1}}
        write(directory/"comparison.json",all_results[method])
        write(directory/"status.json",{"status":"complete","stage":"content_condition"})
    write(work/"comparison.json",all_results)
    write(work/"status.json",{"status":"complete","stage":"equal_budget_content_hypothesis_test"})


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    for key in ("controlled","pool","work-dir","wait-for"):
        parser.add_argument("--"+key,type=Path,required=True)
    parser.add_argument("--iterations",type=int,default=1000)
    parser.add_argument("--cutoff",default="2026-10-09T09:00:00+00:00")
    args=parser.parse_args()
    try:
        run(args)
    except Exception as error:
        write(args.work_dir/"status.json",{"status":"failed","error":str(error)})
        raise
