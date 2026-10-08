# Evaluation metrics

Fresh physical evaluations of all 28 policies and all 26 calibration replay conditions are complete. They reuse the trained checkpoints and collect new trajectories. No policy is retrained for this metric update.

## Whole-body errors

G1 evaluation includes 24 rigid bodies and three extended points at the hands and head. For predicted position $p_{t,j}$ and reference position $r_{t,j}$, global position error is

$$
E_g=\operatorname{mean}_{t,j}\|p_{t,j}-r_{t,j}\|.
$$

Root-relative error first subtracts each trajectory's own pelvis position. Velocity error compares first differences, $p_{t+1,j}-p_{t,j}$. Acceleration error compares second differences, $p_{t+1,j}-2p_{t,j}+p_{t-1,j}$.

| Metric | Unit | Meaning |
|---|---|---|
| Global position | mm | Whole-body error in world coordinates |
| Root-relative position | mm | Pose error after removing root translation |
| Body velocity | mm/frame | Mean whole-body first-difference error |
| Root velocity | mm/frame | Pelvis first-difference error |
| Body acceleration | mm/frame² | Mean whole-body second-difference error |

The [ASAP paper](https://arxiv.org/html/2502.01143v3#S4) calls its velocity measure root velocity. The [official metric helper](https://github.com/ZhengyiLuo/SMPLSim/blob/master/smpl_sim/smpllib/smpl_eval.py) averages velocity over body points. We report both with distinct names. These units are per frame, not per second. Recording stays fixed at 50 Hz.

## Completion and tracking success

Completion means that the policy reaches the recorded end of the reference motion without an earlier reset. It is shown as a percentage.

The paper's tracking criterion uses average body distance: a trial is unsuccessful if that distance exceeds 0.5 m at any time. Our paper-success score requires both this condition and full completion. Runtime termination remains unchanged, so success is scored separately from termination. The existing environment uses different failure checks, including a maximum-point distance threshold of 1.5 m.

## Failure handling

For policy evaluation, the first stored frame comes from the setup warm step. It is kept for initialization checks and excluded from error means. The success check still includes this state. A reset row belongs to the next episode. It and all later rows are excluded. Derivatives never cross a reset.

Replay also excludes its first stored frame. Torque replay saves only every fourth 200 Hz step. Its model has already acted before the first saved frame at 20 ms. Those states differ from zero correction, so torque results include the startup procedure. Action replay and the six data-selection models have matching first stored states against their controls.

Reports show completion, tracking success and survival. They also distinguish errors over available frames, completed trials and successful trials. Prefix means use only trials that reach that prefix. This prevents a small error over early surviving frames from being presented as full-motion success.

## Historical results

Earlier position reports use 24 actual rigid bodies. Earlier velocity reports are joint-velocity RMSE in rad/s. Those values remain valid for their stated definitions, but they are not the new ASAP-style velocity and acceleration metrics. They are kept as historical evidence.

The new queue is `paper_eval_20261008`. It waits for the second data-content run and its replay controls. It then checks one complete physical rollout before evaluating the remaining policies. A separate fresh replay queue, `paper_replay_20261008`, follows policy evaluation. It replays the existing held-out records with frozen calibration models. Those target records contain 24 physical bodies, so replay reports keep that point set. They use the same position and difference formulas and do not invent hand/head measurements.

Both physics queues and their configuration audits are complete. All fresh stored starts match the historical records. Replay metrics were recomputed from the actual recordings. [Squat](../results/paper_evaluation/SquatL1.md), [CR7](../results/paper_evaluation/CR7.md), [Step](../results/paper_evaluation/StepFBL1.md) and [calibration replay](../results/paper_replay/metrics.md) tables report the measured results.
