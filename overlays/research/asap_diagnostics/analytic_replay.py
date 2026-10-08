"""Known ankle-gain diagnostics; never used by ordinary training/evaluation.

Select this environment explicitly via Hydra's env._target_. The 50 Hz mode
holds the computed delta like a policy. The 200 Hz mode recomputes it at each
physics substep and is an implementation control, not a learned-policy baseline.
"""
import torch

from humanoidverse.envs.delta_a.delta_a_open_loop import DeltaA_OpenLoop


def ankle_gain_delta(nominal, position, default_position, action_scale,
                     gain_ratio, ankle_indices):
    if action_scale <= 0 or not 0 < gain_ratio <= 1:
        raise ValueError("Require positive action_scale and 0 < target/source Kp <= 1")
    if nominal.shape != position.shape:
        raise ValueError("Nominal action and position shapes must agree")
    delta = torch.zeros_like(nominal)
    idx = list(ankle_indices)
    error_in_action_units = nominal + (default_position - position) / action_scale
    delta[:, idx] = (gain_ratio - 1) * error_in_action_units[:, idx]
    return delta


class DiagnosticAnkleReplay(DeltaA_OpenLoop):
    def __init__(self, config, device):
        super().__init__(config, device)
        self.diagnostic_mode = self.config.get("diagnostic_delta_mode", "analytic_control")
        if self.diagnostic_mode not in ("analytic_control", "analytic_substep"):
            raise ValueError("Select analytic_control or analytic_substep")
        if self.config.robot.control.control_type != "P":
            raise ValueError("Analytic ankle compensation requires position PD control")
        if not self.config.get("add_extra_action", False) or self.config.get("zero_delta_a", False):
            raise ValueError("Require add_extra_action=True and zero_delta_a=False")
        if not self.config.get("anklePR", False):
            raise ValueError("Require anklePR=True for the four-ankle diagnostic")
        random_flags = ("randomize_ctrl_delay", "randomize_pd_gain", "randomize_torque_rfi")
        if any(self.config.domain_rand.get(key, False) for key in random_flags):
            raise ValueError("Disable delay, gain randomization, and torque noise")
        names = list(self.config.robot.dof_names)
        ankles = ("left_ankle_pitch_joint", "left_ankle_roll_joint",
                  "right_ankle_pitch_joint", "right_ankle_roll_joint")
        self.diagnostic_ankle_indices = tuple(names.index(name) for name in ankles)
        if self.diagnostic_ankle_indices != (4, 5, 10, 11):
            raise ValueError("This diagnostic expects the stock 23 DOF G1 ankle mask")
        self.diagnostic_gain_ratio = float(self.config.get("diagnostic_gain_ratio", 0.8))
        self.diagnostic_clip_count = 0
        self.diagnostic_component_count = 0

    def _analytic_delta(self):
        delta = ankle_gain_delta(
            self.get_open_loop_action_at_current_timestep(), self.simulator.dof_pos,
            self.default_dof_pos, float(self.config.robot.control.action_scale),
            self.diagnostic_gain_ratio, self.diagnostic_ankle_indices)
        limit = float(self.config.robot.control.action_clip_value)
        # Match the learned policy's action bound. Saturation can break exact
        # torque equivalence; expose it rather than silently ignoring it.
        self.diagnostic_clip_count += int((delta.abs() > limit).sum().item())
        self.diagnostic_component_count += delta.numel()
        fraction = self.diagnostic_clip_count / self.diagnostic_component_count
        self.log_dict["diagnostic_analytic_clip_fraction"] = fraction
        if self.diagnostic_clip_count:
            raise ValueError("Analytic delta exceeds the policy action bound")
        return torch.clip(delta, -limit, limit)

    def _pre_physics_step(self, actions):
        # Initialize the held action once per control step in both modes.
        # In substep mode, the recorded action is this first value only;
        # subsequent physics-substep corrections are not calibration data.
        super()._pre_physics_step(self._analytic_delta())

    def _compute_torques(self, actions):
        if self.diagnostic_mode == "analytic_substep":
            actions = self._analytic_delta()
        return super()._compute_torques(actions)
