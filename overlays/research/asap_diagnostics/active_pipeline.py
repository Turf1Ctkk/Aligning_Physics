"""Serialized G1 active-SysID adaptation: design, new acquisition, refit, deploy."""
import argparse
from datetime import datetime
import fcntl
import json
from pathlib import Path
import sys
import time

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research.asap_diagnostics.active_design import (
    decode_design, excite, finite_difference_gains, group_windows,
    information_score, valid_trajectory,
)
from research.asap_diagnostics.controlled_pipeline import launch, write, fine_overrides, tracking_overrides
from research.asap_diagnostics.controlled_sampling import hierarchical_weights
from research.asap_diagnostics.dataset_tools import slice_motion
from research.asap_diagnostics.sysid_pipeline import evaluate_candidates


def replay(work, inputs, gains, checkpoint, label, deadline, acquire=False):
    directory = work / label
    directory.mkdir(parents=True, exist_ok=True)
    dataset = directory / "inputs.pkl"
    manifest = directory / "gains.json"
    joblib.dump(inputs, dataset)
    write(manifest, gains)
    output = directory / "replay.pkl"
    overrides = [
        "+checkpoint=" + str(checkpoint), "+headless=True", "+num_envs=" + str(len(inputs)), "+opt=record",
        "+domain_rand=NO_domain_rand", "++seed=7201",
        "++env._target_=research.asap_diagnostics." + ("active_runtime.NominalGainReplay" if acquire else "sysid_runtime.CandidateGainReplay"),
        "++algo._target_=research.asap_diagnostics." + ("active_runtime.NominalRecorderPPO" if acquire else "dataset_runtime.RolloutRecorderPPO"),
        "++env.config.sysid_manifest=" + str(manifest),
        "++robot.motion.motion_file=" + str(dataset), "++robot.motion.use_recorded_velocities=True",
        "++robot.asset.self_collisions=0", "++env.config.noise_to_initial_level=0",
        "++env.config.dataset_evaluation=True", "++env.config.enforce_randomize_motion_start_eval=False",
        "++env.config.resample_motion_when_training=False", "++env.config.save_motion=False",
        # Keep the 52 post-step samples (through 1.04s) before timeout. This
        # does not change the one-second information/held-out scoring horizon.
        "++env.config.max_episode_length_s=1.1",
        "++env.config.dataset_record_path=" + str(output), "++env.config.dataset_record_steps=52",
        "++eval_log_dir=" + str(directory / "effective_config"),
    ]
    launch(work, "eval", 7201, overrides, label, deadline)
    return joblib.load(output)


def evaluate_designs(work, windows, weights, units, center, checkpoint, label, deadline):
    inputs, gains = {}, {}
    perturbations = finite_difference_gains(center)
    for candidate, unit in enumerate(units):
        commands = excite(windows, decode_design(unit))
        for shift, theta in enumerate(perturbations):
            for key, motion in commands.items():
                unique = "d%03d_p%d__%s" % (candidate, shift, key)
                inputs[unique] = motion
                gains[unique] = theta.tolist()
    predictions = replay(work, inputs, gains, checkpoint, label, deadline)
    size = 4 * len(windows)
    scores = []
    for candidate in range(len(units)):
        subset = {"motion%d" % i: predictions["motion%d" % (candidate * size + i)] for i in range(size)}
        scores.append(information_score(subset, list(windows), weights))
    write(work / label / "information.json", scores)
    return scores


def fit_new_data(work, data, checkpoint, label, generations, deadline):
    import cma
    weights = hierarchical_weights(data)
    optimizer = cma.CMAEvolutionStrategy([20., 20.], 2.,
        {"bounds": [8., 30.], "popsize": 12, "seed": 7301, "verbose": -9})
    history = []
    for generation in range(generations):
        candidates = optimizer.ask()
        scores = evaluate_candidates(work, data, weights, candidates, checkpoint,
                                      label + "_fit%02d" % generation, deadline)
        values = [row["objective"] for row in scores]
        optimizer.tell(candidates, values)
        history.append({"generation": generation, "gains": [list(map(float, c)) for c in candidates],
                        "objective": values, "mean": optimizer.mean.tolist()})
        write(work / (label + "_fit_history.json"), history)
    result = {"gains": optimizer.result.xbest.tolist(), "objective": float(optimizer.result.fbest),
              "evaluations": int(optimizer.result.evaluations)}
    write(work / (label + "_identified.json"), result)
    return result


def run(args):
    import cma
    from research.asap_diagnostics.torque_pipeline import overrides
    from research.asap_diagnostics.multi_motion_pipeline import aggregate_cases
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    lock = (work / "run.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    if (work / "protocol.json").exists():
        raise RuntimeError("Active run already exists; inspect it instead of silently restarting")
    write(work / "status.json", {"status": "waiting", "stage": "preceding_comparison"})
    while args.wait_for:
        state = json.loads(args.wait_for.read_text()) if args.wait_for.exists() else {}
        if state.get("status") == "complete":
            break
        if state.get("status") == "failed":
            raise RuntimeError("Preceding queue failed; inspect before active collection")
        if time.time() > deadline - 60:
            raise TimeoutError("Cutoff while waiting for preceding queue")
        time.sleep(30)
    plan = json.loads((args.controlled / "plan.json").read_text())
    selected = json.loads((args.controlled / "delta_selection.json").read_text())["checkpoint"]
    identified = json.loads((args.sysid / "identified.json").read_text())
    center = [identified["ankle_pitch_Kp"], identified["ankle_roll_Kp"]]
    windows = group_windows(joblib.load(args.controlled / "datasets/mixed30.pkl"))
    weights = hierarchical_weights(windows)
    write(work / "protocol.json", {
        "method": "G1 bounded-command active SysID adaptation; not the original Go2 command interface",
        "initial_estimate": center, "training_groups": len(windows), "window_input_frames": 54,
        "collection": "52 actual post-step frames per group and arm; fixed original commands plus ankle sinusoidal excitation",
        "arms": ["zero", "random", "active"], "target_gain_setting": "Kp16, collection only; never supplied to design or fitting",
        "design": "Four normalized variables: pitch/roll amplitude <= .08 rad and frequencies .5-3 Hz; opposite legs have pi phase",
        "information": "Task/group-weighted ankle-position trajectory Fisher approximation; gain differences +/-.5; assumed noise .005 rad; ridge .001",
        "constraints": "One-second simulator trajectories complete, root height >= .35 m, projected gravity |x,y| <= .8; no hardware safety claim",
        "budget": {"design_population": 8, "design_generations": args.design_generations,
                   "refit_population": 12, "refit_generations_per_arm": args.fit_generations},
        "data_isolation": "New acquisitions originate only from mixed30 training groups; validation/test recording groups unchanged",
        "policy_selection": "Fixed final update; one training seed; three deployment seeds",
    })
    # Baseline and random designs also undergo estimated-model feasibility checks.
    random = np.random.RandomState(7201).uniform(.1, .9, 4).tolist()
    zero = [0., 0., .5, .5]
    initial = evaluate_designs(work, windows, weights, [zero, random], center, selected, "design_controls", deadline)
    if not all(row["feasible"] for row in initial):
        raise RuntimeError("A predeclared control design is infeasible; preserve diagnostics and revise explicitly")
    optimizer = cma.CMAEvolutionStrategy([.5] * 4, .22,
        {"bounds": [0., 1.], "popsize": 8, "seed": 7201, "verbose": -9})
    best_unit, best_score = zero, initial[0]["objective"]
    history = []
    for generation in range(args.design_generations):
        candidates = optimizer.ask()
        scores = evaluate_designs(work, windows, weights, candidates, center, selected,
                                 "design%02d" % generation, deadline)
        values = [row["objective"] for row in scores]
        optimizer.tell(candidates, values)
        for candidate, row in zip(candidates, scores):
            if row["feasible"] and row["objective"] < best_score:
                best_unit, best_score = candidate.tolist(), row["objective"]
        history.append({"generation": generation, "units": [list(map(float, c)) for c in candidates], "scores": scores})
        write(work / "design_history.json", history)
    designs = {"zero": decode_design(zero), "random": decode_design(random), "active": decode_design(best_unit)}
    write(work / "selected_designs.json", {"designs": designs, "active_information_objective": best_score,
                                           "zero_information_objective": initial[0]["objective"]})
    inputs, gains, provenance = {}, {}, []
    for label, design in designs.items():
        for key, motion in excite(windows, design).items():
            unique = label + "__" + key
            inputs[unique], gains[unique] = motion, [16., 16.]
            provenance.append({"key": unique, "arm": label, "source_key": key,
                               "task": motion["dataset_task"], "group": motion["dataset_group"]})
    acquired = replay(work, inputs, gains, selected, "new_target_acquisition", deadline, acquire=True)
    arms = {label: {} for label in designs}
    audit = []
    for index, row in enumerate(provenance):
        prediction = acquired["motion%d" % index]
        if not valid_trajectory(prediction):
            raise RuntimeError("Actual target acquisition violates the declared feasibility constraints")
        # Recenter its time axis without discarding any newly measured frames.
        prediction = slice_motion(prediction, 0, len(prediction["dof"])) if not np.asarray(prediction["terminate"]).any() else prediction
        if len(prediction["dof"]) != 52 or np.asarray(prediction["terminate"]).any():
            raise RuntimeError("New collection terminated; do not silently discard failed acquisition groups")
        # The initial warm step uses input action[1]; each subsequent action uses
        # the next saved command. This check detects actor-output recording bugs.
        recorded = np.asarray(prediction["action"])
        expected = np.asarray(inputs[row["key"]]["action"])[1:53]
        error = float(np.max(np.abs(recorded - expected)))
        if error > 2e-5:
            raise RuntimeError("Acquisition command alignment failed: max error %g" % error)
        prediction.update(dataset_task=row["task"], dataset_group=row["group"], acquisition_arm=row["arm"])
        arms[row["arm"]][row["source_key"]] = prediction
        audit.append(dict(row, frames=52, command_max_error=error))
    write(work / "acquisition_audit.json", audit)
    fits = {}
    for label, data in arms.items():
        joblib.dump(data, work / (label + "_acquired.pkl"))
        fits[label] = fit_new_data(work, data, selected, label, args.fit_generations, deadline)
    write(work / "identified_comparison.json", fits)
    heldout = {}
    for label, fitted in fits.items():
        heldout[label] = {}
        for split in ("val", "test"):
            references = joblib.load(args.controlled / "datasets" / (split + "_cases.pkl"))
            scores = evaluate_candidates(work, references, hierarchical_weights(references), [fitted["gains"]],
                                          selected, label + "_" + split, deadline)[0]
            rows = [{"task": references[row["key"]]["dataset_task"], "group": references[row["key"]]["dataset_group"],
                     "metrics": {"1.0": row["full"]}} for row in scores["cases"]]
            heldout[label][split] = aggregate_cases(rows, 1.)
    write(work / "replay_comparison.json", heldout)
    ft = overrides(fine_overrides(work, plan, selected, "active_sysid_ft", "SquatL1", args.iterations), [
        "++algo._target_=research.asap_diagnostics.torque_runtime.FreshTaskPPO",
        "++env._target_=humanoidverse.envs.motion_tracking.motion_tracking.LeggedRobotMotionTracking",
        "env.config.add_extra_action=False", "++obs.obs_dict.closed_loop_actor_obs=[ref_motion_phase]",
        "robot.control.stiffness.ankle_pitch=" + str(fits["active"]["gains"][0]),
        "robot.control.stiffness.ankle_roll=" + str(fits["active"]["gains"][1]),
    ])
    launch(work, "train", plan["training_seed"] + 1000, ft, "train_active_sysid_ft", deadline)
    final = work / "models/active_sysid_ft" / ("model_%d.pt" % args.iterations)
    tracking = {}
    for seed in (8101, 8102, 8103):
        label = "active_sysid_ft_seed%d" % seed
        launch(work, "eval", seed, tracking_overrides(work, final, label, "SquatL1", plan, .2, seed), label, deadline)
        tracking[label] = json.loads((work / "tracking" / (label + ".json")).read_text())
    write(work / "tracking_comparison.json", {"results": tracking, "training_seeds": 1})
    write(work / "status.json", {"status": "complete", "stage": "G1_active_acquisition_refit_and_policy_comparison"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--controlled", type=Path, required=True)
    parser.add_argument("--sysid", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--wait-for", type=Path)
    parser.add_argument("--design-generations", type=int, default=6)
    parser.add_argument("--fit-generations", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--cutoff", default="2026-10-09T09:00:00+00:00")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        write(args.work_dir / "status.json", {"status": "failed", "error": str(error)})
        raise
