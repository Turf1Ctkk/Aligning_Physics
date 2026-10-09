# Training-setting audit

This audit separates an implementation problem from choices in the experiment. It uses saved server configs and the [ASAP paper](https://arxiv.org/html/2502.01143v3). Completed results remain unchanged.

## A confirmed input mismatch

Delta calibration uses zero noise on base height and foot contact force. Policy fine-tuning inherited noise scales of 1.0 and 0.01 on these inputs. Both belong to the frozen delta's observation, even though the task actor does not use them.

The observation helper adds uniform noise before scaling. With noise curriculum disabled, the height channel therefore receives noise between −1 and +1 metre during fine-tuning. It was noiseless during calibration. The three-task repair below tests this mismatch.

Earlier audits checked the deployed task actor's noise. They did not check these frozen-delta inputs during training. The helper now sets both scales to zero. Old checkpoints remain unchanged. The main comparison uses noise-and-reset repaired delta policies for all three tasks; the subset runs retain the old settings. The torque model reads simulator history directly, so this specific noise mismatch does not explain its results.

## FT-only is additional optimization in A

FT-only starts from the same task checkpoint as the calibrated methods and receives 1,000 additional PPO updates in source A. It learns no calibration model and sees no B training environment. It is an extra-training baseline, not the paper's target-domain oracle.

It also does not exactly continue the pretraining configuration:

| Setting | Saved pretraining | Current comparison fine-tuning |
|---|---|---|
| Actor learning rate at setup | 0.001 | 0.0001 |
| Critic learning rate at setup | 0.001 | 0.001 |
| Entropy coefficient | 0.01 | 0 |
| Optimizer state | Load on resume | Reset |
| Motion-distance termination | Enabled with curriculum | Disabled during training |
| Action-rate penalty | −0.5 | −0.2 |
| Penalty curriculum | Enabled, initial scale 0.1 | Disabled, scale 1.0 |
| Initial-state noise multiplier | 0 | 0.2 |
| Used task sensor noise | Nonzero | Zero |

All adapted methods share these policy settings. That makes them an equal-budget comparison under this protocol. It does not make them an exact reproduction of pretraining or of every paper setting. Learning rates change later under the inherited adaptive-KL schedule; the table lists setup values.

## What matches the paper, and what differs

The pipeline learns a correction from target rollouts, freezes it during policy training, and removes it at target deployment. The one-second delta horizon agrees with the best closed-loop horizon in the paper's analysis. The action-norm penalty magnitude is 0.1, also supported by that analysis; Table II separately lists 0.2. This difference alone is not evidence of a bug.

The paper describes fine-tuning with the same task reward as pretraining. Our saved runs change action-rate regularization and penalty scheduling. It also describes a motion-distance curriculum from 1.5 to 0.3 m; ours disables it during fine-tuning. These are material differences to test, not proven explanations of a particular failure.

This study uses a small, controlled ankle-gain change in one engine. It has 30 calibration rollouts and one training seed per main method. It uses two-gain SysID and G1 command adaptations rather than literal SPI-Active or UAN reproductions. Action and torque models have different architectures and transition budgets. Paper improvements cannot be assumed to hold under all these changes.

## Implementation and evaluation checks

The installed CPU checks pass for action units, current-action conditioning, post-step replay time, grid indexing, recorded velocities and sampling weights. The five core patches are still installed. Fresh policy evaluation matches all historical stored starts and effective deployment settings. Deployments attach no correction model.

Replay uses 24 measured target bodies; policy evaluation uses 27 points. Both report the four requested error formulas. Main E_vel follows the paper's root-velocity description, while body velocity remains in the raw reports. Closed-loop figures distinguish first-second errors from full-motion success. Torque replay includes startup before its first saved state; it is not a same-post-step-state contrast against zero correction.

The original and FT-only source-domain checks use the same frozen checkpoints and evaluation protocol, with only ankle gains changed from 16 to 20. Physics and the config audit are complete. Original Step succeeds at 90.6% in A and 1.0% in B. [Source quality](../results/source_quality/metrics.md).

The author chose a minimal repair comparison on all three motions. It zeros only the two frozen-delta noise channels. It reuses the same calibrator, source checkpoint, training seed and 1,000-update budget. Rewards and curricula stay the same.

All three repairs are complete. Squat success falls from 89.6% to 70.8%, although first-second global position, velocity and acceleration errors decrease. CR7 success rises from 91.7% to 99.0%; first-second acceleration error increases. Step success falls from 79.2% to 25.0%. None exceeds its FT-only success.

All tasks pass the saved-setting checks and exact stored-start comparison. All trial metrics were recomputed. The input mismatch is confirmed, but repair does not uniformly improve control in this training seed. It does not resolve the remaining setting differences or prove that data size causes the failures. [Repair results](../results/noise_repair/metrics.md).

## A further reset issue

The installed closed-loop training environment clears nominal actions at an episode reset. It does not clear `actions_closed_loop`. This value is part of the frozen delta's next input. Calibration clears its corresponding previous-action input, so the two reset paths differ.

A CPU check executed the installed reset and observation methods with synthetic buffers. The nominal action became zero, while the previous delta remained in the observation. This confirms the reset issue. It does not measure its effect during physical training or explain the success rates. No runtime file or checkpoint was changed. [Audit](../results/settings_audit/delta_reset_contract.json).

Two later physical probes tested this path on Step without updating weights. The retained input changed the ankle correction by up to 0.571 action units at a reset state. An opt-in environment clears the input and passes the same check. Core files and existing checkpoints stay unchanged. This issue does not apply to the SysID or torque interface. [Physical check](../results/delta_reset_probe/metrics.md).

The author approved a separate three-task reset-only comparison. All tasks are complete. Success rises from 70.8% to 91.7% for Squat and from 25.0% to 37.5% for Step. All four first-second errors decrease in both tasks. CR7 success falls from 99.0% to 94.8%. Its relative position and velocity errors decrease, while global position and acceleration errors increase. Full-motion errors do not uniformly improve, and successful cohorts change.

Saved training settings differ only in the reset environment and output paths. All stored starts and deployment settings match, and every new trial metric was recomputed. This is one paired training seed per task, so it does not establish a general improvement. All fixed-final reset-repaired policies enter the main comparison together. [Reset results](../results/reset_repair/metrics.md).
