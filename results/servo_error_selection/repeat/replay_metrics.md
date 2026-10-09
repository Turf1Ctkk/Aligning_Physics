# Second-seed calibration replay

Only completed, audited calibrators are shown. Step control is a separate endpoint. This run reuses exactly the same selected data; it is not new acquisition.

Position is in mm, acceleration in mm/frame² and root velocity in mm/frame at 50 Hz. Replay uses the first second and 24 measured bodies. The source-zero control was recorded once at the fixed shared replay seed.

![Second-seed replay errors](../repeat_replay.png)

| Group | E_g-mpjpe | E_mpjpe | E_acc | E_vel | Complete replay (%) |
|---|---:|---:|---:|---:|---:|
| Shared source20 zero | 39.774 | 21.043 | 0.799 | 3.521 | 100.0 |
| Random-N | 31.744 | 16.967 | 0.811 | 2.819 | 100.0 |

Pending calibration: Servo-coverage-N. No second-seed selector contrast is available yet.

| Group | Validation at 500 (mm) | Validation at 1,000 (mm) | Selected update |
|---|---:|---:|---:|
| Random-N | 48.108 | 42.053 | 1000 |

Both validation candidates are retained. Test outcomes do not select checkpoints. Actual case identities, hashes and metric aggregates were recomputed from physical records. Learned and shared-zero starts, actions and clocks match exactly. No reconstruction floor is subtracted.

Two training seeds cannot establish a reliable ranking. Do not select the better run. The full [control report](../metrics.md) includes completed audited policies only.

## Per-ankle magnitude strata

Bins are fixed from training. Inclusion is the share of planned scored samples for that ankle. Errors average available cases by parent and task. Entries overlap across ankles and are not independent trials. Sign is not separated in this table.

| Group | Ankle | Magnitude | Inclusion (%) | Body error (mm) | Joint RMSE (rad) | Joint velocity RMSE (rad/s) |
|---|---|---|---:|---:|---:|---:|
| Random-N | Left pitch | Small | 30.9 | 35.068 | 0.11909 | 4.69782 |
| Random-N | Left pitch | Medium | 36.3 | 39.471 | 0.11757 | 1.59466 |
| Random-N | Left pitch | Large | 32.8 | 37.369 | 0.11309 | 2.16648 |
| Random-N | Left roll | Small | 35.6 | 40.249 | 0.06510 | 3.49348 |
| Random-N | Left roll | Medium | 32.1 | 27.916 | 0.03900 | 3.17163 |
| Random-N | Left roll | Large | 15.9 | 43.574 | 0.04800 | 6.98064 |
| Random-N | Right pitch | Small | 43.8 | 39.364 | 0.19266 | 5.76085 |
| Random-N | Right pitch | Medium | 29.3 | 39.465 | 0.15299 | 3.16152 |
| Random-N | Right pitch | Large | 23.9 | 26.779 | 0.08311 | 1.58059 |
| Random-N | Right roll | Small | 36.7 | 25.290 | 0.06501 | 2.70241 |
| Random-N | Right roll | Medium | 36.6 | 22.221 | 0.02534 | 2.01176 |
| Random-N | Right roll | Large | 26.7 | 40.358 | 0.03451 | 2.48726 |
