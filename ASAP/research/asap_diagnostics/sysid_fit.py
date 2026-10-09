"""Gain fitting used in the study, without experiment scheduling or SSH.

The caller supplies a batched simulator callback. Target gains are never inputs.
"""
import numpy as np
from research.asap_diagnostics.dataset_tools import slice_motion, replay_metrics
from research.asap_diagnostics.controlled_sampling import hierarchical_weights


def central_windows(dataset):
    windows = {}
    for key, motion in dataset.items():
        start = (len(motion['dof']) - 52) // 2
        if start < 0:
            raise ValueError('Short calibration segment')
        windows[key] = slice_motion(motion, start, start + 52)
    return windows


def trajectory_loss(reference, prediction):
    short = replay_metrics(reference, prediction, .25)
    full = replay_metrics(reference, prediction, 1.)
    if not short['complete'] or not full['complete']:
        raise ValueError('Incomplete candidate trajectory; preserve it before stopping')
    return (short['all_joint_rmse_rad'] / .1) ** 2 + short['joint_velocity_rmse_rad_s'] ** 2


def fit_ankle_gains(windows, simulate_candidates, seed=7101, generations=8):
    """simulate_candidates(gains, windows) returns one prediction dict per gain pair.

    Dict keys must match windows. CandidateGainReplay implements simulator gains.
    The callback is responsible for matched initialization and executed commands.
    """
    import cma
    weights = hierarchical_weights(windows)
    optimizer = cma.CMAEvolutionStrategy([20., 20.], 2.,
        {'bounds': [8., 30.], 'popsize': 12, 'seed': seed, 'verbose': -9})
    history = []
    for generation in range(generations):
        candidates = optimizer.ask()
        predictions = simulate_candidates(candidates, windows)
        if len(predictions) != len(candidates):
            raise ValueError('Missing candidate results')
        losses = []
        for prediction in predictions:
            if set(prediction) != set(windows):
                raise ValueError('Candidate window identities changed')
            losses.append(sum(weights[k] * trajectory_loss(windows[k], prediction[k]) for k in windows))
        optimizer.tell(candidates, losses)
        history.append({'generation': generation, 'gains': np.asarray(candidates).tolist(), 'losses': losses})
    return {'gains': optimizer.result.xbest.tolist(), 'loss': float(optimizer.result.fbest), 'history': history}


def optimize_excitation(evaluate_candidates, seed=7201, generations=6):
    """Callback returns information_score dictionaries for normalized designs.

    Check the predeclared zero and random controls before optimizing. An invalid
    control stops the search rather than disappearing from the comparison.
    """
    import cma
    zero = [0., 0., .5, .5]
    random = np.random.RandomState(seed).uniform(.1, .9, 4).tolist()
    controls = list(evaluate_candidates([zero, random]))
    if len(controls) != 2 or not all(row['feasible'] for row in controls):
        raise ValueError('Predeclared excitation control is infeasible')
    best, value = zero, controls[0]['objective']
    optimizer = cma.CMAEvolutionStrategy([.5] * 4, .22,
        {'bounds': [0., 1.], 'popsize': 8, 'seed': seed, 'verbose': -9})
    for _ in range(generations):
        candidates = optimizer.ask()
        scores = list(evaluate_candidates(candidates))
        values = [row['objective'] for row in scores]
        if len(scores) != len(candidates) or not np.isfinite(values).all():
            raise ValueError('Invalid excitation evaluation')
        optimizer.tell(candidates, values)
        for candidate, row in zip(candidates, scores):
            if row['feasible'] and row['objective'] < value:
                best, value = np.asarray(candidate).tolist(), row['objective']
    return best, float(value)
