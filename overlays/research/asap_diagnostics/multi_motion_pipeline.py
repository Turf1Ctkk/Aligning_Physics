"""Server workflow: collect diverse Kp16 rollouts, split, train, evaluate.

All GPU work runs in separate seeded IsaacGym subprocesses. This manager is CPU
only. `prepare` resolves paths and freezes the experiment plan before `run`.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import joblib
import numpy as np
import yaml

from dataset_tools import continuous_segments, fingerprint, replay_metrics, slice_motion


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "research/asap_diagnostics/seeded_entry.py"
TASKS = ("CR7", "SquatL1", "StepFBL1")
RECORDER = "research.asap_diagnostics.dataset_runtime.RolloutRecorderPPO"
REPLAY_ENV = "research.asap_diagnostics.dataset_runtime.GridDeltaReplay"


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def checkpoint_info(checkpoint):
    checkpoint = Path(checkpoint).expanduser().resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    config_path = checkpoint.parent / "config.yaml"
    if not config_path.exists():
        config_path = checkpoint.parent.parent / "config.yaml"
    config = yaml.safe_load(config_path.read_text())
    if "LeggedRobotMotionTracking" not in config["env"]["_target_"]:
        raise ValueError("Not a pretrained motion-tracking checkpoint: " + str(checkpoint))
    ref_path = Path(config["robot"]["motion"]["motion_file"])
    ref_path = ref_path if ref_path.is_absolute() else ROOT / ref_path
    references = joblib.load(ref_path)
    if len(references) != 1:
        raise ValueError("Expected a single-motion pretrained policy: " + str(ref_path))
    reference = next(iter(references.values()))
    frames = len(reference["root_trans_offset"])
    duration = (frames - 1) / float(reference["fps"])
    if config["robot"]["dof_obs_size"] != 23:
        raise ValueError("Expected 23 DOF policy")
    control = config["robot"]["control"]
    for ankle in ("ankle_pitch", "ankle_roll"):
        if control["stiffness"][ankle] != 20:
            raise ValueError("Source ankle Kp must be 20: " + str(checkpoint))
    if control["action_scale"] != 0.25 or config["robot"]["asset"]["self_collisions"] != 0:
        raise ValueError("Expected action_scale=.25 and self_collisions=0")
    sim = config["simulator"]["config"]["sim"]
    if sim["fps"] != 200 or sim["control_decimation"] != 4:
        raise ValueError("Expected 200 Hz physics / 50 Hz control")
    info = {"checkpoint": str(checkpoint), "source_config": str(config_path),
            "reference": str(ref_path), "reference_duration_s": duration,
            "record_steps": max(55, int(math.floor(duration * 50)) - 4)}
    return info, config


def classify(config):
    text = (config.get("experiment_name", "") + " " + config["robot"]["motion"]["motion_file"]).lower()
    if "cr7" in text or "ronaldo" in text:
        return "CR7"
    if "squatl1" in text or "squat_level1" in text:
        return "SquatL1"
    if "stepfbl1" in text or "step_forward_back_level1" in text:
        return "StepFBL1"
    return None


def prepare(args):
    work = args.work_dir.resolve()
    if (work / "plan.json").exists():
        print("Plan already exists:", work / "plan.json")
        print((work / "plan.json").read_text())
        return
    if args.rollouts < 16:
        raise ValueError("Use at least 16 rollouts per motion; default is 40")
    explicit = {"CR7": args.cr7, "SquatL1": args.squat, "StepFBL1": args.step}
    # With three explicit paths, no logs discovery or rg installation is needed.
    filenames = []
    if any(path is None for path in explicit.values()):
        if shutil.which("rg"):
            inventory = subprocess.run(["rg", "--files", "--no-ignore", "-g", "config.yaml", "logs"],
                                       cwd=ROOT, capture_output=True, text=True)
            if inventory.returncode not in (0, 1):
                raise RuntimeError(inventory.stderr)
            filenames = inventory.stdout.splitlines()
        else:
            filenames = list((ROOT / "logs").rglob("config.yaml"))
    candidates = {task: [] for task in TASKS}
    for filename in filenames:
        path = ROOT / filename
        models = [p for p in path.parent.glob("model_*.pt") if re.fullmatch(r"model_\d+\.pt", p.name)]
        if not models:
            continue
        config = yaml.safe_load(path.read_text())
        if "LeggedRobotMotionTracking" not in config.get("env", {}).get("_target_", ""):
            continue
        task = classify(config)
        if task:
            candidates[task].extend(models)
    selected, physics = {}, []
    for task in TASKS:
        checkpoint = explicit[task]
        if checkpoint is None:
            if not candidates[task]:
                raise ValueError("No checkpoint found for " + task + "; supply --cr7/--squat/--step")
            checkpoint = max(candidates[task], key=lambda p: (p.stat().st_mtime, int(p.stem.split('_')[-1])))
        info, config = checkpoint_info(checkpoint)
        selected[task] = info
        physics.append({"control": config["robot"]["control"],
                        "asset": config["robot"]["asset"],
                        "joint_names": config["robot"]["dof_names"],
                        "default_angles": config["robot"]["init_state"]["default_joint_angles"],
                        "sim": config["simulator"]["config"]["sim"]})
        print(task, "->", info["checkpoint"], "duration", round(info["reference_duration_s"], 3), "s")
    if not all(item == physics[0] for item in physics[1:]):
        raise ValueError("The three source policies have different robot/physics settings; inspect configs")
    open_source = (ROOT / "humanoidverse/envs/delta_a/delta_a_open_loop.py").read_text()
    lib_source = (ROOT / "humanoidverse/utils/motion_lib/motion_lib_base.py").read_text()
    if "def _get_reference_motion_times" not in open_source or "nearest_frame" not in lib_source or "_apply_recorded_velocities" not in lib_source:
        raise ValueError("Apply the existing timing and replay fidelity patches first")
    plan = {"version": 1, "tasks": selected, "rollouts_per_motion": args.rollouts,
            "collection_seed": args.seed, "training_seed": args.seed + 10000,
            "initial_noise_level": 0.2, "horizon_s": 1.0,
            "iterations": args.iterations, "training_num_envs": args.num_envs,
            "validation_checkpoints": sorted(set((args.iterations // 2, args.iterations))),
            "source_kp": 20, "target_kp": 16,
            "selection_metric": "validation equal-task/equal-rollout global_body_mpjpe_mm at 1 s"}
    if args.iterations < 200 or args.iterations % 200:
        raise ValueError("iterations must be a multiple of 200; default 1000")
    write_json(work / "plan.json", plan)
    print("Plan:", work / "plan.json")
    print("Next: run this script with `run --work-dir", work, "`")


def launch(work, mode, seed, overrides, log_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(ENTRY), mode, "--rng-seed", str(seed)] + overrides
    write_json(log_path.with_suffix(".command.json"), {"command": command, "cwd": str(ROOT), "seed": seed})
    print("Launching", mode, "log:", log_path, flush=True)
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = str(seed)
    with log_path.open("w") as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print("\n".join(log_path.read_text(errors="replace").splitlines()[-45:]), flush=True)
        raise RuntimeError("Subprocess failed; inspect " + str(log_path))


def collect(work, plan):
    for task_index, task in enumerate(TASKS):
        info = plan["tasks"][task]
        raw = work / "raw" / (task + ".pkl")
        if raw.exists():
            print("Using existing raw file:", raw, flush=True)
            continue
        overrides = [
            "+checkpoint=" + info["checkpoint"], "+headless=True",
            "++seed=" + str(plan["collection_seed"] + task_index),
            "+num_envs=" + str(plan["rollouts_per_motion"]), "+opt=record",
            "++algo._target_=" + RECORDER,
            "++eval_log_dir=" + str(work / "collection_configs" / task),
            "++robot.control.stiffness.ankle_pitch=16", "++robot.control.stiffness.ankle_roll=16",
            "++robot.asset.self_collisions=0", "++env.config.save_motion=False",
            "++env.config.resample_motion_when_training=False",
            "++env.config.enforce_randomize_motion_start_eval=False",
            "++env.config.noise_to_initial_level=0.2",
            "++env.config.init_noise_scale.root_pos=0.0", "++env.config.init_noise_scale.root_rot=0.0",
            "++domain_rand.randomize_ctrl_delay=False", "++domain_rand.randomize_pd_gain=False",
            "++domain_rand.randomize_torque_rfi=False", "++domain_rand.push_robots=False",
            "++domain_rand.randomize_friction=False", "++domain_rand.randomize_link_mass=False",
            "++domain_rand.randomize_base_com=False", "++domain_rand.randomize_base_mass=False",
            "++domain_rand.randomize_motion_ref_xyz=False", "++domain_rand.motion_package_loss=False",
            "++env.config.dataset_record_path=" + str(raw),
            "++env.config.dataset_record_steps=" + str(info["record_steps"]),
        ]
        launch(work, "eval", plan["collection_seed"] + task_index, overrides,
               work / "raw" / (task + ".log"))
        if not raw.exists():
            raise RuntimeError("Collector returned without creating " + str(raw))


def build(work, plan):
    data_dir = work / "datasets"
    data_dir.mkdir(exist_ok=True)
    n = plan["rollouts_per_motion"]
    train_end = int(n * 0.75)
    val_end = train_end + (n - train_end) // 2
    partitions = {split: {} for split in ("train", "val", "test")}
    groups = {task: [] for task in TASKS}
    report = {"tasks": {}, "duplicates": [], "split_unit": "original environment rollout, before segment/window creation"}
    seen = {}
    for task in TASKS:
        raw = joblib.load(work / "raw" / (task + ".pkl"))
        if len(raw) != n:
            raise ValueError("Raw rollout count differs from frozen plan")
        audit = []
        first_ankles = []
        for env_index in range(n):
            group = task + "__rollout" + str(env_index).zfill(3)
            split = "train" if env_index < train_end else "val" if env_index < val_end else "test"
            segments, details = continuous_segments(raw["motion" + str(env_index)], plan["horizon_s"])
            details.update({"group": group, "split": split, "usable_segments": len(segments)})
            audit.append(details)
            for index, (start, stop, motion) in enumerate(segments):
                digest = fingerprint(motion)
                if digest in seen:
                    report["duplicates"].append({"group": group, "duplicate_of": seen[digest]})
                    continue
                seen[digest] = group
                key = group + "__segment" + str(index)
                motion.update({"dataset_task": task, "dataset_group": group,
                               "source_rows": [start, stop]})
                partitions[split][key] = motion
                first_ankles.append(motion['dof'][0, [4,5,10,11]])
            if split == "train" and any(m["dataset_group"] == group for m in partitions[split].values()):
                groups[task].append(group)
        report["tasks"][task] = {
            "rollouts": audit,
            "first_recorded_ankle_std_rad": np.std(np.asarray(first_ankles), axis=0).tolist() if first_ankles else [],
            "usable_rollout_groups": len({m['dataset_group'] for split in partitions.values()
                                           for m in split.values() if m['dataset_task'] == task}),
        }
    write_json(work / "dataset_audit.json", report)
    minimum = min(len(groups[task]) for task in TASKS)
    if minimum < 10:
        raise ValueError("Fewer than 10 usable distinct training rollouts in one task; inspect dataset_audit.json")
    datasets = {}
    for name, count in (("balanced1", 1), ("balanced10", 10), ("balanced_full", minimum)):
        selected_groups = {g for task in TASKS for g in groups[task][:count]}
        motions = {key: motion for key, motion in partitions["train"].items()
                   if motion["dataset_group"] in selected_groups}
        path = data_dir / (name + ".pkl")
        joblib.dump(motions, path)
        datasets[name] = {"path": str(path), "rollout_groups": len(selected_groups), "clips": len(motions),
                          "groups_per_task": count,
                          "transitions": sum(len(m["dof"]) - 1 for m in motions.values()),
                          "valid_1s_grid_windows": sum(len(m["dof"]) - 51 for m in motions.values()),
                          "groups": sorted(selected_groups)}
    for split in ("val", "test"):
        if any(not any(m["dataset_task"] == task for m in partitions[split].values()) for task in TASKS):
            raise ValueError("No usable held-out rollout for one task in " + split)
        joblib.dump(partitions[split], data_dir / (split + ".pkl"))
        cases = {}
        frames = int(math.ceil(plan["horizon_s"] * 50)) + 2
        for key, motion in partitions[split].items():
            last = len(motion["dof"]) - frames
            for start in sorted(set((0, last // 2, last))):
                case = slice_motion(motion, start, start + frames)
                case["case_start_frame"] = start
                cases[key + "__start" + str(start).zfill(4)] = case
        joblib.dump(cases, data_dir / (split + "_cases.pkl"))
        datasets[split] = {"clips": len(partitions[split]), "cases": len(cases),
                           "rollout_groups": len({m["dataset_group"] for m in partitions[split].values()})}
    write_json(work / "dataset_summary.json", datasets)
    print(json.dumps({name: {key:value for key,value in item.items() if key != 'groups'}
                      for name,item in datasets.items()}, indent=2, ensure_ascii=False), flush=True)
    return datasets


def train(work, plan, datasets):
    for name in ("balanced1", "balanced10", "balanced_full"):
        output = work / "models" / name
        final = output / ("model_" + str(plan["iterations"]) + ".pt")
        if final.exists():
            print("Training already complete:", final, flush=True)
            continue
        if (output / "config.yaml").exists():
            raise ValueError("Incomplete training directory exists: " + str(output)
                             + ". Preserve/rename it before rerunning; no automatic checkpoint resume.")
        overrides = [
            "+simulator=isaacgym", "+exp=train_delta_a_open_loop", "+domain_rand=NO_domain_rand",
            "+rewards=motion_tracking/delta_a/reward_delta_a_openloop",
            "+robot=g1/g1_29dof_anneal_23dof", "+terrain=terrain_locomotion_plane", "+obs=delta_a/open_loop",
            "num_envs=" + str(plan["training_num_envs"]), "headless=True",
            "checkpoint=null", "auto_load_latest=False", "project_name=DeltaA_MultiMotion",
            "experiment_name=" + name, "experiment_dir=" + str(output),
            "++env._target_=" + REPLAY_ENV, "robot.motion.motion_file=" + datasets[name]["path"],
            "++robot.motion.use_recorded_velocities=True",
            "robot.control.stiffness.ankle_pitch=20", "robot.control.stiffness.ankle_roll=20",
            "robot.asset.self_collisions=0", "env.config.max_episode_length_s=1.0",
            "env.config.noise_to_initial_level=0", "env.config.resample_motion_when_training=True",
            "env.config.resample_time_interval_s=10000", "++env.config.add_extra_action=True",
            "++env.config.zero_delta_a=False", "++env.config.anklePR=True",
            "obs.noise_scales.base_pos_z=0.0", "obs.noise_scales.feet_contact_force=0.0",
            "rewards.reward_scales.penalty_minimal_action_norm=-0.1",
            "algo.config.init_at_random_ep_len=False", "algo.config.save_interval=100",
            "algo.config.num_learning_iterations=" + str(plan["iterations"]),
            "seed=" + str(plan["training_seed"]),
        ]
        launch(work, "train", plan["training_seed"], overrides, work / "models" / (name + ".log"))
        if not final.exists():
            raise RuntimeError("Training returned without final checkpoint")


def aggregate_cases(rows, horizon):
    metrics = [row["metrics"][str(horizon)] for row in rows]
    names = [name for name in metrics[0] if name.endswith(("_mm", "_rad", "_rad_s"))]
    tasks = {}
    for task in TASKS:
        selected = [row for row in rows if row["task"] == task]
        group_ids = sorted({row["group"] for row in selected})
        # Average windows inside each rollout, then rollouts inside each task.
        tasks[task] = {name: float(np.mean([
            np.mean([row["metrics"][str(horizon)][name] for row in selected if row["group"] == group])
            for group in group_ids])) for name in names}
    return {"equal_task_mean": {name: float(np.mean([tasks[t][name] for t in TASKS])) for name in names},
            "per_task": tasks, "complete_cases": sum(m["complete"] for m in metrics), "total_cases": len(metrics)}


def evaluate_batch(work, plan, checkpoint, split, label, kp=20, zero=False):
    output_dir = work / "evaluation" / split
    report_path = output_dir / (label + ".json")
    if report_path.exists():
        return json.loads(report_path.read_text())
    reference_path = work / "datasets" / (split + "_cases.pkl")
    references = joblib.load(reference_path)
    raw = output_dir / (label + ".pkl")
    overrides = [
        "+checkpoint=" + str(checkpoint), "+headless=True", "+num_envs=" + str(len(references)), "+opt=record",
        "++seed=" + str(plan["training_seed"] + 100),
        "++algo._target_=" + RECORDER, "++env._target_=" + REPLAY_ENV,
        "++eval_log_dir=" + str(output_dir / (label + "_config")),
        "++robot.motion.motion_file=" + str(reference_path), "++robot.motion.use_recorded_velocities=True",
        "++robot.control.stiffness.ankle_pitch=" + str(kp), "++robot.control.stiffness.ankle_roll=" + str(kp),
        "++robot.asset.self_collisions=0", "++env.config.dataset_evaluation=True",
        "++env.config.add_extra_action=True", "++env.config.zero_delta_a=" + str(zero),
        "++env.config.anklePR=True", "++env.config.noise_to_initial_level=0",
        "++env.config.enforce_randomize_motion_start_eval=False", "++env.config.save_motion=False",
        "++env.config.resample_motion_when_training=False",
        "++env.config.dataset_record_path=" + str(raw), "++env.config.dataset_record_steps=55",
    ]
    launch(work, "eval", plan["training_seed"] + 100, overrides, output_dir / (label + ".log"))
    predictions = joblib.load(raw)
    if len(predictions) != len(references):
        raise ValueError("Evaluation case count mismatch")
    rows = []
    for index, (key, ref) in enumerate(references.items()):
        pred = predictions["motion" + str(index)]
        rows.append({"key": key, "task": ref["dataset_task"], "group": ref["dataset_group"],
                     "metrics": {str(h): replay_metrics(ref, pred, h) for h in (0.25, 0.5, 1.0)}})
    report = {"checkpoint": str(checkpoint), "split": split, "kp": kp, "zero_delta": zero,
              "scope": "Replay errors on recorded Kp16 trajectories; 24 actual rigid bodies; no policy fine-tuning",
              "summary": {str(h): aggregate_cases(rows, h) for h in (0.25, 0.5, 1.0)}, "cases": rows}
    write_json(report_path, report)
    return report


def evaluate(work, plan):
    results = {}
    baseline_checkpoint = work / "models/balanced1" / ("model_" + str(plan["iterations"]) + ".pt")
    for split in ("val", "test"):
        results[split] = {
            "same16_zero": evaluate_batch(work, plan, baseline_checkpoint, split, "same16_zero", kp=16, zero=True),
            "source20_zero": evaluate_batch(work, plan, baseline_checkpoint, split, "source20_zero", zero=True),
        }
    choices = {}
    for name in ("balanced1", "balanced10", "balanced_full"):
        scored = []
        for iteration in plan["validation_checkpoints"]:
            checkpoint = work / "models" / name / ("model_" + str(iteration) + ".pt")
            label = name + "_" + str(iteration)
            report = evaluate_batch(work, plan, checkpoint, "val", label)
            results["val"][label] = report
            summary = report["summary"]["1.0"]
            if summary["complete_cases"] != summary["total_cases"]:
                raise ValueError("Incomplete validation replay; inspect " + label)
            scored.append((summary["equal_task_mean"]["global_body_mpjpe_mm"], iteration))
        _, chosen = min(scored)
        choices[name] = chosen
        checkpoint = work / "models" / name / ("model_" + str(chosen) + ".pt")
        results["test"][name] = evaluate_batch(work, plan, checkpoint, "test", name + "_selected")
    write_json(work / "selected_checkpoints.json", choices)
    compact = {split: {label: report["summary"] for label, report in items.items()}
               for split, items in results.items()}
    write_json(work / "comparison.json", compact)
    print("Held-out TEST, 1 s; equal-task/equal-rollout mean", flush=True)
    print("label | ankle(rad) | all-joint(rad) | joint-vel(rad/s) | root(mm) | global-body MPJPE(mm) | complete")
    for label, report in results["test"].items():
        summary = report["summary"]["1.0"]
        m = summary["equal_task_mean"]
        print(label, '|', round(m['ankle_rmse_rad'], 6), '|', round(m['all_joint_rmse_rad'], 6), '|',
              round(m['joint_velocity_rmse_rad_s'], 6), '|', round(m['root_position_mean_error_mm'], 3), '|',
              round(m['global_body_mpjpe_mm'], 3), '|', str(summary['complete_cases'])+'/'+str(summary['total_cases']))
    print("Results:", work / "comparison.json", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "collect", "build", "train", "evaluate", "run"))
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--cr7", type=Path)
    parser.add_argument("--squat", type=Path)
    parser.add_argument("--step", type=Path)
    parser.add_argument("--rollouts", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--num-envs", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=20261008)
    args = parser.parse_args()
    os.chdir(ROOT)
    work = args.work_dir.resolve()
    if args.stage == "prepare":
        prepare(args)
        return
    plan = json.loads((work / "plan.json").read_text())
    if args.stage in ("collect", "run"):
        collect(work, plan)
    if args.stage in ("build", "run"):
        build(work, plan)
    if args.stage in ("train", "run"):
        train(work, plan, json.loads((work / "dataset_summary.json").read_text()))
    if args.stage in ("evaluate", "run"):
        evaluate(work, plan)


if __name__ == "__main__":
    main()
