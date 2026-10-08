# Correction mechanisms and adaptation plan

These formulations specify the planned comparison; only the action-residual replay pilot has measured results so far. A G1/IsaacGym adaptation must not be presented as a reproduction of another paper's entire hardware and task pipeline.

## Delta action: existing pilot, downstream stage pending

For a nominal position-target action a, learn

$$
s_{t+1}^{A,\Delta}=f_A(s_t,a_t+\Delta a_\theta(s_t,a_t)).
$$

Train the residual through PPO using recorded target trajectories, then freeze it while fine-tuning the task policy on the original reference motion. Deploy the resulting task policy in B without the residual. The nominal recorded input is fixed during replay; the residual remains state-conditioned. [ASAP, Sections III and VIII](https://arxiv.org/html/2502.01143v3).

## Structured parameter identification

Estimate physical parameters using recorded-input trajectory matching:

$$
\hat\theta=\arg\min_\theta\sum_{c,t}\|s_{t,c}^B-\hat s_{t,c}(\theta)\|_W^2,
\qquad \hat s_{t+1,c}=f_A(\hat s_{t,c},a_{t,c};\theta).
$$

For the initial stiffness test, estimate a bounded ankle-gain parameter from training data. The estimator must not read B's configured gain as its fitted answer. The known target parameter is used only for experiment construction and post-fit diagnostic reporting. This is intentionally a well-specified, low-dimensional SysID test, not a realistic claim that all hardware errors reduce to stiffness.

The SPI method uses parallel candidate rollouts and sampling-based optimization. The **active** stage additionally optimizes exploration commands using an information criterion, then collects new target data and re-estimates parameters. Under a stated observation-noise model, a finite-difference trajectory-sensitivity proxy has the form

$$
F\approx\sum_t J_t^\top\Sigma^{-1}J_t,
\quad J_t=\partial\hat s_t/\partial\theta.
$$

Optimizing this criterion over a fixed dataset is data selection; it is not by itself the paper's active command-generation stage. [SPI-Active, Sections 3–4](https://arxiv.org/html/2505.14266v1).

The inspected [official active-SysID guide](https://github.com/LeCAR-Lab/SPI-Active/blob/main/active_sysid.md) uses a Go2 command-conditioned multi-behavior controller. Our saved G1 policies are phase-conditioned single-motion trackers. A complete active-exploration comparison therefore requires a disclosed command/interface adaptation and new collection. The initial parameter-estimation comparison should be labelled **SPI-style SysID** until that stage is implemented and evaluated. Official source inspected at commit `edc07d0b957bce9a430aa5a48b71a266a0a9f635`.

## Unsupervised actuator torque correction

Learn a corrective torque from actuator history:

$$
\tau_t=\tau_{\mathrm{nominal},t}+\delta\tau_\psi(h_t).
$$

The original UAN uses PPO without measured corrective-torque labels, a shared per-joint MLP with two 128-unit layers, 20 samples of error history, and execution every 5 ms. Its collection uses square waves, sine waves, and Gaussian noise rather than task-policy data. [UAN, Section II-A](https://arxiv.org/html/2502.10894v1).

An ASAP action residual is not automatically UAN: it alters position targets, may observe whole-body state, and currently runs at 50 Hz. A torque-model adaptation must explicitly define nominal torque semantics, history construction, sharing across distinct ankle actuators, torque clipping order, and update rate.

The existing 50 Hz rollout files cannot recover measured 200 Hz histories through interpolation. Two experiments should be distinguished:

1. A controlled **torque-residual adaptation** using the common existing dataset and a disclosed rate/horizon, isolating correction representation as far as possible.
2. A closer UAN-method adaptation with newly collected excitation and genuine 5 ms state/history samples.

The second experiment also changes the data source; it cannot isolate model representation unless matched-data controls are added. Neither has run yet.

## Delta state/dynamics model: secondary baseline

$$
s_{t+1}=f_A(s_t,a_t)+g_\phi(s_t,a_t).
$$

This changes predicted state directly, unlike action or torque correction. A physically coherent G1 implementation must treat orientation, constraints, simulator synchronization, and contact carefully. It is a separate possible baseline; a torque residual must not be renamed delta dynamics. It is secondary to completing the action/SysID/torque comparisons.

## Fair downstream comparison

Fine-tune each method from the same pretrained policy, against the same original motion reference and with equal additional PPO budgets. Select checkpoints on validation seeds. Evaluate in the unchanged B domain without corrective models. Include continued source-domain training without calibration. Publish negative results and integration failures rather than inferring success from training reward alone.
