"""CPU interface tests for shared actuator inference and four-substep commands."""
import ast
from pathlib import Path

import torch
from torch import nn
from torch.distributions import Normal


def extract(name, scope):
    source = Path(__file__).with_name("torque_runtime.py").read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == name)
    node.bases = [ast.Name(id="object", ctx=ast.Load())] if name == "TorqueReplay" else node.bases
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(Path(__file__).with_name("torque_runtime.py")), "exec"), scope)
    return scope[name]


def main():
    ankles = (4, 5, 10, 11)
    scope = {"torch": torch, "nn": nn, "Normal": Normal, "ANKLES": ankles}
    actor_type = extract("SharedTorqueActor", scope)
    actor = actor_type()
    obs = torch.randn(8, 160)
    assert torch.count_nonzero(actor.act_inference(obs)) == 0
    with torch.no_grad():
        actor.network[-1].weight.normal_()
    out = actor.act_inference(obs)
    other = [i for i in range(23) if i not in ankles]
    assert torch.count_nonzero(out[:, other]) == 0
    permuted = obs.reshape(8, 4, 40)[:, [2, 0, 3, 1]].reshape(8, 160)
    assert torch.allclose(actor.act_inference(permuted)[:, ankles], out[:, ankles][:, [2, 0, 3, 1]], atol=1e-6)
    actions = actor.act(obs)
    logp = actor.get_actions_log_prob(actions)
    assert logp.shape == (8,) and torch.isfinite(logp).all()
    (-logp.mean()).backward()
    assert torch.isfinite(actor.log_std.grad) and torch.isfinite(actor.network[0].weight.grad).all()
    # A 50Hz recorded command a[i+1] must be held for all four 200Hz steps.
    class Library:
        _motion_dt = torch.tensor([.02])
        def get_motion_actions(self, ids, times):
            return torch.round(times / .02).long()
    replay_type = extract("TorqueReplay", scope)
    replay = replay_type()
    replay._motion_lib = Library()
    replay.motion_ids = torch.tensor([0])
    replay.motion_start_times = torch.tensor([.04])
    replay.dt = .005
    indices = []
    for step in range(8):
        replay.episode_length_buf = torch.tensor([step])
        indices.append(int(replay.get_open_loop_action_at_current_timestep()))
    assert indices == [3, 3, 3, 3, 4, 4, 4, 4], indices
    print("PASS: zero initialization, joint sharing/masking, finite PPO gradients, 200Hz nominal-command holding")
    print("Scope: CPU tensor interfaces only; not physics or calibration performance")


if __name__ == "__main__":
    main()
