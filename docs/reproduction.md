# Replay implementation and reproduction notes

This repository is a research report and an overlay for ASAP, not a replacement implementation of its simulator and assets. The pilot used [ASAP](https://github.com/LeCAR-Lab/ASAP) with local corrections. The inspected base commit is `df5320cc47dd8cad97961bdfabfe402dd62ad999`; later experiment manifests must record their actual commit and source diff.

## Corrections required by the pilot

| Contract | Reason |
|---|---|
| Recorded state/action time | The post-step recorder stores the action that produced that frame; the next transition uses the following action row. |
| Reference time after stepping | Delta replay compares the simulated post-step state to the recorded state at the corresponding time, avoiding a second one-step offset. |
| Action lookup on the 50 Hz grid | Float rounding must not select the preceding action at an integer frame boundary. |
| Recorded initial velocities | Replay must read saved joint and world-frame root velocities instead of reconstructing them from poses. |
| Frozen-delta units | An action-space residual must be multiplied by the same action scale before it modifies the PD position target. |
| Frozen-delta conditioning | The correction must receive the current nominal action, not a cached previous action. |
| Valid window starts | Replay episodes must fit entirely inside the selected continuous clip. |
| Batch evaluation order | Evaluated motion IDs must correspond to the order used to score reference cases. |

Saved joint/root state does not restore contact-solver history. Same-domain replay remains a required physical check for arbitrary window starts. CPU contract checks alone cannot establish physical fidelity or a successful RL result.

The diagnostic overlay and patches are provided under [overlays/research/asap_diagnostics](../overlays/research/asap_diagnostics). Copy the overlay into an ASAP checkout and inspect the patches before applying them. If equivalent fixes are already installed, do not apply patches twice. The diagnostic scripts infer their root from their installed path inside ASAP; running them from this report repository is not the intended layout.

`installed_core.patch` is the complete five-file diff captured from the server for the controlled run. It applies to the inspected upstream commit and includes the timing, action lookup, saved-velocity and frozen-delta fixes. Use this **instead of** the two overlapping historical patches on a pristine checkout. Its applicability was checked with `git apply --check` against the local pristine checkout; installed CPU contracts were checked on the server.

The pilot's `verify_multi_motion.py` is a CPU check. Collection/training/evaluation commands are described in its `MULTI_MOTION.md`. Those commands reproduce the **original clip-uniform pilot**, including its sampling limitation; they are not yet the corrected data-content protocol.

`verify_contracts.py` demonstrates a patch against pristine source. On an already-patched checkout, use `verify_installed_contracts.py` to inspect the installed methods directly; do not reapply a patch for a preflight check.

The controlled first experiment is launched from the ASAP root with:

```bash
python -m research.asap_diagnostics.controlled_pipeline \
  --pilot /path/to/completed/multi_motion_pilot \
  --work-dir /path/to/new/controlled_experiment
```

It reuses the isolated mixed30 data, writes a task/group sampling manifest, runs delta validation, and queues both SquatL1 fine-tuning conditions and standalone target evaluation serially. It stops on subprocess failure and enforces the configured UTC cutoff. Existing incomplete model runs are preserved and cause an explicit stop, rather than a silent resume. Run it under a detached process supervisor for long jobs; inspect `status.json` and stage logs.

`sysid_pipeline.py` runs bounded two-parameter CMA-ES using `cma==4.4.0`, initially centered on source Kp20 with bounds [8,30], 12 candidates per generation and eight generations. `--controlled` adds held-out replay and an equal-budget Squat policy comparison; `--wait-for` serializes it after the preceding experiment's `status.json`. `torque_pipeline.py` queues the shared actuator-model comparison with the same failure/cutoff behavior. Both methods remain adaptations with the boundaries described in the methods document.

`verify_torque_contracts.py` checks CPU actuator interfaces. The torque queue first runs a small physical smoke train before its full calibration budget. CPU PASS and smoke completion must not be reported as calibration gains. `seeded_entry.py` limits CPU PyTorch threading to four by default (`ASAP_CPU_THREADS` can override it); this controls runtime contention rather than changing sample budgets.

`active_pipeline.py --controlled /path/to/controlled --sysid /path/to/sysid --work-dir /path/to/new/active --wait-for /path/to/torque/status.json` queues bounded command design, new target acquisition, matched unchanged/random/optimized refitting and an optimized-arm Squat policy comparison. `verify_active.py` checks CPU command and information contracts only. New acquisition must also pass an executed-command alignment check; actor outputs ignored during replay must never be substituted for actual acquisition commands. The active pipeline stops on infeasible controls, failed acquisition groups, subprocess failures or cutoff; it does not discard failed groups silently.

`tracking_overrides` now explicitly disables task-observation noise for all checkpoints, in addition to fixing shared termination and initialization settings. The first original-policy evaluation inherited nonzero noise absent from the fine-tuned models; it is retained as an audited historical artifact, not used as a matched baseline. `matched_evaluation.py` serializes a new standalone evaluation of all final checkpoints, without changing weights, then runs a post-hoc known-gain SysID diagnostic. The known target gains enter that diagnostic only, not fitting or active-design selection.

`extend_tasks.py` serializes CR7 and StepFBL1 fine-tuning after the true-rate wave comparison. It reuses the selected shared corrections and fitted gains; each task starts from its own recorded pretrained checkpoint and uses the same 1000-update policy budget. Incomplete runs stop explicitly. It is an extension of the same controlled test, not a cross-motion calibration holdout because all three motions contributed calibration data.

`wave_pipeline.py --controlled /path/to/controlled --torque /path/to/torque --work-dir /path/to/new/wave --wait-for /path/to/active/status.json` queues actual 200Hz target collection, alignment/rate checks, same-domain replay, and two matched torque-model/policy comparisons. `verify_wave.py` checks bounded wave support, four-step nominal holding and command-corruption detection on CPU fixtures only. The recorder's explicit `dataset_record_stride=1` preserves 200Hz replay output; the common-data pipeline retains its default stride4 and 50Hz output. `extend_tasks.py --wave /path/to/wave` also reuses the selected excitation-trained torque model on CR7 and StepFBL1.

`select_content.py` implements the fixed-parent retrospective selectors. `content_pipeline.py --controlled /path/to/controlled --pool /path/to/training/balanced_full.pkl --work-dir /path/to/new/content --wait-for /path/to/extensions/status.json` queues three 954-transition calibration/policy comparisons, with isolated checkpoint validation and common target evaluation. It reports each subset's replay floor, preserves parent identities across selectors and enforces a five-hour start margin before cutoff. The underlying dataset filename `mixed30.pkl` is reused for compatibility with the common launcher; this optional test contains 18 parents as explicitly recorded in its manifest, not 30.

For figures and trajectory animations, install `requirements-analysis.txt` in a separate analysis environment. JSON-only reporting does not require the simulator.

## Artifact policy

Keep large checkpoints, robot/motion assets, and trusted joblib datasets outside Git. Publish metrics, dataset manifests, final effective settings, source diffs, hashes, plotting scripts, and compact derived visualizations. Never commit SSH credentials or cloud access details. Load pickle/joblib artifacts only from trusted experiment sources.

## Pilot policy provenance

| Task | Recorded source checkpoint | SHA-256 |
|---|---|---|
| CR7 | `model_6000.pt` | `c13bc7a430712e1f2e2e912e88b3d6c00c31a31cc895d20cd70565688deea7f7` |
| SquatL1 | `model_6000.pt` | `b58e04d49ce2c46773af4400be83d7d6af44163f1c98ae47e0e2933c57433000` |
| StepFBL1 | `model_6000.pt` | `9e67bb692d34867d9861bdf8ff0e768a65a590f1a8cbcbe91b1051a34c0ca91b` |

These hashes were computed directly on the server files. Checkpoint filenames alone are not sufficient provenance.

`report_matched_tracking.py --input /path/to/matched/tracking_comparison.json --active /path/to/active/tracking_comparison.json` adds the completed active-arm policy to the common deployment report. The separately published feature-support audit uses training-only scaling and all 96 first-second deployment prefixes; it does not change queued selectors or checkpoint choices.

`plot_true_rate_replay.py` plots both completed acquisition arms after validating their common zero-correction baselines. `report_wave_comparison.py --unchanged /path/to/wave/unchanged` reports the completed unchanged-input policy; add `--excitation /path/to/wave/wave` only after its policy evaluation completes. Pending arms remain explicitly absent from the plot and report rather than being rendered as zero performance.
