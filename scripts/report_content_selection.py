"""Report complete fixed-data selector runs without pooling training seeds."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from report_squat_tracking import aggregate

METHODS = ("uniform", "coverage", "joint_range")
SEEDS = (8101, 8102, 8103)
REPLAY_FIELDS = ("global_body_mpjpe_mm", "root_relative_body_mpjpe_mm",
                 "ankle_rmse_rad", "joint_velocity_rmse_rad_s")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(manifest):
    if set(manifest["selectors"]) != set(METHODS):
        raise ValueError("Require all three prespecified selectors")
    parent_sets = []
    for rows in manifest["selectors"].values():
        parents = {row["group"] for row in rows}
        if len(rows) != 18 or len(parents) != 18:
            raise ValueError("Require one window per each of18 parents")
        if Counter(row["task"] for row in rows) != {"CR7": 6, "SquatL1": 6, "StepFBL1": 6}:
            raise ValueError("Task proportions changed")
        if any(row["stop"] - row["start"] != 54 for row in rows):
            raise ValueError("Require54 states /53 transitions per window")
        parent_sets.append(parents)
    if any(parents != parent_sets[0] for parents in parent_sets):
        raise ValueError("Parent identities differ between selectors")
    if manifest["unique_transitions_per_method"] != 954:
        raise ValueError("Selected transition budget changed")


def validate_tracking(results, horizon):
    expected = {f"asap_ft_seed{s}" for s in SEEDS}
    if set(results) != expected:
        raise ValueError("Require exactly the three fixed deployment seeds")
    for label, report in results.items():
        trials = report["trials"]
        if len(trials) != 32 or {t["trial"] for t in trials} != set(range(32)):
            raise ValueError("Missing or duplicated trial identities: " + label)
        for t in trials:
            duration = t["survival_s"]
            if not math.isfinite(duration) or not 0 <= duration <= horizon + .001:
                raise ValueError("Invalid recorded survival")
            if t["complete"] and abs(duration - horizon) > .001:
                raise ValueError("Complete trial does not reach declared horizon")
            for h in (1., 3.):
                prefix = t["prefix_metrics"][str(h)]
                expected_frames = int(h * 50)
                if prefix["complete"] != (prefix["frames"] == expected_frames):
                    raise ValueError("Prefix frame/completion disagreement")
                if prefix["complete"] and duration + .001 < h:
                    raise ValueError("Prefix exceeds recorded survival")
                for field in ("global_body_mpjpe_mm", "root_relative_body_mpjpe_mm"):
                    if not math.isfinite(prefix[field]) or prefix[field] < 0:
                        raise ValueError("Invalid prefix error")
            for field in ("global_body_mpjpe_mm", "root_relative_body_mpjpe_mm"):
                if not math.isfinite(t[field]) or t[field] < 0:
                    raise ValueError("Invalid full-record error")
    return aggregate(results, "asap_ft")


def replay_summary(row, expected_cases):
    one = row["1.0"]
    if one["total_cases"] != expected_cases or not 0 <= one["complete_cases"] <= expected_cases:
        raise ValueError("Unexpected replay case budget")
    if set(one["per_task"]) != {"CR7", "SquatL1", "StepFBL1"}:
        raise ValueError("Missing replay task")
    for field in REPLAY_FIELDS:
        if not math.isfinite(one["equal_task_mean"][field]) or one["equal_task_mean"][field] < 0:
            raise ValueError("Invalid replay metric")
    return one


def load_run(root, expected_seed, horizon):
    if read(root / "status.json")["status"] != "complete":
        raise ValueError("Pending/failed run is not performance evidence: " + str(root))
    manifest = read(root / "selection_manifest.json")
    validate_manifest(manifest)
    plan = read(root / "plan.json")
    if (plan["training_seed"], plan["source_kp"], plan["target_kp"], plan["training_num_envs"], plan["iterations"]) != (expected_seed, 20, 16, 2048, 1000):
        raise ValueError("Prespecified seed or training settings changed")
    raw = read(root / "comparison.json")
    if set(raw) != set(METHODS):
        raise ValueError("Do not publish a selected subset of completed selectors")
    results = {}
    for method in METHODS:
        directory = root / method
        if read(directory / "status.json")["status"] != "complete":
            raise ValueError("Condition did not complete")
        selection = read(directory / "delta_selection.json")
        checkpoint = Path(selection["checkpoint"]).name
        if checkpoint not in ("model_500.pt", "model_1000.pt"):
            raise ValueError("Unexpected calibration checkpoint")
        tracking = raw[method]["tracking"]
        if tracking["training_seeds"] != 1:
            raise ValueError("Each run must represent one training seed")
        results[method] = {
            "selected_checkpoint": checkpoint,
            "validation_body_mpjpe_mm": selection["validation_body_mpjpe_mm"],
            "test_replay": replay_summary(raw[method]["test_replay"], 66),
            "selected_subset_floor": replay_summary(read(directory / "selected_subset_replay_floor.json"), 18),
            "tracking": validate_tracking(tracking["results"], horizon),
            "floor_provenance": read(directory / "floor_provenance.json") if (directory / "floor_provenance.json").exists() else {"scope": "Measured primary same-domain replay"},
        }
        if expected_seed == 20305009 and not (directory / "floor_provenance.json").exists():
            raise ValueError("Repeat floor requires copied-measurement provenance")
    baselines = read(root / "shared_test_baselines.json")
    if set(baselines) != {"same16_zero", "source20_zero"}:
        raise ValueError("Missing fixed shared replay baselines")
    return {"calibration_seed": expected_seed, "policy_seed": expected_seed + 1000,
            "source_comparison_sha256": sha(root / "comparison.json"),
            "manifest_sha256": sha(root / "selection_manifest.json"),
            "shared_test_baselines": {k: replay_summary(v, 66) for k, v in baselines.items()},
            "results": results}


def contrasts(run):
    """Signed method-minus-uniform differences, independently per training seed."""
    rows, base = {}, run["results"]["uniform"]
    for method in METHODS[1:]:
        row = run["results"][method]
        a, b = row["tracking"], base["tracking"]
        rows[method + "_minus_uniform"] = {
            "replay_metric_differences": {f: row["test_replay"]["equal_task_mean"][f] - base["test_replay"]["equal_task_mean"][f] for f in REPLAY_FIELDS},
            "completion_percentage_points": 100 * (a["completion_rate"] - b["completion_rate"]),
            "mean_survival_s": a["mean_survival_s"] - b["mean_survival_s"],
            "first_second_body_mm": None if a["prefix_metrics"]["1.0"]["global_body_mpjpe_mm"] is None or b["prefix_metrics"]["1.0"]["global_body_mpjpe_mm"] is None else a["prefix_metrics"]["1.0"]["global_body_mpjpe_mm"] - b["prefix_metrics"]["1.0"]["global_body_mpjpe_mm"],
            "first_second_valid_counts": [a["prefix_metrics"]["1.0"]["complete_trials"], b["prefix_metrics"]["1.0"]["complete_trials"]],
            "test_replay_complete_counts": [row["test_replay"]["complete_cases"], base["test_replay"]["complete_cases"]],
        }
    return rows


def verify_repeat_inputs(primary, repeat):
    hashes = read(repeat / "input_hashes.json")
    for method in METHODS:
        for filename in ("mixed30.pkl", "val_cases.pkl", "test_cases.pkl", "sampling_manifest.json", "selected_subset_replay_floor.json"):
            subpath = Path("datasets") / filename if filename.endswith(".pkl") else Path(filename)
            a, b = primary / method / subpath, repeat / method / subpath
            if sha(a) != sha(b) or sha(b) != hashes[method][filename]:
                raise ValueError("Repeat data/provenance changed: " + str(subpath))
    for filename in ("selection_manifest.json", "shared_test_baselines.json"):
        if sha(primary / filename) != sha(repeat / filename) or sha(repeat / filename) != hashes[filename]:
            raise ValueError("Repeat manifest/baseline changed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--repeat", type=Path)
    parser.add_argument("--preview", type=Path, required=True, help="Prespecified public selection_manifest_preview.json; actual selections must match")
    parser.add_argument("--horizon", type=float, required=True, help="Actual deployment record steps /50, checked against saved evaluation commands")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if abs(args.horizon - 5.22) > .001:
        parser.error("This fixed Squat protocol expects261 actual50Hz frames")
    runs = {"primary": load_run(args.primary, 20305008, args.horizon)}
    if read(args.primary / "selection_manifest.json") != read(args.preview):
        raise ValueError("Actual selection/scaler differs from prespecified public preview")
    if args.repeat:
        runs["repeat"] = load_run(args.repeat, 20305009, args.horizon)
        verify_repeat_inputs(args.primary, args.repeat)
    report = {"scope": "Fixed acquisition pool and selected data; descriptive contrasts per training seed, never pooled192-trial training replication",
              "training_replications": len(runs), "selected_transitions_per_selector": 954,
              "deployment_horizon_s": args.horizon,
              "repeat_included": bool(args.repeat),
              "error_scope": "Tracking prefix/full means condition on prefix/full completion. Replay metrics average available pretermination prefixes with equal task/group weights; completion counts are separate. No floor subtraction.",
              "audit_scope": "Artifact/identity/budget/hash checks here; actual command, state and effective-setting audits must accompany publication separately",
              "inference_limit": "One or two fixed-data training seeds are not acquisition replication or a population ranking. Existing FT-only uses another training seed and is contextual, not a same-seed control.",
              "runs": runs, "contrasts": {name: contrasts(run) for name, run in runs.items()}}
    rows = ["| Run | Selector | Replay body / velocity (mm / rad/s; complete /66) | Subset floor body (mm; complete /18) | Policy completion /96 | Survival (s) | First1s body / root-relative (mm; valid n) | Full body / root-relative (mm; successful n) |",
            "|---|---|---|---|---:|---:|---|---|"]
    def pair(a, b, n):
        return "Unavailable (0)" if not n else f"{a:.2f} / {b:.2f} ({n})"
    for name, run in runs.items():
        for method in METHODS:
            row = run["results"][method]
            replay, floor, tracking = row["test_replay"], row["selected_subset_floor"], row["tracking"]
            p = tracking["prefix_metrics"]["1.0"]
            r, f = replay["equal_task_mean"], floor["equal_task_mean"]
            prefix = pair(p["global_body_mpjpe_mm"], p["root_relative_body_mpjpe_mm"], p["complete_trials"])
            full = pair(tracking["complete_trial_global_body_mpjpe_mm"], tracking["complete_trial_root_relative_body_mpjpe_mm"], tracking["complete_trials"])
            rows.append(f"| {name} | {method} | {r['global_body_mpjpe_mm']:.2f} / {r['joint_velocity_rmse_rad_s']:.3f} ({replay['complete_cases']}) | {f['global_body_mpjpe_mm']:.2f} ({floor['complete_cases']}) | {tracking['complete_trials']} | {tracking['mean_survival_s']:.3f} | {prefix} | {full} |")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (args.output / "metrics.md").write_text("\n".join(rows) + "\n")
    print(json.dumps({name: {m: r["tracking"]["complete_trials"] for m, r in run["results"].items()} for name, run in runs.items()}))


if __name__ == "__main__":
    main()
