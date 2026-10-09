# Current work

Updated October 9, 2026, 15:44 Beijing time (UTC+8).

The seven-method comparisons, paper metrics, source checks, and three-task noise/reset repairs are complete. Main charts use the preset repaired policies. Earlier results remain available.

## Servo-error study

The primary run is complete and audited. Random-N and Servo-coverage-N both have 0% Step success. Matched FT-only reaches 5.2% and has lower first-second error on all four measures. FT-only itself is weak; the cause is not isolated. [Errors and audits](../results/servo_error_selection/metrics.md).

Second-seed Random is also complete and audited. Success is 20.8%, completion is 21.9%, and mean survival is 2.75 seconds. First-second global and relative errors are 83.23 and 46.83 mm. Acceleration is 1.869 mm/frame²; root velocity is 4.638 mm/frame. All trials reach one second. These four errors are lower than in the primary Random run.

The runs use identical selected data. Calibration and policy training seeds change together; replay and deployment seeds stay fixed. The repeat has no matched FT-only. Both outcomes are retained, without selecting a better seed.

Second-seed Servo calibration began at 15:40 Beijing and is the only GPU stage. Its learned and control results remain pending. Low-error calibration runs only if its preset time gate permits. No windows or settings change after outcomes.

## Scope and deadlines

All completed settings, hashes, stored starts and metrics pass independent audits. Known log limits and reconstruction floors remain disclosed. No floor is subtracted, and terminations are not automatically classified as falls.

The old subset study retains earlier noise/reset defects and remains exploratory. No new GIFs, hardware claims or unseen-motion claims are added. Raw science, checkpoints and failures are preserved; final cleanup and author visualizations follow review.

GPU cutoff: October 9 at 17:00 Beijing. Submission deadline: October 10 at 04:59 Beijing.
