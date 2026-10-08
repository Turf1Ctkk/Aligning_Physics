# Fixed-budget data-content test

This experiment compares uniform selection, actuator-feature coverage and large ankle range. Every rule uses the same 18 training rollouts, with one window per rollout and 954 selected transitions. The model, sampler and training budgets stay fixed. Validation chooses the calibration checkpoint; final policy checkpoints are fixed.

Both training runs are complete. The repeat uses byte-identical selected data.

These action-policy runs contain the frozen-delta noise mismatch found in the [setting audit](../../docs/settings_audit.md). Results remain valid for that procedure, but transfer conclusions need a repair check.

| Rule | First-run replay position (mm) | Repeat replay position (mm) | First-run completion (%) | Repeat completion (%) |
|---|---:|---:|---:|---:|
| Uniform | 33.62 | 44.88 | 8.3 | 99.0 |
| Actuator coverage | 28.99 | 35.72 | 41.7 | 77.1 |
| Large joint range | 46.66 | 49.17 | 77.1 | 95.8 |

These are fresh physical results. Replay uses 24 measured bodies; policy evaluation uses 27 points. Every one-second replay is complete. The figure shows whole-body velocity and acceleration, rather than the joint-velocity RMSE used in older reports.

![Fresh data-selection results](../paper_replay/content_selection.png)

Coverage improves replay position, velocity and acceleration against its own no-correction control in both runs. It does not consistently give better control. The combined hypothesis is not confirmed. The figure reports tracking success, which also checks the 0.5 m mean body-distance criterion. The table reports completion.

Two fixed-data training seeds are a sensitivity check, rather than independent acquisition repeats. Replay evaluation also changes seed between runs; policy deployment seeds stay fixed. Selection changes phase, contact conditions and initialization as well as the intended features. Selected windows have different same-domain replay floors, which are retained without subtraction or replacement. Equal selected data size does not equalize the cost of acquiring the larger pool.

[Fresh replay table](../paper_replay/metrics.md) and [fresh Squat policy table](../paper_evaluation/SquatL1.md) contain all current metrics. [Both-run historical table](repeat/metrics.md), [paired summary](repeat/paired_summary.json), [selection manifest](selection_manifest_actual.json) and [repeat replay controls](repeat_controls/fresh_test_baselines.json) preserve earlier evidence. Every arm retains its trials, validation candidates, settings and input audits. Repeated same-domain floors are labelled as reused measurements.
