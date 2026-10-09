# Frozen-delta reset repair

The repair clears the previous delta action when an environment resets. Both conditions already use zero height and foot-force noise. Data, source and calibration checkpoints, seeds and 1,000-update budgets stay the same. Other saved training settings match.

This is one paired training run per task. Three evaluation seeds measure deployment variation, not training replication. All stored starts and effective deployment settings match the historical evaluation. Metrics were recomputed from the new 27-point recordings.

Pending tasks: SquatL1, CR7. The table contains completed tasks only.

Errors use the first second. Success and completion use the full motion. E_vel is root velocity at 50 Hz.

| Task | Setting | Success (%) | Completion (%) | Included (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel (mm/frame) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| StepFBL1 | Before | 25.0 | 26.0 | 100.0 | 86.302 | 48.729 | 1.843 | 4.481 |
| StepFBL1 | After | 37.5 | 38.5 | 100.0 | 80.791 | 46.993 | 1.667 | 4.099 |

Full-motion errors below include successful trials only. The two settings can have different successful trials, so these means do not compare the same cohort.

| Task | Setting | Full-motion inclusion (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel (mm/frame) |
|---|---|---:|---:|---:|---:|---:|
| StepFBL1 | Before | 25.0 | 112.471 | 52.271 | 1.221 | 3.473 |
| StepFBL1 | After | 37.5 | 86.821 | 48.482 | 1.241 | 3.569 |

The calibrator was not retrained, so open-loop calibration results stay unchanged. The subset policies were not repaired. Their earlier transfer results still carry the input-noise and reset caveats.

