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

The original-policy evaluation inherited nonzero task-observation noise, while the fine-tuned policies used zero noise. Its 37/96 completion is retained as an audited historical artifact. The completed explicit common-noise reevaluation gives 51/96 for the original policy, 96/96 FT-only, 87/96 ASAP, 93/96 passive SysID, and 96/96 torque-model FT. No weights were retrained. All evaluations preserve original Squat termination criteria. The first stored states/actions match exactly across all five conditions for all 32 seed8101 trials. [Matched evidence](../results/matched_squat/README.md).

An additional matched clean source-domain check completed all 261 recorded frames (5.22 seconds), with global body MPJPE 87.07 mm and root-relative body MPJPE 36.10 mm. This one-trial contrast establishes a useful baseline, but is not a statistical estimate of the effect of the domain change.

A post-hoc first-second deployment-feature audit has also completed for all 96 trials per method. It observes different actuator regimes relative to mixed30 calibration support, but does not establish that feature distance explains control ranking. Calibration-only scaling/reference, per-trial measures and the one-training-seed boundary are documented in [the audit](../results/policy_regimes/README.md). The queued selectors are unchanged.

## Not yet completed

- Active-arm policy comparison; design, acquisition, refitting and replay completed.
- Genuine high-rate excitation collection and learning; common-data torque adaptation completed.
- Equal-budget calibration-data selection test.
- CR7 and StepFBL1 downstream extensions.

Passive SysID selected pitch/roll gains 13.0122/10.4212 rather than the configured target 16/16. Test replay body error is 30.87 mm and velocity RMSE 0.80029 rad/s; all 66 windows complete. This is trajectory fitting, not demonstrated parameter recovery. Post-hoc training-window loss is 1.11580 for source20, 0.48918 for known 16, and 0.27028 for fitted gains: the current objective itself prefers the fitted surrogate. The precise cause remains unresolved. The UAN-style shared torque calibration, replay and policy comparison are complete: replay body error 36.69→24.48 mm, velocity 0.862→0.951 rad/s; all 66 windows complete. Validation chooses its 1000-update checkpoint. Its policy completes 96/96 trials but has higher full-horizon body error than FT-only (105.12 versus 94.45 mm, both 96 completed).

The GPU stages are serialized after an attempted concurrent candidate replay caused CPU contention. An hourly thread follow-up checks artifacts and failures, with the confirmed GPU cutoff retained.

A bounded-command active-acquisition stage has completed design and new target acquisition, with matched unchanged/random/optimized acquisition budgets. The initial central-window unchanged controls violated feasibility limits in two CR7 parent recordings; the random control additionally failed in a third before optimization. All failed artifacts were archived. The revised run uniformly uses the first 54 states of each parent's first eligible segment, keeps all 30 parents and the original limits, and passes all 90 acquisition command-alignment checks (52 recorded frames each). All three refits and held-out replay are complete; optimized-arm policy fine-tuning is running. This adaptation does not use the original Go2 command interface; its scope, revision and assumptions are described in the methods document.

True-200Hz target acquisition is queued after active acquisition, with matched unchanged-input and bounded-wave/noise arms. CPU wave/holding/alignment-corruption contracts passed; physical acquisition is pending. Each arm uses 30 groups and 6210 unique transitions, the same torque model and calibration/policy budget. Same-domain replay and command recording will be checked before learning. This is a closer UAN data adaptation, with its G1 command-interface boundary disclosed.

CR7 and StepFBL1 extensions are queued after this true-rate comparison. They reuse the frozen multi-motion corrections and fitted gains, including the wave model, with fresh equal-budget fine-tuning from each task's recorded `model_6000.pt`. Their original termination flags and thresholds were inspected and match the common evaluation overrides. No additional-task result is available yet.

The minimum content test is queued after the task extensions, conditional on at least five hours before cutoff. Its selector preview fixes identical 18 parent groups and 954 unique transitions per uniform/coverage/joint-range arm; no validation/test features are used. Each selected subset will have its own reported same-domain replay floor. Calibration and downstream results are pending.

Missing results remain labelled as missing; this file will be updated from actual artifacts.
