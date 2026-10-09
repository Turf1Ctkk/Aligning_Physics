"""Predeclared Random/Servo calibration comparison; repaired Step transfer; cutoff-aware."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time

import joblib
import numpy as np

from research.asap_diagnostics.controlled_pipeline import launch, write, delta_overrides
from research.asap_diagnostics.noise_repair_queue import replace, sha
from research.asap_diagnostics.paper_eval_queue import audit
from research.asap_diagnostics.paper_metrics import summarize
from research.asap_diagnostics.paper_replay_queue import score, aggregate
from research.asap_diagnostics.reset_repair_queue import CORE, idle_gpu

BASE = Path('/root/autodl-tmp/aligning_physics')
ARMS = ('random', 'servo')


def run(root, prepared, cutoff):
    if root.exists():
        raise RuntimeError('Preexisting learning root; refuse silent resume')
    if json.loads((prepared / 'status.json').read_text())['status'] != 'complete':
        raise ValueError('CPU selection is incomplete')
    deadline = datetime.fromisoformat(cutoff).timestamp()
    source = BASE / 'reset_repair_20261009/StepFBL1'
    if json.loads((source.parent / 'status.json').read_text())['status'] != 'complete':
        raise ValueError('Physical repair predecessor incomplete')
    root.mkdir(parents=True)
    selection = json.loads((prepared / 'selection_manifest.json').read_text())
    if selection['unique_transitions_per_arm'] != 954:
        raise ValueError('Unexpected data budget')
    shutil.copy2(prepared / 'selection_manifest.json', root / 'selection_manifest.json')
    template = json.loads((source / 'commands/train_asap_ft.json').read_text())['command']
    old_args = {x.split('=', 1)[0].lstrip('+'): x.split('=', 1)[1] for x in template[5:]}
    frozen = {str(Path('/root/ASAP/humanoidverse') / name): sha(Path('/root/ASAP/humanoidverse') / name) for name in CORE}
    for module in ('delta_reset_runtime.py', 'select_servo.py', 'servo_step_pipeline.py', 'servo_replay_metrics.py'):
        path = Path('/root/ASAP/research/asap_diagnostics') / module
        frozen[str(path)] = sha(path)
    for name in ('audit_servo_step.py', 'audit_noise_repair.py', 'audit_paper_evaluation.py', 'audit_task_evaluations.py'):
        path = BASE / name
        frozen[str(path)] = sha(path)
    for key in ('checkpoint', 'robot.motion.motion_file'):
        frozen[old_args[key]] = sha(Path(old_args[key]))
    for path in (source / 'commands').glob('*.json'):
        frozen[str(path)] = sha(path)
    for arm in ('random', 'servo', 'low_error'):
        for name in ('selected.pkl', 'sampling_manifest.json'):
            path = prepared / arm / name
            frozen[str(path)] = sha(path)
    frozen[str(prepared / 'selection_manifest.json')] = sha(prepared / 'selection_manifest.json')
    controlled = BASE / 'controlled_squat_20261008'
    for split in ('val', 'test'):
        path = controlled / 'datasets' / (split + '_cases.pkl')
        frozen[str(path)] = sha(path)
    write(root / 'frozen_manifest.json', frozen)
    original_plan = json.loads((controlled / 'plan.json').read_text())
    design = {'created_utc': datetime.now(timezone.utc).isoformat(), 'cutoff_utc': cutoff,
        'prepared': str(prepared), 'failed_preflight': str(BASE / 'servo_step_preflight_20261009'),
        'task': 'StepFBL1', 'main_arms': list(ARMS), 'data_transitions': 954, 'parent_groups': 18,
        'calibration_seeds': [20309009, 20309010], 'policy_seeds': [20310009, 20310010],
        'fixed_replay_seed': 20309109, 'deployment_seeds': [8101, 8102, 8103],
        'calibration_updates': 1000, 'policy_updates': 1000, 'validation_checkpoints': [500, 1000],
        'primary_endpoint': 'Equal task/parent1s heldout global body MPJPE; calibration and control claims separate',
        'stratified_endpoint': 'Perjoint small/medium/large target servo-error transition bins from fixed training edges',
        'policy_selection': 'Every final model_1000, both main arms regardless of test outcomes',
        'control': 'Fresh primary-seed FT-only; repeat compares main arms at its shared seed',
        'repeat_gate': 'Run second paired main seed only with>=2.2hours left, else explicit skipped',
        'low_error_gate': 'Supplemental calibration only after main/repeat decision, if>=50minutes remain; otherwise skipped',
        'training_template': str(source / 'commands/train_asap_ft.json'),
        'hypothesis': 'Unsaturated perjoint servo-error sign/magnitude coverage improves replay over random at fixed budget; Step transfer tested separately',
        'scope': 'SameIsaacGym source20 target16; mixed calibration parents; downstreamStep chosen using earlier evidence; contact is a proxy, exact continuous velocity/contact matching is not claimed'}
    write(root / 'queue_plan.json', design)

    def invariant():
        if any(sha(Path(path)) != digest for path, digest in frozen.items()):
            raise ValueError('Frozen input/runtime/core changed')
        idle_gpu()

    import research.asap_diagnostics.multi_motion_pipeline as replay
    replay.launch = lambda w, mode, seed, arguments, log: launch(w, mode, seed, arguments, log.stem, deadline)
    reports = {}

    def physics(work, plan, checkpoint, split, label, kp=20, zero=False):
        invariant()
        eval_plan = dict(plan, training_seed=20309009)
        write(root / 'status.json', {'status': 'running', 'stage': str(work.relative_to(root)) + '/' + label})
        result = replay.evaluate_batch(work, eval_plan, checkpoint, split, label, kp=kp, zero=zero)
        if split in ('val', 'test'):
            from research.asap_diagnostics.servo_replay_metrics import measured
            report = measured(work, checkpoint, label, selection['servo_magnitude_edges_rad'], split=split)
            write(work / (label + '_paper_metrics.json'), report)
            if split == 'test' and label in ('learned', 'source20_zero'):
                zero = root / 'primary/random/evaluation/test/source20_zero.pkl'
                if zero.exists():
                    from research.asap_diagnostics.paper_eval_queue import FIELDS
                    reference, actual = joblib.load(zero), joblib.load(work / 'evaluation/test/learned.pkl')
                    if set(reference) != set(actual):
                        raise ValueError('Replay startup case identities changed')
                    for key in reference:
                        for field in FIELDS:
                            if not np.array_equal(np.asarray(reference[key][field])[0], np.asarray(actual[key][field])[0]):
                                raise ValueError('Replay startup differs from shared source-zero: ' + key + '/' + field)
                    write(work / 'replay_start_audit.json', {'source_zero_sha256': sha(zero),
                        'learned_sha256': sha(work / 'evaluation/test/learned.pkl'), 'cases': len(actual), 'fields': list(FIELDS), 'exact': True})
        return result

    def policy(work, plan, calibrator, seed, enabled=True):
        invariant()
        args = replace(template[5:], {'algo.config.policy_checkpoint': str(calibrator),
            'seed': str(seed), 'experiment_dir': str(work / 'models/asap_ft'),
            'experiment_name': 'servo_step_' + work.name, 'env.config.add_extra_action': str(enabled)})
        write(root / 'status.json', {'status': 'running', 'stage': str(work.relative_to(root)) + '/policy_train'})
        launch(work, 'train', seed, args, 'train_asap_ft', deadline)
        final = work / 'models/asap_ft/model_1000.pt'
        trials = []
        for eval_seed in (8101, 8102, 8103):
            invariant()
            label = 'asap_ft_seed%d' % eval_seed
            old = json.loads((source / 'commands' / (label + '.json')).read_text())['command']
            arguments = replace(old[5:], {'checkpoint': str(final), 'eval_log_dir': str(work / 'tracking' / (label + '_config')),
                'env.config.dataset_record_path': str(work / 'tracking' / (label + '.pkl'))})
            write(root / 'status.json', {'status': 'running', 'stage': str(work.relative_to(root)) + '/' + label})
            launch(work, 'eval', eval_seed, arguments, label, deadline)
            record = work / 'tracking' / (label + '.pkl')
            write(work / (label + '_start_audit.json'), audit(source / 'tracking' / (label + '.pkl'), record))
            trials.extend(dict(t, seed=eval_seed) for t in json.loads(record.with_suffix('.json').read_text())['trials'])
        result = {'summary': summarize(trials), 'trials': trials, 'checkpoint': str(final),
            'checkpoint_sha256': sha(final), 'training_seed': seed, 'calibrator': str(calibrator), 'correction_enabled': enabled}
        write(work / 'comparison.json', result)
        subprocess.run(['/root/autodl-tmp/conda/envs/hvgym/bin/python', str(BASE / 'audit_servo_step.py'),
                        '--root', str(root), '--directory', str(work)], check=True)
        write(work / 'status.json', {'status': 'complete'})
        return result

    def calibration(work, plan):
        invariant()
        write(root / 'status.json', {'status': 'running', 'stage': str(work.relative_to(root)) + '/calibration_train'})
        launch(work, 'train', plan['training_seed'], delta_overrides(work, plan, 1000), 'train_delta', deadline)
        candidates = []
        for iteration in (500, 1000):
            checkpoint = work / 'models/delta' / ('model_%d.pt' % iteration)
            result = physics(work, plan, checkpoint, 'val', 'delta_%d' % iteration)
            summary = json.loads((work / ('delta_%d_paper_metrics.json' % iteration)).read_text())
            if summary['complete_cases'] != summary['total_cases']:
                raise ValueError('Incomplete validation; preserve and stop')
            candidates.append((summary['paper_metrics']['metrics']['global_position_mm'], checkpoint))
        loss, chosen = min(candidates, key=lambda row: row[0])
        write(work / 'delta_selection.json', {'checkpoint': str(chosen), 'sha256': sha(chosen),
            'validation_loss': loss, 'candidates': [{'loss': v, 'checkpoint': str(p)} for v, p in candidates]})
        frozen[str(chosen)] = sha(chosen)
        write(root / 'frozen_manifest.json', frozen)
        physics(work, plan, chosen, 'test', 'learned')
        subprocess.run(['/root/autodl-tmp/conda/envs/hvgym/bin/python', str(BASE / 'audit_servo_step.py'),
                        '--root', str(root), '--directory', str(work), '--calibration-only'], check=True)
        return chosen

    def prepare(work, arm):
        (work / 'datasets').mkdir(parents=True)
        for target in ('mixed30.pkl', 'train_check_cases.pkl'):
            shutil.copy2(prepared / arm / 'selected.pkl', work / 'datasets' / target)
        shutil.copy2(prepared / arm / 'sampling_manifest.json', work / 'sampling_manifest.json')
        for split in ('val', 'test'):
            shutil.copy2(controlled / 'datasets' / (split + '_cases.pkl'), work / 'datasets' / (split + '_cases.pkl'))
        if sha(work / 'datasets/mixed30.pkl') != frozen[str(prepared / arm / 'selected.pkl')]:
            raise ValueError('Copied selection differs')
        for file in list((work / 'datasets').glob('*.pkl')) + [work / 'sampling_manifest.json']:
            frozen[str(file)] = sha(file)
        write(root / 'frozen_manifest.json', frozen)

    for index, run_name in enumerate(('primary', 'repeat')):
        if index and deadline-time.time() < 2.2*3600:
            write(root / 'repeat/status.json', {'status': 'skipped', 'reason': 'Insufficient cutoff margin'})
            break
        plan = dict(original_plan, training_seed=design['calibration_seeds'][index])
        write(root / run_name / 'plan.json', plan)
        reports[run_name] = {}
        for arm in ARMS:
            work = root / run_name / arm
            prepare(work, arm)
            original_delta = Path(old_args['algo.config.policy_checkpoint'])
            if index == 0:
                physics(work, plan, original_delta, 'train_check', 'same16_zero', kp=16, zero=True)
            calibrator = calibration(work, plan)
            if index == 0 and arm == 'random':
                for label, kp in (('same16_zero', 16), ('source20_zero', 20)):
                    physics(work, plan, calibrator, 'test', label, kp=kp, zero=True)
            reports[run_name][arm] = policy(work, plan, calibrator, design['policy_seeds'][index])
            write(root / 'comparison.json', reports)
        if index == 0:
            calibrator = Path(reports['primary']['random']['calibrator'])
            reports['primary']['ft_only'] = policy(root / 'primary/ft_only', plan, calibrator, design['policy_seeds'][0], enabled=False)
            write(root / 'comparison.json', reports)
        write(root / run_name / 'status.json', {'status': 'complete'})
    if deadline-time.time() >= 50*60:
        work = root / 'low_error'
        prepare(work, 'low_error')
        plan = dict(original_plan, training_seed=design['calibration_seeds'][0])
        physics(work, plan, Path(old_args['algo.config.policy_checkpoint']), 'train_check', 'same16_zero', kp=16, zero=True)
        calibration(work, plan)
        write(work / 'status.json', {'status': 'complete', 'scope': 'Supplemental calibration only, no policy selection'})
    else:
        write(root / 'low_error/status.json', {'status': 'skipped', 'reason': 'Insufficient cutoff margin'})
    invariant()
    write(root / 'status.json', {'status': 'complete', 'stage': 'servo_error_hypothesis', 'completed_runs': list(reports)})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work-dir', type=Path, required=True)
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--cutoff', default='2026-10-09T09:00:00+00:00')
    a = p.parse_args(); existed = a.work_dir.exists()
    try:
        run(a.work_dir, a.prepared, a.cutoff)
    except Exception as exc:
        if not existed and a.work_dir.exists():
            write(a.work_dir / 'status.json', {'status': 'failed', 'error': repr(exc)})
        raise
