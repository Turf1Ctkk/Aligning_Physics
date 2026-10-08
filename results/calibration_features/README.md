# Features in the calibration pool

This audit describes training data before selection. It uses 90 original rollouts, 128 continuous clips and 18,775 transitions. It measures ankle command error, velocity, command changes and modeled torque-limit activity.

The tasks have different actuator conditions. Motion names and joint range alone do not describe these differences. This provides a reason to test actuator features, but does not prove that a feature improves model learning.

The audit uses training data only. [Summary](summary.json) records the features and source hashes. The selector uses a fixed training-only scaler. No feature rule was changed after test results.
