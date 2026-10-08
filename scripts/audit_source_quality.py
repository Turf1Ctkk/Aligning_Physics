"""Check the actual source-domain commands/configs and recompute each trial."""
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import yaml
from audit_task_evaluations import extract, effective_extract
from audit_paper_evaluation import normalized


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args()
    import sys
    sys.path.insert(0, '/root/ASAP')
    from research.asap_diagnostics.paper_metrics import trial_metrics
    if json.loads((a.root/'status.json').read_text())['status']!='complete':
        raise ValueError('Source physics audit incomplete')
    plan=json.loads((a.root/'queue_plan.json').read_text())
    checks=[]
    for row in plan['jobs']:
        work=a.root/row['task']/row['method']; label=row['label']
        original=normalized(row['overrides'])
        fresh=normalized(json.loads((work/'commands'/(label+'.json')).read_text())['command'][5:])
        changes={k for k in set(original)|set(fresh) if original.get(k)!=fresh.get(k)}
        expected={'robot.control.stiffness.ankle_pitch','robot.control.stiffness.ankle_roll','eval_log_dir','env.config.dataset_record_path'}
        if changes!=expected:raise ValueError('Unexpected source audit command change')
        checkpoint=Path(row['checkpoint'])
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=row['checkpoint_sha256']:raise ValueError('Checkpoint changed')
        old_config=Path(original['eval_log_dir'])/'config.yaml'
        config=Path(fresh['eval_log_dir'])/'config.yaml'
        before=effective_extract(extract(yaml.safe_load(old_config.read_text())))
        after=effective_extract(extract(yaml.safe_load(config.read_text())))
        if after['robot.control.stiffness']['ankle_pitch']!=20 or after['robot.control.stiffness']['ankle_roll']!=20:
            raise ValueError('Source gain wrong')
        after['robot.control.stiffness']['ankle_pitch']=16
        after['robot.control.stiffness']['ankle_roll']=16
        if before!=after:raise ValueError('Settings changed beyond gains')
        file=Path(fresh['env.config.dataset_record_path']); records=joblib.load(file)
        report=json.loads(file.with_suffix('.json').read_text())
        if set(records)!={f'motion{i}' for i in range(32)}:raise ValueError('Missing source trial')
        for trial in report['trials']:
            actual=trial_metrics(records['motion'+str(trial['trial'])])
            for flag in ('complete','paper_tracking_success','first_reset_row'):
                if actual[flag]!=trial[flag]:raise ValueError('Stored success inconsistent')
            for key in actual['metrics']:
                if not np.isclose(actual['metrics'][key],trial['metrics'][key],atol=1e-10):raise ValueError('Stored metrics inconsistent')
        checks.append({'task':row['task'],'method':row['method'],'seed':row['seed'],
            'checkpoint_sha256':row['checkpoint_sha256'],'record_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
            'only_gains_changed':True,'trials_recomputed':32})
    a.output.write_text(json.dumps({'jobs_checked':len(checks),'audit':checks,
        'scope':'Same checkpoints, seeds and effective B settings except source gains20. Post-warm states may differ physically; no pre-step state equality claimed.'},indent=2)+'\n')
    print('PASS: 18 source jobs, unchanged checkpoint/seed/settings except gains; actual success/metrics recomputed.')


if __name__=='__main__':main()
