"""Check frozen inputs, effective settings and saved fresh replay metrics."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import yaml

from audit_paper_evaluation import normalized

def replay_settings(config):
    # Replay observations differ from task-policy observations. Compare the full
    # relevant config families rather than assuming a history_actor key exists.
    selected = {k: config[k] for k in ('robot', 'simulator', 'terrain', 'domain_rand', 'obs', 'rewards', 'algo', 'env')}
    selected = json.loads(json.dumps(selected))
    selected['env']['config'].pop('dataset_record_path', None)
    selected.update({k: config[k] for k in ('num_envs', 'headless', 'seed')})
    return selected


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--asap-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.asap_dir))
    from research.asap_diagnostics.paper_replay_queue import score, FIELDS
    read = lambda path: json.loads(path.read_text())
    if read(args.root / 'status.json')['status'] != 'complete':
        raise ValueError('Fresh replay queue is incomplete')
    plan = read(args.root / 'queue_plan.json')
    results = read(args.root / 'comparison.json')
    if len(plan['jobs']) != 26 or set(results) != {r['label'] for r in plan['jobs']}:
        raise ValueError('Missing planned replay condition')
    audits, starts = {}, {}
    for row in plan['jobs']:
        directory = args.root / row['label']
        provenance = read(directory / 'provenance.json')
        source_path = Path(row['source_command'])
        source = read(source_path)['command']
        fresh = read(directory / 'commands/replay.json')['command']
        before, after = normalized(source[5:]), normalized(fresh[5:])
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        if changed != {'eval_log_dir', 'env.config.dataset_record_path'} or source[4] != fresh[4]:
            raise ValueError('Unexpected change beyond output paths')
        inputs, checkpoint = Path(before['robot.motion.motion_file']), Path(before['checkpoint'])
        for path, field in ((source_path, 'command_sha256'), (inputs, 'input_sha256'),
                            (checkpoint, 'checkpoint_sha256')):
            if sha(path) != provenance[field]:
                raise ValueError('Frozen source changed: ' + str(path))
        configs = [yaml.safe_load((Path(o['eval_log_dir']) / 'config.yaml').read_text())
                   for o in (before, after)]
        if replay_settings(configs[0]) != replay_settings(configs[1]):
            raise ValueError('Effective replay settings changed')
        old_path, fresh_path = Path(before['env.config.dataset_record_path']), Path(after['env.config.dataset_record_path'])
        old, actual, target = joblib.load(old_path), joblib.load(fresh_path), joblib.load(inputs)
        expected = {f'motion{i}' for i in range(66)}
        if set(old) != expected or set(actual) != expected or len(target) != 66:
            raise ValueError('Replay identities changed')
        differences = {k: max(float(np.max(np.abs(np.asarray(old[m][k][0]) - np.asarray(actual[m][k][0]))))
                              for m in actual) for k in FIELDS}
        if any(differences.values()):
            raise ValueError('Stored initialization changed')
        report = results[row['label']]
        if report['point_count'] != 24 or report['fps'] != 50 or len(report['cases']) != 66:
            raise ValueError('Invalid report point/rate/case budget')
        max_error = 0.
        for i, (key, reference) in enumerate(target.items()):
            case = report['cases'][i]
            if (case['key'], case['task'], case['group']) != (key, reference['dataset_task'], reference['dataset_group']):
                raise ValueError('Case identity differs')
            for horizon in (.25, .5, 1.):
                measured, saved = score(reference, actual[f'motion{i}'], horizon), case['horizons'][str(horizon)]
                if measured['complete'] != saved['complete'] or measured['scored_frames'] != saved['scored_frames']:
                    raise ValueError('Scored prefix/reset differs')
                if (measured['metrics'] is None) != (saved['metrics'] is None):
                    raise ValueError('Metric availability differs')
                if measured['metrics'] is not None:
                    for k, value in measured['metrics'].items():
                        error = abs(value - saved['metrics'][k])
                        max_error = max(max_error, error)
                        if not np.isclose(value, saved['metrics'][k], rtol=1e-10, atol=1e-10):
                            raise ValueError('Saved metric differs from actual records')
        audits[row['label']] = {'initial_max_difference': differences, 'effective_settings_match': True,
                               'scored_case_count': 66, 'max_recomputed_metric_difference': max_error,
                               'old_record_sha256': sha(old_path), 'fresh_record_sha256': sha(fresh_path),
                               'source_provenance': provenance, 'replay_seed': int(source[4])}
        starts[row['label']] = {k: np.stack([np.asarray(actual[f'motion{i}'][k][0]) for i in range(66)]) for k in FIELDS}
    pairs = [
        ('controlled_squat_20261008__source20_zero', 'controlled_squat_20261008__controlled_delta'),
        ('torque_20261008__source20_zero', 'torque_20261008__torque'),
        ('wave_20261008_unchanged__source20_zero', 'wave_20261008_unchanged__torque'),
        ('wave_20261008_wave__source20_zero', 'wave_20261008_wave__torque'),
    ]
    for root, baseline in (('content_20261008', 'content_20261008_uniform__source20_zero'),
                           ('content_repeat_20261008', 'repeat_controls_20261008__source20_zero')):
        pairs += [(baseline, root + '_' + rule + '__learned') for rule in ('uniform', 'coverage', 'joint_range')]
    paired = {}
    for baseline, model in pairs:
        differences = {k: float(np.max(np.abs(starts[baseline][k] - starts[model][k]))) for k in FIELDS}
        if audits[baseline]['source_provenance']['input_sha256'] != audits[model]['source_provenance']['input_sha256'] or audits[baseline]['replay_seed'] != audits[model]['replay_seed']:
            raise ValueError('Declared replay baseline has a different input or seed')
        paired[model] = {'baseline': baseline, 'input_and_seed_match': True,
                         'initial_max_difference': differences, 'stored_starts_match': not any(differences.values())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'scope': 'Actual records, frozen sources, settings and recomputed per-case metrics; no hidden solver-state claim',
                                      'jobs_checked': len(audits), 'audit': audits, 'paired_baseline_audits': paired,
                                      'audit_implementation_note': 'The initial task-policy config helper expected history_actor observations absent in replay. The final audit compares full replay config families. Physics files and runs were unchanged.'}, indent=2) + '\n')
    print('PASS: all 26 fresh replay conditions, stored starts, settings and measured metrics.')


if __name__ == '__main__':
    main()
