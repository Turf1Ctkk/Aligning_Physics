# Current work

Updated October 9, 2026, 09:15 Beijing time (UTC+8).

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
- Three-task reset repair, with the same independent checks and all new trial metrics recomputed.

## Server queue

The previous queues and input-noise repair are complete. That repair changes only height and foot-force noise. Success changes from 89.6% to 70.8% for Squat, 91.7% to 99.0% for CR7, and 79.2% to 25.0% for Step. [Before/after results](../results/noise_repair/metrics.md).

The reset-only comparison is complete and independently audited on all three tasks. Success rises from 70.8% to 91.7% for Squat and from 25.0% to 37.5% for Step. All four first-second errors decrease in both tasks. CR7 success falls from 99.0% to 94.8%, with mixed error changes. Full-motion errors do not uniformly improve, and successful cohorts change. [Results](../results/reset_repair/metrics.md).

The authorized queues are complete. No GPU job remains. Every repair started from its original model_6000 with the same frozen delta model_500, seed and 1,000-update budget. Rewards, curricula and optimizer settings stayed fixed. No further training is scheduled.

Main charts use all three fixed-final noise-and-reset repaired delta policies. No version was chosen by test performance. Other policies and open-loop calibration results stay unchanged. Original and noise-only chart data remain available. The heartbeat is paused after publication.

Policy and replay evaluations report position, velocity and acceleration errors. Completion and tracking success are separate percentages. Policy evaluation uses 27 points; replay uses the 24 bodies measured in the target recordings.

## Document repair

Reader-facing documents use short explanations. The main report now places observations after the method comparison and before the subset test. The old completion-only table is replaced by error bars and closed-loop success. GIFs remain removed. Percentages appear in readable tables; raw counts remain in JSON.

## Main finding so far

Passive SysID improves Step under this protocol. Reset repair raises Squat success to 91.7%, below FT-only's 100%. Step reaches 37.5%, close to FT-only's 36.5%, while its first-second position errors remain higher. Each main method has only one training seed. The subset policies have not been repaired, so their transfer findings remain provisional. [Setting audit](settings_audit.md).

Raw results, historical reports and failed acquisition records are preserved. Final repository cleanup and author-supplied IsaacGym visuals follow review.

A reset audit found that the previous delta action remains in the frozen model's input. Two no-update physical probes confirm that it changes the correction. Core files and completed experiments stay unchanged. [Reset audit](../results/delta_reset_probe/metrics.md).

GPU cutoff: October 9 at 17:00 Beijing time. Submission deadline: October 10 at 04:59 Beijing time.
