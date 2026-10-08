# Measured 200 Hz excitation data

Two arms collect new B data from the same 30 parents. One holds the recorded commands. The other adds bounded sine, square and Gaussian offsets at 200 Hz. Each arm contains 6,210 transitions from actual 5 ms measurements. All command-alignment and feasibility checks pass.

Both arms use the same torque model and 1,000 calibration plus 1,000 policy updates.

| Data | Held-out body error (mm) | Joint-velocity RMSE (rad/s) | Squat completion (%) |
|---|---:|---:|---:|
| Unchanged inputs | 31.80 | 0.999 | 35.4 |
| Excitation | 30.35 | 0.943 | 99.0 |

Excitation improves these two replay metrics and completion relative to unchanged data. Ankle error is slightly worse. Neither arm beats ordinary fine-tuning's 100.0% completion. These are observations from one training seed, not proof that one feature causes the difference.

Joint range barely changes between arms. This motivates further tests of command timing and actuator conditions. This G1 interface differs from the original UAN experiment. [Summary](comparison_summary.json) and [raw evidence](.) preserve the paired results. Fresh 27-point policy errors are queued.
