# Reusing calibration across three tasks

The same frozen calibrators are reused for Squat, CR7 and StepFBL1. Each task starts from its own pretrained policy and receives the same extra training budget. All three motions were present in calibration, so this is not an unseen-motion test.

Calibration improves completion on Step compared with ordinary fine-tuning. It does not improve completion further on Squat or CR7. Task behavior therefore matters when judging the value of calibration.

![Historical completion percentages](completion.png)

Squat is evaluated for 5.22 seconds; CR7 and Step for 3.92 seconds. Do not pool these tasks into one score. Each method has one training seed and three deployment seeds. [CR7 details](CR7/README.md), [Step details](StepFBL1/README.md) and [raw counts and hashes](completion_summary.json) are retained. Fresh 27-point error evaluation is queued.
