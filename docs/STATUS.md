# Current work

Updated October 9, 2026, 12:08 Beijing time (UTC+8).

The seven-method comparisons, fresh paper metrics, source checks, and three-task noise and reset repairs are complete. Main charts use all three preset repaired delta policies. Earlier records remain available.

## Running

The new [servo-error experiment](servo_error_experiment.md) compares Random-N and Servo-coverage-N. Each group trains a fresh delta action model and then fine-tunes Step. Both use the repaired inputs and reset. A fresh FT-only policy shares the primary seed.

Selection, quotas and bin edges are frozen. The first reference-phase preflight failed because late Step windows were unavailable. A revised CPU preflight passed with shared training-candidate phase tertiles. The failed preflight is retained.

Random's same-domain training-window check is complete. Its historical 24-body position error is 21.52 mm. This is an initialization/reconstruction diagnostic, not a learned result. Random delta calibration is running. There are no new learned results yet. Servo, the paired training repeat and supplemental Low-error calibration follow serially, subject to cutoff gates. Only one heavy stage runs at a time.

All four errors and closed-loop success will be reported. Audits check actual settings, fixed checkpoints, stored starts and recomputed metrics. Missing or failed audits stop downstream work. Partial runs are not silently resumed.

## Scope

The old data-content test retains the earlier noise and reset issues. Its findings remain exploratory. New selectors are not chosen from its test ranking.

Reader-facing reports use percentages and short English. GIFs remain removed. Raw results, checkpoints and failed artifacts are preserved. Final cleanup and author-supplied visualizations follow review.

GPU cutoff: October 9 at 17:00 Beijing time. Submission deadline: October 10 at 04:59 Beijing time.
