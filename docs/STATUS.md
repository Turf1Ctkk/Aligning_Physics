# Current work

Updated October 9, 2026, 13:17 Beijing time (UTC+8).

The seven-method comparisons, fresh paper metrics, source checks, and three-task noise and reset repairs are complete. Main charts use all three preset repaired delta policies. Earlier records remain available.

## Running

The new [servo-error experiment](servo_error_experiment.md) compares Random-N and Servo-coverage-N. Each group trains a fresh delta action model and then fine-tunes Step. Both use the repaired inputs and reset. A fresh FT-only policy shares the primary seed.

Selection, quotas and bin edges are frozen. The first reference-phase preflight failed because late Step windows were unavailable. A revised CPU preflight passed with shared training-candidate phase tertiles. The failed preflight is retained.

Random calibration is complete and audited. Validation selected update 1,000. Test global position error falls from 39.77 to 35.58 mm; relative position and root velocity also improve. Acceleration rises from 0.799 to 0.817 mm/frame². [Random replay results](../results/servo_error_selection/primary/random/replay_metrics.md).

Random Step training and evaluation are complete and independently audited. Success is 0%, with mean survival 1.69 seconds. First-second global/relative position errors are 99.76/47.90 mm; acceleration is 1.913 mm/frame² and root velocity is 5.965 mm/frame. All trials reach one second and terminate between 1.34 and 2.42 seconds. No termination cause is assigned. [Audited results](../results/servo_error_selection/metrics.md).

Servo calibration started at 13:02 Beijing and is the only GPU stage. Its selected-training same16 error is 19.61 mm, compared with Random's 21.52 mm. These are reconstruction diagnostics, not subtracted floors. The new FT-only policy, paired repeat and Low-error calibration remain pending. There is no selector ranking or matched FT-only contrast yet.

All four errors and closed-loop success will be reported. Audits check actual settings, fixed checkpoints, stored starts and recomputed metrics. Missing or failed audits stop downstream work. Partial runs are not silently resumed.

## Scope

The old data-content test retains the earlier noise and reset issues. Its findings remain exploratory. New selectors are not chosen from its test ranking.

Reader-facing reports use percentages and short English. GIFs remain removed. Raw results, checkpoints and failed artifacts are preserved. Final cleanup and author-supplied visualizations follow review.

GPU cutoff: October 9 at 17:00 Beijing time. Submission deadline: October 10 at 04:59 Beijing time.
