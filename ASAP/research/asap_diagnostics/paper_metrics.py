"""ASAP evaluation formulas. Positions are metres; differences are per frame.

The official SMPLSim helper averages velocity over bodies. The paper text calls
E_vel a root-velocity error. We report both, with separate names.
"""
import numpy as np


def errors(prediction, reference):
    p, r = np.asarray(prediction, dtype=np.float64), np.asarray(reference, dtype=np.float64)
    if p.shape != r.shape or p.ndim != 3 or p.shape[-1] != 3 or not np.isfinite(p).all() or not np.isfinite(r).all():
        raise ValueError('Expected finite matching [frames, bodies, 3] arrays')
    if len(p) < 3:
        raise ValueError('At least three consecutive frames are required')
    return {
        'global_position_mm': float(np.linalg.norm(p - r, axis=-1).mean() * 1000),
        'root_relative_position_mm': float(np.linalg.norm(
            (p - p[:, :1]) - (r - r[:, :1]), axis=-1).mean() * 1000),
        'body_velocity_mm_frame': float(np.linalg.norm(np.diff(p, axis=0) - np.diff(r, axis=0), axis=-1).mean() * 1000),
        'root_velocity_mm_frame': float(np.linalg.norm(np.diff(p[:, 0], axis=0) - np.diff(r[:, 0], axis=0), axis=-1).mean() * 1000),
        'body_acceleration_mm_frame2': float(np.linalg.norm(np.diff(p, n=2, axis=0) - np.diff(r, n=2, axis=0), axis=-1).mean() * 1000),
    }


def trial_metrics(record, root_index=0):
    p = np.asarray(record['paper_body_pos'])
    r = np.asarray(record['paper_reference_body_pos'])
    if root_index != 0:
        raise ValueError('This G1 body order has pelvis at index zero')
    if p.shape != r.shape or p.shape[1:] != (27, 3):
        raise ValueError('Expected exactly 27 G1 evaluation points')
    if not np.isclose(record['fps'], 50):
        raise ValueError('Per-frame comparisons require the fixed 50 Hz recording rate')
    resets = np.flatnonzero(record['terminate'])
    stop = int(resets[0]) if len(resets) else len(p)
    # The setup warm step is kept for initialization audits, excluded from scores.
    # A reset row contains the new episode's state, so exclude it and everything later.
    start = 1
    clock = np.asarray(record['motion_times'])[start:stop]
    if len(clock) > 1 and not np.allclose(np.diff(clock), 1 / 50, atol=2e-6):
        raise ValueError('Nonconsecutive recording clock before first reset')
    complete = not len(resets)
    mean_distance = np.linalg.norm(p[:stop] - r[:stop], axis=-1).mean(axis=-1)
    # Include warm-state deviation in the success check, although not in means.
    success = complete and bool(len(mean_distance)) and bool(np.all(mean_distance <= .5))
    prefix = {}
    for horizon in (1., 3.):
        wanted = min(len(p), int(round(horizon * 50)))
        end = min(stop, wanted)
        prefix[str(horizon)] = {
            'complete_prefix': stop >= wanted,
            'scored_frames': max(0, end - start),
            'metrics': errors(p[start:end], r[start:end]) if end - start >= 3 else None,
        }
    return {
        'complete': complete, 'paper_tracking_success': success,
        'first_reset_row': int(resets[0]) if len(resets) else None,
        'survival_s': stop / 50, 'recorded_frames': len(p),
        'scored_frames': max(0, stop - start),
        'max_mean_body_distance_m': float(mean_distance.max()) if len(mean_distance) else None,
        'metrics': errors(p[start:stop], r[start:stop]) if stop - start >= 3 else None,
        'prefix_metrics': prefix,
    }


def summarize(trials):
    if not trials:
        raise ValueError('No trials')
    def means(rows):
        values = [row['metrics'] for row in rows if row['metrics'] is not None]
        return {k: float(np.mean([v[k] for v in values])) for k in values[0]} if values else None
    successful = [row for row in trials if row['paper_tracking_success']]
    complete = [row for row in trials if row['complete']]
    return {
        'total_trials': len(trials), 'complete_trials': len(complete),
        'paper_success_trials': len(successful),
        'completion_pct': 100 * len(complete) / len(trials),
        'paper_success_pct': 100 * len(successful) / len(trials),
        'mean_survival_s': float(np.mean([t['survival_s'] for t in trials])),
        'all_trial_available_metrics': means(trials),
        'completed_trial_metrics': means(complete),
        'paper_successful_trial_metrics': means(successful),
        'prefix_metrics': {key: {
            'valid_trials': sum(t['prefix_metrics'][key]['complete_prefix'] for t in trials),
            'metrics': means([t['prefix_metrics'][key] for t in trials if t['prefix_metrics'][key]['complete_prefix']]),
        } for key in ('1.0', '3.0')},
    }
