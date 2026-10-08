# Research argument: from calibration data to control

## 1. The object being learned

The question concerns data-driven calibration for humanoid motion tracking. It does not ask which human reference motions are easiest to imitate. Those reference motions define the task; calibration trajectories describe how the target system actually responds to actions, including imperfect responses before a failure.

Let A be the source simulator and B the target system. In a controlled sim-to-sim test, B is another configured simulator. Let D be target recordings collected with the original policy π0. A learned correction changes the command channel of A, producing an approximate calibrated transition model. A task policy is then fine-tuned in that model and deployed in B without the correction.

This creates two distinct experimental outcomes:

$$
R_{\mathrm{replay}}(\psi;D_{\mathrm{test}})
=\mathbb E\big[\|y^B_{t:t+H}-\hat y^{A,\psi}_{t:t+H}\|_W^2\big],
$$

where nominal inputs are the recorded actions, and

$$
J_B(\pi_D)=\mathbb E_B\big[\text{task tracking cost and failure cost under }\pi_D\big],
$$

where the adapted policy generates its own actions. The observer y specifies what is measured, such as body positions or joint states. A position metric alone does not determine force accuracy or stability.

The recorded state may be incomplete: actuator memory, contact-solver history, and support interactions need not be recoverable from joint/root position and velocity. In that case, replay error contains more than the intended dynamics mismatch. Same-domain replay and interface checks are therefore part of the measurement design, not optional implementation housekeeping.

## 2. The research gap is narrower than “data matters”

Three established ideas already constrain the proposal. Task-policy rollouts can train a reusable action correction; structured identification benefits from targeted excitation; actuator learning can use non-task wave/noise excitation. These are supported respectively by [ASAP](https://arxiv.org/html/2502.01143v3), [SPI-Active](https://arxiv.org/html/2505.14266v1), and [UAN](https://arxiv.org/html/2502.10894v1).

Recent [Contact-UAN's author project page](https://contact-uan.csail.mit.edu/) also reports reuse of walking calibration for other behaviors and emphasizes contact-consistent replay. That directly rules out the premise that the downstream motion's own successful rollout is always necessary. Its project-page evidence is related context, not a reproduction performed here.

The proposed study instead asks whether measurable content of an existing target calibration pool predicts usefulness for **both** replay and policy adaptation, with data amount and optimization held fixed. It is a controlled diagnosis within one architecture. A claim of methodological novelty would require a broader literature comparison than this initial proposal.

## 3. Why joint range is not enough

For a nominal PD position target,

$$
q_{\rm cmd}=q_{\rm default}+\alpha a,
\qquad \tau=K_p(q_{\rm cmd}-q)-K_d\dot q.
$$

With only stiffness changed and before saturation, the instantaneous difference is

$$
\tau_B-\tau_A=(K_p^B-K_p^A)e,
\qquad e=q_{\rm cmd}-q.
$$

Thus, the actuator error e is directly relevant to this particular mismatch. A joint can move through a wide range while staying close to its commanded position. Conversely, a relatively small excursion can occur under a large commanded error or load. Range alone does not identify which situation the data contain.

This is a mechanistic argument for a feature, not a guarantee that an e-diverse dataset produces a better neural model. An estimator with the correct one-parameter structure may need very little data. A residual model may instead be limited by optimization, regularization, finite update frequency, or other state-dependent effects. The Kp experiment is deliberately favorable to structured SysID and should be described that way.

The actual controller clips ankle torque at ±50 Nm. Its instantaneous mismatch is therefore

$$
\Delta\tau=\operatorname{clip}(K_p^B e-K_d\dot q,\pm L)
-\operatorname{clip}(K_p^A e-K_d\dot q,\pm L).
$$

Away from a clipping boundary, the local source sensitivity to stiffness is $e\,\mathbf 1(|K_p^A e-K_d\dot q|<L)$. A large error can thus have zero local sensitivity when the torque is already saturated. When both source and target saturate in the same direction, their instantaneous torques coincide. Near a boundary, a finite gain change can alter the active regime, so the local derivative alone is insufficient. This makes source torque headroom and coverage around saturation boundaries meaningful candidates alongside e. Neither formula is used to supply corrective-action training labels.

A [descriptive training-pool audit](../results/calibration_features/README.md) illustrates this distinction. Evaluating the source PD law at recorded target states gives weighted nominal saturation fractions of approximately 18.94% for CR7, 0.009% for SquatL1, and 3.65% for StepFBL1. These are modeled source commands, not measured target torques. Clip-level joint range and servo-error RMS also have task-dependent associations. No model has yet been trained using these features for selection; they motivate an experiment rather than confirm the hypothesis.

For the actual post-step data format, compute transition features using

$$
e_i=q_{\rm default}+\alpha a[i+1]-q[i].
$$

Using action[i] with state[i] would measure the preceding command, rather than the next recorded transition. This matters when judging which data excite the mechanism.

Velocity and command change are candidate conditioning/coverage features. They are directly relevant to other mechanisms, such as damping, friction, and response delay; they are not automatically independent sources of information about a pure Kp change. The proposed selector uses them to describe actuator regimes and tests their value, rather than declaring that every additional feature must help.

## 4. Why replay and control can disagree

Training data originate from π0 in B; fine-tuning creates πD in the calibrated A. Their state-action occupancy distributions can differ. A low average replay loss under the former does not guarantee an accurate correction under the latter.

A [post-hoc support audit](../results/policy_regimes/README.md) queries the first 49 transitions of all 96 target deployment trials per policy against mixed30 calibration data in 12 training-scaled actuator coordinates. Mean nearest-feature distance is 0.736 for the original policy, 0.959 for FT-only, 1.351 for ASAP, 1.467 for passive SysID and 1.318 for torque-model FT. This measures a change in visited feature regimes, not a probability-density ratio or model error. SysID has the largest distance but higher completion than ASAP, so the observed distance does not explain the ranking on its own. Only B deployment is observed; calibrated-A training occupancy and correction errors on those states remain unmeasured. The queued selection protocol is unchanged by this exploratory test-set analysis.

There is also a difference in error propagation. Within a locally smooth contact regime, a first-order closed-loop error has the schematic form

$$
\xi_{t+1}\approx
\left(\frac{\partial f}{\partial x}
+\frac{\partial f}{\partial a}\frac{\partial\pi}{\partial x}\right)\xi_t
+\varepsilon_\psi(x_t,\pi(x_t)).
$$

This expression is a local explanatory approximation, not a global stability guarantee for contact-rich motion. It shows why the effect of a model error depends on controller sensitivity and feedback. Some errors can be attenuated; others can affect balance, contact timing, or failure. A uniformly averaged kinematic replay score does not encode all of these consequences.

Consequently, an apparent closed-loop plateau has multiple possible causes:

| Explanation | Discriminating evidence |
|---|---|
| Repeated data cover already-observed regimes | Additional groups add little measured feature coverage; equal-budget coverage selection changes results. |
| Improvement occurs in control-insensitive regions | Replay improves while target failures and task tracking do not; phase-resolved errors differ. |
| Policy-induced distribution shift | Adapted-policy features occupy poorly covered calibration regions. |
| Residual representation/rate limitation | Increasing data does not help, while a suitable model/history/update rate does. |
| Optimization or fine-tuning budget limitation | Longer or independently repeated optimization changes the ranking. |
| Replay initialization artifact | Same-domain error is large or depends strongly on window starts. |

The current pilot distinguishes none of these conclusively. In particular, 30 versus 90 recording groups cannot establish saturation because task weights changed and only one training seed was run.

The [matched Squat result](../results/matched_squat/README.md) now provides a concrete disagreement: the weighted mixed30 action correction lowers held-out replay body error by 19.0%, yet its adapted policy completes 87/96 trials compared with 96/96 for equal-budget continued training without calibration. Its first-second global and root-relative tracking errors are also higher. A shared torque correction similarly improves replay but does not exceed FT-only completion and has higher full-horizon position error. This establishes that the chosen replay improvement is insufficient for an additional downstream benefit in these runs. It does not prove that calibration data are deficient, or that dataset scaling caused a plateau. The same data-content intervention remains necessary to test the proposed explanation.

The [structured estimator's post-hoc diagnostic](../results/passive_sysid/README.md) adds a measurement caution. On the same training windows, known target gains 16/16 produce a larger short-horizon fitting loss than the fitted 13.01/10.42. Thus optimizing the present trajectory objective can favor surrogate parameters that compensate for replay conditions or other unmodeled effects. Recovery error cannot be attributed solely to insufficient search. The precise mechanism is not resolved; neither the fitted gains nor the target-gain control supplies labels to a learned correction. This is another reason to report same-domain floors and window-start sensitivity alongside data-selection outcomes.

The [actual 200 Hz acquisition comparison](../results/wave_acquisition/README.md) separates another pair of claims. Its new training records have sub-millimeter same-domain position replay, yet the unchanged-input calibrated policy completes only 34/96 target trials. All 96 survive the first three seconds; the 62 terminations occur at 4.56–5.16 seconds. Early tracking means therefore miss the late stability deficit. This does not identify a cause: collection phase coverage, correction extrapolation, optimization and reward tradeoffs remain competing explanations. A finer measurement rate alone is not evidence of useful calibration data. The matched excitation arm improves some held-out replay metrics and worsens another; its policy completes 95/96, compared with 34/96 for unchanged data and 96/96 for FT-only. Collection amount, parent identities, architecture, training seed, update budgets and selection rule are held fixed, and evaluation settings/first stored states match. Thus changing acquisition inputs and resulting trajectories changes the outcome of this training pipeline in this seed. Nearly unchanged joint-range summaries coexist with a large completion difference, so range alone does not describe the intervention. This neither identifies a causal feature nor excludes optimization variability: independent training repetitions and targeted temporal/regime ablations are needed. Excitation also has higher first-second global error than unchanged data, despite better root-relative error and completion; the measurements cannot be collapsed into a universal improvement.

The FT-only control completes 96/96 in this sample, leaving a completion ceiling for demonstrating extra benefit in the current test. Tracking error and survival must accompany completion, and independently trained policies are needed to judge small differences. A harder mismatch or evaluation distribution could provide additional headroom in a later study; the current thresholds and budgets are retained rather than changed after seeing these outcomes.

## 5. A hypothesis with explicit conditions

For an actuator-response mismatch that the chosen residual interface can represent, and after replay artifacts are controlled, **equal-budget datasets covering relevant command-state regimes should improve calibration on held-out trajectories compared with a dataset selected only for large joint range or uniform repetition**.

The downstream extension is conditional: this benefit should improve target-domain control when those regimes overlap the adapted policy's behavior and the calibrated simulator does not introduce exploitable errors. This is the difficult part of the question, not an assumed consequence of the first result.

The conditions prevent an overly broad claim, but must not become post-hoc excuses. Before testing, fix the mismatch, model interface, feature definitions, budgets, and evaluation. Report whether the conditions are met using the same-domain check, measured coverage, independent target trajectories, and adapted-policy feature distributions. If a coverage selector performs no better than uniform selection under these settings, the hypothesis is unsupported for this test.

The experimental unit for a data-selection claim is the entire calibration-and-adaptation run. Write its deployed policy as $\pi(D,z)$, where $z$ contains calibration and policy-training randomness. A population claim would concern

$$
\Delta J=\mathbb E_z[J_B(\pi(D_{\rm coverage},z))-J_B(\pi(D_{\rm uniform},z))],
$$

with cost defined consistently so lower is better. The present results retain completion, survival and tracking as separate outcomes; no post-hoc scalar weighting is used to declare a winner. The queued experiment estimates one paired-seed contrast, not this expectation or its training variance. Repeated deployment initializations measure another source of variability. Repeated windows from a trained calibrator do not turn it into multiple trained models. Shared seeds reduce one avoidable difference but do not make optimization trajectories identical across datasets.

Changing a subset or acquisition input is also a bundled intervention. It can change actuator features, their temporal order, support/contact regimes and the optimization landscape together. An observed performance difference identifies an effect of that dataset construction in the tested pipeline; it does not identify a unique causal feature. To test the proposed mechanism later, remove one feature family from the selector or vary temporal excitation while matching parent identities, duration and coarse joint range, using fresh training seeds and an untouched evaluation split. These are follow-up ablations, not selectors adjusted after the present test results.

The minimal selector is deliberately weaker than an optimal information design: its 28 window summaries approximate command-state diversity, while neither controller sensitivity nor future adapted-policy occupancy enters its objective. Consequently, a negative result would reject this heuristic under the tested model, gap and budget. It would not establish that all information-aware selection is ineffective. A positive replay-only result would support the calibration component, while leaving the conditional control component unverified. This separation keeps the hypothesis falsifiable without treating every outcome as confirmation.

## 6. What would count as evidence

First, establish that calibration can change replay and downstream performance in the common task framework. Compare correction representations and include equal-budget continued policy training without calibration. This establishes the experimental phenomenon; it does not itself prove a data-content explanation.

Second, change only the calibration subset at a fixed unique-transition budget. Compare uniform, command-state coverage, and joint-range selection. Keep parent groups, task mixture, residual architecture, training budget, and checkpoint selection controlled. Record overlap between windows and the data needed for history prefixes.

Third, measure both held-out replay and target policy control. A same-motion held-out rollout tests trajectory generalization. A motion excluded from calibration tests a different claim; report it separately. Independent training seeds, rather than many correlated windows from one trained model, are needed for a stable method ranking.

Finally, test a second mismatch if claiming mechanism dependence. For example, data useful for a linear stiffness change need not be useful for a saturation mechanism. This experiment is secondary to finishing one complete downstream comparison before the submission deadline.

The practical contribution is a falsifiable diagnostic protocol connecting data content, learned calibration, and target-domain control. A negative result can narrow the hypothesis or identify a stronger bottleneck; it should remain visible in the submission.
