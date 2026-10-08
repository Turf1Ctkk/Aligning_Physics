# Fresh calibration replay

These physical replays compare predictions with 24 measured target bodies. Errors use the one-second horizon, excluding the first stored frame. All jobs use 50 Hz output.

Cases are averaged within each recorded parent, then within each task, then across the three tasks. Available uninterrupted frames are scored; completion is reported separately. No derivatives cross a reset.

## Delta action

| Condition | Complete (%) | Position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|
| Target-gain diagnostic | 100.0 | 7.542 | 4.729 | 0.775 | 0.701 | 0.302 |
| No correction | 100.0 | 38.420 | 20.387 | 3.390 | 3.460 | 0.771 |
| Delta action | 100.0 | 31.121 | 16.634 | 2.682 | 2.678 | 0.663 |

## Passive SysID

| Condition | Complete (%) | Position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|
| Fitted gains | 100.0 | 31.496 | 16.882 | 2.895 | 3.009 | 0.677 |

## Common-data torque

| Condition | Complete (%) | Position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|
| Target-gain diagnostic | 100.0 | 8.315 | 5.201 | 0.842 | 0.770 | 0.319 |
| No correction | 100.0 | 37.426 | 19.812 | 3.304 | 3.359 | 0.773 |
| Torque correction | 100.0 | 24.974 | 13.680 | 2.251 | 2.229 | 0.661 |

## Active acquisition

| Condition | Complete (%) | Position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|
| Unchanged-data fit | 100.0 | 9.526 | 5.563 | 0.921 | 0.870 | 0.324 |
| Random-excitation fit | 100.0 | 8.850 | 5.329 | 0.874 | 0.812 | 0.318 |
| Optimized-excitation fit | 100.0 | 9.351 | 5.470 | 0.910 | 0.855 | 0.323 |

## Measured 200 Hz: unchanged data

| Condition | Complete (%) | Position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|
| Target-gain diagnostic | 100.0 | 8.315 | 5.201 | 0.842 | 0.770 | 0.319 |
| No correction | 100.0 | 37.426 | 19.812 | 3.304 | 3.359 | 0.773 |
| Torque correction | 100.0 | 32.441 | 17.786 | 2.873 | 2.883 | 0.727 |

## Measured 200 Hz: excitation data

| Condition | Complete (%) | Position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|
| Target-gain diagnostic | 100.0 | 8.315 | 5.201 | 0.842 | 0.770 | 0.319 |
| No correction | 100.0 | 37.426 | 19.812 | 3.304 | 3.359 | 0.773 |
| Torque correction | 100.0 | 30.962 | 16.568 | 2.741 | 2.736 | 0.722 |

## Data selection: first run

| Condition | Complete (%) | Position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|
| Uniform | 100.0 | 33.623 | 17.636 | 2.880 | 2.817 | 0.767 |
| Coverage | 100.0 | 28.989 | 15.913 | 2.575 | 2.491 | 0.702 |
| Joint range | 100.0 | 46.661 | 24.453 | 3.984 | 4.095 | 0.887 |
| Target-gain diagnostic | 100.0 | 9.586 | 5.591 | 0.932 | 0.864 | 0.347 |
| No correction | 100.0 | 37.665 | 19.701 | 3.273 | 3.325 | 0.727 |

## Data selection: repeat

| Condition | Complete (%) | Position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |
|---|---:|---:|---:|---:|---:|---:|
| Uniform | 100.0 | 44.882 | 22.977 | 3.950 | 3.980 | 0.979 |
| Coverage | 100.0 | 35.724 | 19.301 | 3.173 | 3.166 | 0.786 |
| Joint range | 100.0 | 49.171 | 25.992 | 4.164 | 4.235 | 0.936 |
| No correction | 100.0 | 39.988 | 21.133 | 3.510 | 3.558 | 0.803 |
| Target-gain diagnostic | 100.0 | 12.001 | 7.402 | 1.188 | 1.086 | 0.419 |

Target-gain rows are implementation diagnostics, not learned methods. Each no-correction row belongs to its own experiment and replay seed. The passive fit has no separate fresh matched zero row here.
Action replay and all six data-selection models match their source controls at the first stored state. Torque replay saves only every fourth physical step. Its model has already acted before the first saved frame, so those saved states differ from zero correction. Torque results describe the full replay procedure, including its startup.
Model architectures, calibration transitions and acquisition phases differ between method families. These results do not establish a representation ranking.
Replay uses 24 measured target bodies; policy evaluation uses 27 points. Their absolute error values should not be compared as the same point set.
