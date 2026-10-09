# Servo-error selection results

The selectors were frozen before learning. The planned arms use the same parents and selected data budget. Results include completed audited conditions only. Replay and Step control are separate endpoints. Scheduled policies use repaired inputs and reset.

Replay has 24 measured bodies. Step tracking has 27 points. Errors use the first second. Velocity is root velocity at 50 Hz. Units are mm for position, mm/frame² for acceleration and mm/frame for velocity. Early terminations change inclusion; full-motion means include successful trials only.

Pending or skipped: primary/servo, primary/ft_only, repeat/random, repeat/servo.

## Primary

| Group | Replay E_g-mpjpe | Replay E_mpjpe | Replay E_acc | Replay E_vel | Complete replay (%) |
|---|---:|---:|---:|---:|---:|
| Random-N | 35.575 | 18.359 | 0.817 | 3.029 | 100.0 |

| Group | Success (%) | Completion (%) | First-second inclusion (%) | E_g-mpjpe | E_mpjpe | E_acc | E_vel |
|---|---:|---:|---:|---:|---:|---:|---:|
| Random-N | 0.0 | 0.0 | 100.0 | 99.759 | 47.901 | 1.913 | 5.965 |

| Group | Successful full-motion inclusion (%) | E_g-mpjpe | E_mpjpe | E_acc | E_vel |
|---|---:|---:|---:|---:|---:|
| Random-N | 0.0 | N/A | N/A | N/A | N/A |

Stratified replay uses separate ankle magnitude bins from the training pool. Missing bins are not filled. Frame entries can overlap across ankles. Joint-error tables are in stratified_metrics.md; raw strata and inclusion are in stratified_metrics.json.

Phase quotas cover the available training pool, rather than the full reference. Contact uses a height/speed proxy. Continuous speed and contact distributions still differ. No same-domain floor is subtracted. The selected budget is not total acquisition cost.

The new matched FT-only policy is pending; no comparison against it is available yet. The repeat compares two selectors at its own shared seed; it has no new matched FT-only. Runs are reported separately. Two seeds do not establish a reliable ranking.
