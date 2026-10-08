# Fixed-budget data-content test

This experiment compares three data-selection rules. All use the same 18 training parents, with one window per parent and 954 selected transitions. The model, sampler and training budget stay fixed. Validation chooses the calibration checkpoint; final policy checkpoints are fixed.

| Rule | Historical replay position error (mm) | Joint-velocity RMSE (rad/s) | Squat completion (%) | Mean survival (s) |
|---|---:|---:|---:|---:|
| Uniform | 32.96 | 0.990 | 8.3 | 4.993 |
| Actuator coverage | 28.42 | 0.845 | 41.7 | 3.921 |
| Large joint range | 45.73 | 1.053 | 77.1 | 5.117 |

Coverage gives smaller replay errors, while range gives higher completion. The combined replay-and-control hypothesis is not confirmed in this first seed. Coverage also has shorter mean survival than uniform; completion alone does not summarize every outcome.

Selected windows have different same-domain replay errors. We retain those floors without subtraction or replacement. Selection can change motion phase, contacts and initialization as well as the intended feature. Equal selected data size also does not equalize the cost of acquiring the original pool.

The second run uses byte-identical selected data. Two arms are complete; range is still running.

| Rule | First-run completion (%) | Second-run completion (%) | Second-run historical replay position error (mm) |
|---|---:|---:|---:|
| Uniform | 8.3 | 99.0 | 43.96 |
| Actuator coverage | 41.7 | 77.1 | 35.02 |
| Large joint range | 77.1 | Pending | Pending |

These changes show strong sensitivity to the training seed. Both runs will be reported separately. Replay evaluation also changes seed between runs, so its variation is not due to training alone. Fresh second-run zero-correction controls are pending. Copied first-run controls are not matched baselines.

Coverage's second-run mean survival is 4.991 s. Its first-second body error is 93.40 mm, using every trial. The first-three-second mean uses 99.0% of trials, and full-motion errors use only completed trials. Terminations occur from 2.42 to 5.18 s; their cause is not classified. These are historical 24-body metrics. Fresh whole-body evaluations remain queued.

[First-run report](primary/metrics.md), [selection manifest](selection_manifest_actual.json) and [raw summary](primary/summary.json) preserve the evidence. The completed [uniform](repeat/uniform/summary.json) and [coverage](repeat/coverage/summary.json) repeat results include separate state/settings and input-copy audits. Both retain all trials and validation candidates.
