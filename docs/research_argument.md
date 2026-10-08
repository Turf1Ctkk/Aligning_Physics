# Why study calibration data?

## The problem

A motion reference tells the robot what to do. A calibration rollout records what it actually did after receiving commands. These are different kinds of data. This study concerns the second kind.

Let $f_A$ describe the source simulator and $f_B$ the target dynamics. ASAP learns an action correction $\Delta a$ so that

$$
f_A(s,a+\Delta a(s,a))\approx f_B(s,a).
$$

The correction is then frozen during policy fine-tuning. The final policy runs in B without the correction. A useful dataset must therefore support more than accurate replay. It must help train a policy that works in B.

## What previous work suggests

ASAP collects task-policy rollouts. SPI-Active chooses commands that reveal physical parameters. UAN uses wave and noise inputs to learn actuator corrections. These are different ways to obtain informative responses. Informative collection is already an established research topic.

The proposed contribution is a more specific test: compare data choices for learned calibration, then measure their effect on policy control. I do not assume that a data rule successful for parameter identification will also be successful for a flexible residual model.

[ASAP](https://arxiv.org/html/2502.01143v3), [SPI-Active](https://github.com/LeCAR-Lab/SPI-Active), [UAN](https://arxiv.org/abs/2502.10894v1).

## Why joint range may be insufficient

Consider a PD actuator with command error $e=q_{cmd}-q$:

$$
\tau=K_pe-K_d\dot q.
$$

At the same state and command, an unsaturated stiffness mismatch produces

$$
\tau_B-\tau_A=(K_p^B-K_p^A)e.
$$

This gives a reason to measure servo error. A joint can move through a large range while following its command closely. Another joint can move little but have a large command error. Their ranges do not tell us which response reveals a stiffness mismatch.

Torque limits complicate the picture. If both systems clip to the same torque, increasing command error may reveal little extra information. Delay and friction would require different features. I therefore treat actuator coverage as a testable heuristic, not a universal rule.

The current selector uses servo error, velocity, command changes and torque-limit statistics. It does not optimize the future policy's sensitivity. Such a method would be a separate research step.

## Why replay may not predict control

Replay uses a fixed nominal action sequence. Fine-tuning changes the policy, so it can change both commands and visited states. Three possible problems follow:

- The policy may visit conditions that the calibration data rarely covers.
- The model may reduce errors that have little effect on task control.
- The policy may exploit an inaccurate part of the calibrated simulator.

These are hypotheses, not explanations established by the present results. A feature-distance audit finds changed actuator conditions, but distance alone does not explain the ranking of policies.

Other explanations also matter. Optimization can vary across training seeds. Model capacity may limit calibration. Replay initialization may not restore contact history. Correction rate may also matter: PD torque updates at 200 Hz, while the action correction is held at 50 Hz.

For unsaturated actuators with equal damping and no delay, a command chosen to match torque at state $q_k$ leaves the following discrepancy at a later shared state $q_t$:

$$
\tau_A-\tau_B=(K_p^B-K_p^A)(q_k-q_t).
$$

This is a same-state identity. It is not a bound on the best learned correction or a proof of why a policy failed. A known-gain replay diagnostic checks the interface separately from learning.

## What would support the hypothesis?

At equal data and training budgets, coverage should reduce held-out replay error compared with uniform selection and range selection. The resulting policy should also improve target control after the same fine-tuning budget.

Both claims matter. A replay gain without a control gain supports only the first. A negative result for this selector does not rule out every form of information-aware collection.

Both subset runs show this distinction. Coverage has lower replay position error, but it does not consistently produce better policy control. Completion changes substantially between seeds. The combined hypothesis is not confirmed. Different selected phases also have different same-domain replay errors. These are retained rather than subtracted or used to replace windows.

## What the current study can establish

The data-content experiment compares three complete pipelines using the same recorded parents. It measures the effect of a selection rule, which may change several data properties at once. It does not isolate the causal effect of one feature.

A completed second seed repeats training on the same selected data. This checks sensitivity to the pipeline seed. It does not repeat acquisition, and two seeds cannot establish a reliable population ranking. Replay evaluation seed also changes between runs. Policy deployment seeds remain fixed.

A stronger follow-up would repeat acquisition and training, vary one data property at a time, and record the conditions visited during fine-tuning. It should also test a harder dynamics mismatch, since ordinary fine-tuning already reaches full completion on two tasks here.
