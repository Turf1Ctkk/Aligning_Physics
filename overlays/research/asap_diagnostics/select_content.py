"""Retrospective, fixed-parent window selectors; no validation or utility labels."""
from collections import defaultdict

import numpy as np

from research.asap_diagnostics.dataset_tools import slice_motion

ANKLES = [4, 5, 10, 11]


def features(motion):
    q = np.asarray(motion["dof"])
    a = np.asarray(motion["action"])
    e = np.array([-.2, 0., -.2, 0.]) + .25*a[1:, ANKLES] - q[:-1, ANKLES]
    v = np.asarray(motion["dof_vel"])[:-1, ANKLES]
    torque = 20*e - np.array([.2, .1, .2, .1])*v
    change = .25*np.diff(a[1:, ANKLES], axis=0)
    return np.concatenate((e.mean(0), e.std(0), v.mean(0), np.sqrt((v**2).mean(0)),
                           np.sqrt((change**2).mean(0)), (np.abs(torque)<50).mean(0),
                           ((np.abs(torque)>=40)&(np.abs(torque)<50)).mean(0)))


def select(motions, groups_per_task=6, seed=7701):
    rng = np.random.RandomState(seed)
    candidates, tasks = defaultdict(list), defaultdict(set)
    for key, motion in motions.items():
        n = len(motion["dof"])
        if n < 54:
            continue
        starts = sorted(set(list(range(0, n-53, 54)) + [n-54]))
        for start in starts:
            window = slice_motion(motion, start, start+54)
            vector = features(window)
            if not np.isfinite(vector).all():
                raise ValueError("Non-finite selection features")
            row = {"source_clip": key, "start": start, "stop": start+54,
                   "task": motion["dataset_task"], "group": motion["dataset_group"],
                   "rom": float(np.ptp(window["dof"][:, ANKLES], axis=0).mean()),
                   "features": vector, "motion": window}
            candidates[row["group"]].append(row)
            tasks[row["task"]].add(row["group"])
    matrix = np.stack([row["features"] for rows in candidates.values() for row in rows])
    center = np.median(matrix, axis=0)
    scale = np.percentile(matrix, 75, axis=0)-np.percentile(matrix, 25, axis=0)
    scale[scale<1e-6] = 1.
    selected_groups = {}
    for task in sorted(tasks):
        groups = sorted(tasks[task])
        if len(groups) < groups_per_task:
            raise ValueError("Too few eligible parent groups for " + task)
        selected_groups[task] = rng.choice(groups, groups_per_task, replace=False).tolist()
    # Alternate tasks in a fixed seeded group order; every selector uses exactly
    # the same groups and one window per group, avoiding a group-mixture confound.
    order = [selected_groups[task][index] for index in range(groups_per_task) for task in sorted(tasks)]
    outputs, manifest = {}, {}
    for method in ("uniform", "coverage", "joint_range"):
        chosen = []
        data, rows = {}, []
        for group in order:
            options = candidates[group]
            normalized = np.stack([(row["features"]-center)/scale for row in options])
            if method == "uniform":
                index = int(rng.randint(len(options)))
            elif method == "joint_range":
                index = int(np.argmax([row["rom"] for row in options]))
            elif not chosen:
                index = int(np.argmin(np.linalg.norm(normalized, axis=1)))
            else:
                distance = np.linalg.norm(normalized[:, None]-np.stack(chosen)[None], axis=-1)
                index = int(np.argmax(distance.min(1)))
            row = options[index]
            chosen.append(normalized[index])
            data[group] = row["motion"]
            rows.append({k: row[k] for k in ("source_clip", "start", "stop", "task", "group", "rom")})
            rows[-1]["features"] = row["features"].tolist()
        outputs[method], manifest[method] = data, rows
    if any(set(data) != set(outputs["uniform"]) for data in outputs.values()):
        raise AssertionError("Parent-group identities differ across methods")
    return outputs, {"selectors": manifest, "seed": seed, "frames_per_window": 54,
        "unique_transitions_per_method": len(order)*53, "parent_groups_per_method": len(order),
        "inventory_candidate_windows": len(matrix), "inventory_unique_transitions": sum(len(m["dof"])-1 for m in motions.values()),
        "scaling": {"median": center.tolist(), "iqr": scale.tolist()},
        "feature_order": "Four joints each: servo-error mean/std, velocity mean/RMS, command-change RMS, unsaturated fraction, near-clipping fraction",
        "scope": "Retrospective selected-training-data budget; full pool acquisition/inspection is not reduced; candidate windows can overlap but only one is trained per parent"}
