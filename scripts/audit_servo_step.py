"""Verify repaired Step training commands/configs and recompute all B metrics."""
import argparse
import json
from pathlib import Path
import sys

import joblib
import yaml

from audit_noise_repair import flatten, same, sha
from audit_paper_evaluation import normalized
from audit_task_evaluations import extract, effective_extract


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--calibration-only', action='store_true')
    a = p.parse_args()
    sys.path.insert(0, '/root/ASAP')
    from research.asap_diagnostics.paper_metrics import trial_metrics, summarize
    from research.asap_diagnostics.paper_eval_queue import audit
    plan = json.loads((a.root / 'queue_plan.json').read_text())
    frozen = json.loads((a.root / 'frozen_manifest.json').read_text())
    if any(sha(Path(path)) != digest for path, digest in frozen.items()):
        raise ValueError('Frozen inputs/core changed')
    source_file = Path(plan['training_template'])
    source = source_file.parent.parent
    work = a.directory
    if a.calibration_only:
        original = Path('/root/autodl-tmp/aligning_physics/controlled_squat_20261008/models/delta/config.yaml')
        old = flatten(yaml.safe_load(original.read_text()))
        new = flatten(yaml.safe_load((work / 'models/delta/config.yaml').read_text()))
        changes = {'seed': new['seed'], 'experiment_dir': str(work / 'models/delta'),
            'env.config.sampling_manifest': str(work / 'sampling_manifest.json'),
            'robot.motion.motion_file': str(work / 'datasets/mixed30.pkl')}
        if new['seed'] not in plan['calibration_seeds'] or new != dict(old, **changes):
            differences = {k: [dict(old, **changes).get(k), new.get(k)] for k in old.keys() | new.keys()
                           if dict(old, **changes).get(k) != new.get(k)}
            raise ValueError('Unexpected calibration recipe: ' + repr(differences))
        selection = json.loads((work / 'delta_selection.json').read_text())
        candidates = [(json.loads((work / ('delta_%d_paper_metrics.json' % i)).read_text())['paper_metrics']['metrics']['global_position_mm'],
                       str(work / 'models/delta' / ('model_%d.pt' % i))) for i in (500, 1000)]
        loss, checkpoint = min(candidates, key=lambda row: row[0])
        if selection['checkpoint'] != checkpoint or selection['validation_loss'] != loss or sha(Path(checkpoint)) != selection['sha256']:
            raise ValueError('Validation selection changed')
        data = joblib.load(work / 'datasets/mixed30.pkl')
        if len(data) != 18 or sum(len(m['dof'])-1 for m in data.values()) != 954:
            raise ValueError('Calibration budget changed')
        (work / 'calibration_audit.json').write_text(json.dumps({'actual_recipe_changes': changes,
            'template_sha256': sha(original), 'selected_checkpoint': selection, 'datasets_frozen': True,
            'selected_transitions': 954, 'selection_rule': 'Minimum heldout validation global body MPJPE;500/1000 only'}, indent=2)+'\n')
        print('PASS calibration recipe/data/budget/validation selection:', work)
        return
    report = json.loads((work / 'comparison.json').read_text())
    if report['training_seed'] not in plan['policy_seeds']:
        raise ValueError('Unexpected policy seed')
    before = json.loads(source_file.read_text())['command']
    new_file = work / 'commands/train_asap_ft.json'
    after = json.loads(new_file.read_text())['command']
    seed = report['training_seed']
    if before[:4] != after[:4] or after[4] != str(seed):
        raise ValueError('Training launcher or seed mismatch')
    replacements = {'algo.config.policy_checkpoint': report['calibrator'], 'seed': str(seed),
        'experiment_dir': str(work / 'models/asap_ft'), 'experiment_name': 'servo_step_' + work.name,
        'env.config.add_extra_action': str(report['correction_enabled'])}
    expected = dict(normalized(before[5:]), **replacements)
    if normalized(after[5:]) != expected:
        raise ValueError('Unexpected training command changes')
    old_config = flatten(yaml.safe_load((source / 'models/asap_ft/config.yaml').read_text()))
    new_config = flatten(yaml.safe_load((work / 'models/asap_ft/config.yaml').read_text()))
    expected_config = dict(old_config, **dict(replacements, seed=seed))
    expected_config['env.config.add_extra_action'] = report['correction_enabled']
    if new_config != expected_config:
        changes = {k: [expected_config.get(k), new_config.get(k)] for k in expected_config.keys() | new_config.keys()
                   if expected_config.get(k) != new_config.get(k)}
        raise ValueError('Unexpected actual training config: ' + repr(changes))
    final = work / 'models/asap_ft/model_1000.pt'
    if report['checkpoint'] != str(final) or sha(final) != report['checkpoint_sha256']:
        raise ValueError('Not fixed-final model')
    trials, checks = [], []
    for eval_seed in (8101, 8102, 8103):
        label = 'asap_ft_seed%d' % eval_seed
        old, new = [json.loads((folder / 'commands' / (label + '.json')).read_text())['command'] for folder in (source, work)]
        record = work / 'tracking' / (label + '.pkl')
        expected_eval = dict(normalized(old[5:]), **{'checkpoint': str(final),
            'eval_log_dir': str(work / 'tracking' / (label + '_config')), 'env.config.dataset_record_path': str(record)})
        if old[:5] != new[:5] or normalized(new[5:]) != expected_eval:
            raise ValueError('Unexpected evaluation change')
        start = audit(source / 'tracking' / (label + '.pkl'), record)
        settings = [effective_extract(extract(yaml.safe_load((folder / 'tracking' / (label + '_config/config.yaml')).read_text())))
                    for folder in (source, work)]
        if settings[0] != settings[1]:
            raise ValueError('Effective B settings changed')
        data, measured = joblib.load(record), json.loads(record.with_suffix('.json').read_text())
        if len(measured['trials']) != 32 or {t['trial'] for t in measured['trials']} != set(range(32)):
            raise ValueError('Missing trial identity')
        recomputed = []
        for t in measured['trials']:
            actual = trial_metrics(data['motion%d' % t['trial']])
            same(actual, {k: v for k, v in t.items() if k != 'trial'})
            recomputed.append(dict(actual, trial=t['trial']))
        same(summarize(recomputed), measured['summary'])
        trials.extend(dict(t, seed=eval_seed) for t in recomputed)
        checks.append({'seed': eval_seed, 'start_audit': start, 'effective_settings': settings[1], 'recomputed_trials': 32})
    same(summarize(trials), report['summary'])
    index = {(t['seed'], t['trial']): t for t in trials}
    if len(report['trials']) != 96 or {(t['seed'], t['trial']) for t in report['trials']} != set(index):
        raise ValueError('Aggregate trial identities mismatch')
    for t in report['trials']:
        same(t, index[(t['seed'], t['trial'])])
    result = {'scope': 'Actual repairedStep train recipe, fixed-final policy, stored starts/effectiveB settings and recomputed metrics',
        'training_seed': seed, 'calibrator': report['calibrator'], 'calibrator_sha256': sha(Path(report['calibrator'])),
        'source_sha256': sha(Path(expected['checkpoint'])), 'final_checkpoint_sha256': sha(final),
        'training_command_sha256': sha(new_file), 'training_config_changes': {k: [old_config.get(k), v] for k, v in new_config.items() if old_config.get(k) != v},
        'evaluation_audit': checks}
    (work / 'publication_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:', work.name, 'actualStep settings and all96 trial metrics.')


if __name__ == '__main__':
    main()
