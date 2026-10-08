# Aligning Physics

## 1. Open research question

**For humanoid motion tracking with learned simulator correction, which calibration trajectory features improve replay at a fixed data budget? Do these improvements lead to better control after policy fine-tuning?**

## 2. How I arrived at this question

A humanoid can track a motion in simulation and still behave differently on hardware. Actuator response and contact dynamics are two sources of this gap. Calibration tries to make simulation better represent the target robot before further policy training.

Different methods collect different data. [ASAP](https://arxiv.org/html/2502.01143v3) uses motion-tracking policy rollouts to learn an action correction. [SPI-Active](https://github.com/LeCAR-Lab/SPI-Active) designs commands for parameter identification. [UAN](https://arxiv.org/abs/2502.10894v1) uses wave and noise inputs to learn actuator torque corrections.

These works already consider informative data. My question is narrower: **what makes data useful for a learned correction, and does better replay lead to better control?** A large joint range may help, but it does not describe the relationship between commands and actual joint motion. ASAP's data-size experiment also motivates this question. Its replay and control results do not improve in the same way. That observation suggests a question, rather than proving its cause.

## 3. Hypothesis

**At the same data budget, data that covers relevant actuator conditions will improve calibration more than data chosen only for large joint range. The benefit should reach control when those conditions also occur during policy training.**

I test two claims separately: better replay of unseen recordings, and better target-domain control after equal-budget fine-tuning. Replay improvement alone does not confirm the second claim.

## 4. Why this seems plausible

For a PD actuator,

$$
\tau=K_p(q_{cmd}-q)-K_d\dot q.
$$

A stiffness error changes torque through the command error, $q_{cmd}-q$. Joint range alone does not measure this error. Velocity, changing commands and torque limits may also affect what the model can learn. The relevant features depend on the type of dynamics mismatch.

Control adds another issue. A fine-tuned policy chooses new actions and visits new states. A correction that fits the recorded trajectories may be inaccurate there. This explains why I evaluate the complete calibration-and-training pipeline, not just the correction model. [Reasoning and alternatives](docs/research_argument.md).

## 5. Experiments so far

I use G1 in IsaacGym. Domain A has ankle stiffness 20; domain B has stiffness 16. Other dynamics stay fixed. Calibration uses 30 target rollouts: ten each from CR7, SquatL1 and StepFBL1. Each adapted policy receives 1,000 additional PPO updates, then runs in B without a correction model.

The implemented methods are delta action, passive SysID, active SysID and torque correction. The latter two adapt ideas from SPI-Active and UAN to G1. They are not complete reproductions of those papers. A state-transition residual model has not been implemented. [Methods](docs/methods.md).

| Policy | Squat completion (%) | CR7 completion (%) | Step completion (%) |
|---|---:|---:|---:|
| Original | 53.1 | 100.0 | 1.0 |
| Fine-tuning only | 100.0 | 100.0 | 40.6 |
| Delta action | 90.6 | 95.8 | 79.2 |
| Passive SysID | 96.9 | 80.2 | 100.0 |
| Torque correction | 100.0 | 72.9 | 85.4 |
| Active SysID | 95.8 | 90.6 | 90.6 |
| Excitation-data torque correction | 99.0 | 57.3 | 86.5 |

These completion results come from fresh physical evaluations. Each method has one training seed. Calibration helps Step, but shows no extra completion benefit over ordinary fine-tuning on Squat or CR7. All three motions occur in calibration. This is not an unseen-motion test.

![Fresh tracking success, position, velocity and acceleration](results/paper_evaluation/overview.png)

The figure reports 27-point tracking errors and tracking success. Errors use the first second; some CR7 trials end earlier and are excluded from those means. Tracking success also checks the paper's 0.5 m mean body-distance criterion. Velocity and acceleration use mm/frame and mm/frame² at 50 Hz. [Squat](results/paper_evaluation/SquatL1.md), [CR7](results/paper_evaluation/CR7.md), [Step](results/paper_evaluation/StepFBL1.md) and [metric definitions](docs/evaluation.md) give the details.

## 6. Minimum hypothesis test

I select equal-size subsets from the same 18 training rollouts. Each contains 954 transitions. The rules are uniform selection, actuator-feature coverage and large ankle range. Models and training budgets stay the same.

| Selection rule | First-run replay error (mm) | Repeat replay error (mm) | First-run completion (%) | Repeat completion (%) |
|---|---:|---:|---:|---:|
| Uniform | 33.62 | 44.88 | 8.3 | 99.0 |
| Actuator coverage | 28.99 | 35.72 | 41.7 | 77.1 |
| Large joint range | 46.66 | 49.17 | 77.1 | 95.8 |

Fresh replay uses 24 measured target bodies. Coverage gives smaller replay errors in both runs, but it does not consistently give better control. **The combined hypothesis is not confirmed.** Completion changes substantially between training seeds. Selection also changes motion phase and contact conditions, so the results do not isolate one causal feature. The budget fixes selected training data, rather than the cost of acquiring the larger pool. [Data-content experiment](results/content_selection/README.md).

![Data selection: fresh replay and downstream tracking success](results/paper_replay/content_selection.png)

[Experiment details](docs/experimental_protocol.md) · [Reproduction](docs/reproduction.md) · [Reading guide](docs/reading_guide.md)
