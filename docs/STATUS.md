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

New weighted delta training and isolated replay have completed. Validation selects the 500-update checkpoint. Held-out global body MPJPE decreases from 37.66 to 30.51 mm; velocity RMSE slightly worsens (0.87892 to 0.89057 rad/s). All 66 one-second test windows complete. Both equal-budget task-policy runs and B deployment comparisons have completed: FT-only completes 96/96 trials, ASAP FT 87/96, and passive SysID FT 93/96. ASAP has no additional benefit over the FT-only control in this training seed. First-second tracking, survival, raw trials and fixed-trial animations are published.

The original-policy evaluation inherited nonzero task-observation noise, while the fine-tuned policies used zero noise. Its 37/96 completion is retained as an audited historical artifact, excluded from the matched method table. A full explicit common-noise reevaluation is queued after the running torque stage; no weights are retrained. All evaluations preserve original Squat termination criteria.

An additional matched clean source-domain check completed all 261 recorded frames (5.22 seconds), with global body MPJPE 87.07 mm and root-relative body MPJPE 36.10 mm. This one-trial contrast establishes a useful baseline, but is not a statistical estimate of the effect of the domain change.

## Not yet completed

- Common-noise reevaluation of the original and all adapted policies.
- Active exploration and new target acquisition; passive parameter fitting is complete.
- UAN torque-residual adaptation and genuine high-rate excitation collection.
- Equal-budget calibration-data selection test.
- CR7 and StepFBL1 downstream extensions.

Passive SysID selected pitch/roll gains 13.0122/10.4212 rather than the configured target 16/16. Test replay body error is 30.87 mm and velocity RMSE 0.80029 rad/s; all 66 windows complete. This is trajectory fitting, not demonstrated parameter recovery. A post-hoc known-gain control is queued for diagnosis. The UAN-style shared torque model is now in its full calibration run; no calibration or downstream gain is claimed from its earlier smoke checks.

The GPU stages are serialized after an attempted concurrent candidate replay caused CPU contention. An hourly thread follow-up checks artifacts and failures, with the confirmed GPU cutoff retained.

A bounded-command active-acquisition stage is queued after the torque comparison and matched reevaluation, with matched unchanged/random/optimized acquisition budgets. CPU checks verify command support, a known finite-difference information matrix, and rejection of infeasible trajectories. Physical acquisition, refitting and control results remain pending. This adaptation does not use the original Go2 command interface; its scope and assumptions are described in the methods document.

CR7 and StepFBL1 extensions are queued after active acquisition. They reuse the frozen multi-motion corrections and fitted gains, with fresh equal-budget fine-tuning from each task's recorded `model_6000.pt`. Their original termination flags and thresholds were inspected and match the common evaluation overrides. No additional-task result is available yet.

Missing results remain labelled as missing; this file will be updated from actual artifacts.
