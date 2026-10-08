# Controlled delta-action experiment

The calibration dataset contains ten target rollouts per task. Sampling gives equal weight to tasks and original rollouts. Delta training uses one-second episodes and 1,000 PPO updates. Validation selects update 500.

Held-out body position error changes from 37.66 to 30.51 mm. Ankle RMSE changes from 0.07500 to 0.06131 rad. Joint-velocity RMSE rises from 0.87892 to 0.89057 rad/s. Every test window reaches one second.

The correction improves position replay, but not every metric. It is frozen during policy fine-tuning and removed at B deployment. The matched policy results are in [the Squat comparison](../matched_squat/README.md).

These are historical 24-body metrics. [Raw evidence](.) includes the selection, replay summaries and settings.
