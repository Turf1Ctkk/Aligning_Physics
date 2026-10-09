"""Actual replay scoring plus fixed training-derived perjoint servo-error strata."""
from collections import defaultdict
from pathlib import Path
import numpy as np
import joblib

from research.asap_diagnostics.replay_scoring import score, aggregate
from research.asap_diagnostics.dataset_tools import replay_metrics
from research.asap_diagnostics.select_servo import ANKLES, signals
import hashlib

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measured(work, checkpoint, label, edges, split='test'):
    checkpoint = Path(checkpoint)
    reference_path = work / 'datasets' / (split + '_cases.pkl')
    prediction_path = work / 'evaluation' / split / (label + '.pkl')
    reference, prediction = joblib.load(reference_path), joblib.load(prediction_path)
    if set(prediction) != {'motion%d' % i for i in range(len(reference))} or len(reference) != (66 if split == 'test' else 60):
        raise ValueError('Heldout case identity changed')
    cases, strata = [], defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    edges = np.asarray(edges)
    for case_index, (key, target) in enumerate(reference.items()):
        output = prediction['motion%d' % case_index]
        result = score(target, output, 1.0)
        joint = replay_metrics(target, output, 1.0)
        cases.append({'key': key, 'task': target['dataset_task'], 'group': target['dataset_group'],
            'horizons': {'1.0': result}, 'joint_metrics': joint})
        times = np.asarray(output['motion_times']).reshape(-1)
        reset = np.flatnonzero(np.asarray(output['terminate']).reshape(len(times), -1).any(axis=1))
        stop = int(reset[0]) if len(reset) else len(times)
        rows = np.flatnonzero((times[:stop] > 1e-6) & (times[:stop] <= 1+1e-6))
        rows = rows[rows > 0]
        frame = times[rows]*50
        indices = np.rint(frame).astype(int)
        if not np.allclose(frame, indices, atol=1e-4):
            raise ValueError('Unexpected non-grid replay clock')
        e, _, unsaturated = signals(target)
        body_error = np.linalg.norm(np.asarray(output['body_pos'])[rows] - np.asarray(target['body_pos'])[indices], axis=-1).mean(-1)*1000
        q_error = np.asarray(output['dof'])[rows][:, ANKLES] - np.asarray(target['dof'])[indices][:, ANKLES]
        v_error = np.asarray(output['dof_vel'])[rows][:, ANKLES] - np.asarray(target['dof_vel'])[indices][:, ANKLES]
        cases[-1]['ankle_position_rmse_rad'] = float(np.sqrt(np.mean(q_error*q_error)))
        cases[-1]['ankle_velocity_rmse_rad_s'] = float(np.sqrt(np.mean(v_error*v_error)))
        for joint_index in range(4):
            bins = np.searchsorted(edges[joint_index], np.abs(e[indices-1, joint_index]), side='right')
            for magnitude in range(3):
                mask = (bins == magnitude) & unsaturated[indices-1, joint_index]
                if mask.any():
                    strata['j%d_bin%d' % (joint_index, magnitude)][target['dataset_task']][target['dataset_group']].append({
                        'frames': int(mask.sum()), 'global_position_mm': float(body_error[mask].mean()),
                        'joint_position_mse_rad2': float(np.mean(q_error[mask, joint_index]**2)),
                        'joint_velocity_mse_rad2_s2': float(np.mean(v_error[mask, joint_index]**2))})
    stratified = {}
    for label_key, tasks in strata.items():
        means = []
        count, groups = 0, 0
        for task_groups in tasks.values():
            values = []
            for records in task_groups.values():
                values.append({k: float(np.mean([record[k] for record in records])) for k in
                    ('global_position_mm', 'joint_position_mse_rad2', 'joint_velocity_mse_rad2_s2')})
                count += sum(r['frames'] for r in records); groups += 1
            means.append({k: float(np.mean([v[k] for v in values])) for k in values[0]})
        values = {k: float(np.mean([v[k] for v in means])) for k in means[0]}
        stratified[label_key] = dict(values, joint_position_rmse_rad=float(np.sqrt(values['joint_position_mse_rad2'])),
            joint_velocity_rmse_rad_s=float(np.sqrt(values['joint_velocity_mse_rad2_s2'])),
            included_frame_entries=count, included_parent_groups=groups, included_tasks=len(tasks))
    return {'checkpoint': str(checkpoint), 'checkpoint_sha256': sha(checkpoint),
        'target_sha256': sha(reference_path), 'record_sha256': sha(prediction_path), 'point_count': 24,
        'cases': cases, 'paper_metrics': aggregate(cases, 1.0), 'stratified': stratified,
        'complete_cases': sum(c['horizons']['1.0']['complete'] for c in cases), 'total_cases': len(cases),
        'stratum_scope': 'Target preceding-transition unsaturated servo magnitude, separately perjoint; frame entries overlap across joints and are not independent trials',
        'stratum_weights': 'Equal tasks, then parents, then available case means; per-bin inclusion differs; no floor subtraction'}
