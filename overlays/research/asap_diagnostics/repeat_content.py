"""Conditional second paired training seed on the primary experiment's exact data."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research.asap_diagnostics.controlled_pipeline import (
    launch, write, delta_overrides, fine_overrides, tracking_overrides,
)

METHODS = ("uniform", "coverage", "joint_range")


def verify_manifest(manifest):
    if set(manifest["selectors"]) != set(METHODS):
        raise ValueError("All three fixed selectors are required")
    parent_sets = []
    for rows in manifest["selectors"].values():
        parents = {row["group"] for row in rows}
        if len(rows) != 18 or len(parents) != 18:
            raise ValueError("Exactly one window per each of18 parents required")
        if Counter(row["task"] for row in rows) != {"CR7": 6, "SquatL1": 6, "StepFBL1": 6}:
            raise ValueError("Task proportions changed")
        if any(row["stop"] - row["start"] != 54 for row in rows):
            raise ValueError("Window length changed")
        parent_sets.append(parents)
    if any(parents != parent_sets[0] for parents in parent_sets):
        raise ValueError("Parent identities differ across selectors")


def copy_verified(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError("Copied data changed: " + str(source))
    return digest


def run(args):
    import research.asap_diagnostics.multi_motion_pipeline as replay
    work = args.work_dir.resolve()
    if (work / "status.json").exists():
        raise RuntimeError("Repeat already has artifacts; no automatic restart or resume")
    work.mkdir(parents=True, exist_ok=True)
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    write(work / "queue_plan.json", {"planned_utc": datetime.now(timezone.utc).isoformat(),
        "primary": str(args.primary), "seed_offset": 1, "methods": list(METHODS),
        "iterations_per_stage": 1000, "minimum_margin_hours": 4, "cutoff_utc": args.cutoff,
        "scope": "One additional paired training seed after primary completion; exact data reuse; no acquisition or selector changes"})
    write(work / "status.json", {"status": "waiting", "stage": "primary_content_experiment"})
    while True:
        state = json.loads((args.primary / "status.json").read_text()) if (args.primary / "status.json").exists() else {}
        if state.get("status") == "complete":
            break
        if state.get("status") == "skipped" or time.time() > deadline - 60:
            write(work / "status.json", {"status": "skipped", "stage": "primary_skipped_or_cutoff"})
            return
        if state.get("status") == "failed":
            raise RuntimeError("Primary content experiment failed; inspect rather than retry")
        time.sleep(30)
    if deadline - time.time() < 4 * 3600:
        write(work / "status.json", {"status": "skipped", "stage": "insufficient_cutoff_margin", "minimum_margin_hours": 4})
        return
    manifest = json.loads((args.primary / "selection_manifest.json").read_text())
    verify_manifest(manifest)
    primary_plan = json.loads((args.primary / "plan.json").read_text())
    plan = dict(primary_plan)
    plan["training_seed"] += 1
    plan["protocol"] = "Second paired training seed; byte-identical primary selected data; no selector changes"
    write(work / "plan.json", plan)
    write(work / "protocol.json", {"primary": str(args.primary), "seed_offset": 1,
        "primary_training_seed": primary_plan["training_seed"], "repeat_calibration_seed": plan["training_seed"],
        "repeat_policy_seed": plan["training_seed"] + 1000, "iterations_per_stage": 1000,
        "minimum_margin_hours": 4, "evaluation_seeds": [8101, 8102, 8103],
        "scope": "Repeat planned before primary content results; exact same three selected datasets; not a new acquisition replicate",
        "selection": "Validation selects500/1000 calibration; fixed final1000 task policy; never test-ranked seeds"})
    hashes = {"selection_manifest.json": copy_verified(args.primary / "selection_manifest.json", work / "selection_manifest.json"),
              "shared_test_baselines.json": copy_verified(args.primary / "shared_test_baselines.json", work / "shared_test_baselines.json")}
    replay.launch = lambda w, mode, seed, command, log: launch(w, mode, seed, command, log.stem, deadline)
    results = {}
    for method in METHODS:
        directory, source = work / method, args.primary / method
        write(work / "status.json", {"status": "running", "stage": method + "_independent_training_repeat"})
        hashes[method] = {}
        for filename in ("mixed30.pkl", "val_cases.pkl", "test_cases.pkl"):
            hashes[method][filename] = copy_verified(source / "datasets" / filename, directory / "datasets" / filename)
        hashes[method]["sampling_manifest.json"] = copy_verified(source / "sampling_manifest.json", directory / "sampling_manifest.json")
        motions = joblib.load(directory / "datasets/mixed30.pkl")
        if len(motions) != 18 or any(len(motion["dof"]) != 54 for motion in motions.values()):
            raise ValueError("Actual selected data violate18-window /954-transition contract")
        actual_parents = {motion["dataset_group"] for motion in motions.values()}
        if actual_parents != {row["group"] for row in manifest["selectors"][method]}:
            raise ValueError("Actual selected parent identities changed")
        hashes[method]["selected_subset_replay_floor.json"] = copy_verified(
            source / "selected_subset_replay_floor.json", directory / "selected_subset_replay_floor.json")
        write(directory / "floor_provenance.json", {"scope": "Copied primary same-domain floor for identical data; no repeat physics measurement", "source": str(source)})
        write(work / "input_hashes.json", hashes)
        launch(directory, "train", plan["training_seed"], delta_overrides(directory, plan, 1000), "train_delta", deadline)
        candidates = []
        for iteration in (500, 1000):
            checkpoint = directory / "models/delta" / ("model_%d.pt" % iteration)
            validation = replay.evaluate_batch(directory, plan, checkpoint, "val", "delta_%d" % iteration)["summary"]["1.0"]
            if validation["complete_cases"] != validation["total_cases"]:
                raise RuntimeError("Incomplete repeat validation; preserve artifacts")
            candidates.append((validation["equal_task_mean"]["global_body_mpjpe_mm"], checkpoint))
        score, selected = min(candidates, key=lambda item: item[0])
        write(directory / "delta_selection.json", {"checkpoint": str(selected), "validation_body_mpjpe_mm": score})
        test = replay.evaluate_batch(directory, plan, selected, "test", "learned")["summary"]
        launch(directory, "train", plan["training_seed"] + 1000,
               fine_overrides(directory, plan, selected, "asap_ft", "SquatL1", 1000), "train_asap_ft", deadline)
        final = directory / "models/asap_ft/model_1000.pt"
        tracking = {}
        for seed in (8101, 8102, 8103):
            label = "asap_ft_seed%d" % seed
            launch(directory, "eval", seed, tracking_overrides(directory, final, label, "SquatL1", plan, .2, seed), label, deadline)
            tracking[label] = json.loads((directory / "tracking" / (label + ".json")).read_text())
        results[method] = {"test_replay": test, "tracking": {"results": tracking, "training_seeds": 1}}
        write(directory / "comparison.json", results[method])
        write(directory / "status.json", {"status": "complete", "stage": "content_condition_repeat"})
    write(work / "comparison.json", results)
    write(work / "status.json", {"status": "complete", "stage": "second_paired_training_seed"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--verify-manifest", type=Path, help="CPU manifest checks only; does not run training")
    parser.add_argument("--cutoff", default="2026-10-09T09:00:00+00:00")
    args = parser.parse_args()
    if args.verify_manifest:
        verify_manifest(json.loads(args.verify_manifest.read_text()))
        print("PASS: fixed18 parents,6/task,54 states,954 transitions,all three selectors; CPU only")
    else:
        if not args.primary or not args.work_dir:
            parser.error("--primary and --work-dir required for the queue")
        if args.work_dir.exists() and any(args.work_dir.iterdir()):
            parser.error("Existing repeat artifacts retained; use a new root after explicitly inspecting the previous run")
        try:
            run(args)
        except Exception as error:
            write(args.work_dir / "status.json", {"status": "failed", "error": str(error)})
            raise
