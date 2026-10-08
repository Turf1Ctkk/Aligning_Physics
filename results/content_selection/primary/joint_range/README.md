# First-run joint range selection

This arm uses the same 18 parents and 954 transitions as the other selectors. It receives 1,000 calibration and 1,000 policy updates. The window manifest is unchanged from the published preview.

Validation selects update 1,000. Held-out body error is 45.73 mm and joint-velocity RMSE is 1.053 rad/s. Squat completion is 77.1%, with mean survival 5.117 seconds.

These are historical 24-body position and joint-velocity metrics. Completion uses the original matched runtime criteria. The new ASAP-style metrics require fresh evaluation.

[Summary](summary.json), [trials](comparison.json), [validation](delta_selection.json) and [selected-window replay floor](selected_subset_replay_floor.json) retain the results. Failed trials remain in the report. No window is replaced and no replay floor is subtracted. [Full comparison](../../README.md).
