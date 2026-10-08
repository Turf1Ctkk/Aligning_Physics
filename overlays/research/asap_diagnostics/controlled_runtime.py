"""Opt-in runtime for the controlled calibration/downstream comparison."""
import json
from pathlib import Path

import numpy as np
import torch

from humanoidverse.agents.delta_a.train_delta_a import PPODeltaA
from humanoidverse.agents.ppo.ppo import PPO
from humanoidverse.utils.motion_lib.motion_lib_robot import MotionLibRobot
from research.asap_diagnostics.dataset_runtime import GridDeltaReplay, snapshot


class WeightedGridDeltaReplay(GridDeltaReplay):
    def _init_motion_lib(self):
        self.config.robot.motion.step_dt = self.dt
        self._motion_lib = MotionLibRobot(self.config.robot.motion, num_envs=self.num_envs, device=self.device)
        manifest = json.loads(Path(self.config.sampling_manifest).read_text())
        keys = list(self._motion_lib._motion_data_keys)
        if set(keys) != set(manifest["weights"]):
            raise ValueError("Sampling manifest and loaded motion keys differ")
        probabilities = torch.tensor([manifest["weights"][key] for key in keys],
                                     device=self.device, dtype=torch.float32)
        self._motion_lib._sampling_prob = probabilities / probabilities.sum()
        self._motion_lib.load_motions(random_sample=not self.is_evaluating)
        self._resample_motion_times(torch.arange(self.num_envs, device=self.device))
        self.motion_dt = self._motion_lib._motion_dt
        self.motion_start_idx = 0
        self.num_motions = self._motion_lib._num_unique_motions
        loaded_keys = [keys[int(i)] for i in self._motion_lib._curr_motion_ids.cpu()]
        counts = {}
        for key in loaded_keys:
            task = manifest["metadata"][key]["task"]
            counts[task] = counts.get(task, 0) + 1
        print("CONTROLLED_SAMPLING_BATCH", json.dumps(counts), flush=True)


class FreshFineTunePPO(PPODeltaA):
    """Load task weights/std, but start a new additional-iteration experiment."""
    def load(self, path):
        result = super().load(path)
        self.current_learning_iteration = 0
        print("FINETUNE_START: task weights loaded; iteration counter reset; optimizer loading =",
              self.load_optimizer, flush=True)
        return result


class TrackingRecorderPPO(PPO):
    """Evaluate a standalone task policy against its original motion reference."""
    def __init__(self, *args, **kwargs):
        self.frames = []
        super().__init__(*args, **kwargs)

    def _record(self):
        env = self.env
        frame = snapshot(env)
        times = env.episode_length_buf * env.dt + env.motion_start_times
        reference = env._motion_lib.get_motion_state(env.motion_ids, times, offset=env.env_origins)
        actual_body = env.simulator._rigid_body_pos
        reference_body = reference["rg_pos"][:, :actual_body.shape[1]]
        frame["tracking_body_error_mm"] = torch.linalg.vector_norm(
            actual_body - reference_body, dim=-1).mean(-1).detach().cpu().numpy() * 1000
        frame["tracking_root_relative_body_error_mm"] = torch.linalg.vector_norm(
            (actual_body - env.simulator.robot_root_states[:, None, :3]) -
            (reference_body - reference["root_pos"][:, None]), dim=-1).mean(-1).detach().cpu().numpy() * 1000
        self.frames.append(frame)
        if len(self.frames) < int(env.config.dataset_record_steps):
            return
        import joblib
        output = Path(env.config.dataset_record_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fields = {key: np.stack([f[key] for f in self.frames], axis=1) for key in self.frames[0]}
        motions, trials = {}, []
        for i in range(env.num_envs):
            motion = {key: value[i] for key, value in fields.items()}
            motion.update(fps=1 / env.dt, body_names=list(env.config.robot.body_names))
            motions["motion" + str(i)] = motion
            resets = np.flatnonzero(motion["terminate"])
            stop = int(resets[0]) if len(resets) else len(self.frames)
            trials.append({"trial": i, "complete": not len(resets), "first_reset_row":
                           int(resets[0]) if len(resets) else None, "valid_frames": stop,
                           "survival_s": stop * env.dt,
                           "global_body_mpjpe_mm": float(np.mean(motion["tracking_body_error_mm"][:stop])) if stop else None,
                           "root_relative_body_mpjpe_mm": float(np.mean(motion["tracking_root_relative_body_error_mm"][:stop])) if stop else None})
            prefixes = {}
            for horizon in (.25, .5, 1., 2., 3.):
                wanted = int(np.floor(horizon / env.dt + 1e-5))
                end = min(stop, wanted)
                prefixes[str(horizon)] = {"complete": stop >= wanted, "frames": end,
                    "global_body_mpjpe_mm": float(np.mean(motion["tracking_body_error_mm"][:end])) if end else None,
                    "root_relative_body_mpjpe_mm": float(np.mean(motion["tracking_root_relative_body_error_mm"][:end])) if end else None}
            trials[-1]["prefix_metrics"] = prefixes
        joblib.dump(motions, output)
        complete = [row for row in trials if row["complete"]]
        report = {"scope": "Closed-loop standalone task policy in target; no learned correction attached",
                  "trials": trials, "complete_trials": len(complete), "total_trials": len(trials),
                  "completion_rate": len(complete) / len(trials),
                  "mean_survival_s": float(np.mean([t["survival_s"] for t in trials])),
                  "global_body_mpjpe_mm": float(np.mean([t["global_body_mpjpe_mm"] for t in complete])) if complete else None,
                  "root_relative_body_mpjpe_mm": float(np.mean([t["root_relative_body_mpjpe_mm"] for t in complete])) if complete else None,
                  "error_average_scope": "Complete trials only; failures and survival reported separately",
                  "checkpoint": str(self.config.get("checkpoint", "see effective config"))}
        report["prefix_metrics"] = {}
        for horizon in (.25, .5, 1., 2., 3.):
            valid = [t["prefix_metrics"][str(horizon)] for t in trials if t["prefix_metrics"][str(horizon)]["complete"]]
            report["prefix_metrics"][str(horizon)] = {"complete_trials": len(valid), "total_trials": len(trials),
                "global_body_mpjpe_mm": float(np.mean([t["global_body_mpjpe_mm"] for t in valid])) if valid else None,
                "root_relative_body_mpjpe_mm": float(np.mean([t["root_relative_body_mpjpe_mm"] for t in valid])) if valid else None}
        output.with_suffix(".json").write_text(json.dumps(report, indent=2))
        print("TRACKING_EVAL", json.dumps({k: v for k, v in report.items() if k != "trials"}), flush=True)
        raise SystemExit(0)

    def _pre_eval_env_step(self, state):
        if "step" not in state and not self.frames:
            self._record()
        return super()._pre_eval_env_step(state)

    def _post_eval_env_step(self, state):
        state = super()._post_eval_env_step(state)
        self._record()
        return state
