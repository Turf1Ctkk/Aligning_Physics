# Completed task-policy reuse comparisons

All three task comparisons are complete. Calibrators/gains are shared and frozen during task training; adapted policies start from each task's recorded model6000 and receive1000 additional updates. Standalone B deployment uses no learned correction and common effective settings within each task. Each method has one task-training seed and96 evaluation trials across three deployment seeds.

| Policy | SquatL1 /96 (5.22s) | CR7 /96 (3.92s) | StepFBL1 /96 (3.92s) |
|---|---:|---:|---:|
| Original |51|96|1|
| FT only |96|96|39|
| ASAP |87|92|76|
| Passive SysID |93|77|96|
| Common torque |96|70|82|
| Active SysID |92|87|87|
| Excitation torque |95|55|83|

![Task-dependent completion](completion.png)

[Summary with source hashes](completion_summary.json), [reproduction script](../../scripts/report_task_completion.py), [Squat metrics/audits](../matched_squat/README.md), [CR7 metrics/audits](CR7/README.md), [Step metrics/audits](StepFBL1/README.md). The Squat excitation column is the completed true-rate acquisition policy reported [separately](../wave_acquisition/README.md).

There is no additional completion benefit over FT-only on Squat or CR7 in these samples. Step supplies a positive observation: passive SysID completes96/96 versus FT-only39/96 and lowers first-second global/root-relative tracking errors over all96 prefixes. These are task-dependent trained-policy outcomes, not independent calibrator replications. Different task horizons, initial policies and policy optimization prevent a pooled cross-task method ranking. Later tracking errors condition on surviving subsets and remain in the task-level reports. All three motions contributed calibration data, so this is not calibration-motion holdout or hardware validation. No data selector, threshold or checkpoint was changed based on these outcomes.
