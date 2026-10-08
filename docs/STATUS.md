# Experiment status

## Completed evidence

- Source policies for CR7, SquatL1, and StepFBL1 exist.
- Recorder/replay timing, saved-velocity initialization, and frozen-delta interface corrections have been exercised in the earlier diagnostics.
- Multi-motion target collection, three delta dataset sizes, validation checkpoint selection, and held-out trajectory replay completed.
- The pilot shows position-metric improvements, velocity-metric regressions, and non-monotonic data-scale results. Its sampler and same-domain replay limitations are documented.
- Existing server artifacts and source checkpoints have been inspected read-only. The saved pilot plan uses CR7 `model_6000.pt`, not the available `model_8800.pt`; all three collection checkpoints are `model_6000.pt`.

## Confirmed first experiment

- Mixed-motion 30-group calibration baseline: 10 original recording groups per task.
- Same-engine Kp20 to Kp16 ankle mismatch; other dynamics fixed, domain randomization disabled.
- 1-second calibration, four ankle physical corrections, 200/50 Hz physics/control, 2048 environments, 1000 PPO iterations, one initial training seed.
- SquatL1 task-policy fine-tuning: 1000 additional iterations per condition, actor LR 1e-4, critic LR 1e-3, entropy 0, optimizer reset, pretrained weights/std retained.
- GPU experiment cutoff: 2026-10-09 12:00 UTC+03:00.

New weighted delta training is now running. Installed CPU contracts passed. A clean initial B-domain standalone SquatL1 evaluation terminated at approximately 3.9 seconds before completing the 5.23-second reference; this is one trial, not a measured aggregate completion rate.

An additional matched clean source-domain check completed all 261 recorded frames (5.22 seconds), with global body MPJPE 87.07 mm and root-relative body MPJPE 36.10 mm. This one-trial contrast establishes a useful baseline, but is not a statistical estimate of the effect of the domain change.

## Not yet completed

- Corrected task/group-weighted calibration run: in progress.
- Full closed-loop SquatL1 fine-tuning and target deployment comparison.
- SPI-style parameter-identification baseline; full active exploration is a separate stage.
- UAN torque-residual adaptation and genuine high-rate excitation collection.
- Equal-budget calibration-data selection test.
- Target-domain motion-tracking GIF/video comparisons.

Missing results remain labelled as missing; this file will be updated from actual artifacts.
