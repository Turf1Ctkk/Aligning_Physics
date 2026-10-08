# Current work

Updated October 8, 2026, 21:08 UTC.

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

## Server queue

The earlier queues are complete. A new noise-repair queue is training SquatL1, then CR7 and StepFBL1. It fixes only height and foot-force noise entering the frozen delta during policy fine-tuning. Data, model checkpoints, seeds and 1,000-update budgets are unchanged. One GPU job runs at a time; the cutoff remains in force. Results are pending.

Policy and replay evaluations report position, velocity and acceleration errors. Completion and tracking success are separate percentages. Policy evaluation uses 27 points; replay uses the 24 bodies measured in the target recordings.

## Document repair

Reader-facing documents use short explanations. The main report now places observations after the method comparison and before the subset test. The old completion-only table is replaced by error bars and closed-loop success. GIFs remain removed. Percentages appear in readable tables; raw counts remain in JSON.

## Main finding so far

Step shows calibration benefits under the current protocol. Squat and CR7 show no consistent extra control benefit. The source check gives original Step success 90.6% in A and 1.0% in B. It confirms a transfer problem. The delta policy results, including subset tests, precede a confirmed frozen-input noise repair. Their conclusions need that check. [Setting audit](settings_audit.md).

Raw results, historical reports and failed acquisition records are preserved. Final repository cleanup and author-supplied IsaacGym visuals follow review.

GPU cutoff: October 9 at 09:00 UTC. Submission deadline: October 9 at 20:59 UTC.
