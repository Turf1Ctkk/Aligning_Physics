# Passive gain identification

CMA-ES fits ankle pitch and roll gains from recorded inputs and target responses. It uses 96 candidates in total. The estimated gains are 13.01 and 10.42; the configured target gains are both 16.

Held-out body replay error is 30.87 mm and joint-velocity RMSE is 0.80029 rad/s. The Squat policy completes 96.9% of evaluations. These results show useful trajectory fitting, but do not show physical parameter recovery.

A later check finds that the fitting loss is lower at the estimate than at the known gains. The loss is 0.270 at the estimate, 0.489 at the known gains and 1.116 at the source gains. Limited search alone therefore cannot explain the non-recovery. The exact cause is unresolved.

[Replay data](replay_comparison.json) and [other evidence](.) preserve the diagnostics. This passive search is not the full SPI-Active method.
