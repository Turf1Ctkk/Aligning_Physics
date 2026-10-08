# Controlled mixed30 calibration and Squat adaptation

**Status:** calibration training, validation selection and held-out replay have completed. Equal-budget task-policy fine-tuning is running. No closed-loop improvement is claimed yet.

The calibration data contain 30 original target recording groups: ten CR7, ten SquatL1, and ten StepFBL1. The sampler gives equal probability to tasks, to groups within a task, and to continuous segments within a group. Its [sampling manifest](sampling_manifest.json) records these probabilities. The first draw into 2048 parallel environments was CR7 687, SquatL1 657, and StepFBL1 704; expected task weights are 1/3, while a finite draw is approximate.

Training uses the agreed Kp20→Kp16 mismatch, four ankle physical corrections, 200/50 Hz physics/correction, a nominal one-second episode budget, and 1000 PPO updates. [Validation selection](delta_selection.json) chose `model_500.pt` over `model_1000.pt`: validation global body MPJPE was 30.66 versus 35.03 mm. Both validation candidates completed all 60 evaluation windows. Test data were not used for this choice.

## Held-out replay

![Controlled calibration replay](../../assets/figures/controlled_replay.png)

| Test condition | Ankle RMSE (rad) ↓ | All-joint RMSE (rad) ↓ | Joint-velocity RMSE (rad/s) ↓ | Root error (mm) ↓ | Global body MPJPE (mm) ↓ |
|---|---:|---:|---:|---:|---:|
| B Kp16, zero correction | 0.01398 | 0.00932 | 0.49133 | 7.03 | 7.40 |
| A Kp20, zero correction | 0.07500 | 0.03480 | 0.87892 | 39.32 | 37.66 |
| A Kp20, learned correction | 0.06131 | 0.03003 | 0.89057 | 31.37 | 30.51 |

All three conditions complete all 66 one-second windows from the isolated test partition. Results average windows within recording groups, groups within tasks, and tasks equally. They use 24 actual rigid bodies. [Raw replay summaries](replay_comparison.json) include shorter horizons and per-task metrics.

Relative to the mismatched zero-correction baseline, learned calibration reduces global position error by 19.0% and ankle error by 18.2%. Joint-velocity error rises by approximately 1.3%. This establishes useful changes in replay, not uniformly improved dynamics or a downstream-control benefit. Same-domain replay is still nonzero and sets a visible interpretation limit.

This run and the earlier clip-uniform pilot use different training/evaluation seeds and sampling. Their numerical difference is not a controlled sampler ablation.

## Initial target policy check

The original Squat policy in B terminated at approximately 3.9 seconds of the 5.22-second evaluation, in one clean-initialization trial. [Its report](vanilla_clean.json) includes errors on shorter completed prefixes. The full-horizon position mean is intentionally unavailable when no trial completes. This is an integration baseline, not an aggregate completion-rate estimate.

![Original target-domain Squat policy](../../assets/gifs/squat_vanilla_target.gif)

This animation is derived from actual recorded rigid-body positions, with dashed reference positions. It is a skeleton visualization, not an IsaacGym camera render. It shows fixed trial 0 and freezes at the first termination rather than playing the automatically reset episode as a continuation. It does not show a learned-policy result.

The pending comparison uses the same original policy checkpoint and 1000 additional iterations per condition: continued source training without correction versus source training with the frozen selected delta. Both policies will be evaluated in unchanged B without a correction attached, using common termination criteria and seeds. Completion, survival and common-prefix errors will be reported together to avoid hiding failures in averages over successful trials.
