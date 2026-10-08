# Analytic replay diagnostic

`analytic_replay.py` uses the known target gain ratio to test action units and update timing. It is deliberately privileged and is not a learned baseline.

The diagnostic can apply compensation at the 50 Hz control rate or the 200 Hz physics rate. Matching torque at one state does not ensure matching torque throughout a held command.

This environment is opt-in. Training and ordinary target-policy evaluations do not use it. Do not use the known ratio as calibration labels. The report retains the original single-record results and configuration audit.
