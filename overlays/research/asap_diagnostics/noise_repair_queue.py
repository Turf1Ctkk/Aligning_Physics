"""Isolate two frozen-delta input noise channels; never overwrite old runs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

from research.asap_diagnostics.controlled_pipeline import launch, write
from research.asap_diagnostics.paper_eval_queue import audit
from research.asap_diagnostics.paper_metrics import summarize

BASE = Path('/root/autodl-tmp/aligning_physics')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace(arguments, replacements):
    values = dict(replacements)
    out = []
    for arg in arguments:
        key = arg.split('=', 1)[0].lstrip('+')
        out.append('++' + key + '=' + values.pop(key) if key in values else arg)
    out.extend('++' + key + '=' + value for key, value in values.items())
    return out


def run(root, predecessor, cutoff):
    if root.exists():
        raise RuntimeError('Preexisting repair root; refuse silent resume')
    root.mkdir(parents=True)
    deadline = datetime.fromisoformat(cutoff).timestamp()
    manifest = json.loads((BASE / 'paper_eval_20261008/frozen_manifest.json').read_text())
    plan = {'created_utc': datetime.now(timezone.utc).isoformat(), 'cutoff_utc': cutoff,
            'predecessor': str(predecessor), 'tasks': ['SquatL1', 'CR7', 'StepFBL1'],
            'intervention': {'obs.noise_scales.base_pos_z': [1.0, 0.0], 'obs.noise_scales.feet_contact_force': [.01, 0.0]},
            'unchanged': ['source checkpoint', 'frozen calibration checkpoint', 'training seed', '1000 PPO updates',
                          'reward', 'termination', 'initialization', 'optimizer settings', 'evaluation seeds'],
            'purpose': 'Input-noise repair diagnostic; not a full paper-setting restoration'}
    write(root / 'queue_plan.json', plan)
    write(root / 'status.json', {'status': 'waiting', 'stage': 'source_audit'})
    while True:
        if time.time() >= deadline - 60:
            write(root / 'status.json', {'status': 'skipped', 'stage': 'cutoff'})
            return
        if predecessor.exists():
            status = json.loads(predecessor.read_text())['status']
            if status == 'complete':
                break
            if status in ('failed', 'skipped'):
                raise RuntimeError('Predecessor ' + status)
        time.sleep(20)
    frozen, reports = [], {}
    for task in plan['tasks']:
        source = BASE / ('controlled_squat_20261008' if task == 'SquatL1' else 'extend_tasks_20261008/' + task)
        command_file = source / 'commands/train_asap_ft.json'
        command = json.loads(command_file.read_text())['command']
        work = root / task
        work.mkdir()
        original = {arg.split('=', 1)[0].lstrip('+'): arg.split('=', 1)[1] for arg in command[5:]}
        for key in ('checkpoint', 'algo.config.policy_checkpoint'):
            frozen.append({'task': task, 'key': key, 'path': original[key], 'sha256': sha(original[key])})
        overrides = replace(command[5:], {'experiment_dir': str(work / 'models/asap_ft'),
            'experiment_name': 'asap_input_noise_repair', 'obs.noise_scales.base_pos_z': '0.0',
            'obs.noise_scales.feet_contact_force': '0.0'})
        write(root / 'frozen_manifest.json', frozen)
        if subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip():
            raise RuntimeError('Unexpected GPU process')
        write(root / 'status.json', {'status': 'running', 'stage': task + '/train'})
        launch(work, 'train', int(command[4]), overrides, 'train_asap_ft', deadline)
        final = work / 'models/asap_ft/model_1000.pt'
        if not final.exists():
            raise ValueError('Fixed final checkpoint missing')
        trials = []
        for row in [e for e in manifest if e['task'] == task and e['method'] == 'asap_ft']:
            if subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip():
                raise RuntimeError('Unexpected GPU process')
            label = row['label']
            eval_overrides = replace(row['overrides'], {'checkpoint': str(final),
                'eval_log_dir': str(work / 'tracking' / (label + '_config')),
                'env.config.dataset_record_path': str(work / 'tracking' / (label + '.pkl'))})
            write(root / 'status.json', {'status': 'running', 'stage': task + '/' + label})
            launch(work, 'eval', row['seed'], eval_overrides, label, deadline)
            record = work / 'tracking' / (label + '.pkl')
            write(work / (label + '_start_audit.json'), audit(Path(row['old_record']), record))
            report = json.loads(record.with_suffix('.json').read_text())
            trials.extend(dict(t, seed=row['seed']) for t in report['trials'])
        reports[task] = {'summary': summarize(trials), 'trials': trials, 'checkpoint': str(final),
                         'checkpoint_sha256': sha(final)}
        write(work / 'comparison.json', reports[task])
        write(work / 'status.json', {'status': 'complete'})
        write(root / 'comparison.json', reports)
    write(root / 'status.json', {'status': 'complete', 'stage': 'noise_repair_comparison'})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work-dir', type=Path, required=True)
    p.add_argument('--predecessor', type=Path, required=True)
    p.add_argument('--cutoff', default='2026-10-09T09:00:00+00:00')
    a = p.parse_args()
    existed_before = a.work_dir.exists()
    try:
        run(a.work_dir, a.predecessor, a.cutoff)
    except Exception as exc:
        if not existed_before and a.work_dir.exists() and (a.work_dir / 'queue_plan.json').exists():
            write(a.work_dir / 'status.json', {'status': 'failed', 'error': repr(exc)})
        raise
