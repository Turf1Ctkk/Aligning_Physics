"""Opt-in fresh 27-point tracking evaluation. No policy or environment changes."""
import json
from pathlib import Path

import joblib
import numpy as np
import torch

from humanoidverse.agents.ppo.ppo import PPO
from humanoidverse.envs.motion_tracking.motion_tracking import my_quat_rotate
from research.asap_diagnostics.dataset_runtime import snapshot
from research.asap_diagnostics.paper_metrics import trial_metrics, summarize


class PaperTrackingRecorderPPO(PPO):
    def __init__(self, *args, **kwargs):
        self.paper_frames = []
        super().__init__(*args, **kwargs)

    def _record_paper_frame(self):
        env = self.env
        if bool(env.config.add_extra_action):
            raise ValueError('Fresh B deployment must have no learned correction hook')
        frame = snapshot(env)
        times = env.episode_length_buf * env.dt + env.motion_start_times
        ref = env._motion_lib.get_motion_state(env.motion_ids, times, offset=env.env_origins)
        # Use current simulator tensors rather than a cached pre-reset extension.
        rotated = my_quat_rotate(env.simulator._rigid_body_rot[:, env.extend_body_parent_ids].reshape(-1, 4),
                                 env.extend_body_pos_in_parent.reshape(-1, 3))
        extension = my_quat_rotate(env.extend_body_rot_in_parent_xyzw.reshape(-1, 4), rotated).view(env.num_envs, -1, 3)
        extension = extension + env.simulator._rigid_body_pos[:, env.extend_body_parent_ids]
        bodies = torch.cat((env.simulator._rigid_body_pos, extension), dim=1)
        reference = ref['rg_pos_t']
        if bodies.shape[1:] != (27, 3) or reference.shape != bodies.shape:
            raise ValueError('Unexpected G1 extended point order or shape')
        for key, value in [('paper_body_pos', bodies), ('paper_reference_body_pos', reference),
                           ('reference_body_pos', ref['rg_pos'][:, :24])]:
            frame[key] = (value - env.env_origins[:, None]).detach().cpu().numpy().copy()
        frame['reference_root_pos'] = (ref['root_pos'] - env.env_origins).detach().cpu().numpy().copy()
        self.paper_frames.append(frame)
        if len(self.paper_frames) < int(env.config.dataset_record_steps):
            return
        output = Path(env.config.dataset_record_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        arrays = {key: np.stack([f[key] for f in self.paper_frames], axis=1) for key in frame}
        names = list(env.config.robot.body_names) + [v['joint_name'] for v in env.config.robot.motion.extend_config]
        if len(names) != 27 or names[0] != 'pelvis':
            raise ValueError('Expected pelvis followed by 23 rigid bodies and 3 extended points')
        records, trials = {}, []
        for i in range(env.num_envs):
            record = {key: value[i] for key, value in arrays.items()}
            record.update(fps=1 / env.dt, body_names=list(env.config.robot.body_names), paper_body_names=names)
            if not np.array_equal(record['body_pos'], record['paper_body_pos'][:, :24]):
                raise ValueError('Actual rigid-body point mismatch')
            records['motion' + str(i)] = record
            trials.append(dict(trial=i, **trial_metrics(record)))
        joblib.dump(records, output)
        report = {
            'schema_version': 1, 'scope': 'Fresh standalone target-domain policy physics rollout',
            'point_count': 27, 'point_names': names, 'fps': 50,
            'success_rule': 'Complete reference horizon and average point distance never exceeds 0.5 m',
            'runtime_termination': 'Original matched settings; paper threshold is scored separately',
            'metric_scope': 'Trial means; omit setup warm frame and every frame at/after first reset. No derivatives across resets.',
            'velocity_definition': 'Body velocity follows compute_metrics_lite; root velocity separately follows paper text. Both are first differences, not mm/s.',
            'acceleration_definition': 'Mean body second-difference error in mm/frame^2, not mm/s^2',
            'summary': summarize(trials), 'trials': trials,
        }
        output.with_suffix('.json').write_text(json.dumps(report, indent=2))
        print('PAPER_TRACKING_EVAL', json.dumps(report['summary']), flush=True)
        raise SystemExit(0)

    def _pre_eval_env_step(self, state):
        if 'step' not in state and not self.paper_frames:
            self._record_paper_frame()
        return super()._pre_eval_env_step(state)

    def _post_eval_env_step(self, state):
        state = super()._post_eval_env_step(state)
        self._record_paper_frame()
        return state
