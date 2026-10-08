"""Fresh evaluation only, serialized after the existing repeat-control queue."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time

import joblib
import numpy as np

from research.asap_diagnostics.controlled_pipeline import launch, write
from research.asap_diagnostics.paper_metrics import summarize

BASE = Path('/root/autodl-tmp/aligning_physics')
SEEDS = (8101, 8102, 8103)
FIELDS = ('dof', 'dof_vel', 'root_trans_offset', 'root_rot', 'root_lin_vel', 'root_ang_vel', 'action', 'motion_times')
METHODS = ('vanilla', 'ft_only', 'asap_ft', 'sysid_ft', 'torque_ft', 'active_sysid_ft', 'wave_ft')


def sources():
    out = []
    for task in ('SquatL1', 'CR7', 'StepFBL1'):
        for method in METHODS:
            if task != 'SquatL1':
                source, original = BASE / 'extend_tasks_20261008' / task, method
            elif method == 'active_sysid_ft':
                source, original = BASE / 'active_20261008', method
            elif method == 'wave_ft':
                source, original = BASE / 'wave_20261008/wave', 'torque_ft'
            else:
                source, original = BASE / 'matched_eval_20261008', method
            out.append((task, method, source, original))
    out.append(('SquatL1', 'native_unchanged_torque', BASE / 'wave_20261008/unchanged', 'torque_ft'))
    for run in ('primary', 'repeat'):
        source_root = 'content_20261008' if run == 'primary' else 'content_repeat_20261008'
        for selector in ('uniform', 'coverage', 'joint_range'):
            out.append(('SquatL1', run + '_' + selector, BASE / source_root / selector, 'asap_ft'))
    # First job is a full 32-environment smoke, then reused as its final evaluation.
    return sorted(out, key=lambda row: (row[:2] != ('SquatL1', 'ft_only'), row[0], row[1]))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value(command, key):
    items = [a.split('=', 1)[1] for a in command if a.lstrip('+').startswith(key + '=')]
    if len(items) != 1:
        raise ValueError('Missing or repeated override: ' + key)
    return items[0]


def overrides(command, work, label):
    replacement = {
        'algo._target_': 'research.asap_diagnostics.paper_tracking_runtime.PaperTrackingRecorderPPO',
        'eval_log_dir': str(work / 'tracking' / (label + '_config')),
        'env.config.dataset_record_path': str(work / 'tracking' / (label + '.pkl')),
    }
    out = []
    for argument in command[5:]:
        key = argument.split('=', 1)[0].lstrip('+')
        if key in replacement:
            out.append('++' + key + '=' + replacement.pop(key))
        else:
            out.append(argument)
    if replacement:
        raise ValueError('Unexpected source evaluation command')
    if value(out, 'num_envs') != '32' or value(out, 'env.config.add_extra_action') != 'False':
        raise ValueError('Expected standalone 32-trial target evaluation')
    return out


def audit(source_record, fresh_record):
    old, new = joblib.load(source_record), joblib.load(fresh_record)
    if set(old) != set(new) or len(new) != 32:
        raise ValueError('Trial identity mismatch')
    difference = {key: max(float(np.max(np.abs(old[m][key][0] - new[m][key][0]))) for m in new) for key in FIELDS}
    if any(difference.values()):
        raise ValueError('Fresh stored initialization differs: ' + str(difference))
    for m in new:
        if new[m]['paper_body_pos'].shape != (len(old[m]['dof']), 27, 3):
            raise ValueError('Recording shape mismatch')
        if not np.array_equal(new[m]['body_pos'], new[m]['paper_body_pos'][:, :24]):
            raise ValueError('Physical point order mismatch')
    return {'old_record_sha256': sha(source_record), 'fresh_record_sha256': sha(fresh_record),
            'initial_max_absolute_difference': difference,
            'point_count': 27, 'legacy_point_count': 24,
            'scope': 'Exact first stored state/action/clock check; no claim about hidden solver state'}


def run(args):
    root = args.work_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'manager.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (root / 'status.json').exists():
        raise RuntimeError('Preexisting queue artifacts; refuse automatic resume')
    deadline = datetime.fromisoformat(args.cutoff).timestamp()
    plan = {'created_utc': datetime.now(timezone.utc).isoformat(), 'cutoff_utc': args.cutoff,
            'predecessor': str(args.predecessor), 'seeds': list(SEEDS), 'trials_per_seed': 32,
            'purpose': 'Fresh 27-point ASAP metrics; no training/checkpoint changes',
            'metrics': ['global_position_mm', 'root_relative_position_mm', 'body_velocity_mm_frame',
                        'root_velocity_mm_frame', 'body_acceleration_mm_frame2'],
            'success_rule': 'Full horizon and mean point error never exceeds 0.5 m',
            'runtime_termination': 'Copied unchanged from each matched evaluation command',
            'conditions': [{'task': t, 'method': m, 'source': str(s), 'source_method': o} for t,m,s,o in sources()]}
    write(root / 'queue_plan.json', plan)
    write(root / 'status.json', {'status': 'waiting', 'stage': 'repeat_controls_completion'})
    while True:
        if time.time() >= deadline - 60:
            write(root / 'status.json', {'status': 'skipped', 'stage': 'cutoff_while_waiting'})
            return
        if args.predecessor.exists():
            status = json.loads(args.predecessor.read_text())['status']
            if status == 'complete':
                break
            if status in ('failed', 'skipped'):
                raise RuntimeError('Predecessor ' + status + '; preserve artifacts and stop')
        time.sleep(30)
    manifest, checkpoints = [], {}
    for task, method, source, original in sources():
        for seed in SEEDS:
            label = original + '_seed' + str(seed)
            file = source / 'commands' / (label + '.json')
            command = json.loads(file.read_text())['command']
            checkpoint = Path(value(command, 'checkpoint'))
            if str(checkpoint) not in checkpoints:
                checkpoints[str(checkpoint)] = sha(checkpoint)
            work = root / task / method
            fresh_label = method + '_seed' + str(seed)
            manifest.append({'task': task, 'method': method, 'seed': seed, 'label': fresh_label,
                'source_command': str(file), 'source_command_sha256': sha(file),
                'checkpoint': str(checkpoint), 'checkpoint_sha256': checkpoints[str(checkpoint)],
                'old_record': str(source / 'tracking' / (label + '.pkl')),
                'overrides': overrides(command, work, fresh_label)})
    write(root / 'frozen_manifest.json', manifest)
    reports = {}
    for index, entry in enumerate(manifest):
        # Refuse contention with any other user/server GPU process.
        active = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip()
        if active:
            raise RuntimeError('Unexpected GPU process before fresh eval: ' + active)
        work = root / entry['task'] / entry['method']
        work.mkdir(parents=True, exist_ok=True)
        write(root / 'status.json', {'status': 'running', 'stage': entry['task'] + '/' + entry['label'],
                                    'completed_jobs': index, 'total_jobs': len(manifest)})
        launch(work, 'eval', entry['seed'], entry['overrides'], entry['label'], deadline)
        record = work / 'tracking' / (entry['label'] + '.pkl')
        checked = audit(Path(entry['old_record']), record)
        write(work / (entry['label'] + '_audit.json'), checked)
        report = json.loads(record.with_suffix('.json').read_text())
        reports.setdefault(entry['task'], {}).setdefault(entry['method'], []).append(report)
        if index == 0:
            write(root / 'physical_smoke.json', {'status': 'complete', 'initialization_audit': checked,
                                                'summary': report['summary']})
        write(work / 'status.json', {'status': 'complete' if entry['seed'] == SEEDS[-1] else 'running',
                                    'stage': 'fresh_evaluation', 'last_seed': entry['seed']})
        if entry['seed'] == SEEDS[-1]:
            trials = [dict(row, seed=seed) for seed, r in zip(SEEDS, reports[entry['task']][entry['method']]) for row in r['trials']]
            combined = {'task': entry['task'], 'method': entry['method'],
                        'checkpoint': entry['checkpoint'], 'checkpoint_sha256': entry['checkpoint_sha256'],
                        'summary': summarize(trials), 'trials': trials, 'seeds': list(SEEDS),
                        'recorded_horizon_s': int(value(entry['overrides'], 'env.config.dataset_record_steps')) / 50}
            write(work / 'comparison.json', combined)
    combined = {task: {method: json.loads((root / task / method / 'comparison.json').read_text())
                       for method in methods} for task, methods in reports.items()}
    write(root / 'comparison.json', combined)
    write(root / 'status.json', {'status': 'complete', 'stage': 'fresh_27_point_evaluation',
                                'completed_jobs': len(manifest), 'total_jobs': len(manifest)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--predecessor', type=Path, required=True)
    parser.add_argument('--cutoff', default='2026-10-09T09:00:00+00:00')
    args = parser.parse_args()
    try:
        run(args)
    except Exception as exc:
        write(args.work_dir / 'status.json', {'status': 'failed', 'stage': 'fresh_evaluation', 'error': repr(exc)})
        raise
