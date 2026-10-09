# Random-N calibration: first run

Calibration is complete. Validation selected update 1,000: global MPJPE was 41.59 mm, compared with 54.31 mm at update 500. Both candidate reports are retained.

All test cases reach the one-second horizon. Errors exclude the warm sample. Position uses 24 measured bodies. Velocity is root velocity. Weights are equal by parent and task.

| Setting | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel (mm/frame) |
|---|---:|---:|---:|---:|
| Source20, zero correction | 39.774 | 21.043 | 0.799 | 3.521 |
| Random-N delta | 35.575 | 18.359 | 0.817 | 3.029 |
| Same16, zero correction diagnostic | 11.585 | 7.079 | 0.395 | 1.064 |

Random calibration improves both position errors and root velocity. Acceleration error is slightly worse. Servo-coverage is pending, so these results do not compare selection rules. Step fine-tuning is running; no control result is available yet.

The learned and source-zero replays have exactly matching first stored states, actions and clocks. Actual records were independently checked and their metric aggregates recomputed. The same-gain diagnostic is retained without subtraction; its warm state uses different gains.

The selected-training same16 check has a historical 24-body error of 21.52 mm. This is a reconstruction diagnostic, not a learned result. The replay helper reuses the root same16 log and command names. The test check replaces these names after the training check. Both checks retain separate recordings, reports and configs. This limits log provenance.

Four-ankle position and velocity errors and fixed magnitude strata remain in the raw case reports. Stratum inclusion differs; frame entries are not independent trials.

