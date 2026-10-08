# Frozen-delta input-noise repair

The repair sets height and foot-force noise to zero during policy fine-tuning. Calibration already used zero noise. Data, input checkpoints, seeds and 1,000-update budgets stay the same. All other saved training settings match.

This is one paired training run per task. Three evaluation seeds measure deployment variation, not training replication. All stored starts and effective deployment settings match the historical evaluation. Metrics were recomputed from the new 27-point recordings.

Pending tasks: StepFBL1. The table contains completed tasks only.

Errors use the first second. Success and completion use the full motion. E_vel is root velocity at 50 Hz.

| Task | Setting | Success (%) | Completion (%) | Included (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel (mm/frame) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SquatL1 | Before | 89.6 | 90.6 | 100.0 | 96.031 | 37.683 | 1.815 | 4.110 |
| SquatL1 | After | 70.8 | 71.9 | 100.0 | 92.686 | 38.004 | 1.758 | 3.739 |
| CR7 | Before | 91.7 | 95.8 | 100.0 | 127.397 | 55.805 | 2.484 | 5.278 |
| CR7 | After | 99.0 | 99.0 | 100.0 | 123.661 | 51.825 | 2.634 | 5.048 |

Full-motion errors below include successful trials only. The two settings can have different successful trials, so these means do not compare the same cohort.

| Task | Setting | Full-motion inclusion (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel (mm/frame) |
|---|---|---:|---:|---:|---:|---:|
| SquatL1 | Before | 89.6 | 95.293 | 42.624 | 0.838 | 2.762 |
| SquatL1 | After | 70.8 | 102.929 | 47.527 | 0.807 | 2.527 |
| CR7 | Before | 91.7 | 116.205 | 57.629 | 3.126 | 5.703 |
| CR7 | After | 99.0 | 116.903 | 58.464 | 3.086 | 5.590 |

The calibrator was not retrained, so open-loop calibration results stay unchanged. The subset policies were not repaired. Their earlier transfer results still carry the input-noise caveat.

