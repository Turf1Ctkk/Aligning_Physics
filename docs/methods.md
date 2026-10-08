# Methods implemented in ASAP

All methods use G1 in IsaacGym. Source A has ankle stiffness 20; target B has stiffness 16. The methods learn from B records, calibrate A, and fine-tune a motion policy in A. Deployment uses the policy alone in B. The [setting audit](settings_audit.md) identifies a frozen-delta noise mismatch in the completed action-policy runs. Repair comparisons remain separate from these results.

## Delta action

$$
s_{t+1}=f_A(s_t,a_t+\Delta a_\theta(s_t,a_t)).
$$

PPO learns a correction to position-target actions. It receives the current state and nominal action. The network keeps the original 23-output interface, but only four ankle corrections affect physics. The correction runs at 50 Hz; physics and PD torque run at 200 Hz. After calibration, the correction is frozen during policy training.

This follows [ASAP's two-stage adaptation](https://arxiv.org/html/2502.01143v3). Replay uses recorded nominal actions, although the correction itself remains a feedback model.

## Passive SysID

$$
\hat\theta=\arg\min_\theta L(\hat s(\theta),s^B).
$$

CMA-ES searches separate ankle pitch and roll gains in the interval [8, 30]. It starts at 20, uses 12 candidates per generation, and runs eight generations. The loss uses the first 0.25 seconds of joint position and velocity error. Training windows have equal task and rollout weights.

The fit gives gains 13.01 and 10.42, rather than the target value 16. These gains improve some trajectory and control results, but do not establish physical parameter recovery. The fitting objective itself prefers this surrogate to the known gains. [Evidence](../results/passive_sysid/README.md).

## Active SysID

Following the idea of [SPI-Active](https://github.com/LeCAR-Lab/SPI-Active), command design uses finite-difference parameter sensitivities:

$$
F\approx\sum_t J_t^T\Sigma^{-1}J_t.
$$

The design minimizes the trace of a regularized inverse information matrix. It adds bounded sinusoidal offsets to recorded ankle commands, then collects new B trajectories and refits the gains. Unchanged, random and optimized inputs have the same acquisition and refitting budgets.

Our G1 tracker does not have the original Go2 command interface. This is an adaptation, not a full reproduction. Only the preselected optimized arm receives downstream policy training. The first acquisition attempt failed feasibility checks. All failed records remain archived. The revised run uses the first eligible window of every parent, with unchanged limits and no dropped parents. [Evidence](../results/active_acquisition/README.md).

## Torque correction

$$
\tau_t=\operatorname{clip}(\tau_{PD,t}+\delta\tau_\psi(h_t)).
$$

The [UAN-inspired model](https://arxiv.org/abs/2502.10894v1) shares one MLP across four ankles. Each joint receives 20 samples of position error and velocity error. The MLP has two 128-unit ELU layers and one torque output. Inference runs every 5 ms. The output scale is 5 Nm, and the summed torque is clipped at the existing limit.

Two datasets are tested. The common-data model uses measured 50 Hz target records and actual 200 Hz source histories. Interpolating its target reference does not create measured 200 Hz target data. The second experiment collects genuine 200 Hz target records, with unchanged inputs or bounded wave/noise offsets. Both new arms use the same model and budgets. [Evidence](../results/wave_acquisition/README.md).

Torque and action models differ in architecture, rate and PPO transition count. Their results do not isolate the effect of representation alone.

## State-transition residual

$$
s_{t+1}=f_A(s_t,a_t)+g_\phi(s_t,a_t).
$$

This predicts a change in state directly. It has not been implemented in this study. Torque correction is not a state-transition residual. A future implementation must handle rotations, contacts and simulator state updates consistently.

## Shared policy comparison

FT-only continues policy optimization in uncalibrated A. It does not train in B. Fixed-command replay is identical to the original uncalibrated simulator, so it shares that open-loop baseline.

Each task starts from its recorded `model_6000.pt` and receives 1,000 additional PPO updates. Optimizers are reset, while policy weights and action standard deviations are retained. Initial actor and critic learning rates are $10^{-4}$ and $10^{-3}$. The inherited adaptive-KL schedule remains enabled.

The saved fine-tuning recipe also disables motion-distance termination and changes action-rate regularization, penalty scheduling and observation noise from pretraining. These changes are shared by the adapted methods, but the experiment is not an exact continuation of the original training recipe.

Calibration checkpoints are chosen by validation. Policy checkpoints are fixed at the final update. All target evaluations use zero observation noise and matched initialization and termination settings. Three evaluation seeds measure deployment variation; they do not replace independent training seeds.
