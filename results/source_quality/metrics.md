# Source-policy quality

This additional physical test uses the original and FT-only checkpoints. It changes only ankle gains from target16 to source20, plus output paths. Seeds, initialization, noise, references and termination settings remain the same. All actual configs and trial metrics were checked.

| Task | Policy | Source A success (%) | Target B success (%) | Source first-second E_g-mpjpe (mm) | Target first-second E_g-mpjpe (mm) |
|---|---|---:|---:|---:|---:|
| SquatL1 | Original | 88.5 | 44.8 | 91.91 | 94.90 |
| SquatL1 | FT only | 95.8 | 100.0 | 90.79 | 92.84 |
| CR7 | Original | 100.0 | 100.0 | 122.21 | 123.47 |
| CR7 | FT only | 100.0 | 100.0 | 119.94 | 119.98 |
| StepFBL1 | Original | 90.6 | 1.0 | 72.20 | 91.11 |
| StepFBL1 | FT only | 97.9 | 36.5 | 67.96 | 77.69 |

The Step policy can complete the motion in A. Its poor B result is therefore a transfer problem under this protocol, rather than evidence that it never learned the motion. CR7 already succeeds in B, so success alone leaves little room for improvement. Squat and CR7 still have pose and motion errors.

These tests start from model6000, as fixed in the comparison. They do not select a newer or better source checkpoint. Initial states are compared through the settings and seeds; post-warm physical states can change when gains change.

The first launch failed before physics because the environment bin directory was absent from PATH and Ninja was unavailable. Its artifacts remain at source_quality_20261009. The complete fresh run is source_quality_20261009_pathfix. No checkpoint or physics setting changed for this launch repair.

