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

For the actual post-step data format, compute transition features using

$$
e_i=q_{\rm default}+\alpha a[i+1]-q[i].
$$

Using action[i] with state[i] would measure the preceding command, rather than the next recorded transition. This matters when judging which data excite the mechanism.

Velocity and command change are candidate conditioning/coverage features. They are directly relevant to other mechanisms, such as damping, friction, and response delay; they are not automatically independent sources of information about a pure Kp change. The proposed selector uses them to describe actuator regimes and tests their value, rather than declaring that every additional feature must help.

## 4. Why replay and control can disagree

Training data originate from π0 in B; fine-tuning creates πD in the calibrated A. Their state-action occupancy distributions can differ. A low average replay loss under the former does not guarantee an accurate correction under the latter.

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

## 5. A hypothesis with explicit conditions

For an actuator-response mismatch that the chosen residual interface can represent, and after replay artifacts are controlled, **equal-budget datasets covering relevant command-state regimes should improve calibration on held-out trajectories compared with a dataset selected only for large joint range or uniform repetition**.

The downstream extension is conditional: this benefit should improve target-domain control when those regimes overlap the adapted policy's behavior and the calibrated simulator does not introduce exploitable errors. This is the difficult part of the question, not an assumed consequence of the first result.

The conditions prevent an overly broad claim, but must not become post-hoc excuses. Before testing, fix the mismatch, model interface, feature definitions, budgets, and evaluation. Report whether the conditions are met using the same-domain check, measured coverage, independent target trajectories, and adapted-policy feature distributions. If a coverage selector performs no better than uniform selection under these settings, the hypothesis is unsupported for this test.

## 6. What would count as evidence

First, establish that calibration can change replay and downstream performance in the common task framework. Compare correction representations and include equal-budget continued policy training without calibration. This establishes the experimental phenomenon; it does not itself prove a data-content explanation.

Second, change only the calibration subset at a fixed unique-transition budget. Compare uniform, command-state coverage, and joint-range selection. Keep parent groups, task mixture, residual architecture, training budget, and checkpoint selection controlled. Record overlap between windows and the data needed for history prefixes.

Third, measure both held-out replay and target policy control. A same-motion held-out rollout tests trajectory generalization. A motion excluded from calibration tests a different claim; report it separately. Independent training seeds, rather than many correlated windows from one trained model, are needed for a stable method ranking.

Finally, test a second mismatch if claiming mechanism dependence. For example, data useful for a linear stiffness change need not be useful for a saturation mechanism. This experiment is secondary to finishing one complete downstream comparison before the submission deadline.

The practical contribution is a falsifiable diagnostic protocol connecting data content, learned calibration, and target-domain control. A negative result can narrow the hypothesis or identify a stronger bottleneck; it should remain visible in the submission.
