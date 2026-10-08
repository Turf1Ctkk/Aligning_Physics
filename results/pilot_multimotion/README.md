# Original data-size pilot

This pilot trained delta action on 3, 30 or 90 original target rollouts. Each dataset included CR7, Squat and Step. Validation selected the checkpoints; test parents stayed separate.

| Training rollouts | Body position error (mm) | Joint-velocity RMSE (rad/s) |
|---|---:|---:|
| Zero correction | 35.99 | 0.851 |
| 3 | 29.33 | 0.935 |
| 30 | 27.43 | 0.933 |
| 90 | 28.40 | 0.876 |

Position improves, but velocity does not. The original sampler also changes task weights as the number of clips changes. Same-domain replay has nonzero error. This is an exploratory result, not a clean scaling test.

These historical errors use 24 rigid bodies and joint velocities. [Raw files](.) retain the original summaries and dataset audits. The later controlled experiment fixes task and rollout weights.
