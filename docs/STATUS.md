# Current work

Updated October 9, 2026, 07:40 Beijing time (UTC+8).

## Completed

- Replay and frozen-correction interface fixes.
- Mixed-motion delta calibration and policy comparisons.
- Passive and active SysID adaptations.
- Common-data and measured-200-Hz torque adaptations.
- Seven-policy comparisons for Squat, CR7 and StepFBL1.
- Both training seeds of the three-rule data-content test and fresh repeat-seed replay controls.
- Fresh 27-point policy evaluations and checks of all stored starts and effective settings.
- Fresh 24-body calibration replays, with metrics recomputed from recorded trajectories.
- Source-A checks of original and FT-only policies on all three tasks, with saved settings and actual metrics audited.
- Four-error method comparison charts and a separate closed-loop success chart.
- Three-task frozen-delta input-noise repair, with all training settings checked and all new trial metrics recomputed.

## Server queue

The previous queues and input-noise repair are complete. That repair changes only height and foot-force noise. Success changes from 89.6% to 70.8% for Squat, 91.7% to 99.0% for CR7, and 79.2% to 25.0% for Step. [Before/after results](../results/noise_repair/metrics.md).

The author approved a separate reset-only comparison on all three tasks. Step is training; Squat and CR7 follow serially. Every run starts from its original model_6000 with the same frozen delta model_500, seed and 1,000-update budget. Both noise channels remain zero. Rewards, curricula and optimizer settings stay fixed. Each final policy receives the same three-seed B evaluation and independent metric audit. No new tracking result is available yet.

Main comparison charts use the fixed-final repaired delta policy on every task. Other methods and all open-loop calibration results are unchanged. Historical raw reports and the original chart data remain available.

Policy and replay evaluations report position, velocity and acceleration errors. Completion and tracking success are separate percentages. Policy evaluation uses 27 points; replay uses the 24 bodies measured in the target recordings.

## Document repair

Reader-facing documents use short explanations. The main report now places observations after the method comparison and before the subset test. The old completion-only table is replaced by error bars and closed-loop success. GIFs remain removed. Percentages appear in readable tables; raw counts remain in JSON.

## Main finding so far

Passive SysID improves Step under this protocol. The repaired delta policies do not exceed FT-only success on any task. Fixing the confirmed input mismatch helps CR7 but reduces Squat and Step success. Each main method still has only one training seed. The subset policies have not been repaired, so their transfer findings remain provisional. [Setting audit](settings_audit.md).

Raw results, historical reports and failed acquisition records are preserved. Final repository cleanup and author-supplied IsaacGym visuals follow review.

A further reset audit found that the previous delta action remains in the frozen model's input. Two no-update physical probes confirm that it changes the correction. An opt-in reset repair passes CPU and physical checks. Core files and completed experiments stay unchanged. Its effect on tracking success remains unknown while the new comparison runs. [Reset audit](../results/delta_reset_probe/metrics.md).

GPU cutoff: October 9 at 17:00 Beijing time. Submission deadline: October 10 at 04:59 Beijing time.
