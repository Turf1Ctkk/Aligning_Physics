# A short guide to this research repository

The repository has three layers: a research proposal, measured experiments, and the code/evidence needed to inspect those experiments. Most JSON files are supporting records or audits within an experiment, not separate research studies.

## Suggested reading order

1. [Main README](../README.md): question, motivation, hypothesis and current observations.
2. [Research argument](research_argument.md): why actuator range alone may be insufficient, why replay and policy control are different outcomes, and what would falsify the hypothesis.
3. [Three-task comparison](../results/task_extensions/README.md): completed Squat, CR7 and Step results, including both positive and negative outcomes.
4. [Fixed-budget data-content study](../results/content_selection/README.md): the direct uniform/actuator-coverage/joint-range experiment and its current completion state.

The methods and raw files can be read afterward when checking a particular claim.

## What each experiment contributes

| Evidence | Purpose | Where to read |
|---|---|---|
| Interface and known-gain controls | Establish whether recorded actions, initialization and update rates are interpreted correctly; known-gain compensation is a diagnostic, not learning evidence. | [Reproduction](reproduction.md), [rate diagnostic](../results/control_rate_diagnostic/README.md) |
| Initial3/30/90-group pilot | Explore data amount; task weighting and replay-floor differences limit scaling conclusions. | [Pilot](../results/pilot_multimotion/README.md) |
| Weighted mixed30 action calibration | Verify the recorded-rollout→delta→frozen-correction task-training pipeline. | [Controlled run](../results/controlled_squat/README.md) |
| Passive/active SysID and torque correction | Test other correction mechanisms in G1, with explicit differences from SPI-Active/UAN. | [Methods](methods.md), [passive](../results/passive_sysid/README.md), [active](../results/active_acquisition/README.md), [torque](../results/torque_adaptation/README.md) |
| Matched three-task deployment | Ask whether calibration adds benefit over equal-budget continued policy training. | [Squat](../results/matched_squat/README.md), [CR7](../results/task_extensions/CR7/README.md), [Step](../results/task_extensions/StepFBL1/README.md) |
| Genuine200Hz unchanged/excitation collection | Compare two acquisition inputs under matched data amounts and model/training budgets. | [Paired acquisition](../results/wave_acquisition/README.md) |
| Fixed-budget subset selection | Directly test uniform, actuator-feature coverage and joint-range window selection. | [Content study](../results/content_selection/README.md) |
| Feature audits | Describe calibration regimes and deployment support changes; they do not identify causes of control failure. | [Calibration features](../results/calibration_features/README.md), [deployment features](../results/policy_regimes/README.md) |

## Files and terminology

- `docs/`: argument, methods, fixed protocol, reproduction notes and current status.
- `results/`: readable experiment summaries, measured per-trial reports, checkpoint choices and audits. Start with each directory's README; JSON supports the displayed claims.
- `assets/`: plots and actual recorded rigid-body animations. Skeleton animations are derived from simulator trajectories, not camera renders; fixed trials illustrate behavior without representing aggregate success rates.
- `overlays/`: research extensions and patches to upstream ASAP, rather than a complete standalone ASAP checkout.
- `scripts/`: aggregation, plotting, animation and artifact audits. CPU contract checks do not establish physics or training success.

Calibration rollouts are actual target-system responses to commands. Human reference motions define the tracking task. Replay fixes nominal recorded inputs while allowing a state-conditioned correction. Downstream evaluation uses the adapted policy's own actions in B without learned correction hooks.

The current evidence is controlled IsaacGym sim-to-sim, not hardware validation. All three motions were used in calibration, so task reuse is not motion holdout. Most comparisons have one training seed per method;96 deployment trials are not96 trained policies. Full-motion error averages over completed trials retain their success counts. Full checkpoints and large rollout files remain on the server; the repository contains the proposal, measured evidence and reproduction overlay.
