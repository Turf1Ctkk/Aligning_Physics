"""Audit a completed task without requiring the other repair tasks to finish."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import yaml
from audit_paper_evaluation import normalized
from audit_task_evaluations import extract, effective_extract

BASE = Path('/root/autodl-tmp/aligning_physics')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flatten(value, prefix=''):
    out = {}
    for key, item in value.items():
        name = prefix + '.' + key if prefix else key
        if isinstance(item, dict):
            out.update(flatten(item, name))
        else:
            out[name] = item
    return out


def same(actual, expected):
    if isinstance(actual, dict):
        if set(actual) != set(expected):
            raise ValueError('Report keys differ')
        for key in actual:
            same(actual[key], expected[key])
    elif isinstance(actual, (float, int)) and not isinstance(actual, bool):
        if not np.isclose(actual, expected, rtol=0, atol=1e-10):
            raise ValueError('Recomputed numeric result differs')
    elif actual != expected:
        raise ValueError('Recomputed result differs')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--task', choices=('SquatL1', 'CR7', 'StepFBL1'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, '/root/ASAP')
    from research.asap_diagnostics.paper_metrics import trial_metrics, summarize
    from research.asap_diagnostics.paper_eval_queue import audit
    work = args.root / args.task
    if json.loads((work / 'status.json').read_text())['status'] != 'complete':
        raise ValueError('Task is incomplete')
    source = BASE / ('controlled_squat_20261008' if args.task == 'SquatL1'
                     else 'extend_tasks_20261008/' + args.task)
    old_command_file = source / 'commands/train_asap_ft.json'
    new_command_file = work / 'commands/train_asap_ft.json'
    before_cmd = json.loads(old_command_file.read_text())['command']
    after_cmd = json.loads(new_command_file.read_text())['command']
    if before_cmd[:5] != after_cmd[:5]:
        raise ValueError('Training launcher or seed changed')
    before_args, after_args = normalized(before_cmd[5:]), normalized(after_cmd[5:])
    allowed = {'experiment_dir', 'experiment_name', 'obs.noise_scales.base_pos_z',
               'obs.noise_scales.feet_contact_force'}
    changes = {k for k in before_args.keys() | after_args.keys() if before_args.get(k) != after_args.get(k)}
    if changes != allowed:
        raise ValueError('Unexpected training command intervention')
    configs = [flatten(yaml.safe_load((q / 'models/asap_ft/config.yaml').read_text()))
               for q in (source, work)]
    config_changes = {k: [configs[0].get(k), configs[1].get(k)] for k in configs[0].keys() | configs[1].keys()
                      if configs[0].get(k) != configs[1].get(k)}
    if set(config_changes) != allowed or config_changes['obs.noise_scales.base_pos_z'] != [1., 0.] or config_changes['obs.noise_scales.feet_contact_force'] != [.01, 0.]:
        raise ValueError('Actual training configuration differs beyond planned repair')
    frozen = [r for r in json.loads((args.root / 'frozen_manifest.json').read_text()) if r['task'] == args.task]
    if {r['key'] for r in frozen} != {'checkpoint', 'algo.config.policy_checkpoint'}:
        raise ValueError('Missing frozen source or calibrator')
    for row in frozen:
        if row['path'] != before_args[row['key']] or sha(Path(row['path'])) != row['sha256']:
            raise ValueError('Frozen input checkpoint changed')
    final = work / 'models/asap_ft/model_1000.pt'
    report = json.loads((work / 'comparison.json').read_text())
    if report['checkpoint'] != str(final) or report['checkpoint_sha256'] != sha(final):
        raise ValueError('Evaluation did not use fixed-final model')
    original_manifest = json.loads((BASE / 'paper_eval_20261008/frozen_manifest.json').read_text())
    jobs = [r for r in original_manifest if r['task'] == args.task and r['method'] == 'asap_ft']
    if {r['seed'] for r in jobs} != {8101, 8102, 8103} or len(jobs) != 3:
        raise ValueError('Unexpected evaluation seeds')
    trials, checks = [], []
    for row in jobs:
        command_file = work / 'commands' / (row['label'] + '.json')
        new_cmd = json.loads(command_file.read_text())['command']
        old_args, new_args = normalized(row['overrides']), normalized(new_cmd[5:])
        if new_cmd[4] != str(row['seed']):
            raise ValueError('Deployment seed changed')
        changed = {k for k in old_args.keys() | new_args.keys() if old_args.get(k) != new_args.get(k)}
        if changed != {'checkpoint', 'eval_log_dir', 'env.config.dataset_record_path'} or new_args['checkpoint'] != str(final):
            raise ValueError('Unexpected evaluation change')
        old_record, new_record = Path(row['old_record']), Path(new_args['env.config.dataset_record_path'])
        start_audit = audit(old_record, new_record)
        def effective(record):
            path = record.parent / (record.stem + '_config/config.yaml')
            return effective_extract(extract(yaml.safe_load(path.read_text())))
        settings = effective(new_record)
        if effective(old_record) != settings:
            raise ValueError('Effective deployment settings changed')
        records = joblib.load(new_record)
        measured = json.loads(new_record.with_suffix('.json').read_text())
        if {t['trial'] for t in measured['trials']} != set(range(32)) or len(measured['trials']) != 32:
            raise ValueError('Missing deployment trial')
        recomputed = []
        for trial in measured['trials']:
            actual = trial_metrics(records['motion' + str(trial['trial'])])
            expected = {k: v for k, v in trial.items() if k != 'trial'}
            same(actual, expected)
            recomputed.append(dict(actual, trial=trial['trial']))
        same(summarize(recomputed), measured['summary'])
        trials.extend(dict(t, seed=row['seed']) for t in recomputed)
        checks.append({'seed': row['seed'], 'start_audit': start_audit, 'effective_settings': settings,
                      'metrics_recomputed': 32, 'command_sha256': sha(command_file)})
    same(summarize(trials), report['summary'])
    if len(report['trials']) != 96 or {(t['seed'], t['trial']) for t in report['trials']} != {(t['seed'], t['trial']) for t in trials}:
        raise ValueError('Aggregate trial identities differ')
    indexed = {(t['seed'], t['trial']): t for t in trials}
    for trial in report['trials']:
        same(indexed[trial['seed'], trial['trial']], trial)
    result = {'task': args.task, 'training_seed': int(after_cmd[4]), 'training_config_changes': config_changes,
              'old_training_command_sha256': sha(old_command_file), 'new_training_command_sha256': sha(new_command_file),
              'frozen_inputs': frozen, 'final_checkpoint_sha256': sha(final), 'evaluation_audit': checks,
              'scope': 'Two noise channels only; all recorded starts and effective evaluation settings match. All metrics recomputed. One paired training seed.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:', args.task, 'training intervention, frozen inputs, evaluation settings/starts and all trial metrics.')


if __name__ == '__main__':
    main()
