"""CPU checks for the live known-gain diagnostic, without importing IsaacGym."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import torch
from omegaconf import OmegaConf


SOURCE = Path(__file__).with_name("analytic_replay.py")


def load_diagnostic(base):
    tree = ast.parse(SOURCE.read_text())
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    namespace = {"torch": torch, "DeltaA_OpenLoop": base}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 str(SOURCE), "exec"), namespace)
    return namespace["ankle_gain_delta"], namespace["DiagnosticAnkleReplay"]


def main():
    class FakeBase:
        def __init__(self, config, device):
            self.config = config
            self.default_dof_pos = torch.zeros(1, 23, dtype=torch.float64)
            self.simulator = SimpleNamespace(dof_pos=torch.full((1, 23), 0.1, dtype=torch.float64))
            self.nominal = torch.full((1, 23), 0.4, dtype=torch.float64)
            self.log_dict = {}

        def get_open_loop_action_at_current_timestep(self):
            return self.nominal.clone()

        def _pre_physics_step(self, actions):
            self.actions = actions.clone()
            self.actions_after_delay = actions.clone()

        def _compute_torques(self, actions):
            return actions.clone()

    delta_fn, diagnostic = load_diagnostic(FakeBase)
    idx = (4, 5, 10, 11)
    names = ["joint_" + str(i) for i in range(23)]
    for i, name in zip(idx, ("left_ankle_pitch_joint", "left_ankle_roll_joint",
                             "right_ankle_pitch_joint", "right_ankle_roll_joint")):
        names[i] = name
    config = OmegaConf.create({
        "diagnostic_delta_mode": "analytic_control", "diagnostic_gain_ratio": 0.8,
        "add_extra_action": True, "zero_delta_a": False, "anklePR": True,
        "robot": {"dof_names": names, "control": {"control_type": "P",
                   "action_scale": 0.25, "action_clip_value": 100.0}},
        "domain_rand": {"randomize_ctrl_delay": False, "randomize_pd_gain": False,
                        "randomize_torque_rfi": False},
    })
    torch.manual_seed(42)
    nominal = torch.randn(32, 23, dtype=torch.float64)
    position = torch.randn_like(nominal)
    default = torch.randn(1, 23, dtype=torch.float64)
    velocity = torch.randn_like(nominal)
    delta = delta_fn(nominal, position, default, 0.25, 0.8, idx)
    kp_source = torch.full((23,), 20., dtype=torch.float64)
    kp_target = kp_source.clone()
    kp_target[list(idx)] *= 0.8
    kd = torch.full((23,), 0.2, dtype=torch.float64)
    target_torque = kp_target * (0.25 * nominal + default - position) - kd * velocity
    source_torque = kp_source * (0.25 * (nominal + delta) + default - position) - kd * velocity
    torch.testing.assert_close(source_torque, target_torque, rtol=1e-12, atol=1e-12)
    nonankle = [i for i in range(23) if i not in idx]
    assert not delta[:, nonankle].any()
    # Equal pre-clipping torques remain equal under the same torque bound.
    assert torch.allclose(source_torque.clamp(-50, 50), target_torque.clamp(-50, 50))

    held = diagnostic(config, "cpu")
    held._pre_physics_step(torch.ones(1, 23))
    first = held.actions_after_delay.clone()
    assert torch.equal(first, held._analytic_delta())
    held.simulator.dof_pos += 0.025
    assert torch.equal(held._compute_torques(first), first), "50 Hz mode must hold the delta"
    sub_config = OmegaConf.merge(config, {"diagnostic_delta_mode": "analytic_substep"})
    live = diagnostic(sub_config, "cpu")
    live._pre_physics_step(torch.ones(1, 23))
    live.simulator.dof_pos += 0.025
    new = live._compute_torques(live.actions_after_delay)
    assert not torch.equal(new, live.actions_after_delay), "200 Hz mode must recompute the delta"
    assert torch.equal(new, live._analytic_delta())
    live.config.robot.control.action_clip_value = 0.001
    live.simulator.dof_pos += 1
    try:
        live._analytic_delta()
    except ValueError:
        pass
    else:
        raise AssertionError("Saturation must not be hidden")
    for bad in (-0.25, 0):
        try:
            delta_fn(nominal, position, default, bad, 0.8, idx)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid action scale was accepted")
    print(json.dumps({"instantaneous_torque_max_error": float((source_torque - target_torque).abs().max()),
                      "ankle_mask_and_50hz_hold_vs_200hz_update": "PASS",
                      "action_bound_check": "PASS",
                      "scope": "CPU formula and dispatch checks; no physics rollout or training"}, indent=2))


if __name__ == "__main__":
    main()
