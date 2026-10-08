"""Audit completed fresh recording, frozen overrides and actual effective config."""
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import yaml
from audit_task_evaluations import extract, effective_extract

FIELDS=('dof','dof_vel','root_trans_offset','root_rot','root_lin_vel','root_ang_vel','action','motion_times')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(arguments):
    out={}
    for a in arguments:
        if '=' in a:
            key, value=a.split('=',1)
            key=key.lstrip('+')
            if key in out:raise ValueError('Duplicate effective override')
            out[key]=value
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if json.loads((args.root/'status.json').read_text())['status']!='complete':
        raise ValueError('Fresh physics queue is incomplete')
    manifest=json.loads((args.root/'frozen_manifest.json').read_text())
    checked={}
    for row in manifest:
        source=Path(row['source_command'])
        command=json.loads(source.read_text())['command']
        if digest(source)!=row['source_command_sha256'] or digest(Path(row['checkpoint']))!=row['checkpoint_sha256']:
            raise ValueError('Frozen source changed')
        old_overrides=normalized(command[5:])
        fresh_overrides=normalized(row['overrides'])
        changed={k for k in set(old_overrides)|set(fresh_overrides) if old_overrides.get(k)!=fresh_overrides.get(k)}
        if changed!={'algo._target_','eval_log_dir','env.config.dataset_record_path'}:
            raise ValueError('Evaluation changes beyond recorder and paths')
        fresh=Path(fresh_overrides['env.config.dataset_record_path'])
        old=Path(row['old_record'])
        configs=[]
        for record in (old,fresh):
            config=record.parent/(record.stem+'_config/config.yaml')
            configs.append(extract(yaml.safe_load(config.read_text())))
        if effective_extract(configs[0])!=effective_extract(configs[1]):
            raise ValueError('Effective physics, noise or termination differs')
        before,after=joblib.load(old),joblib.load(fresh)
        if set(before)!=set(after) or len(after)!=32:raise ValueError('Trial identities differ')
        difference={k:max(float(np.max(np.abs(before[m][k][0]-after[m][k][0]))) for m in after) for k in FIELDS}
        if any(difference.values()):raise ValueError('Initialization differs')
        for m,r in after.items():
            if r['paper_body_pos'].shape!=(len(before[m]['dof']),27,3) or not np.array_equal(r['body_pos'],r['paper_body_pos'][:,:24]):
                raise ValueError('Fresh extended point recording is invalid')
        key=row['task']+'/'+row['label']
        checked[key]={'initial_max_difference':difference,'effective_settings_match':True,
                      'actual_record_sha256':digest(fresh),'checkpoint_sha256':row['checkpoint_sha256'],
                      'effective_settings':effective_extract(configs[1]),
                      'raw_setting_differences':{k:{'old':configs[0][k],'fresh':v} for k,v in configs[1].items() if v!=configs[0][k]}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'scope':'Fresh and historical stored starts and effective settings; no hidden solver-state claim',
                                      'jobs_checked':len(checked),'audit':checked},indent=2)+'\n')
    print('PASS: all fresh trial starts, frozen checkpoint/overrides and actual effective settings.')


if __name__=='__main__':main()
