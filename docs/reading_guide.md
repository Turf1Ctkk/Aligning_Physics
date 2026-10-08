# Reading guide

Start with the [main report](../README.md). It contains the question, hypothesis and main observations.

For more detail:

- [Research argument](research_argument.md): why actuator data may matter, and why replay may not predict control.
- [Methods](methods.md): what was implemented and how it differs from the source papers.
- [Evaluation](evaluation.md): position, velocity, acceleration, completion and tracking success.
- [Protocol](experimental_protocol.md): datasets, budgets and comparisons.
- [Reproduction](reproduction.md): code installation and experiment tools.
- [Setting audit](settings_audit.md): the confirmed input mismatch and differences from pretraining.

The `results` folders hold measured evidence. Their short reports explain the experiment; JSON files hold individual trials, settings and audits. Raw counts remain in those files. Reader-facing tables use percentages.

The original 27-point policy metrics are in [Squat](../results/paper_evaluation/SquatL1.md), [CR7](../results/paper_evaluation/CR7.md) and [Step](../results/paper_evaluation/StepFBL1.md). The [calibration replay table](../results/paper_replay/metrics.md) reports 24-body errors. The [data-content report](../results/content_selection/README.md) compares both training runs separately.

The [method comparison](../results/method_comparison/metrics.md) collects the four requested errors and closed-loop success. It uses all three repaired delta policies, with other methods unchanged. The [repair report](../results/noise_repair/metrics.md) preserves before/after results. The [source check](../results/source_quality/metrics.md) compares original and FT-only policies in A and B.

The `overlays` folder contains code installed into ASAP. `scripts` contains analysis and reporting tools. Large checkpoints and recordings stay on the experiment server. Historical records are retained while experiments finish; a final cleanup will reduce the repository further.

Existing GIFs have been removed. IsaacGym visualizations will be added by the author later.
