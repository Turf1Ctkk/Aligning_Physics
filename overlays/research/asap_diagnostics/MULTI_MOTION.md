# Multi-motion calibration

`multi_motion_pipeline.py` collects target-domain rollouts from CR7, SquatL1 and StepFBL1. It splits by original rollout before forming continuous clips and evaluation windows. Check the plan's checkpoint and motion-reference paths before starting.

`verify_multi_motion.py` validates CPU interfaces and paths. It does not collect data or train a model. Run the pipeline from an ASAP checkout, where the overlay can find the simulator and motion assets.

The original pilot samples clips uniformly. That changes task weights when the number of clips changes. `controlled_pipeline.py` uses explicit task and rollout weights for the later mixed30 experiment.

Data-selection experiments use a separate fixed-parent manifest. Do not infer the number of parents from a compatibility filename such as `mixed30.pkl`; read the manifest.
