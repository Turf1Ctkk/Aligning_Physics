# Original multi-motion replay pilot

These files are measured server outputs supplied before the new controlled downstream experiment. They are preserved as historical evidence and are not replaced by proposed results.

| File | Content |
|---|---|
| [comparison.json](comparison.json) | Validation and held-out test summaries at 0.25/0.5/1 second. |
| [dataset_summary.json](dataset_summary.json) | Dataset counts, selected training groups, and valid-window counts. |
| [dataset_audit.json](dataset_audit.json) | Segmentation, reset rows, rejected short segments, and duplicate audit. |

The pilot used three `model_6000.pt` source policies. The 3/30/90-group subsets contain 5/41/128 continuous clips and 634/6198/18775 transitions. The test has 15 original recording groups, producing 66 correlated windows. All evaluated test cases completed the one-second replay horizon.

Validation selected delta checkpoints at iterations 500, 1000, and 1000 for the three subset sizes. The test averages give global body MPJPE 29.327/27.431/28.403 mm versus 35.991 mm without calibration. These are **replay errors**, not errors of a fine-tuned task policy in the target domain.

## Limits retained in the report

- One independent training seed.
- All three motion classes appear in calibration; held-out trajectories are not held-out motion classes.
- Uniform clip sampling gives unequal task and parent-recording weights after reset segmentation. Changing subset size also changes task mixture.
- Same-domain CR7 replay error is 24.737 mm. This needs a case-level initialization/configuration audit; it cannot simply be subtracted from cross-domain error.
- Joint-velocity errors regress despite position improvements.

Use [the plotting script](../../scripts/plot_pilot.py) to regenerate the figure directly from these summaries. Large trusted joblib rollouts and checkpoints remain outside Git; their omission does not mean this repository contains a complete stand-alone training environment.
