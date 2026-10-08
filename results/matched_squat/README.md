# Squat policy comparison

All policies run alone in B. Evaluation shares zero used observation noise, initialization and enabled termination settings. Each adapted policy receives 1,000 further PPO updates.

| Policy | Completion (%) | First-second body error (mm) |
|---|---:|---:|
| Original | 53.1 | 95.18 |
| Fine-tuning only | 100.0 | 92.62 |
| Delta action | 90.6 | 97.14 |
| Passive SysID | 96.9 | 91.41 |
| Torque correction | 100.0 | 91.85 |
| Active SysID | 95.8 | 93.54 |

All trials reach the first second. Later errors use only trials that reach the stated horizon. This run does not establish extra control benefit from calibration over ordinary fine-tuning.

An earlier original-policy run used nonzero sensor noise. It remains historical evidence and is not used in this table. [Trials](tracking_comparison.json), [summary](summary.json) and state/config audits are retained. Position errors here use the old 24-body definition. Fresh [27-point errors](../paper_evaluation/SquatL1.md) and a separate [noise-repair comparison](../noise_repair/metrics.md) are available.
