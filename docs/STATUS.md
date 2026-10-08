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

New weighted delta training and isolated replay have completed. Installed CPU contracts passed. Validation selects the 500-update checkpoint. Held-out global body MPJPE decreases from 37.66 to 30.51 mm; velocity RMSE slightly worsens (0.87892 to 0.89057 rad/s). All 66 one-second test windows complete. Equal-budget no-calibration policy fine-tuning is now running. A clean initial B-domain standalone SquatL1 evaluation terminated at approximately 3.9 seconds before completing the 5.23-second reference; this is one trial, not a measured aggregate completion rate.

An additional matched clean source-domain check completed all 261 recorded frames (5.22 seconds), with global body MPJPE 87.07 mm and root-relative body MPJPE 36.10 mm. This one-trial contrast establishes a useful baseline, but is not a statistical estimate of the effect of the domain change.

## Not yet completed

- Corrected task/group-weighted calibration: completed; downstream comparison pending.
- Full closed-loop SquatL1 fine-tuning and target deployment comparison.
- SPI-style parameter-identification baseline; full active exploration is a separate stage.
- UAN torque-residual adaptation and genuine high-rate excitation collection.
- Equal-budget calibration-data selection test.
- Target-domain motion-tracking GIF/video comparisons.

The repository's question, argument, hypothesis, pilot evidence and reproducibility overlay have been pushed. A training-pool actuator-feature audit is now available. SPI-style passive SysID and its downstream comparison are queued behind the main ASAP comparison. The UAN-style shared torque model passed CPU interface checks and a 32-environment, four-update physical training smoke run; a same-domain replay smoke test completed all 60 validation windows. No torque-calibration or downstream gain is claimed from these integration checks.

The GPU stages are serialized after an attempted concurrent candidate replay caused CPU contention. An hourly thread follow-up checks artifacts and failures, with the confirmed GPU cutoff retained.

Missing results remain labelled as missing; this file will be updated from actual artifacts.
