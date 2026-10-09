"""Training-only servo-error selection with shared parent/phase/velocity/proxy quotas."""
from collections import defaultdict
import numpy as np

from research.asap_diagnostics.dataset_tools import slice_motion

ANKLES = [4, 5, 10, 11]
DEFAULT = np.array([-.2, 0., -.2, 0.])
KD = np.array([.2, .1, .2, .1])
METHODS = ('random', 'servo', 'low_error')


def signals(motion):
    # Incoming action[i+1] is applied from the stored state[i].
    q = np.asarray(motion['dof'])[:-1, ANKLES]
    velocity = np.asarray(motion['dof_vel'])[:-1, ANKLES]
    error = DEFAULT + .25*np.asarray(motion['action'])[1:, ANKLES] - q
    torque = 20*error - KD*velocity
    return error, velocity, np.abs(torque) < 50


def histogram(error, unsaturated, edges):
    counts = np.zeros((4, 2, 3), dtype=int)
    for joint in range(4):
        for sign in range(2):
            for magnitude in range(3):
                bins = np.searchsorted(edges[joint], np.abs(error[:, joint]), side='right')
                mask = unsaturated[:, joint] & (np.abs(error[:, joint]) > 1e-8)
                mask &= ((error[:, joint] >= 0) if sign else (error[:, joint] < 0))
                counts[joint, sign, magnitude] = int(np.sum(mask & (bins == magnitude)))
    return counts


def select(motions, raw, durations, seed=7709):
    rng = np.random.RandomState(seed)
    errors, unsaturated, feet = [], [], []
    for motion in motions.values():
        e, _, u = signals(motion)
        errors.append(e); unsaturated.append(u)
        ids = [motion['body_names'].index(n) for n in ('left_ankle_roll_link', 'right_ankle_roll_link')]
        feet.append(np.asarray(motion['body_pos'])[:, ids, 2])
    error_matrix, unsat_matrix = np.concatenate(errors), np.concatenate(unsaturated)
    edges = np.array([np.quantile(np.abs(error_matrix[unsat_matrix[:, j], j]), [1/3, 2/3]) for j in range(4)])
    foot_height = np.quantile(np.concatenate(feet), .1, axis=0) + .025
    rows = []
    for key, motion in sorted(motions.items()):
        task, group = motion['dataset_task'], motion['dataset_group']
        parent_index = int(group.split('rollout')[1])
        if parent_index >= 30:
            raise ValueError('Non-training parent reached selection')
        original = raw[task]['motion%d' % parent_index]
        source_start, source_stop = motion['source_rows']
        if not np.array_equal(np.asarray(original['dof'])[source_start:source_stop], motion['dof']):
            raise ValueError('Raw-to-segment alignment failed')
        n = len(motion['dof'])
        if n < 54:
            continue
        for start in sorted(set(list(range(0, n-53, 5)) + [n-54])):
            window = slice_motion(motion, start, start+54)
            e, v, u = signals(window)
            if not np.isfinite(e).all() or not np.isfinite(v).all():
                raise ValueError('Invalid training window')
            saturation = float(1-u.mean())
            if saturation > .25:
                continue
            raw_times = np.asarray(original['motion_times']).reshape(-1)[source_start+start:source_start+start+54]
            if not np.allclose(np.diff(raw_times), .02, atol=1e-5):
                raise ValueError('Candidate crosses a reset/time discontinuity')
            phase = float(np.mean(raw_times) / durations[task])
            if not 0 <= phase <= 1:
                raise ValueError('Reference phase outside the motion')
            ids = [window['body_names'].index(name) for name in ('left_ankle_roll_link', 'right_ankle_roll_link')]
            positions = np.asarray(window['body_pos'])[:, ids]
            vertical = np.gradient(positions[:, :, 2], 1/50, axis=0)
            proxy = (positions[:, :, 2] <= foot_height) & (np.abs(vertical) < .2)
            fractions = proxy.mean(0)
            proxy_mode = int(fractions[0] >= .5) + 2*int(fractions[1] >= .5)
            rows.append({'source_clip': key, 'start': start, 'stop': start+54, 'task': task, 'group': group,
                'phase': phase, 'velocity_rms': float(np.sqrt(np.mean(v*v))),
                'saturation_fraction': saturation, 'contact_proxy_mode': proxy_mode,
                'contact_proxy_fraction': fractions.tolist(), 'servo_abs_mean': float(np.mean(np.abs(e[u]))),
                'servo_histogram': histogram(e, u, edges).tolist(), 'motion': window})
    # Failed target rollouts need not contain full windows in the late reference phase.
    # Use training-candidate phase tertiles, shared by every arm; do not claim full-phase coverage.
    phase_edges = {task: np.quantile([r['phase'] for r in rows if r['task'] == task], [1/3, 2/3]).tolist()
                   for task in sorted(raw)}
    for row in rows:
        row['phase_bin'] = int(np.searchsorted(phase_edges[row['task']], row['phase'], side='right'))
    velocity_edges = {}
    for task in sorted(raw):
        velocity_edges[task] = {}
        for phase_bin in range(3):
            values = [r['velocity_rms'] for r in rows if r['task'] == task and r['phase_bin'] == phase_bin]
            if not values:
                raise ValueError('No candidate for task/phase quota')
            velocity_edges[task][str(phase_bin)] = float(np.median(values))
    strata = defaultdict(list)
    for row in rows:
        row['velocity_bin'] = int(row['velocity_rms'] >= velocity_edges[row['task']][str(row['phase_bin'])])
        signature = (row['task'], row['phase_bin'], row['group'], row['velocity_bin'], row['contact_proxy_mode'])
        strata[signature].append(row)
    # Require at least3 possible windows, so each fixed parent/quota admits alternatives.
    options = defaultdict(list)
    for signature, candidates in sorted(strata.items()):
        if len(candidates) >= 3:
            task, phase_bin, group, velocity_bin, proxy_mode = signature
            options[(task, phase_bin)].append(signature)
    order = []
    for task in sorted(raw):
        slots = [(task, phase_bin) for phase_bin in range(3) for _ in range(2)]
        shuffled = {}
        for slot in set(slots):
            shuffled[slot] = [options[slot][i] for i in rng.permutation(len(options[slot]))]
        def assign(index, used, chosen):
            if index == len(slots):
                return chosen
            for signature in shuffled[slots[index]]:
                if signature[2] not in used:
                    result = assign(index+1, used | {signature[2]}, chosen + [signature])
                    if result is not None:
                        return result
            return None
        assigned = assign(0, set(), [])
        if assigned is None:
            raise ValueError('Cannot satisfy6 parents/task and2 windows/phase; do not silently relax')
        order.extend(assigned)
    data, selections, summaries = {}, {}, {}
    for method in METHODS:
        chosen, selected, total = {}, [], np.zeros((4, 2, 3))
        for signature in order:
            candidates = strata[signature]
            if method == 'random':
                row = candidates[int(rng.randint(len(candidates)))]
            elif method == 'low_error':
                row = min(candidates, key=lambda r: r['servo_abs_mean'])
            else:
                def gain(candidate):
                    h = np.asarray(candidate['servo_histogram'])
                    return float(np.sum(np.log1p((total+h)/53) - np.log1p(total/53)))
                row = max(candidates, key=gain)
            total += np.asarray(row['servo_histogram'])
            chosen[row['group']] = row['motion']
            selected.append({k: v for k, v in row.items() if k != 'motion'})
        data[method], selections[method] = chosen, selected
        summaries[method] = {'histogram': total.astype(int).tolist(),
            'saturation_fraction': float(np.mean([r['saturation_fraction'] for r in selected])),
            'velocity_rms_mean': float(np.mean([r['velocity_rms'] for r in selected])),
            'velocity_rms_std': float(np.std([r['velocity_rms'] for r in selected])),
            'contact_proxy_fraction': np.mean([r['contact_proxy_fraction'] for r in selected], axis=0).tolist(),
            'servo_abs_mean': float(np.mean([r['servo_abs_mean'] for r in selected]))}
    if len(order) != 18 or any(set(d) != set(data['random']) for d in data.values()):
        raise ValueError('Parent/budget mismatch')
    manifest = {'seed': seed, 'selectors': selections, 'summaries': summaries,
        'frames_per_window': 54, 'unique_transitions_per_arm': 954,
        'servo_magnitude_edges_rad': edges.tolist(), 'velocity_median_edges': velocity_edges,
        'candidate_count_before_stratum_filter': len(rows), 'eligible_strata': len(strata),
        'pool_unique_transitions': sum(len(m['dof'])-1 for m in motions.values()),
        'quotas': [list(s) for s in order], 'window_stride_frames': 5,
        'phase_definition': 'Mean original raw reference clock / task duration; three training-candidate phase tertiles; not full-reference coverage',
        'phase_tertile_edges': phase_edges,
        'contact_scope': 'Height and vertical-speed proxy, not measured force/contact mode',
        'contact_proxy_height_threshold_m': foot_height.tolist(), 'contact_proxy_vertical_speed_threshold_m_s': .2,
        'saturation_scope': 'Source20 PD torque estimate; abs<50Nm perjoint; window mean clipped fraction<=25%',
        'coverage_score': 'Sum log1p cumulative unsaturated histogram counts/53;24joint-sign-magnitude bins',
        'velocity_scope': 'Exact coarse RMS bin quota; continuous speed distributions may still differ',
        'budget_scope': 'Selected training transitions, not acquisition/inspection cost of the existing pool'}
    return data, manifest
