# Fixed-budget content test: selection preview, no learning results yet

The selector has been run on the existing training pool; calibration and policy comparisons are queued after the method/task pipelines, with a five-hour minimum margin before GPU cutoff. [Preview manifest](selection_manifest_preview.json) records actual chosen windows, original parent groups, feature definitions and scaling. It does not contain a performance result.

All three selectors use **the same 18 original recording groups**, six per motion, and one 54-frame window per group: **954 unique next-state transitions** in every condition. Groups are chosen with fixed seed 7701 before selecting windows. Task/group weights, delta architecture, 1000-update calibration budget, validation checkpoint criterion and 1000-update Squat fine-tuning budget are common. Validation/test groups stay unchanged.

| Selector | Window choice within each fixed parent group |
|---|---|
| Uniform | A seeded random eligible window. |
| Actuator coverage | Greedy max-min distance between robustly scaled window-level actuator features; the first window is nearest the pool center. |
| Joint range | Maximum mean ankle joint excursion within the window. |

Coverage uses 28 summary features: signed servo-error mean and standard deviation, velocity mean/RMS, command-change RMS, nominal source unsaturated fraction and near-clipping fraction, each on four ankles. Servo error uses state[i] with action[i+1]. This is a transparent heuristic for command-state diversity; it is not guaranteed to optimize neural-model information or downstream control.

One trained delta and task policy per selector use common seeds. Report held-out replay, target completion/survival and full/common-prefix tracking. Each selected training subset also receives a same-domain zero-correction replay check; its floor is reported without changing the selected windows after observing errors. A large difference in initialization floors would limit a data-content interpretation.

Candidate windows can overlap in the inspected pool, but only one window per parent group enters each training subset. The full pool has 400 candidate windows; inspection and prior acquisition of that pool are additional costs. This experiment controls selected training-data content and amount, not total target-system acquisition cost. It is retrospective and tests only one mechanism, model and training seed.
