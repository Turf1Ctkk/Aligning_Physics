"""Publish fresh evaluation tables; never treat pending jobs as zero results."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

NAMES = {'vanilla':'Original', 'ft_only':'Fine-tuning only', 'asap_ft':'Delta action',
         'sysid_ft':'Passive SysID', 'torque_ft':'Torque correction', 'active_sysid_ft':'Active SysID',
         'wave_ft':'Excitation torque', 'native_unchanged_torque':'Unchanged-data torque',
         'primary_uniform':'Uniform: first run', 'primary_coverage':'Coverage: first run',
         'primary_joint_range':'Range: first run', 'repeat_uniform':'Uniform: repeat',
         'repeat_coverage':'Coverage: repeat', 'repeat_joint_range':'Range: repeat'}


def checked(report):
    trials = report['trials']
    if len(trials) != 96 or {(t['seed'], t['trial']) for t in trials} != {(s,i) for s in (8101,8102,8103) for i in range(32)}:
        raise ValueError('Missing or repeated deployment trial')
    summary = report['summary']
    for flag, rate in [('complete','completion_pct'), ('paper_tracking_success','paper_success_pct')]:
        if not np.isclose(summary[rate], 100 * sum(t[flag] for t in trials) / len(trials)):
            raise ValueError('Summary percentage does not match individual trials')
    return summary


def table(task, reports):
    rows = [f'# {task}: fresh 27-point evaluation', '',
        'The first-second errors below use trials that reach one second. Inclusion is reported separately.', '',
        '| Policy | Completion (%) | Tracking success (%) | Included (%) | Global position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for method, report in reports.items():
        s = checked(report)
        prefix = s['prefix_metrics']['1.0']
        m = prefix['metrics']
        values = [f"{m[k]:.3f}" if m is not None else 'N/A' for k in
                  ('global_position_mm','root_relative_position_mm','body_velocity_mm_frame','root_velocity_mm_frame','body_acceleration_mm_frame2')]
        rows.append(f"| {NAMES.get(method,method)} | {s['completion_pct']:.1f} | {s['paper_success_pct']:.1f} | {100*prefix['valid_trials']/96:.1f} | " + ' | '.join(values) + ' |')
    rows += ['', 'Tracking success requires full completion and mean body distance no greater than 0.5 m throughout the trial.',
             'Full-motion and available-frame metrics remain in the JSON report. No derivatives cross a reset.',
             'These evaluation trials are not independent training replications.', '']
    return '\n'.join(rows)


def overview(results, output):
    methods = list(NAMES)[:7]
    tasks = ('SquatL1', 'CR7', 'StepFBL1')
    panels = [('paper_success_pct', 'Tracking success (%)', 'YlGn', '.1f'),
              ('global_position_mm', 'First-second position (mm)', 'YlOrRd', '.1f'),
              ('body_velocity_mm_frame', 'Body velocity (mm/frame)', 'YlOrRd', '.2f'),
              ('body_acceleration_mm_frame2', 'Acceleration (mm/frame²)', 'YlOrRd', '.2f')]
    fig, axes = plt.subplots(1, 4, figsize=(13.5, 5.1))
    for ax, (key, title, palette, fmt) in zip(axes, panels):
        values = np.empty((len(methods), len(tasks)))
        for i, method in enumerate(methods):
            for j, task in enumerate(tasks):
                s = checked(results[task][method])
                values[i, j] = s[key] if key == 'paper_success_pct' else s['prefix_metrics']['1.0']['metrics'][key]
        image = ax.imshow(values, cmap=palette, aspect='auto', vmin=0,
                          vmax=100 if key == 'paper_success_pct' else None)
        for i, method in enumerate(methods):
            for j, task in enumerate(tasks):
                prefix = results[task][method]['summary']['prefix_metrics']['1.0']
                suffix = '*' if key != 'paper_success_pct' and prefix['valid_trials'] < 96 else ''
                ax.text(j, i, format(values[i, j], fmt) + suffix, ha='center', va='center', fontsize=10,
                        color='white' if image.norm(values[i, j]) > .65 else 'black')
        ax.set_xticks(range(len(tasks)), ('Squat', 'CR7', 'Step'))
        ax.set_yticks(range(len(methods)), [NAMES[m] for m in methods] if ax is axes[0] else [''] * len(methods))
        ax.set_title(title, fontsize=10)
        ax.tick_params(length=0)
        fig.colorbar(image, ax=ax, shrink=.75, pad=.03)
    fig.suptitle('Fresh 27-point policy evaluation', fontsize=13)
    fig.text(.5, .035, '* Error means include only trials that reach one second; see task tables for inclusion percentages.\n'
             'Lower errors are better. Three deployment seeds per policy; one training seed per method.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .11, 1, .96))
    fig.savefig(output / 'overview.png', dpi=180)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if json.loads((args.root/'status.json').read_text())['status']!='complete':
        raise ValueError('Fresh evaluation queue is incomplete')
    results=json.loads((args.root/'comparison.json').read_text())
    if set(results) != {'CR7','SquatL1','StepFBL1'}:
        raise ValueError('Missing task')
    args.output.mkdir(parents=True,exist_ok=True)
    for task,reports in results.items():
        if set(reports) != (set(NAMES) if task=='SquatL1' else set(list(NAMES)[:7])):
            raise ValueError('Unexpected set of trained policy conditions')
        (args.output/(task+'.md')).write_text(table(task,reports))
        (args.output/(task+'.json')).write_text(json.dumps(reports,indent=2)+'\n')
        methods=list(reports)
        names=[NAMES[m] for m in methods]
        fig, axes=plt.subplots(1,4,figsize=(max(13,len(methods)*1.4),4.7))
        for i,ax in enumerate(axes):
            if i==0:
                values=[checked(reports[m])['paper_success_pct'] for m in methods]
                title,unit='Tracking success','Success (%)'
            else:
                key=('global_position_mm','body_velocity_mm_frame','body_acceleration_mm_frame2')[i-1]
                values=[reports[m]['summary']['prefix_metrics']['1.0']['metrics'][key]
                        if reports[m]['summary']['prefix_metrics']['1.0']['metrics'] else None for m in methods]
                title='First-second '+('position','velocity','acceleration')[i-1]
                unit=('mm','mm/frame','mm/frame²')[i-1]
            bars=ax.bar(names,[np.nan if v is None else v for v in values],color='#355C99')
            for b,v in zip(bars,values):
                if v is None: ax.text(b.get_x()+b.get_width()/2,0,'N/A',ha='center')
                else: ax.annotate(f'{v:.1f}',(b.get_x()+b.get_width()/2,v),xytext=(0,3),textcoords='offset points',ha='center',fontsize=7)
            ax.set(title=title,ylabel=unit)
            ax.tick_params(axis='x',rotation=60,labelsize=7)
            ax.spines[['top','right']].set_visible(False)
            ax.margins(y=.2)
        fig.suptitle(task+' — fresh 27-point physics evaluation')
        fig.tight_layout()
        fig.savefig(args.output/(task+'.png'),dpi=170)
        plt.close(fig)
    (args.output/'source_status.json').write_text((args.root/'status.json').read_text())
    (args.output/'frozen_manifest.json').write_text((args.root/'frozen_manifest.json').read_text())
    overview(results, args.output)
    print('Published complete fresh evaluation tables and plots; percentages validated from trial identities.')


if __name__=='__main__':main()
