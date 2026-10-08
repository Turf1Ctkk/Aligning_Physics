"""Matched-data UAN-style torque calibration, then standalone policy transfer."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research.asap_diagnostics.controlled_pipeline import launch, write, delta_overrides, fine_overrides, tracking_overrides
from research.asap_diagnostics.multi_motion_pipeline import aggregate_cases
from research.asap_diagnostics.dataset_tools import replay_metrics


def overrides(base, additions):
    # Last duplicate Hydra key is not relied upon: explicitly replace by key.
    values = {item.lstrip("+").split("=", 1)[0]: item for item in base}
    for item in additions:
        values[item.lstrip("+").split("=", 1)[0]] = item
    return list(values.values())


def torque_training(work, plan, iterations, smoke=False):
    return overrides(delta_overrides(work, plan, iterations), [
        "++env._target_=research.asap_diagnostics.torque_runtime.TorqueReplay",
        "++algo._target_=research.asap_diagnostics.torque_runtime.TorquePPO",
        "experiment_name=uan_style_torque", "experiment_dir=" + str(work / "models" / ("smoke" if smoke else "torque")),
        "simulator.config.sim.control_decimation=1", "++env.config.torque_scale_nm=5.0",
        "obs.obs_dict.actor_obs=[uan_history]", "++obs.obs_dims=[{uan_history:160},{base_pos_z:1},{feet_contact_force:6},{base_lin_vel:3},{base_ang_vel:3},{projected_gravity:3},{dof_pos:23},{dof_vel:23},{actions:23},{dif_local_rigid_body_pos:81},{local_ref_rigid_body_pos:81},{ref_motion_phase:1},{actions_open_loop:23}]",
        "++obs.obs_scales.uan_history=1.0", "++obs.noise_scales.uan_history=0.0",
        "algo.config.num_steps_per_env=" + ("8" if smoke else "96"),
        "num_envs=" + ("32" if smoke else "2048"),
        "algo.config.gamma=" + str(.99 ** .25), "algo.config.lam=" + str(.95 ** .25),
        "algo.config.num_learning_iterations=" + str(iterations), "seed=" + str(plan["training_seed"] + 2000),
    ])


def evaluate(work, plan, checkpoint, split, label, deadline, kp=20, zero=False):
    references = joblib.load(work / "datasets" / (split + "_cases.pkl"))
    directory = work / "evaluation" / split
    directory.mkdir(parents=True, exist_ok=True)
    raw = directory / (label + ".pkl")
    launch(work, "eval", 8100, [
        "+checkpoint=" + str(checkpoint), "+headless=True", "+num_envs=" + str(len(references)), "+opt=record",
        "+domain_rand=NO_domain_rand", "++seed=8100",
        "++algo._target_=research.asap_diagnostics.torque_runtime.TorqueReplayRecorder",
        "++env._target_=research.asap_diagnostics.torque_runtime.TorqueReplay",
        "++env.config.sampling_manifest=" + str(work / "sampling_manifest.json"),
        "++robot.motion.motion_file=" + str(work / "datasets" / (split + "_cases.pkl")),
        "++robot.motion.use_recorded_velocities=True", "++env.config.dataset_evaluation=True",
        "++robot.control.stiffness.ankle_pitch=" + str(kp), "++robot.control.stiffness.ankle_roll=" + str(kp),
        "++env.config.noise_to_initial_level=0", "++env.config.enforce_randomize_motion_start_eval=False",
        "++env.config.resample_motion_when_training=False", "++env.config.save_motion=False",
        "++env.config.zero_delta_a=" + str(zero), "++env.config.dataset_record_steps=55",
        "++env.config.dataset_record_path=" + str(raw), "++eval_log_dir=" + str(directory / (label + "_config")),
    ], label, deadline)
    predictions = joblib.load(raw)
    rows = [{"key": key, "task": ref["dataset_task"], "group": ref["dataset_group"],
             "metrics": {str(h): replay_metrics(ref, predictions["motion" + str(index)], h) for h in (.25, .5, 1.)}}
            for index, (key, ref) in enumerate(references.items())]
    report = {"cases": rows, "summary": {str(h): aggregate_cases(rows, h) for h in (.25, .5, 1.)},
              "scope": "Torque correction at 200 Hz; target measurement and output dump at 50 Hz"}
    write(directory / (label + ".json"), report)
    return report


def run(args):
    import shutil
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    while args.wait_for:
        status = json.loads(args.wait_for.read_text()) if args.wait_for.exists() else {}
        if status.get("status") == "complete":
            break
        if status.get("status") == "failed":
            raise RuntimeError("Preceding SysID failed; inspect before proceeding")
        if time.time() > deadline - 60:
            raise TimeoutError("Cutoff before torque comparison")
        time.sleep(30)
    plan = json.loads((args.controlled / "plan.json").read_text())
    write(work / "plan.json", plan)
    shutil.copytree(args.controlled / "datasets", work / "datasets", dirs_exist_ok=True)
    shutil.copy2(args.controlled / "sampling_manifest.json", work / "sampling_manifest.json")
    write(work / "protocol.json", {"method": "UAN-style torque-model adaptation, not original hardware/data reproduction",
        "target_data": "same mixed30 policy rollouts measured at 50 Hz", "correction_rate_hz": 200,
        "history": "20 genuine simulator states at 5ms; q target error and zero-target-velocity error",
        "actor": "shared per-joint 40-128-128-1 ELU, four ankles", "torque_scale_nm": 5,
        "calibration_budget": "1000 updates, 96 steps per environment; same simulated duration as 50Hz/24-step action baseline",
        "limitations": "Different parameter count and four times as many PPO transitions; target reference is interpolated between measured 50Hz states; history is zeroed at reset"})
    launch(work, "train", plan["training_seed"] + 2000, torque_training(work, plan, 4, smoke=True), "torque_smoke", deadline)
    launch(work, "train", plan["training_seed"] + 2000, torque_training(work, plan, args.iterations), "train_torque", deadline)
    candidates = []
    for iteration in sorted(set((args.iterations // 2, args.iterations))):
        checkpoint = work / "models/torque" / ("model_" + str(iteration) + ".pt")
        # Weighted constructor needs a manifest corresponding to this split.
        refs = joblib.load(work / "datasets/val_cases.pkl")
        from research.asap_diagnostics.controlled_sampling import hierarchical_weights
        write(work / "sampling_manifest.json", {"weights": hierarchical_weights(refs),
              "metadata": {k: {"task": m["dataset_task"], "group": m["dataset_group"]} for k, m in refs.items()}})
        report = evaluate(work, plan, checkpoint, "val", "torque_" + str(iteration), deadline)
        summary = report["summary"]["1.0"]
        if summary["complete_cases"] != summary["total_cases"]:
            raise RuntimeError("Incomplete torque validation")
        candidates.append((summary["equal_task_mean"]["global_body_mpjpe_mm"], checkpoint))
    score, selected = min(candidates, key=lambda x: x[0])
    write(work / "torque_selection.json", {"checkpoint": str(selected), "validation_global_body_mpjpe_mm": score})
    refs = joblib.load(work / "datasets/test_cases.pkl")
    write(work / "sampling_manifest.json", {"weights": hierarchical_weights(refs),
          "metadata": {k: {"task": m["dataset_task"], "group": m["dataset_group"]} for k, m in refs.items()}})
    test = {label: evaluate(work, plan, selected, "test", label, deadline, kp, zero)["summary"]
            for label, kp, zero in (("same16_zero",16,True),("source20_zero",20,True),("torque",20,False))}
    write(work / "replay_comparison.json", test)
    ft = overrides(fine_overrides(work, plan, selected, "torque_ft", "SquatL1", args.iterations), [
        "++algo._target_=research.asap_diagnostics.torque_runtime.FreshTaskPPO",
        "++env._target_=research.asap_diagnostics.torque_runtime.FrozenTorqueTracking",
        "++env.config.torque_checkpoint=" + str(selected), "++env.config.torque_scale_nm=5.0",
        "env.config.add_extra_action=False", "++obs.obs_dict.closed_loop_actor_obs=[ref_motion_phase]",
    ])
    launch(work, "train", plan["training_seed"] + 1000, ft, "train_torque_ft", deadline)
    final = work / "models/torque_ft" / ("model_" + str(args.iterations) + ".pt")
    results = {}
    for seed in (8101, 8102, 8103):
        label = "torque_ft_seed" + str(seed)
        launch(work, "eval", seed, tracking_overrides(work, final, label, "SquatL1", plan, .2, seed), label, deadline)
        results[label] = json.loads((work / "tracking" / (label + ".json")).read_text())
    write(work / "tracking_comparison.json", {"results": results, "training_seeds": 1})
    write(work / "status.json", {"status": "complete", "stage": "uan_style_torque_comparison"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--controlled", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--wait-for", type=Path)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--cutoff", default="2026-10-09T09:00:00+00:00")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        write(args.work_dir / "status.json", {"status": "failed", "error": str(error)})
        raise
