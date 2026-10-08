"""CPU checks only: bounded inputs, held base commands and audit corruption."""
import json
import numpy as np
from research.asap_diagnostics.wave_data import wave_tables, audit_record, ANKLES


def main():
    rng = np.random.RandomState(12)
    windows = {"clip%d" % i: {"dataset_task": "fixture", "dataset_group": "group%d" % i,
                "action": rng.normal(size=(54, 23)).astype(np.float32)} for i in range(3)}
    tables, metadata = wave_tables(windows)
    assert {m["type"] for m in metadata.values()} == {"sine", "square", "bounded_gaussian"}
    for key in windows:
        assert np.max(np.abs(tables[key])) <= .040001
        command = windows[key]["action"][np.arange(208)//4 + 1].copy()
        command[:, ANKLES] += tables[key][:208] / .25
        record = {"action": command, "dof": np.zeros((208, 23)), "fps": 200.,
                  "motion_times": np.arange(1, 209)/200., "terminate": np.zeros(208, bool)}
        for field in ("dof_vel", "root_trans_offset", "root_rot", "root_lin_vel", "root_ang_vel", "body_pos"):
            record[field] = record["dof"]
        assert audit_record(windows[key], record, tables[key])["command_max_absolute_error"] == 0
        record["action"][1, 0] += 1
        try:
            audit_record(windows[key], record, tables[key])
        except ValueError:
            pass
        else:
            raise AssertionError("Corrupted commands were accepted")
    print(json.dumps({"bounded_wave_types": "PASS", "four_step_base_command_holding": "PASS",
                      "command_corruption_rejection": "PASS", "scope": "CPU fixture only; no actual acquisition or physics"}))


if __name__ == "__main__":
    main()
