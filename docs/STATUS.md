# Current work

Updated October 8, 2026, 18:02 UTC.

## Completed

- Replay and frozen-correction interface fixes.
- Mixed-motion delta calibration and policy comparisons.
- Passive and active SysID adaptations.
- Common-data and measured-200-Hz torque adaptations.
- Seven-policy comparisons for Squat, CR7 and StepFBL1.
- First training seed of the three-rule data-content test.

## Running or queued

- Second data-content seed: uniform complete; coverage training is running. Range follows.
- Replay controls at its evaluation seed: queued after the repeat.
- Fresh 27-point policy evaluations: queued after those controls.
- Fresh 24-body calibration replays with velocity and acceleration: queued next.

The new evaluation reports position, velocity and acceleration errors. Completion and paper tracking success will be separate percentages. CPU formula checks have passed. New physical results are not yet available.

## Document repair

Reader-facing documents now use short explanations. The main report follows the six-part question-to-evidence structure. Existing GIFs and their references are removed. Historical tables use completion percentages; old raw JSON counts are preserved.

## Main finding so far

Calibration helps StepFBL1 relative to ordinary fine-tuning. Squat and CR7 do not show extra completion gains. In the first data-content run, coverage improves replay more, while range gives higher completion. This does not confirm the combined hypothesis. Uniform completion changes from 8.3% to 99.0% in the second run on identical data. The remaining second-run arms are pending, so the first-run ranking is uncertain.

GPU cutoff: October 9 at 09:00 UTC. Submission deadline: October 9 at 20:59 UTC. Failures and negative outcomes remain part of the evidence.
