# Delta reset check

The closed-loop training environment retained the previous episode's delta action after a reset. Calibration cleared the corresponding input. This gave the frozen model an inconsistent input at the start of an episode.

Two short StepFBL1 physics probes used the source policy and frozen delta. Each used 64 environments and 320 steps. The probes made no optimizer updates and produced no new policy checkpoint. Both used zero height and foot-force noise.

Within each reset state, the audit computed two delta outputs. They used the same observation and current nominal action. Only the previous-delta input changed to zero.

| Training environment | Maximum retained delta (action units) | Maximum ankle output difference (action units) |
|---|---:|---:|
| Installed reset path | 2.552 | 0.571 |
| Opt-in reset repair | 0.000 | 0.000 |

The largest output difference corresponds to about 0.143 rad of joint-target offset at the action scale of 0.25. This is an input effect at a reset state. It does not measure subsequent tracking success.

The repair clears the delta only for environments that reset. It passed selective and empty-reset CPU checks, then the physical check above. The core environment files were not changed. Saved configs differ only in the environment class and output paths. Raw events, commands and configs are retained here.

The two rollout paths diverge after resets. Their reset counts are not a paired success-rate test. The author approved a separate three-task reset-only training comparison. No new tracking result is available yet, so the existing main comparison remains unchanged. This reset issue concerns delta action; it does not explain the SysID or torque results.
