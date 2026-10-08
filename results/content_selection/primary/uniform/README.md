# Primary uniform subset: completed condition, other selectors pending

This is one completed condition of the prespecified18-parent/954-transition selector study. Coverage has also completed; joint-range calibration is running and repeat outcomes remain pending. The complete three-selector reporter is intentionally not run yet; this snapshot does not establish a selector ranking.

## Calibration and held-out replay

Both validation candidates complete60/60 windows. Validation body error is35.2575mm at500 updates and39.7682mm at1000, selecting `model_500.pt`. [500-update validation](validation_500.json), [1000-update validation](validation_1000.json), [actual selection](delta_selection.json). Calibration still receives1000 total updates; selection uses validation, not test.

| Test replay,1s | Body MPJPE (mm) | Ankle RMSE (rad) | Velocity RMSE (rad/s) | Complete windows |
|---|---:|---:|---:|---:|
| Same16,zero correction |9.3993|0.018757|0.518117|66/66|
| Source20,zero correction |36.9190|0.074967|0.853221|66/66|
| Source20,learned correction |32.9622|0.068624|0.989788|66/66|

Body position improves while velocity worsens. [Actual shared primary controls](../shared_test_baselines.json), [raw condition report](comparison.json), [summary](summary.json). The shared test records are byte-identical to the older mixed30 test, but replay seeds differ; historical baseline values must not replace these measurements.

## Standalone Squat policy

The fixed final1000-update policy completes **8/96** target trials. Mean survival is4.9929s of5.22s. First-second body/root-relative errors are96.5322/34.5262mm over all96 valid prefixes; three-second errors are105.0774/39.3366mm over95 valid prefixes. Full-reference errors are127.7182/51.8538mm over only8 successful trials. Those successful-only means cannot be used as a failure-inclusive tracking score.

All88 terminations are retained: one at2.56s (seed8101,trial7), the remainder after3s; latest5.18s. [Timing for every event](termination_timing.json). These are terminations, not automatically classified as falls. The old FT-only policy is contextual evidence at a different training seed, not a freshly trained same-seed control for this subset study. Training seeds are20305008 calibration/20306008 policy; deployment seeds stay8101–8103.

## Integrity and scope

[The deployment audit](matched_state_config_audit.json) verifies all96 first stored joint/root states and actions against the historical FT-only recordings, exact matching effective noise/termination/init/physics and ordinary task-only deployment with26150Hz frames. Equal deployment initializations do not make policy-training seeds equal. No hidden solver-state equality is claimed.

[Replay initial-sample audit](replay_initial_sample_audit.json) shows identical first stored states/actions for uniform learned and source20-zero replay. The first timestamp is0.02s: `reset_all` includes a zero-residual physics warm step before the recorder starts. Same16 versus source20 stored first samples need not match because that step already uses different dynamics. Historical source20 and primary source20 runs use different replay seeds and have different first stored samples; the exact cause is not isolated by this artifact audit. The held-out files themselves have identical SHA-256 hashes. This is why within-run controls and selected-window floors are necessary.

The [runtime-log audit](runtime_log_audit.json) retains a background keyboard-listener `NameError` caused by the missing optional keyboard import. All8 existing affected evaluation logs contain recorder completion markers; the error occurs in an ancillary thread before PPO setup, while the main recorder completes. The queue launcher rejects a nonzero main-process exit. No record was discarded and no physics result was rerun or patched. Successful train/test same16 checks reuse one root log name; both split-specific raw records, configs and JSON reports remain, and the audit describes only existing logs.

This uniform result alone supports neither actuator coverage nor joint-range selection. The other selectors retain identical budgets and rules; their outcomes and the conditional second seed must be reported whether positive or negative.
