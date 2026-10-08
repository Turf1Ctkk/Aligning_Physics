"""Disclosed UAN-style shared actuator model in the G1 replay/task framework.

Residual inference and its measured simulated state history run at 200 Hz.
The initial matched-data experiment still has 50 Hz target recordings.
"""
from pathlib import Path

import joblib
import numpy as np

import torch
from torch import nn, optim
from torch.distributions import Normal

from humanoidverse.agents.ppo.ppo import PPO
from humanoidverse.agents.modules.ppo_modules import PPOCritic
from humanoidverse.envs.motion_tracking.motion_tracking import LeggedRobotMotionTracking
from research.asap_diagnostics.controlled_runtime import WeightedGridDeltaReplay
from research.asap_diagnostics.dataset_runtime import snapshot

ANKLES = (4, 5, 10, 11)
HISTORY = 20


class SharedTorqueActor(nn.Module):
    """A shared 40→128→128→1 MLP, independently applied to four ankles."""
    def __init__(self, noise=.8):
        super().__init__()
        self.network = nn.Sequential(nn.Linear(40, 128), nn.ELU(), nn.Linear(128, 128), nn.ELU(), nn.Linear(128, 1))
        # Begin at exactly zero deterministic torque correction.
        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)
        self.log_std = nn.Parameter(torch.tensor(float(noise)).log())
        self.distribution = None
        Normal.set_default_validate_args(False)

    def act_inference(self, obs):
        features = obs.reshape(-1, 4, 40)
        ankles = self.network(features).squeeze(-1)
        output = obs.new_zeros((len(obs), 23))
        output[:, ANKLES] = ankles
        return output

    def update_distribution(self, obs):
        mean = self.act_inference(obs)
        std = mean.new_full(mean.shape, 1e-6)
        std[:, ANKLES] = self.log_std.exp().clamp_min(1e-5)
        self.distribution = Normal(mean, std)

    def act(self, obs, **kwargs):
        self.update_distribution(obs)
        return self.distribution.sample()

    def reset(self, dones=None):
        # History belongs to the environment and is cleared at its reset.
        pass

    def get_actions_log_prob(self, actions):
        return self.distribution.log_prob(actions)[:, ANKLES].sum(-1)

    @property
    def action_mean(self):
        return self.distribution.mean

    @property
    def action_std(self):
        return self.distribution.stddev

    @property
    def entropy(self):
        return self.distribution.entropy()[:, ANKLES].sum(-1)

    @property
    def std(self):
        return self.log_std.exp().expand(4)


class TorquePPO(PPO):
    def _setup_models_and_optimizer(self):
        self.actor = SharedTorqueActor(self.config.init_noise_std).to(self.device)
        self.critic = PPOCritic(self.algo_obs_dim_dict, self.config.module_dict.critic).to(self.device)
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=self.actor_learning_rate)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=self.critic_learning_rate)


class TorqueHistory:
    def _init_torque_history(self):
        self.torque_history = torch.zeros(self.num_envs, 4, HISTORY, 2, device=self.device)

    def _append_torque_history(self, nominal):
        error = self.default_dof_pos + self.config.robot.control.action_scale * nominal - self.simulator.dof_pos
        # The PD position-command interface uses zero desired joint velocity.
        velocity_error = -self.simulator.dof_vel
        values = torch.stack((error[:, ANKLES], .05 * velocity_error[:, ANKLES]), -1)
        self.torque_history[:, :, 1:] = self.torque_history[:, :, :-1].clone()
        self.torque_history[:, :, 0] = values

    def _reset_buffers_callback(self, env_ids, target_buf=None):
        super()._reset_buffers_callback(env_ids, target_buf)
        if hasattr(self, "torque_history"):
            self.torque_history[env_ids] = 0

    def _get_obs_uan_history(self):
        return self.torque_history.reshape(self.num_envs, 160)

    def _nominal_pd_torque(self, nominal):
        error = self.default_dof_pos + self.config.robot.control.action_scale * nominal - self.simulator.dof_pos
        return self._kp_scale * self.p_gains * error - self._kd_scale * self.d_gains * self.simulator.dof_vel

    def _clip_torque(self, torque):
        return torch.clip(torque, -self.torque_limits, self.torque_limits) if self.config.robot.control.clip_torques else torque


class TorqueReplay(TorqueHistory, WeightedGridDeltaReplay):
    def _init_buffers(self):
        super()._init_buffers()
        self._init_torque_history()

    def get_open_loop_action_at_current_timestep(self):
        # Record s[i] -- a[i+1] --> s[i+1]; hold that a for four 5-ms steps.
        times = self.episode_length_buf * self.dt + self.motion_start_times
        ids = self.motion_ids
        frame_dt = self._motion_lib._motion_dt[ids]
        frame = torch.floor(times / frame_dt + 1e-5)
        return self._motion_lib.get_motion_actions(ids, (frame + 1) * frame_dt)

    def _compute_observations(self):
        self._append_torque_history(self.get_open_loop_action_at_current_timestep())
        super()._compute_observations()

    def _compute_torques(self, actions):
        nominal = self.get_open_loop_action_at_current_timestep()
        torque = self._nominal_pd_torque(nominal)
        if not self.config.get("zero_delta_a", False):
            torque[:, ANKLES] += float(self.config.torque_scale_nm) * actions[:, ANKLES]
        return self._clip_torque(torque)

    def _reward_penalty_minimal_action_norm(self):
        return torch.exp(torch.linalg.vector_norm(self.actions[:, ANKLES], dim=-1)) - 1


class TorqueReplayRecorder(TorquePPO):
    def __init__(self, *args, **kwargs):
        self.dataset_frames = []
        super().__init__(*args, **kwargs)

    def _record_dataset_frame(self):
        # Save at the original target observation rate; never pretend interpolation
        # supplied measured target histories at 200 Hz.
        stride = int(self.env.config.get("dataset_record_stride", 4))
        if stride not in (1, 4):
            raise ValueError("Recorder supports 200Hz or 50Hz output from 200Hz physics")
        if int(self.env.episode_length_buf[0]) % stride:
            return
        self.dataset_frames.append(snapshot(self.env))
        if len(self.dataset_frames) < int(self.env.config.dataset_record_steps):
            return
        output = Path(self.env.config.dataset_record_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fields = {key: np.stack([frame[key] for frame in self.dataset_frames], axis=1) for key in self.dataset_frames[0]}
        motions = {"motion" + str(i): {key: value[i] for key, value in fields.items()} for i in range(self.env.num_envs)}
        for motion in motions.values():
            motion.update(fps=50. if stride == 4 else 200., body_names=list(self.env.config.robot.body_names))
        joblib.dump(motions, output)
        raise SystemExit(0)

    def _pre_eval_env_step(self, state):
        if "step" not in state:
            self._record_dataset_frame()
        return super()._pre_eval_env_step(state)

    def _post_eval_env_step(self, state):
        result = super()._post_eval_env_step(state)
        self._record_dataset_frame()
        return result


class FreshTaskPPO(PPO):
    def load(self, path):
        result = super().load(path)
        self.current_learning_iteration = 0
        return result


class FrozenTorqueTracking(TorqueHistory, LeggedRobotMotionTracking):
    def __init__(self, config, device):
        super().__init__(config, device)
        self.frozen_actor = SharedTorqueActor().to(self.device)
        checkpoint = torch.load(Path(self.config.torque_checkpoint), map_location=self.device)
        self.frozen_actor.load_state_dict(checkpoint["actor_model_state_dict"])
        self.frozen_actor.eval()
        for parameter in self.frozen_actor.parameters():
            parameter.requires_grad_(False)

    def _init_buffers(self):
        super()._init_buffers()
        self._init_torque_history()

    def _compute_torques(self, actions):
        # Called at every physics step while task-policy targets remain at 50 Hz.
        self._append_torque_history(actions)
        torque = self._nominal_pd_torque(actions)
        with torch.no_grad():
            correction = self.frozen_actor.act_inference(self._get_obs_uan_history())
        torque[:, ANKLES] += float(self.config.torque_scale_nm) * correction[:, ANKLES]
        return self._clip_torque(torque)
