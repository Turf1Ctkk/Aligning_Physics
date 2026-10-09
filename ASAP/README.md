# ASAP source used in this study

Source snapshot of [ASAP / Humanoidverse](https://github.com/LeCAR-Lab/ASAP), based on commit `df5320cc47dd8cad97961bdfabfe402dd62ad999`. The upstream MIT license is preserved in `LICENSE`.

`humanoidverse/` contains the original training framework with the five installed experiment patches. `research/asap_diagnostics/` contains calibration, data-selection, reset and evaluation implementations. `experiment_configs/` contains representative saved settings from completed runs. `source_manifest.yaml` records the installed source hashes.

The G1 IsaacGym assets and the three study reference motions are included. Unrelated model weights, raw motion collections, upstream media and experiment queues are omitted. Other simulator backends remain upstream code; this study does not claim to have run them.
