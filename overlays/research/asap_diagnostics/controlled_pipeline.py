"""Serial GPU queue for calibrated Squat policy and an equal-budget control."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import joblib

# The existing diagnostic manager uses sibling imports when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from research.asap_diagnostics.controlled_sampling import hierarchical_weights, summarize_weights
from research.asap_diagnostics.multi_motion_pipeline import evaluate_batch

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "research/asap_diagnostics/seeded_entry.py"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2))
    temp.replace(path)


def launch(work, mode, seed, overrides, label, deadline):
    remaining = deadline - time.time()
    if remaining < 60:
        raise TimeoutError("Experiment cutoff reached")
    command = [sys.executable, str(ENTRY), mode, "--rng-seed", str(seed)] + overrides
    write(work / "commands" / (label + ".json"), {"command": command, "cwd": str(ROOT)})
    write(work / "status.json", {"stage": label, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat()})
    env = os.environ.copy()
    env.update(PYTHONHASHSEED=str(seed), HYDRA_FULL_ERROR="1")
    with (work / (label + ".log")).open("w") as log:
        process = subprocess.Popen(command, cwd=str(ROOT), env=env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            result = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            raise TimeoutError("Stopped current experiment at configured cutoff")
    if result:
        raise RuntimeError(label + " failed; inspect " + str(work / (label + ".log")))


def delta_overrides(work, plan, iterations):
    return [
        "+simulator=isaacgym", "+exp=train_delta_a_open_loop", "+domain_rand=NO_domain_rand",
        "+rewards=motion_tracking/delta_a/reward_delta_a_openloop", "+robot=g1/g1_29dof_anneal_23dof",
        "+terrain=terrain_locomotion_plane", "+obs=delta_a/open_loop", "num_envs=2048", "headless=True",
        "checkpoint=null", "auto_load_latest=False", "use_wandb=False", "project_name=AligningPhysics",
        "experiment_name=controlled_delta", "experiment_dir=" + str(work / "models/delta"),
        "++env._target_=research.asap_diagnostics.controlled_runtime.WeightedGridDeltaReplay",
        "++env.config.sampling_manifest=" + str(work / "sampling_manifest.json"),
        "robot.motion.motion_file=" + str(work / "datasets/mixed30.pkl"),
        "++robot.motion.use_recorded_velocities=True", "robot.control.stiffness.ankle_pitch=20",
        "robot.control.stiffness.ankle_roll=20", "robot.asset.self_collisions=0", "env.config.max_episode_length_s=1.0",
        "env.config.noise_to_initial_level=0", "env.config.resample_motion_when_training=True",
        "env.config.resample_time_interval_s=10000", "++env.config.add_extra_action=True",
        "++env.config.zero_delta_a=False", "++env.config.anklePR=True",
        "obs.noise_scales.base_pos_z=0.0", "obs.noise_scales.feet_contact_force=0.0",
        "rewards.reward_scales.penalty_minimal_action_norm=-0.1", "algo.config.init_at_random_ep_len=False",
        "algo.config.save_interval=100", "algo.config.num_learning_iterations=" + str(iterations),
        "seed=" + str(plan["training_seed"]),
    ]


def fine_overrides(work, plan, selected, label, task, iterations):
    return [
        "+simulator=isaacgym", "+exp=train_delta_a_closed_loop", "+domain_rand=NO_domain_rand_finetune_with_deltaA",
        "+rewards=motion_tracking/reward_motion_tracking_dm_simfinetuning", "+robot=g1/g1_29dof_anneal_23dof",
        "+terrain=terrain_locomotion_plane", "+obs=delta_a/train_policy_with_delta_a",
        "++algo._target_=research.asap_diagnostics.controlled_runtime.FreshFineTunePPO",
        "algo.config.policy_checkpoint=" + str(selected), "checkpoint=" + plan["tasks"][task]["checkpoint"],
        "robot.motion.motion_file=" + plan["tasks"][task]["reference"], "num_envs=2048", "headless=True",
        "project_name=AligningPhysics", "experiment_name=" + label, "experiment_dir=" + str(work / "models" / label),
        "use_wandb=False", "auto_load_latest=False", "robot.asset.self_collisions=0",
        "robot.control.stiffness.ankle_pitch=20", "robot.control.stiffness.ankle_roll=20",
        "env.config.add_extra_action=" + str(label != "ft_only"), "++env.config.anklePR=True",
        "env.config.noise_to_initial_level=0.2", "env.config.resample_motion_when_training=False",
        "algo.config.load_optimizer=False", "algo.config.actor_learning_rate=0.0001",
        "algo.config.critic_learning_rate=0.001", "algo.config.entropy_coef=0.0",
        "algo.config.init_at_random_ep_len=False", "algo.config.save_interval=100",
        "algo.config.num_learning_iterations=" + str(iterations), "seed=" + str(plan["training_seed"] + 1000),
        "rewards.reward_penalty_curriculum=False", "rewards.reward_initial_penalty_scale=1.0",
    ]


def tracking_overrides(work, checkpoint, label, task, plan, noise, seed, num_envs=32):
    frames = int(math.floor(plan["tasks"][task]["reference_duration_s"] * 50))
    return [
        "+checkpoint=" + str(checkpoint), "+headless=True", "+num_envs=" + str(num_envs), "+opt=record",
        "+domain_rand=NO_domain_rand", "++seed=" + str(seed),
        "++algo._target_=research.asap_diagnostics.controlled_runtime.TrackingRecorderPPO",
        "++env._target_=humanoidverse.envs.motion_tracking.motion_tracking.LeggedRobotMotionTracking",
        # Unused auxiliary buffer remains nonempty for the stock observation assembler.
        "++obs.obs_dict.closed_loop_actor_obs=[ref_motion_phase]", "++eval_log_dir=" + str(work / "tracking" / (label + "_config")),
        "++robot.motion.motion_file=" + plan["tasks"][task]["reference"],
        "++robot.control.stiffness.ankle_pitch=16", "++robot.control.stiffness.ankle_roll=16",
        "++robot.asset.self_collisions=0", "++env.config.noise_to_initial_level=" + str(noise),
        "++env.config.init_noise_scale.root_pos=0", "++env.config.init_noise_scale.root_rot=0",
        "++env.config.enforce_randomize_motion_start_eval=False", "++env.config.resample_motion_when_training=False",
        "++env.config.add_extra_action=False", "++env.config.save_motion=False",
        "++env.config.dataset_record_steps=" + str(frames),
        "++env.config.dataset_record_path=" + str(work / "tracking" / (label + ".pkl")),
        # Match the original Squat evaluation criteria for every checkpoint.
        # Fine-tuning configs otherwise inherit motion_far=False.
        "++env.config.termination.terminate_by_contact=False",
        "++env.config.termination.terminate_by_gravity=True",
        "++env.config.termination.terminate_by_low_height=False",
        "++env.config.termination.terminate_when_motion_end=True",
        "++env.config.termination.terminate_when_motion_far=True",
        "++env.config.termination.terminate_when_close_to_dof_pos_limit=False",
        "++env.config.termination.terminate_when_close_to_dof_vel_limit=False",
        "++env.config.termination.terminate_when_close_to_torque_limit=False",
        "++env.config.termination_scales.termination_gravity_x=0.8",
        "++env.config.termination_scales.termination_gravity_y=0.8",
        "++env.config.termination_scales.termination_motion_far_threshold=1.5",
        "++env.config.termination_curriculum.terminate_when_motion_far_curriculum=False",
    ]


def run(args):
    work, pilot = args.work_dir.resolve(), args.pilot.resolve()
    work.mkdir(parents=True, exist_ok=True)
    lock = (work / "run.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    plan = json.loads((pilot / "plan.json").read_text())
    plan["training_seed"] += 30000
    plan["iterations"] = args.iterations
    plan["protocol"] = "mixed30 task/group/clip weights; standalone target policy deployment"
    plan["cutoff_utc"] = args.cutoff
    write(work / "plan.json", plan)
    (work / "datasets").mkdir(exist_ok=True)
    for name in ("balanced10.pkl", "val_cases.pkl", "test_cases.pkl"):
        shutil.copy2(pilot / "datasets" / name, work / "datasets" / ("mixed30.pkl" if name == "balanced10.pkl" else name))
    motions = joblib.load(work / "datasets/mixed30.pkl")
    weights = hierarchical_weights(motions)
    summary = summarize_weights(motions, weights)
    if any(abs(value - 1 / 3) > 1e-8 for value in summary["tasks"].values()) or len(summary["groups"]) != 30:
        raise ValueError("Dataset is not the confirmed mixed30 baseline")
    manifest = {"weights": weights, "summary": summary,
                "metadata": {k: {"task": m["dataset_task"], "group": m["dataset_group"]} for k, m in motions.items()}}
    write(work / "sampling_manifest.json", manifest)
    # Validate target evaluation before starting calibration/policy training.
    original = plan["tasks"][args.task]["checkpoint"]
    launch(work, "eval", 8101, tracking_overrides(work, original, "vanilla_clean", args.task, plan, 0, 8101, 1), "vanilla_clean", deadline)
    delta_final = work / "models/delta" / ("model_" + str(args.iterations) + ".pt")
    if not delta_final.exists():
        if (delta_final.parent / "config.yaml").exists():
            raise RuntimeError("Incomplete delta run exists; no silent resume")
        launch(work, "train", plan["training_seed"], delta_overrides(work, plan, args.iterations), "train_delta", deadline)
    # Existing evaluator is reused, but all subprocesses go through the cutoff-aware launcher.
    import research.asap_diagnostics.multi_motion_pipeline as replay
    replay.launch = lambda w, mode, seed, overrides, log: launch(w, mode, seed, overrides, log.stem, deadline)
    candidates = []
    for iteration in sorted(set((args.iterations // 2, args.iterations))):
        checkpoint = delta_final.parent / ("model_" + str(iteration) + ".pt")
        result = evaluate_batch(work, plan, checkpoint, "val", "delta_" + str(iteration))
        summary = result["summary"]["1.0"]
        if summary["complete_cases"] != summary["total_cases"]:
            raise RuntimeError("Incomplete validation replay")
        candidates.append((summary["equal_task_mean"]["global_body_mpjpe_mm"], checkpoint))
    score, selected = min(candidates, key=lambda x: x[0])
    write(work / "delta_selection.json", {"checkpoint": str(selected), "validation_global_body_mpjpe_mm": score})
    replay_results = {}
    for label, kp, zero in (("same16_zero",16,True),("source20_zero",20,True),("controlled_delta",20,False)):
        replay_results[label] = evaluate_batch(work, plan, selected, "test", label, kp=kp, zero=zero)["summary"]
    write(work / "replay_comparison.json", replay_results)
    controllers = {"vanilla": original}
    for label in ("ft_only", "asap_ft"):
        final = work / "models" / label / ("model_" + str(args.iterations) + ".pt")
        if not final.exists():
            if (final.parent / "config.yaml").exists():
                raise RuntimeError("Incomplete policy run exists; no silent resume")
            launch(work, "train", plan["training_seed"] + 1000,
                   fine_overrides(work, plan, selected, label, args.task, args.iterations), "train_" + label, deadline)
        controllers[label] = str(final)
    results = {}
    # These first comparisons use fixed final policy checkpoints; no test-based checkpoint selection.
    for label, checkpoint in controllers.items():
        for seed in (8101, 8102, 8103):
            name = label + "_seed" + str(seed)
            launch(work, "eval", seed, tracking_overrides(work, checkpoint, name, args.task, plan, .2, seed), name, deadline)
            results[name] = json.loads((work / "tracking" / (name + ".json")).read_text())
    write(work / "tracking_comparison.json", {"task": args.task, "training_seeds": 1,
          "policy_checkpoint_selection": "Fixed final iteration, not selected using evaluation seeds", "results": results})
    write(work / "status.json", {"stage": "asap_closed_loop_comparison", "status": "complete",
          "finished_utc": datetime.now(timezone.utc).isoformat(), "scope": "One motion; one training seed; SPI/UAN not included"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--task", default="SquatL1", choices=("SquatL1", "StepFBL1", "CR7"))
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--cutoff", default="2026-10-09T09:00:00+00:00")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        write(args.work_dir / "status.json", {"status": "failed", "error": str(error),
              "at_utc": datetime.now(timezone.utc).isoformat()})
        raise
