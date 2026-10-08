"""SPI-style CMA-ES trajectory matching; active command generation is separate."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research.asap_diagnostics.controlled_pipeline import launch, write, fine_overrides, tracking_overrides
from research.asap_diagnostics.controlled_sampling import hierarchical_weights
from research.asap_diagnostics.dataset_tools import slice_motion, replay_metrics


def make_cases(dataset):
    # One fixed central full-second window per continuous training segment.
    cases = {}
    for key, motion in dataset.items():
        start = (len(motion["dof"]) - 52) // 2
        if start < 0:
            raise ValueError("Short calibration segment")
        cases[key] = slice_motion(motion, start, start + 52)
    return cases


def evaluate_candidates(work, cases, weights, candidates, checkpoint, label, deadline):
    inputs, manifest = {}, {}
    for candidate, gains in enumerate(candidates):
        for key, motion in cases.items():
            new_key = "c%03d__%s" % (candidate, key)
            inputs[new_key] = motion
            manifest[new_key] = [float(x) for x in gains]
    directory = work / label
    directory.mkdir(parents=True, exist_ok=True)
    dataset_path, manifest_path = directory / "inputs.pkl", directory / "gains.json"
    joblib.dump(inputs, dataset_path)
    write(manifest_path, manifest)
    output = directory / "replay.pkl"
    overrides = [
        "+checkpoint=" + str(checkpoint), "+headless=True", "+num_envs=" + str(len(inputs)), "+opt=record",
        "+domain_rand=NO_domain_rand", "++seed=7101",
        "++env._target_=research.asap_diagnostics.sysid_runtime.CandidateGainReplay",
        "++algo._target_=research.asap_diagnostics.dataset_runtime.RolloutRecorderPPO",
        "++env.config.sysid_manifest=" + str(manifest_path),
        "++robot.motion.motion_file=" + str(dataset_path), "++robot.motion.use_recorded_velocities=True",
        "++robot.asset.self_collisions=0", "++env.config.noise_to_initial_level=0",
        "++env.config.dataset_evaluation=True", "++env.config.enforce_randomize_motion_start_eval=False",
        "++env.config.resample_motion_when_training=False", "++env.config.save_motion=False",
        "++env.config.dataset_record_path=" + str(output), "++env.config.dataset_record_steps=55",
        "++eval_log_dir=" + str(directory / "effective_config"),
    ]
    launch(work, "eval", 7101, overrides, label, deadline)
    predictions = joblib.load(output)
    results = []
    count = len(cases)
    for candidate, gains in enumerate(candidates):
        rows = []
        for index, (key, ref) in enumerate(cases.items()):
            prediction = predictions["motion" + str(candidate * count + index)]
            short, full = replay_metrics(ref, prediction, .25), replay_metrics(ref, prediction, 1.)
            if not short["complete"] or not full["complete"]:
                raise RuntimeError("Candidate replay terminated; objective is undefined")
            # Fixed dimensionless joint-state loss; no target gain labels.
            loss = (short["all_joint_rmse_rad"] / .1) ** 2 + (short["joint_velocity_rmse_rad_s"] / 1.) ** 2
            rows.append({"key": key, "weight": weights[key], "loss": loss, "short": short, "full": full})
        results.append({"gains": list(map(float, gains)), "objective": float(sum(r["weight"] * r["loss"] for r in rows)),
                        "cases": rows})
    write(directory / "scores.json", results)
    return results


def run(args):
    import cma
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    if args.wait_for:
        while True:
            state = json.loads(args.wait_for.read_text()) if args.wait_for.exists() else {}
            if state.get("status") == "complete":
                break
            if state.get("status") == "failed":
                raise RuntimeError("Preceding controlled comparison failed; inspect before proceeding")
            if time.time() > deadline - 60:
                raise TimeoutError("Cutoff while waiting for preceding comparison")
            time.sleep(30)
    cases = make_cases(joblib.load(args.dataset))
    weights = hierarchical_weights(cases)
    write(work / "protocol.json", {"method": "SPI-style passive CMA-ES SysID; not full SPI-Active",
        "dataset": str(args.dataset), "parameters": ["ankle_pitch_Kp", "ankle_roll_Kp"],
        "bounds": [8, 30], "initial_mean": [20, 20], "initial_sigma": 2,
        "population": 12, "generations": args.generations, "seed": 7101,
        "objective": "task/group/segment-weighted 0.25s joint position and velocity squared errors; scales .1 rad and 1 rad/s",
        "selection": "training objective only; no target parameter read; validation/test remain isolated"})
    optimizer = cma.CMAEvolutionStrategy([20., 20.], 2., {"bounds": [8., 30.], "popsize": 12, "seed": 7101, "verbose": -9})
    history = []
    for generation in range(args.generations):
        candidates = optimizer.ask()
        scores = evaluate_candidates(work, cases, weights, candidates, args.checkpoint,
                                      "generation%02d" % generation, deadline)
        optimizer.tell(candidates, [row["objective"] for row in scores])
        history.append({"generation": generation, "candidate_gains": [list(map(float, c)) for c in candidates],
                        "scores": [row["objective"] for row in scores], "mean": optimizer.mean.tolist()})
        write(work / "history.json", history)
    fitted = optimizer.result.xbest.tolist()
    score = float(optimizer.result.fbest)
    write(work / "identified.json", {"ankle_pitch_Kp": fitted[0], "ankle_roll_Kp": fitted[1],
                                     "training_objective": score, "evaluations": int(optimizer.result.evaluations),
                                     "scope": "Passive structured SysID from recorded transitions; active exploration not performed"})
    if args.controlled:
        from research.asap_diagnostics.torque_pipeline import overrides
        from research.asap_diagnostics.multi_motion_pipeline import aggregate_cases
        plan = json.loads((args.controlled / "plan.json").read_text())
        results = {}
        for split in ("val", "test"):
            references = joblib.load(args.controlled / "datasets" / (split + "_cases.pkl"))
            heldout = evaluate_candidates(work, references, hierarchical_weights(references), [fitted],
                                           args.checkpoint, "identified_" + split, deadline)[0]
            rows = [{"task": references[row["key"]]["dataset_task"],
                     "group": references[row["key"]]["dataset_group"], "metrics": {"1.0": row["full"]}}
                    for row in heldout["cases"]]
            results[split] = aggregate_cases(rows, 1.)
        write(work / "replay_comparison.json", results)
        ft = overrides(fine_overrides(work, plan, args.checkpoint, "sysid_ft", "SquatL1", args.iterations), [
            "++algo._target_=research.asap_diagnostics.torque_runtime.FreshTaskPPO",
            "++env._target_=humanoidverse.envs.motion_tracking.motion_tracking.LeggedRobotMotionTracking",
            "env.config.add_extra_action=False", "++obs.obs_dict.closed_loop_actor_obs=[ref_motion_phase]",
            "robot.control.stiffness.ankle_pitch=" + str(fitted[0]),
            "robot.control.stiffness.ankle_roll=" + str(fitted[1]),
        ])
        launch(work, "train", plan["training_seed"] + 1000, ft, "train_sysid_ft", deadline)
        final = work / "models/sysid_ft" / ("model_" + str(args.iterations) + ".pt")
        tracking = {}
        for seed in (8101, 8102, 8103):
            label = "sysid_ft_seed" + str(seed)
            launch(work, "eval", seed, tracking_overrides(work, final, label, "SquatL1", plan, .2, seed), label, deadline)
            tracking[label] = json.loads((work / "tracking" / (label + ".json")).read_text())
        write(work / "tracking_comparison.json", {"results": tracking, "training_seeds": 1})
    write(work / "status.json", {"status": "complete", "stage": "passive_sysid_and_policy_comparison"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True, help="Replay interface only; actor output is ignored")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--generations", type=int, default=8)
    parser.add_argument("--wait-for", type=Path, help="Serialize after the preceding queue's status.json")
    parser.add_argument("--controlled", type=Path, help="Also run held-out replay and equal-budget policy fine-tuning")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--cutoff", default="2026-10-09T09:00:00+00:00")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        write(args.work_dir / "status.json", {"status": "failed", "error": str(error)})
        raise
