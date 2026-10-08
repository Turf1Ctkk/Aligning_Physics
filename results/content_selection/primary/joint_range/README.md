# Primary joint-range subset: completed condition

All three primary selectors are complete. The second paired seed is running; no repeat result is assumed. See the [complete primary table and contrasts](../metrics.md) and [study interpretation](../../README.md).

## Calibration and held-out replay

Validation body error is67.6199mm at500 updates and55.8945mm at1000; both candidates complete60/60 windows. Validation selects `model_1000.pt`. [500-update validation](validation_500.json), [1000-update validation](validation_1000.json), [selection](delta_selection.json).

| Test replay,1s | Body MPJPE (mm) | Ankle RMSE (rad) | Velocity RMSE (rad/s) | Complete windows |
|---|---:|---:|---:|---:|
| Shared primary Source20,zero correction |36.9190|0.074967|0.853221|66/66|
| Source20,joint-range correction |45.7327|0.086447|1.052676|66/66|

All three displayed replay errors worsen against zero correction. [Raw condition report](comparison.json), [summary](summary.json). This unfavorable result is retained with the same validation criterion and budgets used for the other selectors.

## Standalone Squat policy

The fixed final1000-update policy completes **74/96** trials, with mean survival5.1173s of5.22s. First-second body/root-relative errors are94.9529/31.4977mm over all96 prefixes. Three-second errors are106.8251/36.5587mm over95 valid prefixes. Full-reference errors are129.9661/45.1242mm over74 successes only.

All22 terminations from1.98 to5.20s are retained, without automatic fall classification. [Event timing](termination_timing.json). Joint-range selection has larger replay errors but higher completion, longer survival and lower first-second errors than coverage in this primary training seed. This is a concrete separation of held-out replay and downstream outcomes, not evidence that large range causes better control generally.

## Integrity and interpretation

[The deployment audit](matched_state_config_audit.json) checks all96 first stored states/actions, effective observation noise/init/termination/physics,26150Hz frames and ordinary task-only deployment against historical FT-only. That comparison controls deployment settings, not training-seed equality with the old FT-only policy. [The replay audit](replay_initial_sample_audit.json) checks all66 first stored samples against the primary Source20 zero control, including nominal action and clock; held-out test files are byte-identical. Hidden simulator state is not independently verified. [Seven existing evaluation logs](runtime_log_audit.json) retain the optional keyboard-listener error and main-recorder completion markers, without a rerun or core patch.

The selected-training-record same-domain body floor is26.3861mm and velocity error1.103043rad/s, all18 windows complete. [Measured floor](selected_subset_replay_floor.json). The larger floor is not subtracted; no window is replaced. Temporal/contact phase and initialization conditions vary with subset selection, limiting a causal actuator-feature interpretation. The complete primary results therefore do not confirm the combined replay-and-control hypothesis. The prespecified repeat uses identical selected data and must report its own outcomes independently.
