"""Reuse the shared calibrated models for two additional motion policies."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research.asap_diagnostics.controlled_pipeline import launch, write, fine_overrides, tracking_overrides
from research.asap_diagnostics.torque_pipeline import overrides


def adapted_training(work, plan, task, label, selected, gains, torque, iterations):
    base = fine_overrides(work, plan, selected, label, task, iterations)
    if label in ("ft_only", "asap_ft"):
        return base
    additions = ["++algo._target_=research.asap_diagnostics.torque_runtime.FreshTaskPPO",
                 "env.config.add_extra_action=False", "++obs.obs_dict.closed_loop_actor_obs=[ref_motion_phase]"]
    if label in ("torque_ft", "wave_ft"):
        additions += ["++env._target_=research.asap_diagnostics.torque_runtime.FrozenTorqueTracking",
                      "++env.config.torque_checkpoint=" + str(torque), "++env.config.torque_scale_nm=5.0"]
    else:
        additions += ["++env._target_=humanoidverse.envs.motion_tracking.motion_tracking.LeggedRobotMotionTracking",
                      "robot.control.stiffness.ankle_pitch=" + str(gains[label][0]),
                      "robot.control.stiffness.ankle_roll=" + str(gains[label][1])]
    return overrides(base, additions)


def run(args):
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    write(work / "status.json", {"status": "waiting", "stage": "preceding_active_queue"})
    while True:
        state = json.loads(args.wait_for.read_text()) if args.wait_for.exists() else {}
        if state.get("status") == "complete":
            break
        if state.get("status") == "failed":
            raise RuntimeError("Preceding active comparison failed; inspect before extension")
        if time.time() > deadline - 60:
            raise TimeoutError("Cutoff while waiting for active stage")
        time.sleep(30)
    plan = json.loads((args.controlled / "plan.json").read_text())
    selected = json.loads((args.controlled / "delta_selection.json").read_text())["checkpoint"]
    torque = json.loads((args.torque / "torque_selection.json").read_text())["checkpoint"]
    wave_model = json.loads((args.wave / "wave/torque_selection.json").read_text())["checkpoint"] if args.wave else None
    passive = json.loads((args.sysid / "identified.json").read_text())
    active = json.loads((args.active / "identified_comparison.json").read_text())["active"]["gains"]
    gains = {"sysid_ft": [passive["ankle_pitch_Kp"], passive["ankle_roll_Kp"]], "active_sysid_ft": active}
    write(work / "protocol.json", {"tasks": ["CR7", "StepFBL1"],
        "calibration": "Reuse mixed-motion learned models and fitted gains; do not retrain or change calibration data",
        "task_budget": args.iterations, "num_envs": 2048, "training_seeds": 1,
        "evaluation_seeds": [8101, 8102, 8103], "trials_per_seed": 32,
        "checkpoint_selection": "Fixed final update; original source model_6000.pt for every task",
        "evaluation": "Standalone target Kp16; zero task-observation noise; common termination thresholds verified against both source configs"})
    all_results = {}
    for task in ("CR7", "StepFBL1"):
        write(work / "status.json", {"status": "running", "stage": task + "_policy_comparison"})
        directory = work / task
        directory.mkdir(exist_ok=True)
        controllers = {"vanilla": plan["tasks"][task]["checkpoint"]}
        methods = ["ft_only", "asap_ft", "sysid_ft", "torque_ft", "active_sysid_ft"] + (["wave_ft"] if wave_model else [])
        for label in methods:
            final = directory / "models" / label / ("model_%d.pt" % args.iterations)
            if not final.exists():
                if (final.parent / "config.yaml").exists():
                    raise RuntimeError("Incomplete task policy exists; no silent resume")
                command = adapted_training(directory, plan, task, label, selected, gains,
                                           wave_model if label == "wave_ft" else torque, args.iterations)
                launch(directory, "train", plan["training_seed"] + 1000, command, "train_" + label, deadline)
            controllers[label] = str(final)
        results = {}
        for label, checkpoint in controllers.items():
            for seed in (8101, 8102, 8103):
                name = label + "_seed%d" % seed
                launch(directory, "eval", seed, tracking_overrides(directory, checkpoint, name, task, plan, .2, seed), name, deadline)
                results[name] = json.loads((directory / "tracking" / (name + ".json")).read_text())
        all_results[task] = {"results": results, "training_seeds": 1}
        write(directory / "tracking_comparison.json", all_results[task])
        write(directory / "status.json", {"status": "complete", "stage": "standalone_target_comparison"})
    write(work / "tracking_comparison.json", all_results)
    write(work / "status.json", {"status": "complete", "stage": "two_task_extension"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("controlled", "sysid", "torque", "active", "work-dir", "wait-for"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--wave", type=Path, help="Also reuse the true-rate excitation model on both new tasks")
    parser.add_argument("--cutoff", default="2026-10-09T09:00:00+00:00")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        write(args.work_dir / "status.json", {"status": "failed", "error": str(error)})
        raise
