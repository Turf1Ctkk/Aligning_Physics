# Known-gain replay diagnostic

This historical test uses the known gain ratio to check correction timing. It is an implementation control, not a learned model or a label used in training.

| Correction | Ankle RMSE (rad) | Mean root-position error (mm) |
|---|---:|---:|
| Zero | 0.035351 | 22.383 |
| Known-gain correction at 50 Hz | 0.003968 | 0.913 |
| Known-gain correction at 200 Hz | 0.000049 | 0.012 |

The results cover one second of one Squat record. Initial velocities are restored and no reset occurs. Root-position error is not whole-body position error.

The test shows that instantaneous torque matching need not remain exact when the correction is held over several physics steps. It does not bound the best learned residual or explain downstream policy failures. [Configuration audit](config_audit.json) and [raw results](.) preserve this scope.
