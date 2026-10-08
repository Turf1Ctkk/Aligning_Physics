"""Publish the frozen source-policy quality check, with target results beside it."""
import argparse
import json
from pathlib import Path
from report_paper_evaluation import checked


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if json.loads((a.root/'status.json').read_text())['status']!='complete':raise ValueError('Incomplete source physics')
    audit=json.loads((a.root/'publication_audit.json').read_text())
    if audit['jobs_checked']!=18:raise ValueError('Source config audit incomplete')
    results=json.loads((a.root/'comparison.json').read_text())
    repo=Path(__file__).resolve().parents[1]
    rows=['# Source-policy quality', '',
          'This additional physical test uses the original and FT-only checkpoints. It changes only ankle gains from target16 to source20, plus output paths. Seeds, initialization, noise, references and termination settings remain the same. All actual configs and trial metrics were checked.', '',
          '| Task | Policy | Source A success (%) | Target B success (%) | Source first-second E_g-mpjpe (mm) | Target first-second E_g-mpjpe (mm) |',
          '|---|---|---:|---:|---:|---:|']
    for task in ('SquatL1','CR7','StepFBL1'):
        target=json.loads((repo/'results/paper_evaluation'/(task+'.json')).read_text())
        for method,name in [('vanilla','Original'),('ft_only','FT only')]:
            sa=checked(results[task][method]);sb=checked(target[method])
            rows.append(f"| {task} | {name} | {sa['paper_success_pct']:.1f} | {sb['paper_success_pct']:.1f} | {sa['prefix_metrics']['1.0']['metrics']['global_position_mm']:.2f} | {sb['prefix_metrics']['1.0']['metrics']['global_position_mm']:.2f} |")
    rows+=['', 'The Step policy can complete the motion in A. Its poor B result is therefore a transfer problem under this protocol, rather than evidence that it never learned the motion. CR7 already succeeds in B, so success alone leaves little room for improvement. Squat and CR7 still have pose and motion errors.', '',
           'These tests start from model6000, as fixed in the comparison. They do not select a newer or better source checkpoint. Initial states are compared through the settings and seeds; post-warm physical states can change when gains change.', '',
           'The first launch failed before physics because the environment bin directory was absent from PATH and Ninja was unavailable. Its artifacts remain at source_quality_20261009. The complete fresh run is source_quality_20261009_pathfix. No checkpoint or physics setting changed for this launch repair.', '']
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'metrics.md').write_text('\n'.join(rows)+'\n')
    for name in ('comparison.json','queue_plan.json','status.json','publication_audit.json'):
        (a.output/name).write_text((a.root/name).read_text())
    print('Published verified source-A and target-B quality comparison.')


if __name__=='__main__':main()
