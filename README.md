# Aligning Physics

## 1. Open research question

**For humanoid motion tracking with a learned residual alignment model, which calibration trajectory features improve open-loop replay when the amount of target data is fixed? Do these gains also improve closed-loop policy control?**

## 2. Background

Motion tracking asks a humanoid to follow a sequence of reference poses while maintaining balance. Reinforcement learning can train a feedback policy for this task in simulation. However, the same policy may behave differently on hardware. Actuator response and contact dynamics can differ from the training environment.

One approach is to adjust simulation using data from the target domain. The adjusted environment is called **calibrated simulation** throughout this report. Three works motivate the experiments:

| Work | What it adjusts | What data it uses |
|---|---|---|
| [ASAP](https://arxiv.org/html/2502.01143v3) | Position-target actions through a learned delta action model | Target motion-tracking policy rollouts |
| [SPI-Active](https://github.com/LeCAR-Lab/SPI-Active) | Physical parameters through identification and active exploration | Responses to commands chosen for identification |
| [Unsupervised Actuator Net (UAN)](https://arxiv.org/abs/2502.10894) | Actuator torque through a learned correction | Responses to wave and noise inputs |

These methods use different data to model different parts of the dynamics. They do not give a single data-selection rule for learned correction. A large joint range may not expose the response difference that matters for control.

I tested these ideas in ASAP under a known ankle-stiffness change. Replay improved to different degrees, while control results were less consistent. This motivates the research question.

## 3. Method comparisons

Both domains use G1 in IsaacGym. Four ankle stiffness values change from $K_p=20$ in source A to $K_p=16$ in target B. Other dynamics stay fixed. This known change helps interpret the results; it is not a hardware test.

| Method | Principle |
|---|---|
| Original | Deploy the source policy directly in B. |
| FT-only | Further train the policy in uncalibrated A. |
| Delta action | Learn an action correction from B recordings, then train the policy in calibrated simulation. |
| Passive SysID | Fit ankle pitch and roll gains to recorded joint trajectories. |
| Active SysID | Design informative command offsets, collect new trajectories, and fit the gains. |
| Common torque | Learn a torque correction from the original motion-tracking recordings. |
| Excitation torque | Learn a torque correction from new wave/noise excitation recordings. |

Each task uses its source policy after **6,000 PPO updates**. I run these policies in B to collect commands and states. Calibration then makes replay in A approach those recorded B trajectories. Each adapted policy receives **1,000 further PPO updates** in calibrated simulation. The final policy runs alone in B. FT-only receives the same number of policy updates. Calibration procedures differ between methods.

The SysID and torque methods adapt SPI-Active and UAN ideas to G1. This is not a full reproduction of either paper. Formulas and implementation differences are in [Methods](docs/methods.md). Settings, data collection and implementation fixes are in [Training details](docs/training_details.md).

### Open-loop replay

The chart compares replay in A with recorded trajectories in B over one second. It averages equally across tasks and original recordings. FT-only shares the Original replay value because this test uses fixed recorded commands.

![Four open-loop errors](results/open_loop.png)

All calibrated methods reduce the four mean errors. Active SysID gives the smallest errors. Its fitted pitch/roll gains, **15.80/15.59**, are also close to the target **16/16**. This is consistent with effective identification in this simple mismatch. It does not show that parameter fitting can capture every hardware discrepancy. Passive SysID fits **13.01/10.42**, showing that a useful trajectory fit need not recover the physical parameters.

### Closed-loop motion tracking

Errors below cover the first second in B. Squat and Step include all trials. CR7 inclusion is 100% for Original, FT-only and Delta action; 95.8% for both SysID methods; 89.6% for Common torque; and 85.4% for Excitation torque. Full-motion success is shown separately.

![Four closed-loop errors by task](results/closed_loop.png)

![Full-motion success by task](results/success.png)

Both tests report $E_{g-mpjpe}$, $E_{mpjpe}$, $E_{acc}$ and root $E_{vel}$. Units are mm, mm/frame² and mm/frame at 50 Hz. Replay uses 24 measured bodies; tracking uses 27 points. Success requires completing the motion while mean body distance stays within 0.5 m. Full-motion errors for successful trials are also retained in `results/metrics.csv`.

The original Step policy reaches 90.6% success in A but only 1.0% in B, confirming a transfer challenge under this protocol. Every adapted method improves success over Original on Squat and Step. CR7 already reaches 100% with Original and FT-only; calibration methods reduce its success. Better replay therefore does not guarantee better tracking or higher success. The experiments do not isolate the cause of this difference.

### Recorded examples

These author-recorded clips show behavior in B. They are partial recordings with different start phases. A blank panel marks a clip’s end. Quantitative conclusions use the evaluations above.

**Squat — Left: Original. Right: Delta action.** The delta policy appears more conservative during the squat. Aggregate success rises from 44.8% to 91.7%. Its four first-second errors also decrease. Over successful full motions, root-relative error increases from 50.62 to 55.78 mm, with different successful cohorts. The result is not an increase in every error.

![Squat comparison](results/visualizations/squat.gif)

**CR7 — Left: Original. Right: FT-only.** Both policies jump and return to standing. Further training lowers global error but raises root-relative error. Both have 100% aggregate success.

![CR7 comparison](results/visualizations/cr7.gif)

**Step — Left: Original. Right: Passive SysID.** Original leans sharply away from the reference, while Passive SysID stays upright during the recorded step. Aggregate success rises from 1.0% to 100%. The clip does not isolate the balance mechanism.

![Step comparison](results/visualizations/step.gif)

## 4. Observations and reasoning

Replay measures agreement under recorded commands. Fine-tuning changes the commands and visited states. A correction can fit recordings yet be less useful for the new policy. A pooled replay average cannot explain a particular task's control result.

The known mismatch suggests a measurable data property. For an unsaturated PD actuator, let $e=q_{cmd}-q$. At the same state and command, with equal damping,

$$
\tau_B-\tau_A=(16-20)e=-4e.
$$

Matching this torque instantaneously in A requires

$$
\Delta q_{cmd}=-0.2e.
$$

Servo error therefore exposes the stiffness difference more directly than joint range. Its sign and magnitude both matter. Large error alone is not enough: clipping can hide the gain difference. The correction also runs at 50 Hz while PD runs at 200 Hz, so instantaneous matching does not guarantee trajectory matching.

## 5. Hypothesis

**For this ankle-stiffness mismatch, calibration windows covering different signs and magnitudes of unsaturated ankle servo error will reduce held-out replay error more than random windows of the same total size. Whether this gain improves policy control is tested separately.**

This hypothesis concerns the current gain change.

## 6. Minimum hypothesis test

I compare **Random windows** with **Servo-error coverage**. Both select from the same target training recordings: six from each of the three motions. Each recording contributes one continuous 54-state window, giving **954 transitions per dataset**. Random selection follows fixed task, phase, speed and contact-proxy quotas. Servo-error coverage follows the same quotas but fills sign/magnitude bins separately for each ankle.

Each dataset trains a fresh delta action model with the same architecture and 1,000 updates. Both then fine-tune the same Step source policy for 1,000 updates. Noise and reset fixes are applied. Validation and test recordings are shared and separate from training. Two runs change the calibration and policy training seeds; replay and deployment seeds stay fixed.

![Four replay errors in the minimum test](results/selection_replay.png)

![Four Step tracking errors in the minimum test](results/selection_control.png)

| Training run | Random windows success | Servo-error coverage success | Matched FT-only success |
|---|---:|---:|---:|
| Run 1 | 0.0% | 0.0% | 5.2% |
| Run 2 | 20.8% | 33.3% | Not evaluated |

FT-only in this test is newly trained with the Run 1 policy seed. It is distinct from the main comparison’s FT-only policy.

Random windows give lower replay error on all four measures in both runs. Thus, **this selector has not supported the calibration hypothesis**. In Run 2, Servo-error coverage gives better Step success and lower first-second tracking errors despite worse replay. This reinforces the need to evaluate replay and control separately.

The servo-error contrast is modest, and speed/contact distributions still differ. Two runs cannot establish a stable ranking. Low-error windows were prepared but not trained. Selected windows and final results are retained as CSV files.

**Future work:** test a stronger data contrast and transfer from IsaacGym to IsaacLab or Genesis. No cross-engine results are claimed here.

The `ASAP/` folder contains the framework source, installed fixes and method implementations. Model weights and calibration recordings are held in the separate experiment archive. This public repository provides the report, final metrics, settings, reference motions and code.
