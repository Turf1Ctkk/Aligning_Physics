# Experimental protocol

This protocol specifies the confirmed first experiment and proposed follow-up studies. Mixed-motion 30-group data, same-engine Kp20→Kp16 mismatch, and the initial calibration budget have been confirmed. Previously completed pilot results are recorded separately.

## Primary comparison and budgets

Use the same pretrained task policy, source simulator, target dynamics, reference motion, evaluation initial states, and evaluation seeds for all downstream comparisons. Train in the calibrated source simulator and deploy in the target without the calibration mechanism attached. Include both the original policy and an equal-budget source-domain fine-tuning control.

The proposed first calibration dataset is 10 original training recording groups per motion, for CR7, SquatL1, and StepFBL1. The alternative is 30 SquatL1-only groups. Keep the existing held-out recording groups isolated. Neither option implies that clips or transitions have identical counts; report all three measures and useful target-domain duration.

Fix sampling by task, then original recording group, then valid continuous clip/window. When using clip weights to implement this hierarchy, assign

$$
p(c)=\frac{1}{N_{\mathrm{tasks}}}\frac{1}{N_{\mathrm{groups},m}}\frac{1}{N_{\mathrm{clips},g}}.
$$

Sample a valid grid-aligned start within the chosen clip. This gives equal task and group weights, while avoiding reset-induced clip-count overweighting. Verify the actual loaded batch distribution as well as nominal probabilities. Resampling the motion library must preserve these probabilities.

## Integrity checks

1. Split by original recording group before segmentation or overlapping-window creation.
2. Exclude reset rows and windows crossing time discontinuities. Record rejected durations and reasons; do not select clips by downstream success.
3. Respect the recorder's post-step convention: state[i] transitions under action[i+1] to state[i+1].
4. Restore recorded joint velocities and world-frame root velocities. Normalize environment origins consistently.
5. Reserve enough frames for the full episode, including the implementation's extra timeout step.
6. Compare same-domain zero-correction replay before interpreting cross-domain improvement. Diagnose substantial residual error; do not subtract it linearly from cross-domain metrics.
7. Freeze the calibration network during task-policy fine-tuning; condition it on the current nominal action, with the same observation scaling and action units used during calibration.
8. Verify that target deployment invokes the task policy only, with the original observation/history contract and no residual hook.

## Proposed calibration settings

| Item | Initial proposal |
|---|---|
| Robot | G1, 23 actuated joints |
| Simulator | IsaacGym in both domains |
| Source / target gap | ankle pitch and roll Kp20 / Kp16 |
| Physics / nominal policy rate | 200 Hz / 50 Hz |
| Delta-action update rate | 50 Hz |
| Delta physical support | four ankle joints; retain existing masked interface initially |
| Replay training horizon | 1 second |
| Parallel environments | 2048 |
| Calibration PPO iterations | 1000 initially; validation chooses checkpoint |
| Minimal-action-norm reward scale | -0.1 |
| Domain randomization | disabled for the mechanism comparison |
| Independent training seeds | one pilot first, additional seeds for key comparisons if feasible |

Task-policy fine-tuning starts from SquatL1 `model_6000.pt`, retains the learned policy weights and standard deviation, resets optimizer state, and uses 1000 **additional** iterations. Initial actor LR is 1e-4, critic LR 1e-3, and entropy coefficient 0. Apply the same choice to both downstream conditions. The first comparison uses fixed final-iteration policy checkpoints, rather than selecting them on the evaluation seeds.

## Metrics

Replay: global and root-relative body MPJPE, ankle/all-joint position RMSE, joint-velocity RMSE, root and foot position errors, and complete-window fraction at 0.25, 0.5, and 1 second. Include failure/termination accounting rather than averaging only surviving trials.

Closed-loop: full-reference motion tracking in the target domain, including global/root-relative body errors, completion/fall rate, and survival duration. Fix the evaluation horizon and termination rules. Multiple windows or evaluation seeds from one trained model are not independent training replications.

## Minimal test of data content

Create equal-budget continuous-window subsets from one training pool:

- **Uniform:** sample without using error or coverage scores.
- **Actuator coverage:** cover signed servo errors, joint velocities, and nominal-command changes. Fit feature scaling and bins on the training pool only.
- **Joint range:** select for broad joint-position excursion as the competing explanation.
- **High replay error, optional:** select for uncorrected short-horizon trajectory discrepancy, checking whether it enriches initialization/contact artifacts.

Use the same number of unique target transitions and the same PPO budget. Limit overlapping windows; record any history prefix as part of the data budget. Keep motion and parent-group distributions matched where possible, and show remaining imbalances explicitly.

The hypothesis is unsupported if coverage fails to outperform uniform selection within uncertainty. A replay improvement without target-domain policy improvement supports only the replay component. Repeat key comparisons with independent training seeds before claiming a stable ranking. A second mismatch is required to support the claim that useful features depend on the mechanism, rather than merely the current Kp test.

## Timing and release

Submission deadline: 2026-10-09 23:59 UTC+03:00, equivalent to 20:59 UTC. Proposed experimental cutoff: 2026-10-09 12:00 UTC+03:00. Prefer a complete one-motion comparison with honest limitations over incomplete three-motion claims. Preserve a reviewable repository before the deadline; do not postpone documentation until all methods finish.
