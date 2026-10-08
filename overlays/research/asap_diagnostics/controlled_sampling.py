"""Task/group/clip weights, independent of simulator and tensor libraries."""
from collections import Counter, defaultdict


def hierarchical_weights(motions):
    if not motions:
        raise ValueError("Empty calibration dataset")
    groups = defaultdict(set)
    clips = Counter()
    for motion in motions.values():
        task, group = motion["dataset_task"], motion["dataset_group"]
        groups[task].add(group)
        clips[task, group] += 1
    weights = {}
    for key, motion in motions.items():
        task, group = motion["dataset_task"], motion["dataset_group"]
        weights[key] = 1.0 / len(groups) / len(groups[task]) / clips[task, group]
    total = sum(weights.values())
    if abs(total - 1) > 1e-10:
        raise ValueError("Sampling weights do not sum to one")
    return weights


def summarize_weights(motions, weights):
    tasks, groups = defaultdict(float), defaultdict(float)
    for key, motion in motions.items():
        tasks[motion["dataset_task"]] += weights[key]
        groups[motion["dataset_group"]] += weights[key]
    return {"tasks": dict(tasks), "groups": dict(groups), "clips": len(motions)}
