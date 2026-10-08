# Method comparison

These are the measured results before the training-setting repair. Delta policy training contains the noise mismatch described in the [setting audit](../../docs/settings_audit.md).

## Open-loop replay

One second, 24 measured bodies. All replay cases reach the horizon. Means give equal weight to tasks and original rollouts. Original and FT-only use the same uncalibrated dynamics; task policy weights do not enter fixed-action replay.

| Method | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |
|---|---:|---:|---:|---:|
| Original | 38.420 | 20.387 | 0.771 | 3.460 |
| FT only | 38.420 | 20.387 | 0.771 | 3.460 |
| Delta action | 31.121 | 16.634 | 0.663 | 2.678 |
| Passive SysID | 31.496 | 16.882 | 0.677 | 3.009 |
| Active SysID | 9.351 | 5.470 | 0.323 | 0.855 |
| Common torque | 24.974 | 13.680 | 0.661 | 2.229 |
| Excitation torque | 30.962 | 16.568 | 0.722 | 2.736 |

The common and excitation torque datasets differ in rate, duration and phase. Their contrast does not isolate excitation. A separate unchanged-versus-excitation acquisition experiment provides that paired comparison.

Torque models have already acted before their first saved frame. The control shares the input and seed, but not that post-step state. Results include startup. SysID fitting and replay protocols also differ from delta action. These bars do not establish a model-family ranking.

## Closed-loop SquatL1

Errors use the first second. Success uses the complete reference horizon. E_vel is root velocity; whole-body velocity is retained in the raw reports.

| Policy | Success (%) | Included (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |
|---|---:|---:|---:|---:|---:|---:|
| Original | 44.8 | 100.0 | 94.897 | 36.394 | 1.711 | 3.499 |
| FT only | 100.0 | 100.0 | 92.837 | 34.944 | 1.707 | 3.455 |
| Delta action | 89.6 | 100.0 | 96.031 | 37.683 | 1.815 | 4.110 |
| Passive SysID | 96.9 | 100.0 | 90.554 | 35.141 | 1.755 | 3.269 |
| Active SysID | 95.8 | 100.0 | 93.118 | 38.797 | 1.732 | 3.189 |
| Common torque | 100.0 | 100.0 | 92.499 | 37.158 | 1.716 | 3.736 |
| Excitation torque | 99.0 | 100.0 | 94.626 | 34.471 | 1.723 | 3.643 |

Full-motion errors below use successful trials only. A small error with low inclusion is not evidence of reliable control.

| Policy | Full-motion inclusion (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |
|---|---:|---:|---:|---:|---:|
| Original | 44.8 | 126.136 | 50.619 | 0.828 | 2.801 |
| FT only | 100.0 | 93.250 | 43.279 | 0.795 | 2.591 |
| Delta action | 89.6 | 95.293 | 42.624 | 0.838 | 2.762 |
| Passive SysID | 96.9 | 94.999 | 43.275 | 0.824 | 2.699 |
| Active SysID | 95.8 | 106.547 | 44.631 | 0.807 | 2.619 |
| Common torque | 100.0 | 105.282 | 44.938 | 0.809 | 2.669 |
| Excitation torque | 99.0 | 99.168 | 46.866 | 0.786 | 2.392 |

## Closed-loop CR7

Errors use the first second. Success uses the complete reference horizon. E_vel is root velocity; whole-body velocity is retained in the raw reports.

| Policy | Success (%) | Included (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |
|---|---:|---:|---:|---:|---:|---:|
| Original | 100.0 | 100.0 | 123.467 | 43.260 | 2.662 | 5.277 |
| FT only | 100.0 | 100.0 | 119.983 | 53.270 | 2.569 | 5.336 |
| Delta action | 91.7 | 100.0 | 127.397 | 55.805 | 2.484 | 5.278 |
| Passive SysID | 79.2 | 95.8 | 129.575 | 56.101 | 2.671 | 6.074 |
| Active SysID | 89.6 | 95.8 | 123.418 | 49.294 | 2.690 | 5.681 |
| Common torque | 67.7 | 89.6 | 136.243 | 59.017 | 2.667 | 6.650 |
| Excitation torque | 54.2 | 85.4 | 138.215 | 64.351 | 3.025 | 7.093 |

Full-motion errors below use successful trials only. A small error with low inclusion is not evidence of reliable control.

| Policy | Full-motion inclusion (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |
|---|---:|---:|---:|---:|---:|
| Original | 100.0 | 133.683 | 50.985 | 3.417 | 5.830 |
| FT only | 100.0 | 114.467 | 57.113 | 3.104 | 5.681 |
| Delta action | 91.7 | 116.205 | 57.629 | 3.126 | 5.703 |
| Passive SysID | 79.2 | 115.166 | 57.132 | 3.232 | 6.075 |
| Active SysID | 89.6 | 121.877 | 55.526 | 3.185 | 5.862 |
| Common torque | 67.7 | 126.649 | 56.965 | 3.128 | 5.887 |
| Excitation torque | 54.2 | 127.741 | 59.049 | 3.193 | 6.159 |

## Closed-loop StepFBL1

Errors use the first second. Success uses the complete reference horizon. E_vel is root velocity; whole-body velocity is retained in the raw reports.

| Policy | Success (%) | Included (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |
|---|---:|---:|---:|---:|---:|---:|
| Original | 1.0 | 100.0 | 91.108 | 43.144 | 1.809 | 4.992 |
| FT only | 36.5 | 100.0 | 77.686 | 43.029 | 1.913 | 4.242 |
| Delta action | 79.2 | 100.0 | 76.691 | 43.196 | 1.804 | 3.584 |
| Passive SysID | 100.0 | 100.0 | 62.851 | 39.785 | 1.738 | 2.704 |
| Active SysID | 90.6 | 100.0 | 78.325 | 43.884 | 2.030 | 4.341 |
| Common torque | 84.4 | 100.0 | 66.452 | 36.934 | 1.695 | 2.977 |
| Excitation torque | 85.4 | 100.0 | 85.091 | 43.461 | 2.434 | 5.436 |

Full-motion errors below use successful trials only. A small error with low inclusion is not evidence of reliable control.

| Policy | Full-motion inclusion (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |
|---|---:|---:|---:|---:|---:|
| Original | 1.0 | 91.747 | 41.646 | 1.177 | 3.076 |
| FT only | 36.5 | 119.887 | 47.446 | 1.269 | 3.971 |
| Delta action | 79.2 | 87.411 | 46.147 | 1.291 | 3.232 |
| Passive SysID | 100.0 | 85.321 | 47.885 | 1.274 | 3.305 |
| Active SysID | 90.6 | 96.339 | 47.447 | 1.307 | 4.133 |
| Common torque | 84.4 | 91.691 | 45.203 | 1.273 | 3.251 |
| Excitation torque | 85.4 | 113.382 | 55.265 | 1.342 | 4.548 |

