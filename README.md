> **Open research question:** For humanoid motion-tracking policies adapted through a learned simulator correction, which measurable properties of a fixed-budget target-domain dataset make calibration improve both trajectory replay and downstream closed-loop control?

# Aligning Physics: What Makes Calibration Data Useful?

An experimental research proposal on calibration data for humanoid control, built on [ASAP / Humanoidverse](https://github.com/LeCAR-Lab/ASAP). The current experiments use a Unitree G1 model in **controlled sim-to-sim transfer**. They do not constitute hardware validation.

**Current evidence:** multi-motion delta-action training improves several held-out replay metrics. The new task/group-weighted mixed30 run reduces test global body position error by 19.0%, while velocity error remains slightly worse. Closed-loop policy adaptation is running, and the proposed data-content hypothesis has not yet been validated. Measured results and proposed experiments are labelled separately.

## How I arrived at the question

A humanoid tracking a reference motion must coordinate actuator response, balance, and contact. A policy that tracks well in its training simulator can respond differently after deployment. More policy training is not necessarily enough when the simulator describes the wrong transition dynamics.

There are several ways to address this mismatch. Structured system identification estimates physical parameters; domain randomization trains across parameter variation; learned corrections adjust the simulator from target-domain observations. These approaches depend on both the model class and the information in the calibration data.

The data-collection choices in related work motivated this project:

| Work | Correction and data collection | What it suggests about data |
|---|---|---|
| [ASAP](https://arxiv.org/html/2502.01143v3) | Learns action corrections from pretrained motion-policy rollouts, then freezes the correction during policy fine-tuning. | Task rollouts can provide useful calibration data. |
| [SPI-Active](https://arxiv.org/html/2505.14266v1) | Uses sampling-based parameter estimation and optimizes exploration commands using Fisher information. | Excitation should depend on the parameters being identified. |
| [UAN](https://arxiv.org/html/2502.10894v1) | Learns actuator torque corrections from history; collects square-wave, sine-wave, and noise inputs. | Coverage can come from structured excitation rather than task-policy rollouts. |

[Contact-UAN's author project page](https://contact-uan.csail.mit.edu/) further reports cross-behavior reuse of walking calibration and highlights contact-consistent initialization. This strengthens the case for studying reusable dynamics regimes, and also warns that an apparent calibration benefit can partly correct replay artifacts.

These papers already study data informativeness or explicitly motivate excitation. **I am not claiming that informative data collection is an unstudied problem.** The narrower question is how to diagnose useful data for an ASAP-style learned correction, and whether its usefulness for replay predicts its usefulness for subsequent control.

ASAP's Fig. 10(a) is a particular motivation: replay generalization continues to improve with dataset size, while the reported closed-loop benefit changes little at the largest scales. This observation does not establish a causal explanation. It motivates separating three possibilities: additional data may repeat already-covered dynamics, improve errors that matter little to control, or fail to cover states visited by the fine-tuned policy. Model capacity, optimization, and initialization artifacts are alternative explanations that must be controlled.

## Hypothesis

**At equal calibration-data and optimization budgets, covering mismatch-sensitive actuator regimes that overlap downstream policy behavior will support learned calibration better than selecting data solely for large joint range or large uncorrected trajectory error.**

Here, useful regimes may include the direction and magnitude of commanded position error, torque headroom, joint velocity, and command change. Motion names and clip count are indirect proxies. Contact phase and history may matter for some mismatches, but are not assumed to be sufficient or necessary in advance.

There are two separately falsifiable parts:

1. Coverage-based selection improves replay on held-out target trajectories relative to uniform selection.
2. With the correction frozen during equal-budget policy fine-tuning, that improvement transfers to control in the target domain **without the correction at deployment**.

An improvement in replay alone supports only the first part. Equal or worse performance under coverage selection is an informative negative result.

## Why this hypothesis is plausible

Calibration aims to align transition models, rather than reproduce an action's name or its reference pose. For a PD actuator,

$$
\tau = K_p e-K_d\dot q,\qquad e=q_{\mathrm{cmd}}-q.
$$

A stiffness mismatch directly couples to the servo error $e$. A large joint excursion does not imply a large servo error, and two motions can excite similar actuator regimes despite having different names. This provides a concrete reason to measure command-state relationships rather than joint range alone.

The same reasoning is conditional on the mismatch: velocity-dependent friction, torque saturation, and delay need different excitation. It is not a theorem that one coverage measure is optimal for every residual model. For the present Kp test, velocity is a conditioning feature, not automatically an independent source of stiffness information. The post-step record also requires computing the next-transition servo error from state[i] and action[i+1].

Torque clipping further complicates “more excitation”: when both systems saturate in the same direction, increasing servo error can leave their instantaneous applied torques identical. A descriptive audit of the existing training pool finds substantially different command-state distributions and source-model saturation fractions across tasks. This motivates measuring torque headroom as well as range; it does not establish which subset trains a better model. [Feature analysis and figure](results/calibration_features/README.md).

Closed-loop adaptation adds another condition. The fine-tuned policy generates its own actions and visits its own states. A correction accurate on recorded inputs may be inaccurate on this changed distribution, or a policy may exploit its errors. Therefore, low average replay error need not be a sufficient proxy for downstream control quality. [The full research argument](docs/research_argument.md) derives these distinctions and lists competing explanations; [the experimental protocol](docs/experimental_protocol.md) makes them testable.

## What has actually been run

The completed pilot uses the same IsaacGym implementation in both domains:

- **Source A:** default ankle stiffness, $K_p=20$.
- **Target B:** ankle pitch and roll stiffness reduced to $K_p=16$; other modeled dynamics held fixed for the calibration comparison.
- **Data:** pretrained CR7, SquatL1, and StepFBL1 policies rolled out in B, recording actual states and executed nominal actions.
- **Calibration:** PPO delta-action learning in A, with physical corrections restricted to the four ankle joints. The existing network retains a 23-dimensional output interface and masks other corrections; this is not a literal four-output-network reproduction.
- **Evaluation:** held-out B recordings replayed in A, using fixed recorded nominal actions and state-conditioned learned corrections. The correction itself is a feedback model; “open-loop replay” refers to the recorded nominal action sequence.

The pilot required correcting action/frame alignment, restoring recorded initialization velocities, and correcting the frozen delta's action scaling and current-action conditioning. These are prerequisites for interpreting physical calibration, not evidence for the research hypothesis. [Implementation notes and patches](docs/reproduction.md) document the changes.

### Measured pilot results

Training subsets contain 3, 30, or 90 original environment-recording groups, equally divided across the three motions before segmentation. Automatic resets create multiple continuous clips per group. Splits are made by original recording group before creating evaluation windows.

| Setting | Training groups | Continuous training clips | Ankle RMSE (rad) ↓ | Joint-velocity RMSE (rad/s) ↓ | Global body MPJPE (mm) ↓ |
|---|---:|---:|---:|---:|---:|
| B replay, zero delta: same-domain check | — | — | 0.02041 | 0.56583 | 10.24 |
| A replay, zero delta: mismatch baseline | — | — | 0.07290 | 0.85052 | 35.99 |
| A replay, learned delta | 3 | 5 | 0.06682 | 0.93544 | 29.33 |
| A replay, learned delta | 30 | 41 | 0.05794 | 0.93312 | 27.43 |
| A replay, learned delta | 90 | 128 | 0.05654 | 0.87592 | 28.40 |

These are 1-second prefixes, using 24 actual simulated rigid-body positions. Means are averaged within original recording groups, then within tasks, then equally across tasks. The test partition contains 15 recording groups and 66 correlated windows. Checkpoints are selected using validation data, not test performance. This pilot has one training seed.

![Pilot data-scale results](assets/figures/pilot_data_scale.png)

The learned corrections reduce global position error by approximately 18.5%, 23.8%, and 21.1% relative to zero correction. More data does not improve every metric: velocity error remains worse than the mismatch baseline for all three learned models.

**Two limitations prevent a clean data-scaling conclusion.** First, the original loader samples segmented clips uniformly. The CR7/Squat/Step sampling proportions change from 20/40/40% to approximately 24/27/49% and 23/30/47% across subsets. Data amount and task weighting are therefore confounded. Second, same-domain replay error is non-negligible, particularly for CR7; arbitrary-window initialization and configuration need further audit. The next calibration run will explicitly control task and recording-group weights. These results are an exploratory pilot, not confirmation of saturation or of the hypothesis.

Raw summary evidence and a detailed audit are in [results/pilot_multimotion](results/pilot_multimotion/README.md).

### New controlled run

The agreed mixed30 run has completed calibration and isolated validation/test replay with corrected task/group sampling. Validation selects the 500-update checkpoint. On the held-out test, global body MPJPE changes from **37.66 to 30.51 mm** and ankle RMSE from **0.07500 to 0.06131 rad**. Joint-velocity RMSE changes from **0.87892 to 0.89057 rad/s**, a regression. All 66 one-second test windows complete; same-domain body replay error is 7.40 mm. These outcomes support a partial replay benefit, not the downstream hypothesis. [Settings, raw evidence and an actual-motion baseline animation](results/controlled_squat/README.md).

## Next experiments: planned, not completed

The first priority is a complete SquatL1 adaptation comparison:

| Controller evaluated in B | Purpose | Status |
|---|---|---|
| Original pretrained policy | Direct-transfer baseline | One clean trial; systematic evaluation queued |
| Policy fine-tuned in A without calibration | Equal-budget continued-training control | Training |
| Policy fine-tuned in A with frozen delta, deployed without delta | ASAP downstream benefit | Queued |
| Policy fine-tuned with identified physical parameters | Structured SysID comparison | Queued |
| Policy fine-tuned with a learned torque correction | UAN-method comparison | Small integration tests passed; full run queued |

Each method must first pass replay and integration checks. Results will be recorded whether or not control improves. The goal is to compare correction mechanisms in a common G1 task, not assume the relative ranking reported on different robots and tasks transfers here.

The [method adaptation plan](docs/methods.md) distinguishes SPI parameter estimation from the additional active-exploration stage, and distinguishes an actuator torque model from an action residual. Adapted experiments will disclose differences in robot, data source, horizon, update rate, and model architecture. A parameter search alone will not be labelled a full SPI-Active reproduction.

If time permits after the pipeline comparison, a minimal hypothesis experiment will compare uniform, actuator-coverage, and joint-range-based selection from the same training pool at equal transition budgets. Training settings, validation selection, and downstream fine-tuning budgets will be fixed. Complete motions will be held out for a separate cross-motion calibration test; the current pilot does not provide that test.

## Reproducibility and interpretation

- [Experimental protocol](docs/experimental_protocol.md): data budget, splits, controls, metrics, and falsification criteria.
- [Method formulations and adaptation boundaries](docs/methods.md).
- [Replay corrections and reproduction notes](docs/reproduction.md).
- [Experiment status](docs/STATUS.md): completed evidence versus planned work.

No robot-hardware results, closed-loop gains, SPI-Active gains, UAN gains, or data-selection gains are claimed until corresponding artifacts exist. The controlled stiffness mismatch is a deliberately narrow mechanism test; it cannot establish full sim-to-real fidelity.

## References

1. [ASAP: Aligning Simulation and Real-World Physics for Learning Agile Humanoid Whole-Body Skills, v3](https://arxiv.org/html/2502.01143v3).
2. [Sampling-Based System Identification with Active Exploration for Legged Robot Sim2Real Learning, v1](https://arxiv.org/html/2505.14266v1); [official implementation](https://github.com/LeCAR-Lab/SPI-Active).
3. [Bridging the Sim-to-Real Gap for Athletic Loco-Manipulation, v1](https://arxiv.org/html/2502.10894v1).
