"""Animate actual recorded rigid-body positions; this is not a Gym render."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import joblib
import matplotlib
matplotlib.use("Agg")
from matplotlib.animation import FuncAnimation, PillowWriter
import matplotlib.pyplot as plt
import numpy as np


def skeleton_edges(urdf, names):
    tree = ET.parse(urdf).getroot()
    parents = {joint.find("child").attrib["link"]: joint.find("parent").attrib["link"] for joint in tree.findall("joint")}
    ids = {name: i for i, name in enumerate(names)}
    edges = []
    for child in names:
        parent = parents.get(child)
        while parent is not None and parent not in ids:
            parent = parents.get(parent)
        if parent in ids:
            edges.append((ids[parent], ids[child]))
    if len(edges) != len(names) - 1:
        raise ValueError("URDF does not connect the recorded body names")
    return edges


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recordings", nargs="+", type=Path, required=True)
    parser.add_argument("--labels", nargs="+", required=True)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--trial", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.labels) != len(args.recordings):
        parser.error("One label per recording is required")
    records = [joblib.load(path)["motion" + str(args.trial)] for path in args.recordings]
    if any(r["body_names"] != records[0]["body_names"] or not np.isclose(r["fps"], 50) for r in records):
        raise ValueError("Body order or record frequency mismatch")
    edges = skeleton_edges(args.urdf, records[0]["body_names"])
    stops = []
    for record in records:
        resets = np.flatnonzero(np.asarray(record["terminate"]))
        stops.append(int(resets[0]) if len(resets) else len(record["body_pos"]))
    valid = np.concatenate([r["body_pos"][:stop].reshape(-1, 3) for r, stop in zip(records, stops)])
    low, high = valid.min(0), valid.max(0)
    center = (low + high) / 2
    half = max(.7, float((high - low).max()) / 2 + .12)
    fig = plt.figure(figsize=(max(6, 4.6 * len(records)), 4.8))
    colors = ("#436CA5", "#C4882F", "#289175", "#8D56A0")
    lines, references, annotations, axes = [], [], [], []
    for i, (record, label) in enumerate(zip(records, args.labels)):
        ax = fig.add_subplot(1, len(records), i + 1, projection="3d")
        ax.set(xlim=(center[0] - half, center[0] + half), ylim=(center[1] - half, center[1] + half),
               zlim=(0, max(1.25, high[2] + .12)), xlabel="x (m)", ylabel="y (m)", zlabel="z (m)")
        ax.set_box_aspect((1, 1, .85))
        ax.view_init(elev=14, azim=-55)
        ax.set_title(label, fontsize=11)
        panel_lines = [ax.plot([], [], [], lw=2.8, color=colors[i % len(colors)])[0] for _ in edges]
        panel_refs = [ax.plot([], [], [], lw=1.2, linestyle="--", color="#999999", alpha=.7)[0] for _ in edges] if "reference_body_pos" in record else []
        lines.append(panel_lines)
        references.append(panel_refs)
        annotations.append(ax.text2D(.03, .92, "", transform=ax.transAxes, fontsize=9))
        axes.append(ax)
    fig.text(.5, .015, "Recorded rigid-body skeletons • dashed: reference when available\nFixed trial %d • motion stops at first termination" % args.trial,
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .08, .98, .98))
    frames = np.arange(0, max(len(r["body_pos"]) for r in records), 2)

    def update(frame):
        artists = []
        for i, record in enumerate(records):
            index = min(int(frame), stops[i] - 1)
            pose = record["body_pos"][index]
            terminated = frame >= stops[i]
            for line, (a, b) in zip(lines[i], edges):
                line.set_data_3d(pose[[a, b]].T)
                line.set_alpha(.4 if terminated else 1.)
            for line, (a, b) in zip(references[i], edges):
                reference = record["reference_body_pos"][index]
                line.set_data_3d(reference[[a, b]].T)
            annotations[i].set_text("t = %.2f s%s" % ((frame + 1) / 50., " | TERMINATED" if terminated else ""))
            annotations[i].set_color("#B63333" if terminated else "#333333")
            artists.extend(lines[i] + references[i] + [annotations[i]])
        return artists

    animation = FuncAnimation(fig, update, frames=frames, interval=40, blit=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    animation.save(args.output, writer=PillowWriter(fps=25), dpi=95)
    args.output.with_suffix(".json").write_text(json.dumps({"scope": "Derived skeleton visualization of recorded simulator positions; not a Gym render",
        "recordings": [p.name for p in args.recordings], "labels": args.labels, "trial": args.trial,
        "first_termination_rows": [s if s < len(r["body_pos"]) else None for s, r in zip(stops, records)],
        "selection": "Fixed trial index; must be disclosed with aggregate metrics", "playback_fps": 25, "record_fps": 50}, indent=2))
    print(args.output)


if __name__ == "__main__":
    main()
