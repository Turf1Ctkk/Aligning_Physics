# StepFBL1 policy comparison

Each adapted policy receives 1,000 additional updates from the task's recorded `model_6000.pt`. The frozen calibration models are shared across tasks. All policies run alone in B for 3.92 seconds.

Original completion is 1.0%, ordinary fine-tuning 40.6%, delta action 79.2%, passive SysID 100.0%, common torque 85.4%, active SysID 90.6%, and excitation-data torque 86.5%. This task supplies positive evidence for calibration beyond ordinary fine-tuning.

Stored initial states and effective evaluation settings match across methods. Prefix and full-motion errors include only trials that reach that horizon. The historical position metrics use 24 bodies. Fresh [27-point metrics](../../paper_evaluation/StepFBL1.md) and a separate [noise-repair comparison](../../noise_repair/metrics.md) are available.

[Historical table](metrics.md), [all trials](tracking_comparison.json) and [audits](.) retain the evidence. Terminations are recorded without automatically calling them falls. One training seed limits method rankings. This motion contributed calibration data and is not an unseen-motion test.
