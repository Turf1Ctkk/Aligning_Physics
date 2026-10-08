# CR7: fresh 27-point evaluation

The first-second errors below use trials that reach one second. Inclusion is reported separately.

| Policy | Completion (%) | Tracking success (%) | Included (%) | Global position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Active SysID | 90.6 | 89.6 | 95.8 | 123.418 | 49.294 | 6.519 | 5.681 | 2.690 |
| Delta action | 95.8 | 91.7 | 100.0 | 127.397 | 55.805 | 6.206 | 5.278 | 2.484 |
| Fine-tuning only | 100.0 | 100.0 | 100.0 | 119.983 | 53.270 | 6.104 | 5.336 | 2.569 |
| Passive SysID | 80.2 | 79.2 | 95.8 | 129.575 | 56.101 | 6.908 | 6.074 | 2.671 |
| Torque correction | 72.9 | 67.7 | 89.6 | 136.243 | 59.017 | 7.311 | 6.650 | 2.667 |
| Original | 100.0 | 100.0 | 100.0 | 123.467 | 43.260 | 6.358 | 5.277 | 2.662 |
| Excitation torque | 57.3 | 54.2 | 85.4 | 138.215 | 64.351 | 8.203 | 7.093 | 3.025 |

Tracking success requires full completion and mean body distance no greater than 0.5 m throughout the trial.
Full-motion and available-frame metrics remain in the JSON report. No derivatives cross a reset.
These evaluation trials are not independent training replications.
