"""Fresh physics replays with ASAP formulas on the recorded 24-body point set."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import time

import joblib
import numpy as np

from research.asap_diagnostics.controlled_pipeline import launch, write
from research.asap_diagnostics.paper_eval_queue import BASE, value, sha, FIELDS
from research.asap_diagnostics.paper_metrics import errors


def jobs():
    out = []
    def add(root, labels):
        for label in labels:
            out.append((root.replace('/', '_') + '__' + label, BASE / root / 'commands' / (label + '.json')))
    add('controlled_squat_20261008', ('same16_zero', 'source20_zero', 'controlled_delta'))
    add('sysid_serial_20261008', ('identified_test',))
    add('torque_20261008', ('same16_zero', 'source20_zero', 'torque'))
    add('active_20261008', ('zero_test', 'random_test', 'active_test'))
    for arm in ('unchanged', 'wave'):
        add('wave_20261008/' + arm, ('same16_zero', 'source20_zero', 'torque'))
    for run in ('content_20261008', 'content_repeat_20261008'):
        for selector in ('uniform', 'coverage', 'joint_range'):
            add(run + '/' + selector, ('learned',))
    add('content_20261008/uniform', ('same16_zero', 'source20_zero'))
    # These are the fresh repeat-seed controls, not copied primary controls.
    add('repeat_controls_20261008', ('source20_zero', 'same16_zero'))
    return out


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


def run(args):
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    lock = (work / 'manager.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (work / 'status.json').exists():
        raise RuntimeError('Preexisting replay queue; no automatic resume')
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    write(work / 'queue_plan.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
        'predecessor': str(args.predecessor), 'cutoff_utc': args.cutoff,
        'jobs': [{'label': label, 'source_command': str(path)} for label, path in jobs()],
        'point_count': 24, 'target_point_scope': 'Actual rigid bodies in unchanged held-out target recordings; no reconstructed hand/head measurements',
        'purpose': 'Fresh calibration replay; position and first/second body differences in ASAP units; no retraining'})
    write(work / 'status.json', {'status': 'waiting', 'stage': 'fresh_policy_evaluation_completion'})
    while True:
        if time.time() >= deadline - 60:
            write(work / 'status.json', {'status': 'skipped', 'stage': 'cutoff_while_waiting'})
            return
        if args.predecessor.exists():
            status = json.loads(args.predecessor.read_text())['status']
            if status == 'complete':
                break
            if status in ('failed', 'skipped'):
                raise RuntimeError('Predecessor ' + status + '; stop without restarting')
        time.sleep(30)
    output = {}
    for index, (label, source) in enumerate(jobs()):
        command = json.loads(source.read_text())['command']
        old_output = Path(value(command, 'env.config.dataset_record_path'))
        inputs = Path(value(command, 'robot.motion.motion_file'))
        if len(joblib.load(inputs)) != 66:
            raise ValueError('Expected original 66 held-out cases, not an acquisition or training split')
        directory = work / label
        directory.mkdir(parents=True, exist_ok=True)
        fresh_path = directory / 'replay.pkl'
        replacements = {'env.config.dataset_record_path': str(fresh_path), 'eval_log_dir': str(directory / 'effective_config')}
        overrides = []
        for a in command[5:]:
            key = a.split('=', 1)[0].lstrip('+')
            overrides.append('++' + key + '=' + replacements.pop(key) if key in replacements else a)
        if replacements:
            raise ValueError('Missing source output override')
        checkpoint = Path(value(command, 'checkpoint'))
        write(directory / 'provenance.json', {'source_command': str(source), 'command_sha256': sha(source),
            'checkpoint_sha256': sha(checkpoint), 'input_sha256': sha(inputs), 'old_output': str(old_output)})
        if subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip():
            raise RuntimeError('Unexpected GPU process before replay')
        write(work / 'status.json', {'status': 'running', 'stage': label, 'completed_jobs': index, 'total_jobs': len(jobs())})
        launch(directory, 'eval', int(command[4]), overrides, 'replay', deadline)
        reference, prediction, old = joblib.load(inputs), joblib.load(fresh_path), joblib.load(old_output)
        if set(prediction) != set(old) or len(prediction) != len(reference):
            raise ValueError('Replay case identity mismatch')
        difference = {k: max(float(np.max(np.abs(prediction[m][k][0] - old[m][k][0]))) for m in prediction) for k in FIELDS}
        if any(difference.values()):
            raise ValueError('Fresh replay initialization differs: ' + str(difference))
        cases = []
        for i, (key, ref) in enumerate(reference.items()):
            cases.append({'key': key, 'task': ref['dataset_task'], 'group': ref['dataset_group'],
                          'horizons': {str(h): score(ref, prediction['motion' + str(i)], h) for h in (.25, .5, 1.)}})
        report = {'point_count': 24, 'fps': 50, 'initial_max_absolute_difference': difference,
                  'horizons': {str(h): aggregate(cases, h) for h in (.25, .5, 1.)}, 'cases': cases,
                  'scope': 'Fresh source physics replay against unchanged measured target records; four ankle corrections or fitted gains. This is not policy deployment.'}
        write(directory / 'metrics.json', report)
        write(directory / 'status.json', {'status': 'complete', 'stage': 'fresh_replay'})
        output[label] = report
    write(work / 'comparison.json', output)
    write(work / 'status.json', {'status': 'complete', 'stage': 'fresh_replay_metrics', 'total_jobs': len(jobs())})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--predecessor', type=Path, required=True)
    parser.add_argument('--cutoff', default='2026-10-09T09:00:00+00:00')
    args = parser.parse_args()
    try:
        run(args)
    except Exception as exc:
        write(args.work_dir / 'status.json', {'status': 'failed', 'stage': 'fresh_replay', 'error': repr(exc)})
        raise
