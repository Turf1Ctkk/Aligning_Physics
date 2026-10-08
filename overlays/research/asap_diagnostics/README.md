# ASAP experiment overlay

Copy this folder into `research/asap_diagnostics` in an ASAP checkout. It contains replay checks, calibration queues, policy evaluation and recording helpers.

Use `installed_core.patch` on a pristine checkout after inspecting it. Already-patched code should be verified rather than patched again. The older patches are historical and overlap this complete patch.

The CPU verification tools check interfaces. A PASS does not run physics or validate a trained model. Each experiment queue preserves checkpoints, stops on failure and enforces its deadline.

See the report's reproduction guide for tool roles. `paper_eval_queue.py` adds fresh 27-point evaluation without changing policy weights or training. Existing calibration code remains unchanged.
