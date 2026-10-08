# Current work

Updated October 8, 2026, 20:29 UTC.

## Completed

- Replay and frozen-correction interface fixes.
- Mixed-motion delta calibration and policy comparisons.
- Passive and active SysID adaptations.
- Common-data and measured-200-Hz torque adaptations.
- Seven-policy comparisons for Squat, CR7 and StepFBL1.
- Both training seeds of the three-rule data-content test and fresh repeat-seed replay controls.
- Fresh 27-point policy evaluations and checks of all stored starts and effective settings.
- Fresh 24-body calibration replays, with metrics recomputed from recorded trajectories.

## Server queue

All planned training and evaluation queues are complete. The GPU is idle. No new training is scheduled.

Policy and replay evaluations report position, velocity and acceleration errors. Completion and tracking success are separate percentages. Policy evaluation uses 27 points; replay uses the 24 bodies measured in the target recordings.

## Document repair

Reader-facing documents now use short explanations. The main report follows the six-part question-to-evidence structure. Existing GIFs and their references are removed. Historical tables use completion percentages; old raw JSON counts are preserved.

## Main finding so far

Calibration helps StepFBL1 relative to ordinary fine-tuning. Squat and CR7 do not show extra completion gains. Coverage gives smaller replay errors in both data-content runs, but it does not consistently give better control. Uniform completion changes from 8.3% to 99.0%, coverage from 41.7% to 77.1%, and range from 77.1% to 95.8%. These two seeds do not establish a stable ranking.

Raw results, historical reports and failed acquisition records are preserved. Final repository cleanup and author-supplied IsaacGym visuals follow review.

GPU cutoff: October 9 at 09:00 UTC. Submission deadline: October 9 at 20:59 UTC.
