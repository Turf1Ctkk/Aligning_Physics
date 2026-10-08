"""Opt-in reset repair and a physical input audit; core files stay unchanged."""
import json
from pathlib import Path

import torch

from humanoidverse.envs.delta_a.delta_a_closed_loop import DeltaA_ClosedLoop
from research.asap_diagnostics.controlled_runtime import FreshFineTunePPO


class ResetSafeDeltaClosedLoop(DeltaA_ClosedLoop):
    def _reset_buffers_callback(self, env_ids, target_buf=None):
        if target_buf is not None:
            raise ValueError('Reset repair supports ordinary task resets, not MPPI buffer restoration')
        super()._reset_buffers_callback(env_ids, target_buf)
        if hasattr(self, 'actions_closed_loop'):
            self.actions_closed_loop[env_ids] = 0.


class DeltaResetProbePPO(FreshFineTunePPO):
    """Run source policy and frozen delta without any optimizer updates."""
    def learn(self):
        self._eval_mode()
        obs = self.env.reset_all()
        layout = self.env.config.obs
        cursor, previous_slice = 0, None
        for key in sorted(layout.obs_dict.closed_loop_actor_obs):
            width = int(layout.obs_dims[key])
            if key == 'actions_closed_loop':
                previous_slice = slice(cursor, cursor + width)
            cursor += width
        if previous_slice is None:
            raise ValueError('Missing previous delta observation')
        rows = []
        reset_count = 0
        with torch.inference_mode():
            for step in range(int(self.env.config.reset_probe_steps)):
                # Stochastic source actions exercise the actual training reset path.
                nominal = self.actor.act(obs['actor_obs']).detach()
                delta = self._infer_delta_for_current_action(obs, nominal)
                mask = (self.env.reset_buf != 0) & (self.env.episode_length_buf == 0)
                if mask.any():
                    counterfactual = dict(obs)
                    corrected = obs['closed_loop_actor_obs'].clone()
                    corrected[mask, previous_slice] = 0.
                    counterfactual['closed_loop_actor_obs'] = corrected
                    fresh = self._infer_delta_for_current_action(counterfactual, nominal)
                    previous = obs['closed_loop_actor_obs'][mask, previous_slice]
                    difference = (delta[mask] - fresh[mask])[:, [4, 5, 10, 11]]
                    count = int(mask.sum())
                    reset_count += count
                    rows.append({'step': step, 'reset_environments': count,
                                 'retained_delta_max_abs': float(previous.abs().max()),
                                 'ankle_output_difference_mean_abs': float(difference.abs().mean()),
                                 'ankle_output_difference_max_abs': float(difference.abs().max())})
                obs, _, _, _ = self.env.step({'actions': nominal, 'actions_closed_loop': delta})
        if not reset_count:
            raise ValueError('No physical episode resets observed; audit is inconclusive')
        report = {'scope': 'Physical training-environment probe; zero optimizer updates',
                  'counterfactual': 'Same observation and current action; only previous delta is zeroed',
                  'steps': int(self.env.config.reset_probe_steps), 'num_envs': self.env.num_envs,
                  'reset_events': reset_count, 'rows': rows,
                  'max_retained_delta': max(r['retained_delta_max_abs'] for r in rows),
                  'max_ankle_output_difference': max(r['ankle_output_difference_max_abs'] for r in rows),
                  'performance_effect': 'Not measured; no success-rate comparison or policy training'}
        output = Path(self.env.config.reset_probe_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n')
        print('DELTA_RESET_PHYSICAL_AUDIT', json.dumps({k: v for k, v in report.items() if k != 'rows'}), flush=True)
