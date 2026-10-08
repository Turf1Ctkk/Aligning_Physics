# Known-parameter control-rate diagnostic

These are **historical implementation controls**, verified from the earlier saved server artifacts. No new GPU experiment was launched for this report. They replay one recorded Squat Kp16 trajectory from its first stored state, with recorded joint/root velocities restored, source Kp20, physics 200 Hz and nominal recorded actions at 50 Hz. All comparisons cover the same 50 post-step frames at 0.02–1.00s, with no reset.

The analytic correction uses the **known target/source gain ratio 0.8** and current source joint state. One version computes it once per 20ms control interval; the other recomputes it every 5ms physics step while holding the nominal input. [Verified configuration/source hashes](config_audit.json), [opt-in diagnostic implementation](../../overlays/research/asap_diagnostics/analytic_replay.py).

| Diagnostic in source Kp20 | Ankle RMSE (rad) | Joint-velocity RMSE (rad/s) | Mean root-position error (mm) |
|---|---:|---:|---:|
| Zero correction | 0.035351 | 0.277929 | 22.383 |
| Known-gain correction held at 50 Hz | 0.003968 | 0.161197 | 0.913 |
| Known-gain correction recomputed at 200 Hz | 0.000049 | 0.012946 | 0.012 |

[Zero-correction comparison](zero_check_1.0.json), [50 Hz comparison](analytic50_1.0.json), [200 Hz comparison](analytic200_1.0.json). These are raw same-origin joint/root errors, **not body MPJPE**, held-out calibration performance or closed-loop tracking.

The diagnostic tests timing and replay integration with privileged knowledge of the gain change. It is not a learned model, deployable calibration method or training label source; it was never an arm in the learned-model task comparison. The 200 Hz rule changes the correction interface, so its advantage does not establish that more data would solve the 50 Hz model's errors. The 50 Hz rule is also not an optimal finite-horizon correction and supplies no lower bound on the best learned model's sampled-position error.

A single recorded prefix cannot establish a population-level update-rate effect or explain the later policy failures. Its role is to make a specific representation/timing alternative concrete. [The unsaturated same-state derivation](../../docs/research_argument.md) states the assumptions and separates torque equivalence from trajectory/control equivalence.
