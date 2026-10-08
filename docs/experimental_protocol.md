# Experimental protocol

## Controlled mismatch

Both domains use IsaacGym and G1. A has ankle pitch and roll stiffness 20; B has stiffness 16. Other physics stays fixed and domain randomization is off. This isolates a simple dynamics difference before testing more complex gaps.

## Calibration data

The main dataset contains ten B rollouts from each of CR7, SquatL1 and StepFBL1. A rollout can contain several continuous clips because of resets. Splits are made by the original rollout before clips or evaluation windows are formed. Training, validation and test parents remain separate.

Sampling gives equal weight to tasks, then to rollouts, then to their continuous clips. Delta training uses one-second episodes, 2,048 environments and 1,000 PPO updates. Only ankle residuals affect physics. Validation chooses between calibration checkpoints; test results do not choose a model.

## Policy training and deployment

Each task starts from its own recorded pretrained policy. Every adaptation receives 1,000 further updates. A fine-tuning-only arm controls for extra training. Calibration models remain frozen. The final policy runs alone in B.

Evaluation uses seeds 8101–8103 and 32 trials per seed. Squat is recorded for 5.22 seconds; CR7 and Step for 3.92 seconds. Initialization, used observation noise and enabled termination settings are matched. One training seed per method limits conclusions about the reliability of method rankings.

[Metric definitions](evaluation.md) explain the new whole-body evaluation. Old physical records remain available for comparison.

## Data-content test

The three rules use the same 18 training parents, six per task. Each selects one 54-state window per parent, giving 954 transitions. Candidate windows and the feature scaler use training data only.

| Rule | Selection |
|---|---|
| Uniform | Seeded random window per parent |
| Actuator coverage | Windows that cover servo error, velocity, command changes and torque regimes |
| Joint range | Window with large mean ankle excursion |

Each rule receives the same action model, sampler and 1,000 calibration plus 1,000 policy updates. The manifest was published before outcomes and remains unchanged. Same-domain replay errors are reported without subtraction or window replacement.

Both seeds are complete. The second uses byte-identical datasets with new training seeds. Replay evaluation seed also changes, so its new zero-correction controls are measured separately. Deployment seeds stay fixed. Both runs are reported, without selecting a favorable seed. These completed action-policy runs contain the frozen-delta noise mismatch found in the [setting audit](settings_audit.md).

This is retrospective selection from an existing pool. Equal selected transition counts do not mean equal total acquisition cost. Motion phase, contact and initialization may change with the selected window. The test compares selection rules, not the causal effect of a single feature.

## Run policy

Heavy stages are serialized. A failed stage stops dependent work. Checkpoints and failed acquisition groups are preserved. Existing incomplete runs are not silently resumed. GPU experiments stop at 09:00 UTC on October 9, leaving time to prepare the submission.
