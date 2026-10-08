# Actuator conditions at deployment

This later audit compares the first second of Squat deployment with the mixed30 calibration pool. Every trial reaches that prefix. It measures nearest-feature distance using 12 actuator features and training-only scaling.

Mean distances are 0.736 for the original policy, 0.959 for fine-tuning only, 1.351 for delta action, 1.467 for passive SysID and 1.318 for torque correction.

The policies visit different conditions. Distance alone does not explain completion: passive SysID is farther from the data than delta action, yet completes more often. This audit measures B deployment, not the states visited during calibrated-A training. It is descriptive and does not establish a failure probability or causal explanation.

[Raw measures](summary.json) include all trials. They did not change the fixed data selectors.
