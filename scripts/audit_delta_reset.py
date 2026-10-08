"""Check the installed delta reset path on CPU, without importing the simulator."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import torch


def methods(path):
    return {n.name: n for c in ast.parse(path.read_text()).body
            if isinstance(c, ast.ClassDef) for n in c.body
            if isinstance(n, ast.FunctionDef)}


def function(path, name):
    namespace = {}
    node = methods(path)[name]
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


def audit(root):
    base = root / "humanoidverse/envs/legged_base_task/legged_robot_base.py"
    motion = root / "humanoidverse/envs/motion_tracking/motion_tracking.py"
    closed = root / "humanoidverse/envs/delta_a/delta_a_closed_loop.py"
    # A subclass override would require auditing that path instead.
    for path in (motion, closed):
        if "_reset_buffers_callback" in methods(path):
            raise ValueError(f"Reset override exists; inspect its behavior: {path}")
    env = SimpleNamespace(history_handler=SimpleNamespace(reset=lambda ids: None),
                          _update_average_episode_length=lambda ids: None)
    for name in ("actions", "last_actions", "actions_after_delay", "last_dof_pos", "last_dof_vel"):
        setattr(env, name, torch.ones(2, 23))
    for name in ("feet_air_time", "episode_length_buf", "reset_buf"):
        setattr(env, name, torch.ones(2))
    env.actions_closed_loop = torch.full((2, 23), 0.4)
    function(base, "_reset_buffers_callback")(env, torch.tensor([0]))
    nominal = function(base, "_get_obs_actions")(env)
    delta = function(closed, "_get_obs_actions_closed_loop")(env)
    assert torch.all(nominal[0] == 0), "Nominal reset contract differs"
    assert torch.all(nominal[1] == 1), "Non-reset environment changed"
    return {
        "scope": "CPU execution of installed methods with synthetic buffers; no physics or training",
        "synthetic_previous_delta": 0.4,
        "nominal_after_reset_max_abs": float(nominal[0].abs().max()),
        "delta_observation_after_reset_max_abs": float(delta[0].abs().max()),
        "previous_episode_delta_retained": bool(torch.any(delta[0] != 0)),
        "nonreset_environment_unchanged": bool(torch.all(nominal[1] == 1)),
        "performance_effect": "Not measured; this audit does not explain a success-rate change",
        "files": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in (base, motion, closed)},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asap-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.asap_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
