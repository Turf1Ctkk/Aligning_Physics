"""Actual 5ms target collection, with 50Hz base commands and 200Hz excitation."""
from pathlib import Path

import joblib
import torch

from research.asap_diagnostics.active_runtime import NominalGainReplay


class WaveGainReplay(NominalGainReplay):
    def _init_motion_lib(self):
        super()._init_motion_lib()
        tables = joblib.load(Path(self.config.wave_tables))
        keys = list(self._motion_lib._motion_data_keys)
        if set(keys) != set(tables):
            raise ValueError("Wave tables and acquisition clips differ")
        self.wave_commands = torch.tensor([tables[key].tolist() for key in keys], device=self.device)

    def get_open_loop_action_at_current_timestep(self):
        time = self.episode_length_buf * self.dt + self.motion_start_times
        ids = self.motion_ids
        frame_dt = self._motion_lib._motion_dt[ids]
        # Hold each original 50Hz command for four true physics steps.
        frame = torch.floor(time / frame_dt + 1e-5)
        nominal = self._motion_lib.get_motion_actions(ids, (frame + 1) * frame_dt).clone()
        wave_frame = torch.floor(time / self.dt + 1e-5).long()
        if torch.any(wave_frame >= self.wave_commands.shape[1]):
            raise ValueError("Acquisition exceeds the predeclared excitation table")
        unique_ids = self._motion_lib._curr_motion_ids[ids]
        nominal[:, [4, 5, 10, 11]] += self.wave_commands[unique_ids, wave_frame] / self.config.robot.control.action_scale
        return nominal
