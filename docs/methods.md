# Correction mechanisms and adaptation plan

These formulations specify the comparison. Only the action-residual pilot has measured calibration results so far; the shared torque model has passed a small physical integration run. A G1/IsaacGym adaptation must not be presented as a reproduction of another paper's entire hardware and task pipeline.

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

The queued passive estimator searches separate pitch/roll ankle gains in [8,30], starting at source gains [20,20]. It uses CMA-ES with 12 candidates per generation and eight generations. Each candidate runs in parallel on one central full-second window per continuous mixed30 segment; the fixed fitting objective uses the first 0.25 seconds of joint position and velocity error, scaled by 0.1 rad and 1 rad/s. Task/group/segment weights match the declared hierarchy. Thus it consumes a subset of the calibration pool, unlike action-model training across valid starts; these initial methods are not a matched-unique-data mechanism ranking. The fitted gains are selected by training error, with isolated validation/test used only to report replay, before the equal-budget downstream comparison.

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

The second experiment also changes the data source; it cannot isolate model representation unless matched-data controls are added. Neither full calibration comparison has completed yet.

The implemented matched-data adaptation uses a shared 40→128→128→1 ELU network independently on four ankles. Its inputs are 20 samples of position-command error and zero-target-velocity error, measured from simulator states every 5 ms. The model starts with zero deterministic correction, learns through PPO, adds a scaled torque residual (5 Nm per normalized output) to the nominal PD torque, and clips the sum at the existing torque limits. History is zeroed at replay resets.

The 5 Nm scale equals the source action residual's nominal torque scale, $K_p\alpha=20\times0.25$. The two interfaces still differ in history, sharing, update rate and clipping interactions; this unit match does not make them identical models.

Target recordings remain measured at 50 Hz. Nominal inputs are held for four physics steps using the verified next-transition action convention; the reference between measured states is interpolated. We do not claim the files provide measured target histories at 200 Hz. Calibration uses 96 rollout steps per update at 200 Hz to match the simulated duration of the action model's 24 steps at 50 Hz, with discount factors converted to the shorter step. This produces four times as many PPO transitions and a different parameter count, so the comparison cannot isolate model representation alone. The downstream task policy remains at 50 Hz while frozen torque inference runs at 200 Hz.

CPU interface checks verified joint sharing, ankle-only output, zero initialization, finite policy gradients, and four-step nominal command holding. A four-update, 32-environment training run and a 60-window zero-correction replay run passed; these establish integration only. Full calibration and policy comparison are queued.

## Delta state/dynamics model: secondary baseline

$$
s_{t+1}=f_A(s_t,a_t)+g_\phi(s_t,a_t).
$$

This changes predicted state directly, unlike action or torque correction. A physically coherent G1 implementation must treat orientation, constraints, simulator synchronization, and contact carefully. It is a separate possible baseline; a torque residual must not be renamed delta dynamics. It is secondary to completing the action/SysID/torque comparisons.

## Fair downstream comparison

Fine-tune each method from the same pretrained policy, against the same original motion reference and with equal additional PPO budgets. Select checkpoints on validation seeds. Evaluate in the unchanged B domain without corrective models. Include continued source-domain training without calibration. Publish negative results and integration failures rather than inferring success from training reward alone.
