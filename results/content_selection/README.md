# Fixed-budget data-content test

This experiment compares three data-selection rules. All use the same 18 training parents, with one window per parent and 954 selected transitions. The model, sampler and training budget stay fixed. Validation chooses the calibration checkpoint; final policy checkpoints are fixed.

| Rule | Historical replay position error (mm) | Joint-velocity RMSE (rad/s) | Squat completion (%) | Mean survival (s) |
|---|---:|---:|---:|---:|
| Uniform | 32.96 | 0.990 | 8.3 | 4.993 |
| Actuator coverage | 28.42 | 0.845 | 41.7 | 3.921 |
| Large joint range | 45.73 | 1.053 | 77.1 | 5.117 |

Coverage gives smaller replay errors, while range gives higher completion. The combined replay-and-control hypothesis is not confirmed in this first seed. Coverage also has shorter mean survival than uniform; completion alone does not summarize every outcome.

Selected windows have different same-domain replay errors. We retain those floors without subtraction or replacement. Selection can change motion phase, contacts and initialization as well as the intended feature. Equal selected data size also does not equalize the cost of acquiring the original pool.

The second seed is running on byte-identical selected datasets. Both runs will be reported separately. [First-run report](primary/metrics.md), [selection manifest](selection_manifest_actual.json) and [raw summary](primary/summary.json) preserve the evidence. Fresh whole-body policy evaluations are queued.
