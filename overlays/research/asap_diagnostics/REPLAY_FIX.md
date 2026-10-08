# Replay checks

The recorder saves post-step states. Action row i produced state row i, so the next transition from state i uses action i+1. Lookup rounds to the nearest valid frame to avoid floating-point boundary errors.

Replay initialization restores saved joint and root velocities. Pose-derived velocities can differ substantially from the recorded values. Contact-solver history is not restored, so same-domain physics replay is still necessary.

`run_replay_fix.sh inputs` checks data and CPU contracts. `run_replay_fix.sh replay` runs same-domain and mismatched-domain physics controls. Keep their outputs separate: CPU correctness is not trajectory fidelity.

Use `verify_installed_contracts.py` on patched code. Do not reapply historical patches just to run a check.
