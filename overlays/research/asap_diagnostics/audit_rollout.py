"""CPU-only audit of trusted ASAP rollout/config files; does not run IsaacGym.

For stock post-step recordings, state[i] -- action[i+1] --> state[i+1].
This checks structural consistency, not physical replay correctness.
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import yaml


def load_config(path):
    return yaml.safe_load(Path(path).read_text())


def get(config, path):
    for key in path.split("."):
        if not isinstance(config, dict) or key not in config:
            return None
        config = config[key]
    return config


def config_summary(config):
    paths = [
        "env._target_", "algo._target_", "robot.control.action_scale",
        "robot.control.stiffness.ankle_pitch", "robot.control.stiffness.ankle_roll",
        "robot.control.damping.ankle_pitch", "robot.control.damping.ankle_roll",
        "robot.asset.self_collisions", "robot.motion.motion_file",
        "simulator.config.sim.fps", "simulator.config.sim.control_decimation",
        "env.config.max_episode_length_s", "env.config.anklePR",
        "domain_rand.randomize_ctrl_delay", "domain_rand.randomize_pd_gain",
        "domain_rand.push_robots", "algo.config.init_at_random_ep_len",
        "rewards.reward_scales.penalty_minimal_action_norm",
    ]
    return {path: get(config, path) for path in paths}


def audit_motion(motion, horizon):
    errors, notes = [], []
    required = ("action", "pose_aa", "root_trans_offset", "fps")
    missing = [key for key in required if key not in motion]
    if missing:
        return {"errors": ["Missing fields: " + ", ".join(missing)]}
    actions = np.asarray(motion["action"])
    if actions.ndim != 2 or actions.shape[1] != 23:
        return {"errors": [f"Expected action (T,23), got {actions.shape}"]}
    n = actions.shape[0]
    if n < 3:
        errors.append("Need at least three states for basic transition diagnostics")
    fps = float(motion["fps"])
    if not np.isfinite(fps) or fps <= 0:
        return {"errors": ["fps must be finite and positive"]}
    for key in ("pose_aa", "root_trans_offset", "dof", "dof_vel", "root_rot",
                "root_lin_vel", "root_ang_vel", "terminate", "motion_times"):
        if key in motion:
            value = np.asarray(motion[key])
            if value.ndim == 0 or value.shape[0] != n:
                errors.append(f"{key}: expected leading dimension {n}, got {value.shape}")
            if not np.isfinite(value).all():
                errors.append(f"{key}: contains non-finite values")
    if not np.isfinite(actions).all():
        errors.append("action contains non-finite values")
    if np.asarray(motion["root_trans_offset"]).shape != (n, 3):
        errors.append("root_trans_offset must have shape (T,3)")
    pose = np.asarray(motion["pose_aa"])
    if pose.ndim != 3 or pose.shape[-1] != 3:
        errors.append("pose_aa must have shape (T,J,3)")
    terminations = []
    if "terminate" in motion:
        term = np.asarray(motion["terminate"])
        if term.shape[0] == n:
            terminations = np.flatnonzero(term.reshape(n, -1).any(axis=1)).tolist()
            if terminations:
                errors.append("Contains reset rows; split episodes and remove reset rows before replay")
    else:
        notes.append("No terminate field: episode continuity cannot be verified")
    time_discontinuities = []
    if "motion_times" in motion:
        times = np.asarray(motion["motion_times"]).reshape(-1)
        if times.size == n:
            time_discontinuities = np.flatnonzero(
                ~np.isclose(np.diff(times), 1.0 / fps, atol=1e-5, rtol=1e-3)
            ).tolist()
            if time_discontinuities:
                errors.append("motion_times has jumps or reset boundaries")
    notes.append("Stock loader reconstructs velocities instead of reading saved velocity fields")
    result = {
        "frames": n, "fps": fps, "duration_s": (n - 1) / fps,
        "transitions": max(n - 1, 0), "termination_rows": terminations,
        "time_discontinuity_after_rows": time_discontinuities,
        "action_abs_max": float(np.max(np.abs(actions))) if n else None,
        "errors": errors, "notes": notes,
    }
    if n:
        result["valid_grid_starts_for_horizon"] = max(n - int(np.ceil(horizon * fps)), 0)
        result["stock_uniform_start_fraction_with_shorter_tail"] = (
            min(horizon / ((n - 1) / fps), 1.0) if n > 1 else 1.0
        )
    q = np.asarray(motion.get("dof", []))
    vel = np.asarray(motion.get("dof_vel", []))
    if q.shape == (n, 23) and vel.shape == (n, 23) and n > 1:
        # This is the loader's forward difference for all non-terminal frames.
        loader_vel = np.diff(q, axis=0) * fps
        result["loader_vs_recorded_joint_velocity_rmse_rad_s"] = float(
            np.sqrt(np.mean((loader_vel - vel[:-1]) ** 2))
        )
    return result


def torque_check(beta=0.8, scale=0.25):
    rng = np.random.default_rng(0)
    e, vel = rng.normal(size=(2, 10000))
    kp, kd = 20.0, 0.2
    delta_action = (beta - 1) * e / scale
    target = beta * kp * e - kd * vel
    source = kp * (e + scale * delta_action) - kd * vel
    return {
        "beta": beta, "action_scale": scale,
        "max_instantaneous_torque_error": float(np.max(np.abs(source - target))),
        "scope": "Same instantaneous state only; not a rollout/control-frequency test",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-config", type=Path)
    parser.add_argument("--delta-config", type=Path)
    parser.add_argument("--rollout", type=Path)
    parser.add_argument("--horizon", type=float, default=1.0)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if args.horizon <= 0:
        parser.error("--horizon must be positive")
    report = {"analytic_sanity_check": torque_check()}
    configs = {}
    for name, path in (("source", args.source_config), ("delta", args.delta_config)):
        if path:
            configs[name] = load_config(path)
            report[name + "_config"] = config_summary(configs[name])
    if len(configs) == 2:
        # Differences are review items, not proof of an error. Some are intentional.
        paths = ["robot.control", "robot.asset", "simulator.config.sim", "terrain",
                 "domain_rand"]
        report["physics_sections_requiring_review"] = [
            path for path in paths if get(configs["source"], path) != get(configs["delta"], path)
        ]
    if args.rollout:
        data = joblib.load(args.rollout)
        if not isinstance(data, dict) or not data:
            parser.error("Expected nonempty motion-name -> motion dictionary")
        report["motions"] = {name: audit_motion(motion, args.horizon)
                             for name, motion in data.items()}
    result = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    print(result)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(result + "\n")
    bad = any(motion.get("errors") for motion in report.get("motions", {}).values())
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
