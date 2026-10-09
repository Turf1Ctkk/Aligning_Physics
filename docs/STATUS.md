# Current work

Updated October 9, 2026, after the author-recorded GUI import.

The authorized servo-error experiment and its physical evaluations are complete. All five Step policies and four calibrators pass independent audits. The manager has exited and the GPU is idle. Low-error calibration was skipped because fewer than 50 minutes remained before the cutoff.

## Findings

Random has lower error on all four replay measures in both training runs. The tested Servo-coverage rule has not shown a calibration advantage in these seeds.

In the primary run, both residual policies have 0% Step success. Matched FT-only reaches 5.2% and has lower first-second error on all four measures. FT-only itself is weak; its cause is not isolated.

In the repeat, Random succeeds at 20.8% and Servo at 33.3%. Servo has lower first-second global/relative error (71.32/40.17 mm), acceleration error (1.632 mm/frame²), and root velocity error (3.426 mm/frame). All trials reach one second. Servo completes 36.5% of motions; success also requires the distance criterion. [Full results and audits](../results/servo_error_selection/metrics.md).

Replay and control rankings differ in the repeat. Calibration and policy training seeds change together; replay and deployment seeds stay fixed. The repeat has no matched FT-only. Both runs remain separate, without choosing a favorable seed. Two seeds cannot establish a population ranking.

## Scope

Settings, input/checkpoint hashes, stored starts and physical metrics are verified. Known log limits and nonzero reconstruction floors remain disclosed. No floor is subtracted; terminations are not classified as falls without evidence.

The seven-method report and repairs remain unchanged. Three author-recorded GUI comparison GIFs are now in the main README, with left/right labels and short observations. They illustrate partial motions; quantitative results are unchanged. Older subset results retain earlier noise/reset defects and remain exploratory. Raw science, checkpoints and failures are preserved. Final cleanup follows review. No further training is queued.

GPU cutoff: October 9 at 17:00 Beijing. Submission deadline: October 10 at 04:59 Beijing.
