# Reproduction

This repository provides a report and an overlay for [ASAP](https://github.com/LeCAR-Lab/ASAP). It does not include the simulator, motion assets or large model files. The inspected upstream commit is `df5320cc47dd8cad97961bdfabfe402dd62ad999`.

## Install the corrections

Copy `overlays/research/asap_diagnostics` into the ASAP checkout. On a pristine checkout, inspect and apply `installed_core.patch` from that folder. It is the complete five-file patch. Do not apply the two older overlapping patches as well. An already-patched checkout should be checked rather than patched again.

The fixes address action/frame timing, action lookup at floating-point frame boundaries, saved initialization velocities, residual units and current-action conditioning. Grid starts also prevent replay episodes from running past a clip's end. These changes make the pipeline interpretable; they do not validate the research hypothesis.

Run CPU checks from the ASAP root:

```bash
python research/asap_diagnostics/verify_installed_contracts.py
python research/asap_diagnostics/verify_multi_motion.py
```

Set the three policy paths in the multi-motion plan or its command-line overrides. Use the recorded `model_6000.pt` checkpoints for the comparisons reported here. CPU checks do not run physics or train a model.

## Experiment tools

| Tool | Purpose |
|---|---|
| `multi_motion_pipeline.py` | Original data-size pilot |
| `controlled_pipeline.py` | Weighted mixed30 delta and policy comparison |
| `sysid_pipeline.py` | Passive gain fitting |
| `active_pipeline.py` | Command design, new collection and gain refitting |
| `torque_pipeline.py` | Shared torque correction on common records |
| `wave_pipeline.py` | New measured 200 Hz data and paired torque training |
| `extend_tasks.py` | CR7 and Step policy comparisons |
| `content_pipeline.py` | Three fixed-budget data selectors |
| `repeat_content.py` | Second seed on the same selected data |
| `repeat_replay_controls.py` | Replay controls at the second run's seed |
| `paper_eval_queue.py` | Fresh 27-point policy evaluations |
| `paper_replay_queue.py` | Fresh calibration replays on measured 24-body targets |
| `noise_repair_queue.py` | Three-task policy retraining with two frozen-delta noise channels set to zero |
| `reset_repair_queue.py` | Three-task retraining that also clears previous delta actions at reset |

Launch these modules from an ASAP checkout. The published command JSON files and plans provide the exact settings for each completed experiment. Queue tools enforce the cutoff and stop on subprocess failure. They do not silently resume incomplete training.

## New evaluation

`paper_metrics.py` computes body position and finite-difference errors. `paper_tracking_runtime.py` records 27 points during a new physics rollout. `paper_eval_queue.py` copies the saved evaluation overrides, changing only the recorder and output paths. It freezes checkpoint hashes before running and checks each first stored state against the old record.

From this report repository, run the independent CPU metric checks:

```bash
python scripts/verify_paper_metrics.py
```

See [metric definitions](evaluation.md) for units and failure handling. The completed queues ran after the repeat and its replay controls. The first policy job also served as the physical smoke check. No new learning was required. `audit_paper_evaluation.py` checks fresh policy records and settings. `audit_paper_replay.py` checks replay inputs, settings and recomputed metrics. The two `report_paper_*` scripts create tables and plots only after their queues complete.

## Artifacts and analysis

Install `requirements-analysis.txt` in an analysis environment to regenerate plots and reports. Scripts verify complete inputs before reporting results. Publication audits check stored starts, effective settings, horizons and checkpoint hashes. They do not prove equality of hidden contact-solver state.

Large checkpoints and trusted joblib recordings stay outside Git. Public artifacts include metrics, trial reports, manifests, hashes and patches. Existing logs preserve an optional keyboard-listener thread error where the main recorder still completed. No failed main process was ignored.

Known-gain analytic replay is an opt-in implementation diagnostic. Ordinary learning queues do not use its privileged gain ratio. It is not a learned method or a training label.

Source policy hashes are retained in the task evaluation audits. All three comparisons use each task's own `model_6000.pt`; a checkpoint name alone is not sufficient provenance.

`audit_noise_repair.py` checks each completed repair task against its old commands and saved configs, then recomputes all metrics. `report_noise_repair.py` creates the separate before/after report. Once all three tasks pass audit, regenerate the main comparison with:

```bash
python scripts/report_noise_repair.py --root results/reset_repair --baseline-root results/noise_repair --repair-kind reset
python scripts/report_method_comparison.py --repair-root results/reset_repair --repair-kind reset
```

The main reporter refuses a pending repair root. It replaces all three delta policies together with their fixed-final noise-and-reset repaired models. It does not select a checkpoint or a repair version from test performance. Open-loop results stay unchanged because the calibrator was not retrained. Earlier chart data and both before/after reports remain available.

## Author-recorded GUI examples

Six policies are prepared for three small comparisons: Original versus repaired ASAP on Squat, Original versus FT-only on CR7, and Original versus passive SysID on Step. [The selection manifest](../results/visualizations/selection_manifest.json) retains checkpoint hashes and aggregate results. These are chosen illustrations, not a complete method ranking. CR7 includes the global/relative error tradeoff, and FT-only remains a stronger Squat success baseline.

The local viewer uses target ankle stiffness 16, seed 8101 and one robot. All six models pass a short local inference check; native viewer creation also passes. This check does not produce new tracking statistics. The prepared local bundle contains `view.sh` and `RECORDING_GUIDE.md`. Press R to start recording and R again to save the video before closing the window.

Once the author records the six videos, import them with:

```bash
python scripts/import_gui_recordings.py --recordings PATH_TO_RECORDINGS --manifest PATH_TO_BUNDLE/manifest.json
```

Expected filenames are `squat_original.mp4`, `squat_asap.mp4`, `cr7_original.mp4`, `cr7_ft.mp4`, `step_original.mp4` and `step_sysid.mp4`. Optional `--starts` accepts a JSON file of start times for clip alignment. The importer creates three comparison GIFs, records video hashes and inserts actual embeds into the main README. Missing videos stop it before any README edit. Review the clips before publishing; they do not replace the aggregate error and success figures.
