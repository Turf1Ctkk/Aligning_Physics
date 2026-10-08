"""Exercise the proposed patch in a temporary directory, without IsaacGym."""
import ast
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

import torch
from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[2]
PATCH = Path(__file__).resolve().with_name("timing_and_delta_units.patch")
FILES = (
    "humanoidverse/envs/motion_tracking/motion_tracking.py",
    "humanoidverse/envs/delta_a/delta_a_open_loop.py",
    "humanoidverse/envs/delta_a/delta_a_closed_loop.py",
    "humanoidverse/agents/delta_a/train_delta_a.py",
)


def method(path, name):
    tree = ast.parse(path.read_text())
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(functions) == 1, name
    namespace = {"torch": torch}
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace[name]


def torque_env(nominal, delta):
    cfg = OmegaConf.create({
        "add_extra_action": True,
        "robot": {"control": {"action_scale": 0.25, "control_type": "P",
                               "clip_torques": False}},
        "domain_rand": {"cotrain_with_without_delta_a": False,
                        "rescale_delta_a": False, "randomize_torque_rfi": False},
    })
    return SimpleNamespace(
        config=cfg, _kp_scale=1., _kd_scale=1.,
        p_gains=torch.ones(23) * 20., d_gains=torch.ones(23) * 0.2,
        default_dof_pos=torch.zeros(1, 23),
        simulator=SimpleNamespace(dof_pos=torch.ones(1, 23) * 0.1,
                                  dof_vel=torch.ones(1, 23) * 0.2),
        get_open_loop_action_at_current_timestep=lambda: nominal.clone(),
        get_closed_loop_action_at_current_timestep=lambda: delta.clone(),
        delta_action_dof_heatmaps=torch.zeros(1, 23),
        detla_action_percentage_heatmaps=torch.zeros(1, 23), delta_action_cnt=1,
    )


def main():
    with tempfile.TemporaryDirectory(prefix="asap-contracts-") as directory:
        staged = Path(directory)
        for filename in FILES:
            target = staged / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / filename, target)
        subprocess.run(["git", "apply", str(PATCH)], cwd=staged, check=True)
        torch.manual_seed(0)
        nominal = torch.rand(5, 23) + 0.1
        delta = torch.randn(5, 23) * 0.2
        with contextlib.redirect_stdout(io.StringIO()):
            open_torque = method(staged / FILES[1], "_compute_torques")(
                torque_env(nominal, delta), delta.clone())
            closed_torque = method(staged / FILES[2], "_compute_torques")(
                torque_env(nominal, delta), nominal.clone())
            original_closed = method(ROOT / FILES[2], "_compute_torques")(
                torque_env(nominal, delta), nominal.clone())
        assert torch.allclose(open_torque, closed_torque)
        assert not torch.allclose(open_torque, original_closed)

        fake = SimpleNamespace(episode_length_buf=torch.tensor([1]), dt=0.02,
                               motion_start_times=torch.tensor([0.0]))
        task_time = method(staged / FILES[0], "_get_reference_motion_times")(fake)
        replay_time = method(staged / FILES[1], "_get_reference_motion_times")(fake)
        assert torch.allclose(task_time, torch.tensor([0.04]))
        assert torch.allclose(replay_time, torch.tensor([0.02]))

        keys = ["base_pos_z", "feet_contact_force", "base_lin_vel", "base_ang_vel",
                "projected_gravity", "dof_pos", "dof_vel", "actions_closed_loop",
                "actions_sim2real_policy"]
        dims = {"base_pos_z": 1, "feet_contact_force": 6, "base_lin_vel": 3,
                "base_ang_vel": 3, "projected_gravity": 3, "dof_pos": 23,
                "dof_vel": 23, "actions_closed_loop": 23, "actions_sim2real_policy": 23}
        cfg = OmegaConf.create({
            "obs": {"obs_dict": {"closed_loop_actor_obs": keys}, "obs_dims": dims,
                    "obs_scales": {key: 1.0 for key in keys}},
            "robot": {"control": {"action_clip_value": 100.0}},
            "normalization": {"clip_observations": 100.0},
        })
        captured = []
        def delta_policy(obs):
            captured.append(obs.clone())
            return torch.zeros(obs.shape[0], 23)
        fake = SimpleNamespace(env=SimpleNamespace(config=cfg),
                               loaded_policy=SimpleNamespace(eval_policy=delta_policy))
        obs = torch.zeros(5, sum(dims.values()))
        before = obs.clone()
        result = method(staged / FILES[3], "_infer_delta_for_current_action")(
            fake, {"closed_loop_actor_obs": obs}, nominal)
        assert result.shape == (5, 23)
        assert torch.equal(obs, before), "Do not mutate PPO's stored observation"
        assert torch.equal(captured[0][:, :23], before[:, :23]), "Preserve previous delta"
        assert torch.equal(captured[0][:, 23:46], nominal), "Use current nominal action"
        assert torch.equal(captured[0][:, 46:], before[:, 46:]), "Preserve state features"
        print("PASS: open/closed delta units, post-step reference time, current-action conditioning.")
        print("Scope: CPU tensor contracts only; no physics rollout or RL training was run.")


if __name__ == "__main__":
    main()
