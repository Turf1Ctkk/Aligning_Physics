# CR7 policy comparison

Each adapted policy receives 1,000 additional updates from the task's recorded `model_6000.pt`. The frozen calibration models are shared across tasks. All policies run alone in B for 3.92 seconds.

Original and ordinary fine-tuning both complete 100.0%. Delta action completes 95.8%, passive SysID 80.2%, common torque 72.9%, active SysID 90.6%, and excitation-data torque 57.3%. Calibration gives no extra completion benefit here.

Stored initial states and effective evaluation settings match across methods. Prefix and full-motion errors include only trials that reach that horizon. The historical position metrics use 24 bodies. Fresh 27-point position, velocity and acceleration metrics are queued.

[Historical table](metrics.md), [all trials](tracking_comparison.json) and [audits](.) retain the evidence. Terminations are recorded without automatically calling them falls. One training seed limits method rankings. This motion contributed calibration data and is not an unseen-motion test.
