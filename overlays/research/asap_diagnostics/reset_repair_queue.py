"""Isolate delta reset clearing after the input-noise repair; no silent resume."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from research.asap_diagnostics.controlled_pipeline import launch, write
from research.asap_diagnostics.noise_repair_queue import replace, sha
from research.asap_diagnostics.paper_eval_queue import audit
from research.asap_diagnostics.paper_metrics import summarize

BASE = Path('/root/autodl-tmp/aligning_physics')
TARGET = 'research.asap_diagnostics.delta_reset_runtime.ResetSafeDeltaClosedLoop'
CORE = ['envs/legged_base_task/legged_robot_base.py', 'envs/motion_tracking/motion_tracking.py',
        'envs/delta_a/delta_a_open_loop.py', 'envs/delta_a/delta_a_closed_loop.py',
        'agents/delta_a/train_delta_a.py']


def idle_gpu():
    if subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid',
                                '--format=csv,noheader'], text=True).strip():
        raise RuntimeError('Unexpected GPU process; do not overlap heavy jobs')


def run(root, baseline, probe, cutoff):
    if root.exists():
        raise RuntimeError('Preexisting reset repair root; refuse silent resume')
    for source in (baseline, probe):
        if json.loads((source / 'status.json').read_text())['status'] != 'complete':
            raise ValueError('Required predecessor is not complete')
    physical = json.loads((probe / 'reset_safe/probe.json').read_text())
    if physical['max_retained_delta'] != 0 or physical['max_ankle_output_difference'] != 0:
        raise ValueError('Reset physical smoke did not pass')
    deadline = datetime.fromisoformat(cutoff).timestamp()
    core = {str(Path('/root/ASAP/humanoidverse') / name):
            sha(Path('/root/ASAP/humanoidverse') / name) for name in CORE}
    runtime = Path('/root/ASAP/research/asap_diagnostics/delta_reset_runtime.py')
    runtime_hash = sha(runtime)
    root.mkdir(parents=True)
    plan = {'created_utc': datetime.now(timezone.utc).isoformat(), 'cutoff_utc': cutoff,
            'baseline': str(baseline), 'physical_smoke': str(probe),
            'tasks': ['StepFBL1', 'SquatL1', 'CR7'],
            'intervention': 'Clear actions_closed_loop only for reset environments',
            'runtime': str(runtime), 'runtime_sha256': runtime_hash, 'core_hashes': core,
            'unchanged': ['zero height and foot-force noise', 'source model_6000', 'delta model_500',
                          'training seed', '1000 PPO updates', 'reward', 'curricula', 'optimizer settings',
                          'initialization', 'data', 'ordinary B evaluation', 'evaluation seeds 8101-8103'],
            'selection': 'Use every fixed-final model_1000 regardless of test outcome'}
    write(root / 'queue_plan.json', plan)
    original = json.loads((BASE / 'paper_eval_20261008/frozen_manifest.json').read_text())
    frozen, reports = [], {}

    def invariant():
        if sha(runtime) != runtime_hash or any(sha(path) != digest for path, digest in core.items()):
            raise ValueError('Runtime or core source changed during the experiment')
        idle_gpu()

    for task in plan['tasks']:
        command_file = baseline / task / 'commands/train_asap_ft.json'
        command = json.loads(command_file.read_text())['command']
        arguments = {arg.split('=', 1)[0].lstrip('+'): arg.split('=', 1)[1] for arg in command[5:]}
        if float(arguments['obs.noise_scales.base_pos_z']) != 0 or float(arguments['obs.noise_scales.feet_contact_force']) != 0:
            raise ValueError('Baseline is not the noiseless delta-input repair')
        if int(arguments['algo.config.num_learning_iterations']) != 1000:
            raise ValueError('Unexpected learning budget')
        work = root / task
        work.mkdir()
        for key in ('checkpoint', 'algo.config.policy_checkpoint'):
            expected = 'model_6000.pt' if key == 'checkpoint' else 'model_500.pt'
            if Path(arguments[key]).name != expected:
                raise ValueError('Unexpected input checkpoint')
            frozen.append({'task': task, 'key': key, 'path': arguments[key], 'sha256': sha(arguments[key])})
        overrides = replace(command[5:], {'env._target_': TARGET,
                    'experiment_dir': str(work / 'models/asap_ft'), 'experiment_name': 'asap_reset_repair'})
        write(root / 'frozen_manifest.json', frozen)
        invariant()
        write(root / 'status.json', {'status': 'running', 'stage': task + '/train'})
        launch(work, 'train', int(command[4]), overrides, 'train_asap_ft', deadline)
        final = work / 'models/asap_ft/model_1000.pt'
        if not final.exists():
            raise ValueError('Fixed-final checkpoint missing')
        trials = []
        for row in [r for r in original if r['task'] == task and r['method'] == 'asap_ft']:
            invariant()
            label = row['label']
            args = replace(row['overrides'], {'checkpoint': str(final),
                'eval_log_dir': str(work / 'tracking' / (label + '_config')),
                'env.config.dataset_record_path': str(work / 'tracking' / (label + '.pkl'))})
            write(root / 'status.json', {'status': 'running', 'stage': task + '/' + label})
            launch(work, 'eval', row['seed'], args, label, deadline)
            record = work / 'tracking' / (label + '.pkl')
            previous = baseline / task / 'tracking' / (label + '.pkl')
            write(work / (label + '_start_audit.json'), audit(previous, record))
            measured = json.loads(record.with_suffix('.json').read_text())
            trials.extend(dict(t, seed=row['seed']) for t in measured['trials'])
        reports[task] = {'summary': summarize(trials), 'trials': trials,
                         'checkpoint': str(final), 'checkpoint_sha256': sha(final)}
        write(work / 'comparison.json', reports[task])
        write(work / 'status.json', {'status': 'complete'})
        # Independent full config, input-hash, record and metric audit before continuing.
        subprocess.run(['/root/autodl-tmp/conda/envs/hvgym/bin/python',
                        str(BASE / 'audit_noise_repair.py'), '--root', str(root), '--task', task,
                        '--baseline-root', str(baseline), '--reset-repair',
                        '--output', str(work / 'publication_audit.json')], check=True)
        invariant()
        write(root / 'comparison.json', reports)
    write(root / 'status.json', {'status': 'complete', 'stage': 'reset_repair_comparison'})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work-dir', type=Path, required=True)
    p.add_argument('--baseline', type=Path, default=BASE / 'noise_repair_20261009')
    p.add_argument('--probe', type=Path, default=BASE / 'delta_reset_probe_20261009')
    p.add_argument('--cutoff', default='2026-10-09T09:00:00+00:00')
    a = p.parse_args()
    existed = a.work_dir.exists()
    try:
        run(a.work_dir, a.baseline, a.probe, a.cutoff)
    except Exception as exc:
        if not existed and (a.work_dir / 'queue_plan.json').exists():
            write(a.work_dir / 'status.json', {'status': 'failed', 'error': repr(exc)})
        raise
