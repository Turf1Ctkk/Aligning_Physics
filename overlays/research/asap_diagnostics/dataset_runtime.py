"""Opt-in recording and grid-start environments for multi-rollout experiments."""
from pathlib import Path

import joblib
import numpy as np
import torch
from scipy.spatial.transform import Rotation

from humanoidverse.agents.ppo.ppo import PPO
from humanoidverse.envs.delta_a.delta_a_open_loop import DeltaA_OpenLoop


def sample_grid_starts(num_frames, frame_dt, horizon, control_dt):
    # Stock episode timeout uses `episode_length > max_episode_length`.
    steps = int(np.ceil(horizon / control_dt)) + 1
    reserve = torch.ceil(steps * control_dt / frame_dt - 1e-5).long()
    max_start = num_frames.long() - 1 - reserve
    if (max_start < 0).any():
        raise ValueError("A clip is shorter than the requested full training episode")
    start = torch.floor(torch.rand(max_start.shape, device=max_start.device)
                        * (max_start + 1)).long()
    return start * frame_dt


class GridDeltaReplay(DeltaA_OpenLoop):
    def set_is_evaluating(self):
        super().set_is_evaluating()
        # Construction loads random clips because is_evaluating starts False.
        # Reload in dictionary order before PPO resets for batched evaluation.
        self._motion_lib.load_motions(random_sample=False, start_idx=0)
        self.motion_dt = self._motion_lib._motion_dt

    def _resample_motion_times(self, env_ids):
        if len(env_ids) == 0:
            return
        ids = self.motion_ids[env_ids]
        self.motion_len[env_ids] = self._motion_lib.get_motion_length(ids)
        fixed_eval = self.config.get("dataset_evaluation", False)
        fixed_eval |= self.is_evaluating and not self.config.enforce_randomize_motion_start_eval
        if fixed_eval:
            self.motion_start_times[env_ids] = 0
        else:
            self.motion_start_times[env_ids] = sample_grid_starts(
                self._motion_lib._motion_num_frames[ids], self._motion_lib._motion_dt[ids],
                float(self.config.max_episode_length_s), self.dt)


def snapshot(env):
    def cpu(value):
        return value.detach().cpu().numpy().copy()
    if env.config.simulator.config.name != "isaacgym":
        raise ValueError("This recorder supports stock IsaacGym world-frame velocities only")
    root = cpu(env.simulator.robot_root_states)
    origin = cpu(env.env_origins)
    q = cpu(env.simulator.dof_pos)
    aa = np.concatenate((Rotation.from_quat(root[:, 3:7]).as_rotvec()[:, None],
                         cpu(env._motion_lib.mesh_parsers.dof_axis)[None] * q[:, :, None],
                         np.zeros((env.num_envs, len(env.config.robot.motion.extend_config), 3))), axis=1)
    return {
        "pose_aa": aa.astype(np.float32),
        "root_trans_offset": root[:, :3] - origin,
        "root_rot": root[:, 3:7], "dof": q,
        "action": cpu(env.actions), "dof_vel": cpu(env.simulator.dof_vel),
        "root_lin_vel": root[:, 7:10], "root_ang_vel": root[:, 10:13],
        "body_pos": cpu(env.simulator._rigid_body_pos) - origin[:, None],
        "terminate": cpu(env.reset_buf),
        "motion_times": cpu(env.episode_length_buf * env.dt + env.motion_start_times),
    }


class RolloutRecorderPPO(PPO):
    """Record the final reset step and actual evaluation steps, not setup resets."""
    def __init__(self, *args, **kwargs):
        self.dataset_frames = []
        super().__init__(*args, **kwargs)

    def _record_dataset_frame(self):
        self.dataset_frames.append(snapshot(self.env))
        count = int(self.env.config.dataset_record_steps)
        if len(self.dataset_frames) < count:
            return
        output = Path(self.env.config.dataset_record_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fields = {k: np.stack([frame[k] for frame in self.dataset_frames], axis=1)
                  for k in self.dataset_frames[0]}
        motions = {}
        for i in range(self.env.num_envs):
            motions["motion" + str(i)] = {k: v[i] for k, v in fields.items()}
            motions["motion" + str(i)]["fps"] = 1.0 / self.env.dt
            motions["motion" + str(i)]["body_names"] = list(self.env.config.robot.body_names)
        joblib.dump(motions, output)
        print("Recorded", self.env.num_envs, "rollouts,", count, "frames each:", output, flush=True)
        raise SystemExit(0)

    def _pre_eval_env_step(self, actor_state):
        # PPO calls this once after the final reset_all, before entering its loop.
        if "step" not in actor_state and not self.dataset_frames:
            self._record_dataset_frame()
        return super()._pre_eval_env_step(actor_state)

    def _post_eval_env_step(self, actor_state):
        actor_state = super()._post_eval_env_step(actor_state)
        self._record_dataset_frame()
        return actor_state
