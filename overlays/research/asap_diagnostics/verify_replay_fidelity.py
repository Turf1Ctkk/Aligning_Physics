"""CPU regression checks and optional inspection of real replay inputs."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

import joblib
import numpy as np
import torch
import yaml
from easydict import EasyDict


ROOT = Path(__file__).resolve().parents[2]
SOURCE = "humanoidverse/utils/motion_lib/motion_lib_base.py"
PATCH = Path(__file__).resolve().with_name("replay_fidelity.patch")


def method(path, name):
    matches = [node for node in ast.walk(ast.parse(path.read_text()))
               if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, name
    namespace = {"torch": torch, "to_torch": lambda value: torch.as_tensor(value)}
    module = ast.Module(body=matches, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace[name]


def action_indices(path, frames, fps, steps):
    # fk_batch stores int(fps); the stock library rebuilds length/dt from it.
    loader_fps = int(fps)
    dt = torch.tensor([1 / loader_fps], dtype=torch.float32)
    length = torch.tensor([(frames - 1) / loader_fps], dtype=torch.float32)
    desired = torch.arange(1, min(steps, frames - 1) + 1)
    times = desired * float(1 / fps)
    fake = SimpleNamespace(
        _motion_lengths=length, _motion_num_frames=torch.tensor([frames]),
        _motion_dt=dt, length_starts=torch.tensor([0]),
        _motion_actions=torch.arange(frames)[:, None])
    fake._calc_frame_blend = lambda *args: method(path, "_calc_frame_blend")(fake, *args)
    ids = torch.zeros(len(times), dtype=torch.long)
    old = fake._calc_frame_blend(times, length[ids], fake._motion_num_frames[ids], dt[ids])[0]
    fixed = method(path, "get_motion_actions")(fake, ids, times)[:, 0]
    assert torch.equal(fixed, desired), "Patched getter selected the wrong exact-grid action"
    # Away from integer boundaries, actions must remain zero-order-held.
    off_grid = (desired.float() - 0.4) / fps
    actual = method(path, "get_motion_actions")(fake, ids, off_grid)[:, 0]
    assert torch.equal(actual, desired - 1)
    bad = old != desired
    return {"frames": frames, "recorded_fps": fps, "stock_loader_fps": loader_fps,
            "legacy_wrong_indices_in_first_steps": int(bad.sum()),
            "expected_frame_indices": desired[bad].tolist(),
            "legacy_selected_frame_indices": old[bad].tolist(),
            "patched_wrong_indices_in_first_steps": int((fixed != desired).sum())}


def velocity_checks(path):
    helper = method(path, "_apply_recorded_velocities")
    n = 12
    recorded = {"dof_vel": np.arange(n * 23).reshape(n, 23).astype(np.float32),
                "root_lin_vel": np.arange(n * 3).reshape(n, 3).astype(np.float32),
                "root_ang_vel": np.arange(n * 3).reshape(n, 3).astype(np.float32) + 100}
    def fake_motion():
        return EasyDict(dof_pos=torch.zeros(8, 23), dof_vels=torch.zeros(8, 23),
                        global_velocity=torch.zeros(8, 24, 3),
                        global_angular_velocity=torch.zeros(8, 24, 3),
                        global_velocity_extend=torch.zeros(8, 27, 3),
                        global_angular_velocity_extend=torch.zeros(8, 27, 3))
    fake = SimpleNamespace(m_cfg={"use_recorded_velocities": True})
    motion = fake_motion()
    helper(fake, motion, recorded, 2, 10, None)
    assert torch.equal(motion.dof_vels, torch.as_tensor(recorded["dof_vel"][2:10]))
    assert torch.equal(motion.global_velocity[:, 0], torch.as_tensor(recorded["root_lin_vel"][2:10]))
    assert torch.equal(motion.global_angular_velocity[:, 0], torch.as_tensor(recorded["root_ang_vel"][2:10]))
    assert torch.equal(motion.global_velocity_extend[:, 0], motion.global_velocity[:, 0])
    assert torch.equal(motion.global_angular_velocity_extend[:, 0], motion.global_angular_velocity[:, 0])
    assert not motion.global_velocity[:, 1:].any(), "Do not overwrite non-root FK body velocities"
    fake.m_cfg["use_recorded_velocities"] = False
    motion = fake_motion()
    helper(fake, motion, {}, 2, 10, None)
    assert not motion.dof_vels.any(), "Default retargeted-reference behavior must remain unchanged"
    fake.m_cfg["use_recorded_velocities"] = True
    try:
        helper(fake, fake_motion(), {}, 2, 10, None)
    except ValueError:
        pass
    else:
        raise AssertionError("Missing recorded velocities must be rejected")
    try:
        helper(fake, fake_motion(), recorded, 2, 10, [0, 0, 0, 1])
    except ValueError:
        pass
    else:
        raise AssertionError("Heading changes require rotating world velocities; reject them for now")


def flatten(mapping, prefix=""):
    if not isinstance(mapping, dict):
        return {prefix: mapping}
    result = {}
    for key, value in mapping.items():
        result.update(flatten(value, prefix + "." + str(key) if prefix else str(key)))
    return result


def physics_differences(collection, replay):
    left = flatten(yaml.safe_load(collection.read_text()))
    right = flatten(yaml.safe_load(replay.read_text()))
    prefixes = ("robot.control.", "robot.asset.", "robot.init_state.default_joint_angles.",
                "simulator.config.sim.", "terrain.", "domain_rand.")
    return [{"key": key, "collection": left.get(key), "replay": right.get(key)}
            for key in sorted(set(left) | set(right))
            if key.startswith(prefixes) and left.get(key) != right.get(key)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollout", type=Path)
    parser.add_argument("--collection-config", type=Path)
    parser.add_argument("--replay-config", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="asap-replay-contracts-") as directory:
        staged = Path(directory)
        target = staged / SOURCE
        target.parent.mkdir(parents=True)
        shutil.copy2(ROOT / SOURCE, target)
        # Works before and after patch application; never edits the live checkout.
        check = subprocess.run(["git", "apply", "--reverse", "--check", str(PATCH)],
                               cwd=staged, capture_output=True)
        if check.returncode != 0:
            subprocess.run(["git", "apply", str(PATCH)], cwd=staged, check=True)
        velocity_checks(target)
        report = {"regression_fixture": action_indices(target, 188, 50., 55),
                  "recorded_velocity_contracts": "PASS",
                  "scope": "CPU checks only; does not run physics or train a model"}
        if args.rollout:
            report["actual_rollout"] = {}
            for key, motion in joblib.load(args.rollout).items():
                entry = action_indices(target, len(motion["action"]), float(motion["fps"]), 55)
                for saved in ("dof_vel", "root_lin_vel", "root_ang_vel"):
                    entry[saved + "_first_recorded_frame"] = np.asarray(motion[saved])[0].tolist()
                report["actual_rollout"][key] = entry
        if bool(args.collection_config) != bool(args.replay_config):
            parser.error("Pass both collection and replay config paths")
        if args.collection_config:
            report["physics_config_differences_to_review"] = physics_differences(
                args.collection_config, args.replay_config)
        result = json.dumps(report, indent=2, allow_nan=False)
        print(result)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(result + "\n")


if __name__ == "__main__":
    main()
