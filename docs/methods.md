# Methods and implementation

This study implements action correction, gain identification and torque correction in ASAP. Every calibrated policy is trained in source A and deployed alone in target B. A uses ankle stiffness 20; B uses 16. The known target gains are never fitting labels.

## What the three papers contribute

| Work | Model and learning objective | Use during policy training | Implementation here |
|---|---|---|---|
| ASAP | Learn an action correction to match recorded target transitions | Freeze the correction in calibrated simulation | G1 delta action with four active ankle outputs |
| SPI-Active | Identify physical parameters and choose informative excitation | Use the identified dynamics | Two ankle gains and bounded recorded-command offsets |
| UAN | Learn a torque correction from actuator responses | Freeze the actuator model in calibrated simulation | Shared ankle torque model with two data sources |

[ASAP](https://arxiv.org/html/2502.01143v3) learns correction from target policy rollouts. Freezing the correction during policy fine-tuning allows deployment without a correction model. However, fitting those rollouts does not directly optimize target policy performance. New policy trajectories can require responses absent from the recordings.

[SPI-Active](https://arxiv.org/abs/2505.14266) combines structured parameter fitting with active exploration. Sensitivity to the assumed parameters guides collection. This makes the parameterization a central design choice. Our two-gain model fits the constructed mismatch, but does not represent every actuator or contact discrepancy. Our prerecorded G1 command interface also differs from the original Go2 interface.

[UAN](https://arxiv.org/abs/2502.10894) learns corrective torque from excitation data without needing measured output torque. Its history captures actuator effects that an instantaneous parameter change can miss. Sharing a model across joints assumes their responses can be represented by the same function. The original system uses a B2 robot with a Z1 arm; our ankle implementation is an adaptation.

## Delta action

Let $f_A$ denote the source simulator transition. The calibrated transition is

$$
\hat s_{t+1}=f_A(s_t,a_t+\Delta a_\theta(o_t,a_t)).
$$

The nominal action sets joint position targets. PPO trains the correction to reduce recorded joint-state mismatch, with a correction penalty. The network retains the 23-output interface, but only four ankle outputs affect physics. One action unit corresponds to 0.25 rad. Correction inference is at 50 Hz; PD and physics run at 200 Hz.

After fitting, the model is frozen. Policy optimization uses its correction in calibrated simulation. Evaluation in B uses the policy alone. FT-only instead performs policy optimization in uncalibrated A. It is not training directly in B.

Code: `ASAP/humanoidverse/agents/delta_a/train_delta_a.py`, `ASAP/humanoidverse/envs/delta_a/`, and `ASAP/research/asap_diagnostics/controlled_runtime.py`. The reset fix is in `delta_reset_runtime.py`.

## Passive SysID

Pitch gains are shared across the two ankles; roll gains are shared likewise. The fitted vector is $\theta=[K_p^{pitch},K_p^{roll}]$. CandidateGainReplay replaces these gains before replay. The fitting objective is

$$
\hat\theta=\arg\min_{\theta\in[8,30]^2}\sum_i w_i
\left[
\left(\frac{\mathrm{RMSE}(q_i^A(\theta)-q_i^B)}{0.1\ \mathrm{rad}}\right)^2+
\left(\frac{\mathrm{RMSE}(\dot q_i^A(\theta)-\dot q_i^B)}{1\ \mathrm{rad/s}}\right)^2
\right].
$$

Each continuous training segment provides a central one-second window. The loss uses the first 0.25 seconds. Weights are equal by task, original recording and segment. CMA-ES starts at [20,20], with standard deviation 2, 12 candidates and eight generations (seed 7101). Incomplete candidate replays stop fitting rather than being dropped.

The fitted gains are 13.0122 and 10.4212. On a later check using the same training windows, the fit's loss is 0.27028, compared with 0.48918 for the known gains and 1.11580 for the source gains. The objective favors a surrogate. Finite search alone does not explain the parameter error; its cause remains unresolved.

Code: `sysid_runtime.py` implements gain injection. `sysid_fit.py` contains the fitting objective and CMA-ES algorithm. Its simulator callback replaces the removed queue launcher; the callback must return matched candidate trajectories.

## Active SysID

Command design seeks sensitivity to the fitted gains. For the joint trajectory $q(\theta,u)$ under commands $u$, use centered finite differences with gain step 0.5:

$$
J_t=\frac{\partial q_t}{\partial\theta},\qquad
F=\sum_i w_i\sum_t J_{it}^{T}\Sigma^{-1}J_{it}.
$$

The design minimizes $\mathrm{tr}[(F+10^{-3}I)^{-1}]$. The observation noise scale is 0.005 rad. Four variables specify pitch/roll amplitudes and frequencies. Sinusoidal offsets are bounded by 0.08 rad, with frequencies from 0.5 to 3 Hz and opposite-leg phase offset $\pi$. Estimated trajectories must retain height at least 0.35 m and absolute projected-gravity X/Y components at most 0.8.

Unchanged, random and optimized commands each collect new B data from the same thirty training recordings. Each arm receives its own 96-candidate gain fit with seed 7301. Command optimization uses seed 7201, eight candidates and six generations. The optimized arm was chosen for policy training before test results. Its gains are 15.8025/15.5854. Random commands yield 16.0058/16.2712; optimized information did not uniformly improve on random acquisition.

New collection also changes motion phase relative to passive fitting. The large replay improvement cannot be attributed solely to active command design.

Code: `active_design.py` implements command offsets, sensitivity and feasibility. `active_runtime.py` records nominal commands. `sysid_fit.py` provides the optimizer without queue scheduling.

## Torque correction

For each ankle, the corrected torque is

$$
\tau_t=\mathrm{clip}\left(\tau_{PD,t}+5g_\psi(h_t),-50,50\right)\ \mathrm{Nm}.
$$

The history $h_t$ contains twenty samples of position error and velocity error at 5 ms intervals. Desired joint velocity is zero in this PD interface, so the second channel is $-0.05\dot q$. A shared 40→128→128→1 MLP uses ELU hidden layers. Four ankles use the same weights. The scale is 5 Nm per output unit; the correction has no separate 5 Nm cap. PPO trains this model against target trajectories. The frozen model then supplies corrective torque during policy training in calibrated simulation.

Common torque uses the original 50 Hz target recordings with actual 200 Hz source histories. Interpolation does not create new measured target samples. Excitation torque uses genuine 200 Hz B recordings collected with bounded 0.04 rad sine, square and clipped-Gaussian offsets. Nominal commands remain at 50 Hz and are held for four physics steps.

The main Common/Excitation contrast changes collection rate, duration and phase as well as input content. A separate unchanged/excited acquisition pair controlled those factors; it is not a comparison between the two main bars. Torque and delta action also differ in architecture and PPO transition count. Their results compare implementations, not representations alone.

Code: `torque_runtime.py` supplies the shared actor, history, PPO update and frozen environment hook. `wave_runtime.py` and `wave_data.py` handle native-rate recording and continuous data preparation.

## Why servo error motivates selection

For equal damping and no clipping,

$$
\tau_A=20(q_{cmd}-q)-K_d\dot q,\qquad
\tau_B=16(q_{cmd}-q)-K_d\dot q.
$$

At the same state, a source command change $\Delta q_{cmd}$ matches instantaneous torque when $20\Delta q_{cmd}=-4e$, hence $\Delta q_{cmd}=-0.2e$. This uses the known gains only to explain the constructed experiment. Selection itself uses source-gain estimates, not target gain labels.

If this correction is computed at state $q_t$ and held across later PD steps, the same-state torque discrepancy at $q_k$ becomes

$$
\tau_A^{corrected}-\tau_B=(K_B-K_A)(q_k-q_t).
$$

This is an algebraic identity under the stated assumptions. It is not an optimal residual bound or an explanation of the observed policy failures. Saturation, contact and policy-induced state changes can alter which recordings are useful.

A direct state-transition residual would instead add a learned term to $f_A(s_t,a_t)$. No such model was trained in this study. Torque correction should not be described as DeltaDynamics.
