"""Matched true-200Hz acquisition: unchanged targets versus wave/noise excitation."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research.asap_diagnostics.active_design import group_windows, valid_trajectory
from research.asap_diagnostics.controlled_pipeline import launch, write
from research.asap_diagnostics.controlled_sampling import hierarchical_weights
from research.asap_diagnostics.dataset_tools import slice_motion
from research.asap_diagnostics.wave_data import wave_tables, audit_record, actuator_features


def acquisition_replay_check(work, arms, checkpoint, deadline):
    from research.asap_diagnostics.dataset_tools import replay_metrics
    from research.asap_diagnostics.multi_motion_pipeline import aggregate_cases
    references = {arm + "__" + key: motion for arm, data in arms.items() for key, motion in data.items()}
    joblib.dump(references, work / "acquisition_references.pkl")
    write(work / "acquisition_sampling.json", {"weights": hierarchical_weights(references),
        "metadata": {key: {"task": m["dataset_task"], "group": m["dataset_group"]} for key, m in references.items()}})
    results = {}
    for label, kp in (("same16", 16), ("source20", 20)):
        raw = work / (label + "_true200_replay.pkl")
        launch(work, "eval", 7602, [
            "+checkpoint=" + str(checkpoint), "+headless=True", "+num_envs=60", "+opt=record",
            "+domain_rand=NO_domain_rand", "++seed=7602",
            "++env._target_=research.asap_diagnostics.torque_runtime.TorqueReplay",
            "++algo._target_=research.asap_diagnostics.torque_runtime.TorqueReplayRecorder",
            "++env.config.sampling_manifest=" + str(work / "acquisition_sampling.json"),
            "++robot.motion.motion_file=" + str(work / "acquisition_references.pkl"), "++robot.motion.use_recorded_velocities=True",
            "++robot.control.stiffness.ankle_pitch=" + str(kp), "++robot.control.stiffness.ankle_roll=" + str(kp),
            "++env.config.zero_delta_a=True", "++env.config.dataset_evaluation=True",
            "++env.config.noise_to_initial_level=0", "++env.config.enforce_randomize_motion_start_eval=False",
            "++env.config.resample_motion_when_training=False", "++env.config.save_motion=False",
            "++env.config.dataset_record_stride=1", "++env.config.dataset_record_steps=200",
            "++env.config.max_episode_length_s=1.1", "++env.config.dataset_record_path=" + str(raw),
            "++eval_log_dir=" + str(work / (label + "_true200_config")),
        ], label + "_true200_replay", deadline)
        predictions = joblib.load(raw)
        rows = []
        for index, (key, ref) in enumerate(references.items()):
            metric = replay_metrics(ref, predictions["motion%d" % index], 1.)
            if not metric["complete"]:
                raise RuntimeError("True200Hz acquisition replay did not complete")
            rows.append({"key": key, "arm": ref["acquisition_arm"], "task": ref["dataset_task"],
                         "group": ref["dataset_group"], "metrics": {"1.0": metric}})
        results[label] = {arm: aggregate_cases([r for r in rows if r["arm"] == arm], 1.) for arm in arms}
    write(work / "acquisition_replay_check.json", results)


def run(args):
    from research.asap_diagnostics.torque_pipeline import run as train_and_compare
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if (work / "protocol.json").exists():
        raise RuntimeError("Existing wave experiment; inspect rather than silently restarting")
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    write(work / "status.json", {"status": "waiting", "stage": "preceding_active_comparison"})
    while True:
        state = json.loads(args.wait_for.read_text()) if args.wait_for.exists() else {}
        if state.get("status") == "complete":
            break
        if state.get("status") == "failed":
            raise RuntimeError("Preceding stage failed; inspect before wave acquisition")
        if time.time() > deadline - 60:
            raise TimeoutError("Cutoff before wave experiment")
        time.sleep(30)
    plan = json.loads((args.controlled / "plan.json").read_text())
    checkpoint = json.loads((args.controlled / "delta_selection.json").read_text())["checkpoint"]
    windows = group_windows(joblib.load(args.controlled / "datasets/mixed30.pkl"), earliest=True)
    tables, metadata = wave_tables(windows)
    write(work / "protocol.json", {"method": "G1 UAN-style true-rate excitation adaptation; not original robot/interface reproduction",
        "arms": ["unchanged", "wave"], "groups_per_arm": 30, "target_states_per_group": 208,
        "unique_transitions_per_arm": 6210, "measured_state_rate_hz": 200,
        "window_selection": "First54 states of every group's first eligible continuous segment; same rule in both arms",
        "base_commands": "Fixed recorded 50Hz nominal targets held for four physics steps, not feedback policy execution",
        "excitation": "200Hz additive position offsets; sine/square/clipped Gaussian; +/- .04rad; frequencies1-3Hz; seed7601",
        "history": "20 genuine source simulation states; target data measured every5ms, no synthetic upsampling",
        "matching": "Same training-group initial states, unique transitions, shared torque architecture and1000-update optimization budget in both arms",
        "evaluation": "Unchanged held-out50Hz task records; same original Squat policy1000-update fine-tuning and standalone common-noise B evaluation",
        "limitations": "Different data duration from full mixed30; target-excitation interface differs from UAN; one training seed; does not isolate model representation against ASAP"})
    write(work / "excitation_manifest.json", metadata)
    inputs, gains, commands, provenance = {}, {}, {}, []
    for arm in ("unchanged", "wave"):
        for key, motion in windows.items():
            unique = arm + "__" + key
            inputs[unique], gains[unique] = motion, [16., 16.]
            commands[unique] = np.zeros_like(tables[key]) if arm == "unchanged" else tables[key]
            provenance.append({"arm": arm, "key": key, "unique_key": unique})
    joblib.dump(inputs, work / "acquisition_inputs.pkl")
    joblib.dump(commands, work / "wave_tables.pkl")
    write(work / "gains.json", gains)
    raw = work / "acquisition.pkl"
    launch(work, "eval", 7601, [
        "+checkpoint=" + str(checkpoint), "+headless=True", "+num_envs=60", "+opt=record",
        "+domain_rand=NO_domain_rand", "++seed=7601",
        "++env._target_=research.asap_diagnostics.wave_runtime.WaveGainReplay",
        "++algo._target_=research.asap_diagnostics.active_runtime.NominalRecorderPPO",
        "++env.config.sysid_manifest=" + str(work / "gains.json"),
        "++env.config.wave_tables=" + str(work / "wave_tables.pkl"),
        "++simulator.config.sim.control_decimation=1", "++env.config.max_episode_length_s=1.1",
        "++robot.motion.motion_file=" + str(work / "acquisition_inputs.pkl"), "++robot.motion.use_recorded_velocities=True",
        "++robot.asset.self_collisions=0", "++env.config.noise_to_initial_level=0",
        "++env.config.dataset_evaluation=True", "++env.config.enforce_randomize_motion_start_eval=False",
        "++env.config.resample_motion_when_training=False", "++env.config.save_motion=False",
        "++env.config.dataset_record_path=" + str(raw), "++env.config.dataset_record_steps=208",
        "++eval_log_dir=" + str(work / "acquisition_config"),
    ], "true200_target_acquisition", deadline)
    records = joblib.load(raw)
    arms, audit = {"unchanged": {}, "wave": {}}, []
    for index, row in enumerate(provenance):
        record = records["motion%d" % index]
        measured = audit_record(inputs[row["unique_key"]], record, commands[row["unique_key"]])
        if not valid_trajectory(record):
            raise RuntimeError("Target acquisition violates declared1s feasibility; preserve every group")
        measured.update(row)
        measured["actuator_features"] = actuator_features(record)
        audit.append(measured)
        record = slice_motion(record, 0, 208)
        record.update(dataset_task=windows[row["key"]]["dataset_task"],
                      dataset_group=windows[row["key"]]["dataset_group"], acquisition_arm=row["arm"])
        arms[row["arm"]][row["key"]] = record
    write(work / "acquisition_audit.json", audit)
    torque_model = json.loads((args.torque / "torque_selection.json").read_text())["checkpoint"]
    acquisition_replay_check(work, arms, torque_model, deadline)
    for arm, data in arms.items():
        prepared = work / ("prepared_" + arm)
        (prepared / "datasets").mkdir(parents=True, exist_ok=True)
        joblib.dump(data, prepared / "datasets/mixed30.pkl")
        for split in ("val", "test"):
            shutil.copy2(args.controlled / "datasets" / (split + "_cases.pkl"), prepared / "datasets" / (split + "_cases.pkl"))
        write(prepared / "plan.json", plan)
        write(prepared / "sampling_manifest.json", {"weights": hierarchical_weights(data),
            "metadata": {key: {"task": m["dataset_task"], "group": m["dataset_group"]} for key, m in data.items()}})
        write(work / "status.json", {"status": "running", "stage": arm + "_torque_training_and_policy_comparison"})
        train_and_compare(SimpleNamespace(controlled=prepared, work_dir=work / arm, wait_for=None,
            iterations=args.iterations, cutoff=args.cutoff,
            target_data_description="New " + arm + " G1 target trajectories measured every5ms,30 training groups,6210 unique transitions",
            limitations_description="True200Hz target training states; held-out policy recordings remain50Hz; history zero at reset; bounded excitation added to prerecorded targets, not original UAN collection interface"))
    write(work / "status.json", {"status": "complete", "stage": "matched_true_rate_excitation_comparison"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("controlled", "torque", "work-dir", "wait-for"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--cutoff", default="2026-10-09T09:00:00+00:00")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        write(args.work_dir / "status.json", {"status": "failed", "error": str(error)})
        raise
