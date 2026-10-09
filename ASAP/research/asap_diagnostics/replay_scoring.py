"""ASAP replay errors for measured body trajectories; no simulator launcher."""
import numpy as np
from research.asap_diagnostics.paper_metrics import errors

def score(reference, prediction, horizon):
    if reference['body_names'] != prediction['body_names'] or len(reference['body_names']) != 24:
        raise ValueError('Expected matching measured 24-body order')
    fps = float(prediction['fps'])
    if not np.isclose(fps, 50) or not np.isclose(reference['fps'], fps):
        raise ValueError('Expected common 50 Hz replay output')
    times = np.asarray(prediction['motion_times']).reshape(-1)
    reset = np.flatnonzero(np.asarray(prediction['terminate']).reshape(len(times), -1).any(axis=1))
    stop = int(reset[0]) if len(reset) else len(times)
    if len(times[:stop]) > 1 and not np.allclose(np.diff(times[:stop]), .02, atol=1e-5):
        raise ValueError('Replay clock discontinuity')
    rows = np.flatnonzero((times[:stop] > 1e-6) & (times[:stop] <= horizon + 1e-6))
    complete = len(rows) == int(np.floor(horizon * fps + 1e-5))
    # Exclude the setup warm-state sample, preserving it for the separate audit.
    rows = rows[rows > 0]
    if len(rows) < 3:
        return {'complete': complete, 'metrics': None, 'scored_frames': len(rows)}
    frame = times[rows] * fps
    lo = np.floor(frame).astype(int)
    hi = np.minimum(lo + 1, len(reference['body_pos']) - 1)
    if np.any(lo >= len(reference['body_pos'])):
        raise ValueError('Reference tail exceeded')
    weights = (frame - lo)[:, None, None]
    ref = np.asarray(reference['body_pos'])
    aligned = (1 - weights) * ref[lo] + weights * ref[hi]
    actual = np.asarray(prediction['body_pos'])[rows]
    return {'complete': complete, 'metrics': errors(actual, aligned), 'scored_frames': len(rows),
            'first_time_s': float(times[rows[0]]), 'last_time_s': float(times[rows[-1]]),
            'first_reset_row': int(reset[0]) if len(reset) else None}

def aggregate(cases, horizon):
    groups = {}
    for c in cases:
        m = c['horizons'][str(horizon)]['metrics']
        if m is not None:
            groups.setdefault(c['task'], {}).setdefault(c['group'], []).append(m)
    tasks = {}
    for task, values in groups.items():
        task_groups = [{k: float(np.mean([x[k] for x in rows])) for k in rows[0]} for rows in values.values()]
        tasks[task] = {k: float(np.mean([g[k] for g in task_groups])) for k in task_groups[0]}
    if set(tasks) != {'CR7', 'SquatL1', 'StepFBL1'}:
        raise ValueError('Missing task in replay metrics')
    return {'metrics': {k: float(np.mean([v[k] for v in tasks.values()])) for k in next(iter(tasks.values()))},
            'completion_pct': 100 * sum(c['horizons'][str(horizon)]['complete'] for c in cases) / len(cases),
            'total_cases': len(cases), 'per_task': tasks,
            'scope': 'Available uninterrupted frames; equal means within group, then task, then across tasks. Read completion separately.'}
