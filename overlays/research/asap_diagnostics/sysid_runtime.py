"""Parallel recorded-input replay with candidate ankle PD gains, no correction."""
import json
from pathlib import Path

import torch

from research.asap_diagnostics.dataset_runtime import GridDeltaReplay


class CandidateGainReplay(GridDeltaReplay):
    def _init_motion_lib(self):
        super()._init_motion_lib()
        manifest = json.loads(Path(self.config.sysid_manifest).read_text())
        keys = list(self._motion_lib._motion_data_keys)
        if set(keys) != set(manifest):
            raise ValueError("Candidate manifest and replay clips differ")
        self.candidate_gains = torch.tensor([manifest[k] for k in keys],
                                            dtype=torch.float32, device=self.device)

    def _compute_torques(self, actions):
        # The network output is deliberately unused. Every input comes from D.
        nominal = self.get_open_loop_action_at_current_timestep()
        error = self.default_dof_pos + self.config.robot.control.action_scale * nominal - self.simulator.dof_pos
        torque = self._kp_scale * self.p_gains * error - self._kd_scale * self.d_gains * self.simulator.dof_vel
        unique_ids = self._motion_lib._curr_motion_ids[self.motion_ids]
        gains = self.candidate_gains[unique_ids]
        for joint, axis in ((4, 0), (5, 1), (10, 0), (11, 1)):
            torque[:, joint] = self._kp_scale[:, joint] * gains[:, axis] * error[:, joint] - self._kd_scale[:, joint] * self.d_gains[joint] * self.simulator.dof_vel[:, joint]
        return torch.clip(torque, -self.torque_limits, self.torque_limits) if self.config.robot.control.clip_torques else torque
