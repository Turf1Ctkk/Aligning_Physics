# Current work

Updated October 9, 2026, 06:34 Beijing time (UTC+8).

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

All authorized queues are complete. No GPU experiment is running or queued. The repair changes only height and foot-force noise entering the frozen delta during fine-tuning. Data, input checkpoints, seeds and 1,000-update budgets stay the same. Success changes from 89.6% to 70.8% for Squat, 91.7% to 99.0% for CR7, and 79.2% to 25.0% for Step. [Before/after results](../results/noise_repair/metrics.md).

Main comparison charts use the fixed-final repaired delta policy on every task. Other methods and all open-loop calibration results are unchanged. Historical raw reports and the original chart data remain available.

Policy and replay evaluations report position, velocity and acceleration errors. Completion and tracking success are separate percentages. Policy evaluation uses 27 points; replay uses the 24 bodies measured in the target recordings.

## Document repair

Reader-facing documents use short explanations. The main report now places observations after the method comparison and before the subset test. The old completion-only table is replaced by error bars and closed-loop success. GIFs remain removed. Percentages appear in readable tables; raw counts remain in JSON.

## Main finding so far

Passive SysID improves Step under this protocol. The repaired delta policies do not exceed FT-only success on any task. Fixing the confirmed input mismatch helps CR7 but reduces Squat and Step success. Each main method still has only one training seed. The subset policies have not been repaired, so their transfer findings remain provisional. [Setting audit](settings_audit.md).

Raw results, historical reports and failed acquisition records are preserved. Final repository cleanup and author-supplied IsaacGym visuals follow review.

GPU cutoff: October 9 at 17:00 Beijing time. Submission deadline: October 10 at 04:59 Beijing time.
