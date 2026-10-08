# Actual 200 Hz target acquisition: unchanged versus excitation

**Status:** physical acquisition, rate/command/feasibility audits and zero-correction replay checks complete. Unchanged-arm shared-torque calibration and held-out replay are complete; its policy fine-tuning is running. The excitation-trained model and matched policy comparisons remain pending.

Both arms use the same 30 original mixed30 parents, ten per task, initialized from their first eligible continuous windows. Unchanged input holds recorded nominal position commands for four physics steps. The excitation arm adds sine, square or clipped Gaussian offsets at 200 Hz, bounded by ±0.04 rad on four ankles; sine/square frequencies are 1–3 Hz. [Actual excitation manifest](excitation_manifest.json). This is a G1 adaptation of UAN's excitation-data idea, with prerecorded task inputs plus offsets rather than the original robot/command interface.

All 60 acquired groups supply **208 actual post-step states**, nominally at 200 Hz, with consecutive timestamps separated by 5 ms within numerical tolerance. There is no synthetic upsampling. All groups pass the declared one-second feasibility and no-reset checks; maximum stored/executed command discrepancy is exactly zero for every group. [Acquisition audit](acquisition_audit.json). Each arm has 6210 unique within-record transitions and 31.05 seconds of within-record transition duration; the warm step is not counted as an additional recorded transition.

## Zero-correction replay checks

The new training records are replayed at 200 Hz, with recorded initialization velocities, no learned correction and the same nominal inputs. These are acquisition-integrity diagnostics, not held-out learned-model results.

| Replay dynamics | Acquisition arm | Complete / 30 | Body MPJPE (mm) | Ankle RMSE (rad) | Joint-velocity RMSE (rad/s) |
|---|---|---:|---:|---:|---:|
| Same-domain Kp16 | Unchanged | 30 | 0.349 | 0.000900 | 0.11883 |
| Same-domain Kp16 | Excitation | 30 | 0.376 | 0.001024 | 0.14230 |
| Source Kp20 | Unchanged | 30 | 23.687 | 0.057353 | 0.58305 |
| Source Kp20 | Excitation | 30 | 24.463 | 0.062037 | 0.62627 |

[Raw summaries](acquisition_replay_check.json) include all tasks. The sub-millimeter same-domain position floor is small relative to the source-domain mismatch, while velocity error remains nonzero. This validates useful measurement fidelity for this collection setup; it does not establish full recovery of hidden contact state.

## What changed in the data?

The following are equal means across the 30 group-level summaries, not independent training replications. Source saturation applies the Kp20 PD law at recorded target states; it is not a measured target torque.

| Observed feature | Unchanged | Excitation |
|---|---:|---:|
| Mean ankle range per group (rad) | 0.34165 | 0.34175 |
| Servo-error RMS (rad) | 0.92454 | 0.92390 |
| Ankle velocity RMS (rad/s) | 2.84317 | 2.83846 |
| Position-command change RMS (rad) | 0.02921 | 0.03320 |
| Modeled source saturation fraction (%) | 5.886 | 5.886 |

The bounded offsets primarily increase command-change RMS (about 13.7%); they barely change these range/error summaries. Thus “excitation data” is not a synonym for broader joint range or universally greater informativeness. Temporal spectra and distribution details can differ even when aggregate RMS is similar. Utility remains an empirical question, and this small perturbation does not test every excitation mechanism.

Both arms now receive the same shared 40→128→128→1 torque actor, 20-sample 200 Hz source history, hierarchical sampling and 1000 calibration updates. Original isolated validation/test policy records remain at 50 Hz. Each arm chooses its calibration checkpoint on validation and receives 1000 additional Squat policy updates, followed by common-noise B deployment without a correction. Architecture/data duration differ from the older common50Hz-data torque run; only these two new arms constitute the matched acquisition-content comparison.


## First completed calibration arm

Validation selects the unchanged-input model at 1000 updates, with body MPJPE 41.94 mm. [Selection](unchanged_selection.json). On the original isolated 66-window test, all cases complete: body error decreases from 36.69 to 31.80 mm and ankle RMSE from 0.07657 to 0.06223 rad, while joint-velocity error increases from 0.86174 to 0.99862 rad/s. [Full held-out summaries](unchanged_replay_comparison.json) retain shorter horizons and per-task metrics.

This is a partial replay benefit, approximately 13.3% in body position, with a 15.9% velocity regression. The new acquisition has shorter duration and narrower phase coverage than the older common-data run. It cannot isolate measurement rate or establish a data-content ranking before the matched excitation arm finishes. Downstream policy outcomes remain pending.
