# SquatL1: fresh 27-point evaluation

The first-second errors below use trials that reach one second. Inclusion is reported separately.

| Policy | Completion (%) | Tracking success (%) | Included (%) | Global position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Fine-tuning only | 100.0 | 100.0 | 100.0 | 92.837 | 34.944 | 3.727 | 3.455 | 1.707 |
| Active SysID | 95.8 | 95.8 | 100.0 | 93.118 | 38.797 | 3.848 | 3.189 | 1.732 |
| Delta action | 90.6 | 89.6 | 100.0 | 96.031 | 37.683 | 4.150 | 4.110 | 1.815 |
| Unchanged-data torque | 35.4 | 16.7 | 100.0 | 92.443 | 36.941 | 3.856 | 3.642 | 1.794 |
| Coverage: first run | 41.7 | 41.7 | 100.0 | 99.348 | 37.817 | 4.206 | 3.597 | 1.702 |
| Range: first run | 77.1 | 65.6 | 100.0 | 94.876 | 36.580 | 3.843 | 3.425 | 1.770 |
| Uniform: first run | 8.3 | 5.2 | 100.0 | 95.359 | 39.444 | 4.112 | 3.779 | 1.850 |
| Coverage: repeat | 77.1 | 76.0 | 100.0 | 93.076 | 35.911 | 3.824 | 3.362 | 1.730 |
| Range: repeat | 95.8 | 95.8 | 100.0 | 93.694 | 37.598 | 3.775 | 3.400 | 1.762 |
| Uniform: repeat | 99.0 | 99.0 | 100.0 | 99.759 | 38.605 | 4.464 | 4.253 | 1.776 |
| Passive SysID | 96.9 | 96.9 | 100.0 | 90.554 | 35.141 | 3.784 | 3.269 | 1.755 |
| Torque correction | 100.0 | 100.0 | 100.0 | 92.499 | 37.158 | 3.981 | 3.736 | 1.716 |
| Original | 53.1 | 44.8 | 100.0 | 94.897 | 36.394 | 3.931 | 3.499 | 1.711 |
| Excitation torque | 99.0 | 99.0 | 100.0 | 94.626 | 34.471 | 3.866 | 3.643 | 1.723 |

Tracking success requires full completion and mean body distance no greater than 0.5 m throughout the trial.
Full-motion and available-frame metrics remain in the JSON report. No derivatives cross a reset.
These evaluation trials are not independent training replications.
