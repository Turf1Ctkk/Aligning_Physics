"""Audit completed task deployments using recordings, commands and saved configs."""
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import yaml

METHODS = ("vanilla", "ft_only", "asap_ft", "sysid_ft", "torque_ft", "active_sysid_ft", "wave_ft")
FIELDS = ("dof", "dof_vel", "root_trans_offset", "root_rot", "root_lin_vel", "root_ang_vel", "action")
CONFIG_PATHS = (
    ("obs", "obs_dict", "actor_obs"), ("obs", "noise_scales"), ("obs", "add_noise_currculum"),
    ("env", "config", "termination"), ("env", "config", "termination_scales"),
    ("env", "config", "termination_curriculum", "terminate_when_motion_far_curriculum"),
    ("env", "config", "noise_to_initial_level"), ("env", "config", "init_noise_scale"),
    ("simulator", "config", "sim"), ("robot", "control", "stiffness"), ("robot", "control", "damping"),
    ("robot", "motion", "motion_file"), ("robot", "asset", "self_collisions"),
    ("obs", "obs_auxiliary", "history_actor"),
)


def extract(config):
    result = {}
    for path in CONFIG_PATHS:
        value = config
        for key in path:
            value = value[key]
        result[".".join(path)] = value
    return result


def effective_extract(raw):
    """Compare actor-used noise and enabled thresholds; retain raw differences."""
    result = dict(raw)
    names = set(raw["obs.obs_dict.actor_obs"]) | set(raw["obs.obs_auxiliary.history_actor"])
    result["obs.noise_scales"] = {key: raw["obs.noise_scales"].get(key, 0) for key in sorted(names)}
    if any(result["obs.noise_scales"].values()):
        raise ValueError("Used task actor/history noise is nonzero")
    flag_for_scale = {
        "termination_close_to_dof_pos_limit": "terminate_when_close_to_dof_pos_limit",
        "termination_close_to_dof_vel_limit": "terminate_when_close_to_dof_vel_limit",
        "termination_close_to_torque_limit": "terminate_when_close_to_torque_limit",
        "termination_min_base_height": "terminate_by_low_height",
        "termination_gravity_x": "terminate_by_gravity",
        "termination_gravity_y": "terminate_by_gravity",
        "termination_motion_far_threshold": "terminate_when_motion_far",
    }
    result["env.config.termination_scales"] = {
        key: value for key, value in raw["env.config.termination_scales"].items()
        if key not in flag_for_scale or raw["env.config.termination"][flag_for_scale[key]]}
    return result


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_value(command, name):
    values = [arg.split("=", 1)[1] for arg in command if arg.lstrip("+").startswith(name + "=")]
    if len(values) != 1:
        raise ValueError(f"Expected one effective override for {name}: {values}")
    return values[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--baseline-directory", type=Path, help="External completed task evaluation used only for stored-state/settings checks")
    parser.add_argument("--baseline-method", choices=METHODS, default="ft_only")
    args = parser.parse_args()
    root, output = args.directory, args.output
    baseline_root = args.baseline_directory or root
    if len(args.methods) != len(set(args.methods)):
        raise ValueError("Duplicate audit method")
    output.mkdir(parents=True, exist_ok=True)
    if json.loads((root / "status.json").read_text())["status"] != "complete":
        raise ValueError("Task is incomplete; no completed comparison audit")
    if json.loads((baseline_root / "status.json").read_text())["status"] != "complete":
        raise ValueError("Declared baseline is incomplete")
    audit = {"scope": "First stored states/actions for all96 trials per selected method against declared baseline; saved settings and commands. Hidden simulator state is not independently verified. External baseline training seeds are not made equal by this audit",
             "baseline_directory": str(baseline_root), "baseline_method": args.baseline_method,
             "baseline_recording_sha256": {},
             "max_absolute_difference": {}, "raw_config": {}, "effective_config": {}, "raw_differences_from_baseline": {},
             "recording_sha256": {}, "evaluation_commands": {}, "policy_checkpoint_sha256": {}}
    for seed in (8101, 8102, 8103):
        baseline_path = baseline_root / "tracking" / f"{args.baseline_method}_seed{seed}.pkl"
        base = joblib.load(baseline_path)
        audit["baseline_recording_sha256"][str(seed)] = file_hash(baseline_path)
        baseline_config = extract(yaml.safe_load((baseline_root / "tracking" / f"{args.baseline_method}_seed{seed}_config/config.yaml").read_text()))
        for method in args.methods:
            label = f"{method}_seed{seed}"
            path = root / "tracking" / (label + ".pkl")
            target = joblib.load(path)
            if set(target) != {f"motion{i}" for i in range(32)} or set(base) != set(target):
                raise ValueError("Expected all32 motion records: " + label)
            difference = {key: max(float(np.max(np.abs(np.asarray(target[f"motion{i}"][key][0]) - np.asarray(base[f"motion{i}"][key][0]))))
                                   for i in range(32)) for key in FIELDS}
            if any(value != 0 for value in difference.values()):
                raise ValueError("Stored initialization mismatch: " + label + str(difference))
            audit["max_absolute_difference"].setdefault(method, {})[str(seed)] = difference
            selected = extract(yaml.safe_load((path.parent / (label + "_config/config.yaml")).read_text()))
            effective = effective_extract(selected)
            if effective != effective_extract(baseline_config):
                raise ValueError("Effective evaluation settings differ: " + label)
            audit["raw_config"][method] = selected
            audit["raw_differences_from_baseline"][method] = {key: {"method": value, "baseline": baseline_config[key]}
                                                           for key, value in selected.items() if value != baseline_config[key]}
            audit["effective_config"][method] = effective
            audit["recording_sha256"].setdefault(method, {})[str(seed)] = file_hash(path)
            command = json.loads((root / "commands" / (label + ".json")).read_text())["command"]
            steps = int(command_value(command, "env.config.dataset_record_steps"))
            if any(len(record["dof"]) != steps or not np.isclose(record["fps"], 50) for record in target.values()):
                raise ValueError("Recording length/rate mismatch: " + label)
            if command_value(command, "env._target_") != "humanoidverse.envs.motion_tracking.motion_tracking.LeggedRobotMotionTracking" or command_value(command, "env.config.add_extra_action") != "False":
                raise ValueError("Deployment correction interface remains attached: " + label)
            checkpoint = Path(command_value(command, "checkpoint"))
            audit["evaluation_commands"][label] = {"record_steps": steps, "horizon_s": steps / 50, "checkpoint": str(checkpoint),
                "task_only_environment": True, "extra_action": False}
            if seed == 8101:
                audit["policy_checkpoint_sha256"][method] = file_hash(checkpoint)
                joblib.dump({"motion0": target["motion0"]}, output / (method + "_seed8101_trial0.pkl"))
    horizons = {entry["horizon_s"] for entry in audit["evaluation_commands"].values()}
    if len(horizons) != 1:
        raise ValueError("Evaluation horizons differ")
    audit["evaluation_horizon_s"] = horizons.pop()
    if args.baseline_method == "ft_only":
        audit["raw_differences_from_ft_only"] = audit["raw_differences_from_baseline"]
    (output / "matched_state_config_audit.json").write_text(json.dumps(audit, indent=2))
    print(f"PASS: all96 initial stored states/actions per{len(args.methods)} selected methods; effective settings, task-only deployment and horizons match declared baseline; raw differences retained")


if __name__ == "__main__":
    main()
