"""Fresh seed-matched replay controls after the fixed-data training repeat.

The existing copied primary controls remain provenance, not repeat measurements.
This queue does not alter training, validation selection or any selected records.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time

from research.asap_diagnostics.controlled_pipeline import launch, write


def run(args):
    import research.asap_diagnostics.multi_motion_pipeline as replay
    root = args.work_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    write(root / "queue_plan.json", {"planned_utc": datetime.now(timezone.utc).isoformat(),
        "repeat": str(args.repeat), "cutoff_utc": args.cutoff, "minimum_margin_minutes": 15,
        "scope": "Two fresh repeat-seed test controls after all repeat training/evaluation; preserve copied primary diagnostics; no learning or selection changes"})
    write(root / "status.json", {"status": "waiting", "stage": "repeat_content_completion"})
    while True:
        state = json.loads((args.repeat / "status.json").read_text()) if (args.repeat / "status.json").exists() else {}
        if state.get("status") == "complete":
            break
        if state.get("status") == "failed":
            raise RuntimeError("Repeat failed; no baseline audit restart or inference from incomplete results")
        if state.get("status") == "skipped" or time.time() > deadline - 15 * 60:
            write(root / "status.json", {"status": "skipped", "stage": "repeat_skipped_or_insufficient_margin"})
            return
        time.sleep(30)
    if deadline - time.time() < 15 * 60:
        write(root / "status.json", {"status": "skipped", "stage": "insufficient_cutoff_margin"})
        return
    source = args.repeat / "uniform"
    plan = json.loads((args.repeat / "plan.json").read_text())
    if plan["training_seed"] != 20305009:
        raise ValueError("Unexpected repeat seed")
    selected = Path(json.loads((source / "delta_selection.json").read_text())["checkpoint"])
    test_source = source / "datasets/test_cases.pkl"
    (root / "datasets").mkdir(exist_ok=True)
    test_target = root / "datasets/test_cases.pkl"
    shutil.copy2(test_source, test_target)
    digest = hashlib.sha256(test_source.read_bytes()).hexdigest()
    if hashlib.sha256(test_target.read_bytes()).hexdigest() != digest:
        raise ValueError("Test records changed")
    write(root / "plan.json", {"replay_seed": plan["training_seed"] + 100,
        "test_records_sha256": digest, "selected_uniform_checkpoint": str(selected),
        "comparison": str(source / "comparison.json"), "minimum_margin_minutes": 15,
        "copied_primary_baselines": str(args.repeat / "shared_test_baselines.json")})
    replay.launch = lambda w, mode, seed, command, log: launch(w, mode, seed, command, log.stem, deadline)
    controls = {}
    for label, kp in (("same16_zero", 16), ("source20_zero", 20)):
        report = replay.evaluate_batch(root, plan, selected, "test", label, kp=kp, zero=True)
        if report["summary"]["1.0"]["complete_cases"] != 66:
            raise RuntimeError("Incomplete fresh repeat control; preserve records and stop")
        controls[label] = report["summary"]
    # Read actual recorded first samples, which follow reset_all's warm step.
    import joblib
    import numpy as np
    learned_path = source / "evaluation/test/learned.pkl"
    control_path = root / "evaluation/test/source20_zero.pkl"
    learned, control = joblib.load(learned_path), joblib.load(control_path)
    if set(learned) != set(control) or len(learned) != 66:
        raise ValueError("Repeat learned/control record identities differ")
    differences = {field: max(float(np.max(np.abs(np.asarray(learned[k][field][0]) - np.asarray(control[k][field][0])))) for k in learned)
                   for field in ("dof", "dof_vel", "root_trans_offset", "root_rot", "root_lin_vel", "root_ang_vel", "action", "motion_times")}
    write(root / "first_record_audit.json", {"scope": "Stored post-warm-step source-A samples; hidden solver state not independently verified",
        "max_absolute_learned_vs_source20_difference": differences,
        "recording_sha256": {"learned": hashlib.sha256(learned_path.read_bytes()).hexdigest(),
                             "source20_zero": hashlib.sha256(control_path.read_bytes()).hexdigest()}})
    if any(differences.values()):
        raise ValueError("Fresh repeat learned/control stored starts differ; inspect before interpreting gains")
    write(root / "fresh_test_baselines.json", {"scope": "Fresh physics controls at repeat replay seed20305109; copied primary diagnostics remain separate",
                                              "results": controls})
    write(root / "status.json", {"status": "complete", "stage": "fresh_repeat_seed_replay_controls"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--cutoff", default="2026-10-09T09:00:00+00:00")
    args = parser.parse_args()
    if args.work_dir.exists() and any(args.work_dir.iterdir()):
        parser.error("Existing controls retained; no automatic restart/resume")
    try:
        run(args)
    except Exception as error:
        write(args.work_dir / "status.json", {"status": "failed", "error": str(error)})
        raise
