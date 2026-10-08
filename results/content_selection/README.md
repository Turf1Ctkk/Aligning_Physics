# Fixed-budget content test: selection preview, no learning results yet

The selector has been run on the existing training pool; calibration and policy comparisons are queued after the method/task pipelines, with a five-hour minimum margin before GPU cutoff. [Preview manifest](selection_manifest_preview.json) records actual chosen windows, original parent groups, feature definitions and scaling. It does not contain a performance result.

All three selectors use **the same 18 original recording groups**, six per motion, and one 54-frame window per group: **954 unique next-state transitions** in every condition. Groups are chosen with fixed seed 7701 before selecting windows. Task/group weights, delta architecture, 1000-update calibration budget, validation checkpoint criterion and 1000-update Squat fine-tuning budget are common. Validation/test groups stay unchanged.

| Selector | Window choice within each fixed parent group |
|---|---|
| Uniform | A seeded random eligible window. |
| Actuator coverage | Greedy max-min distance between robustly scaled window-level actuator features; the first window is nearest the pool center. |
| Joint range | Maximum mean ankle joint excursion within the window. |

Coverage uses 28 summary features: signed servo-error mean and standard deviation, velocity mean/RMS, command-change RMS, nominal source unsaturated fraction and near-clipping fraction, each on four ankles. Servo error uses state[i] with action[i+1]. This is a transparent heuristic for command-state diversity; it is not guaranteed to optimize neural-model information or downstream control.

The primary trained delta and task policy per selector use common seeds. A second paired training seed is conditionally queued after the primary comparison completes, with an additional four-hour cutoff margin. Report held-out replay, target completion/survival and full/common-prefix tracking. Each selected training subset also receives a same-domain zero-correction replay check; its floor is reported without changing the selected windows after observing errors. A large difference in initialization floors would limit a data-content interpretation.

Candidate windows can overlap in the inspected pool, but only one window per parent group enters each training subset. The full pool has 400 candidate windows; inspection and prior acquisition of that pool are additional costs. This experiment controls selected training-data content and amount, not total target-system acquisition cost. It is retrospective and tests only one mechanism, model and training seed.


The [repeat queue plan](repeat_queue_plan.json) was recorded before primary learning results. It reuses byte-identical primary training/validation/test files and sampler manifests, verified by SHA-256, and changes calibration/policy seeds from 20305008/20306008 to 20305009/20306009 for every selector. Both use 1000 calibration and 1000 policy updates, validation selection at 500/1000 and a fixed final policy. No favorable seed is selected or discarded. The repeated same-domain floors are explicitly copied primary diagnostics for identical recordings, not new replay measurements. If the primary stage fails, the repeat fails without resuming it; if time is insufficient or the primary is skipped, the repeat is explicitly skipped. CPU manifest and seed/interface contracts have passed, but no repeat learning or physics result exists yet.

This comparison measures selector differences under common seeds. The earlier FT-only policy uses another training seed and is contextual evidence, not a newly matched control for these content-study seeds. Repeating a fixed dataset does not establish robustness to different acquired parent recordings.
