# StepFBL1: fresh 27-point evaluation

The first-second errors below use trials that reach one second. Inclusion is reported separately.

| Policy | Completion (%) | Tracking success (%) | Included (%) | Global position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Active SysID | 90.6 | 90.6 | 100.0 | 78.325 | 43.884 | 5.203 | 4.341 | 2.030 |
| Delta action | 79.2 | 79.2 | 100.0 | 76.691 | 43.196 | 4.045 | 3.584 | 1.804 |
| Fine-tuning only | 40.6 | 36.5 | 100.0 | 77.686 | 43.029 | 4.948 | 4.242 | 1.913 |
| Passive SysID | 100.0 | 100.0 | 100.0 | 62.851 | 39.785 | 3.433 | 2.704 | 1.738 |
| Torque correction | 85.4 | 84.4 | 100.0 | 66.452 | 36.934 | 3.547 | 2.977 | 1.695 |
| Original | 1.0 | 1.0 | 100.0 | 91.108 | 43.144 | 5.394 | 4.992 | 1.809 |
| Excitation torque | 86.5 | 85.4 | 100.0 | 85.091 | 43.461 | 6.634 | 5.436 | 2.434 |

Tracking success requires full completion and mean body distance no greater than 0.5 m throughout the trial.
Full-motion and available-frame metrics remain in the JSON report. No derivatives cross a reset.
These evaluation trials are not independent training replications.
