"""Report completed 24-body replays and separate downstream policy results."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

FIELDS = ('global_position_mm', 'root_relative_position_mm', 'body_velocity_mm_frame',
          'root_velocity_mm_frame', 'body_acceleration_mm_frame2')
RULES = ('uniform', 'coverage', 'joint_range')


def describe(label):
    root, method = label.split('__')
    groups = {
        'controlled_squat_20261008': 'Delta action', 'sysid_serial_20261008': 'Passive SysID',
        'torque_20261008': 'Common-data torque', 'active_20261008': 'Active acquisition',
        'wave_20261008_unchanged': 'Measured 200 Hz: unchanged data',
        'wave_20261008_wave': 'Measured 200 Hz: excitation data',
    }
    names = {'same16_zero': 'Target-gain diagnostic', 'source20_zero': 'No correction',
             'controlled_delta': 'Delta action', 'identified_test': 'Fitted gains', 'torque': 'Torque correction',
             'zero_test': 'Unchanged-data fit', 'random_test': 'Random-excitation fit', 'active_test': 'Optimized-excitation fit'}
    for prefix, title in (('content_repeat_20261008_', 'Data selection: repeat'),
                          ('content_20261008_', 'Data selection: first run')):
        if root.startswith(prefix):
            return title, root[len(prefix):].replace('_', ' ').capitalize() if method == 'learned' else names[method]
    if root == 'repeat_controls_20261008':
        return 'Data selection: repeat', names[method]
    return groups[root], names[method]


def checked(report):
    cases = report['cases']
    if report['point_count'] != 24 or report['fps'] != 50 or len(cases) != 66:
        raise ValueError('Wrong target point set, rate or case budget')
    if len({c['key'] for c in cases}) != 66 or any(report['initial_max_absolute_difference'].values()):
        raise ValueError('Case identities or stored starts differ')
    for horizon in (.25, .5, 1.):
        groups = {}
        for c in cases:
            row = c['horizons'][str(horizon)]
            if row['metrics'] is not None:
                if row['scored_frames'] < 3 or set(row['metrics']) != set(FIELDS):
                    raise ValueError('Invalid scored metric window')
                if any(not np.isfinite(v) or v < 0 for v in row['metrics'].values()):
                    raise ValueError('Invalid metric')
                groups.setdefault(c['task'], {}).setdefault(c['group'], []).append(row['metrics'])
        if set(groups) != {'CR7', 'SquatL1', 'StepFBL1'}:
            raise ValueError('Missing replay task')
        task_values = {task: {k: np.mean([np.mean([r[k] for r in rows]) for rows in parents.values()]) for k in FIELDS}
                       for task, parents in groups.items()}
        summary = report['horizons'][str(horizon)]
        if not np.isclose(summary['completion_pct'], 100 * sum(c['horizons'][str(horizon)]['complete'] for c in cases) / 66):
            raise ValueError('Completion percentage differs from cases')
        for k in FIELDS:
            if not np.isclose(summary['metrics'][k], np.mean([v[k] for v in task_values.values()]), atol=1e-10):
                raise ValueError('Group/task weighting differs')
    return report['horizons']['1.0']


def content_plot(results, policy, output):
    fig, axes = plt.subplots(2, 4, figsize=(13.5, 7.2))
    colors = ('#888888', '#355C99', '#C4882F')
    for row, (run, root, baseline) in enumerate((
            ('primary', 'content_20261008', 'content_20261008_uniform__source20_zero'),
            ('repeat', 'content_repeat_20261008', 'repeat_controls_20261008__source20_zero'))):
        zero = checked(results[baseline])['metrics']
        labels = ('Uniform', 'Actuator\ncoverage', 'Joint range')
        for col, key in enumerate(('global_position_mm', 'body_velocity_mm_frame', 'body_acceleration_mm_frame2', 'paper_success_pct')):
            ax = axes[row, col]
            values = [policy['SquatL1'][run + '_' + m]['summary'][key] if col == 3
                      else checked(results[root + '_' + m + '__learned'])['metrics'][key] for m in RULES]
            bars = ax.bar(labels, values, color=colors)
            ax.bar_label(bars, labels=[f'{v:.1f}%' if col == 3 else f'{v:.2f}' for v in values], padding=3, fontsize=9)
            if col < 3:
                ax.axhline(zero[key], color='#333333', linestyle='--', label='Matched no correction')
                ax.legend(fontsize=7)
            ax.set_title(('First run' if row == 0 else 'Repeat') + ': ' + ('replay position', 'replay velocity', 'replay acceleration', 'policy tracking success')[col], fontsize=10)
            ax.set_ylabel(('mm', 'mm/frame', 'mm/frame²', '%')[col])
            ax.set_ylim(0, 114 if col == 3 else max(values + [zero[key]]) * 1.28)
            ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Data selection: replay and downstream control', fontsize=13)
    fig.text(.5, .025, 'Replay: 24 measured bodies, one-second horizon, every case complete. Policy: 27 points, full-motion success.\n'
             'Same 18 parents and 954 selected transitions per rule. Two fixed-data training runs are shown separately.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .09, 1, .97))
    fig.savefig(output / 'content_selection.png', dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--policy-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text())
    if read(args.root / 'status.json')['status'] != 'complete' or read(args.policy_root / 'status.json')['status'] != 'complete':
        raise ValueError('Both fresh physics queues must complete')
    results, plan = read(args.root / 'comparison.json'), read(args.root / 'queue_plan.json')
    if len(results) != 26 or set(results) != {j['label'] for j in plan['jobs']}:
        raise ValueError('Missing planned replay condition')
    groups = {}
    for label, report in results.items():
        group, name = describe(label)
        groups.setdefault(group, []).append((name, checked(report)))
    lines = ['# Fresh calibration replay', '',
             'These physical replays compare predictions with 24 measured target bodies. Errors use the one-second horizon, excluding the first stored frame. All jobs use 50 Hz output.', '',
             'Cases are averaged within each recorded parent, then within each task, then across the three tasks. Available uninterrupted frames are scored; completion is reported separately. No derivatives cross a reset.', '']
    for group, rows in groups.items():
        lines += ['## ' + group, '', '| Condition | Complete (%) | Position (mm) | Relative position (mm) | Body velocity (mm/frame) | Root velocity (mm/frame) | Acceleration (mm/frame²) |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for name, row in rows:
            lines.append(f"| {name} | {row['completion_pct']:.1f} | " + ' | '.join(f"{row['metrics'][k]:.3f}" for k in FIELDS) + ' |')
        lines.append('')
    lines += ['Target-gain rows are implementation diagnostics, not learned methods. Each no-correction row belongs to its own experiment and replay seed. The passive fit has no separate fresh matched zero row here.',
              'Action replay and all six data-selection models match their source controls at the first stored state. Torque replay saves only every fourth physical step. Its model has already acted before the first saved frame, so those saved states differ from zero correction. Torque results describe the full replay procedure, including its startup.',
              'Model architectures, calibration transitions and acquisition phases differ between method families. These results do not establish a representation ranking.',
              'Replay uses 24 measured target bodies; policy evaluation uses 27 points. Their absolute error values should not be compared as the same point set.', '']
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'metrics.md').write_text('\n'.join(lines))
    for name in ('comparison.json', 'status.json', 'queue_plan.json'):
        (args.output / name).write_text((args.root / name).read_text())
    content_plot(results, read(args.policy_root / 'comparison.json'), args.output)
    print('Published all 26 measured replay conditions; case identities, percentages and weights checked.')


if __name__ == '__main__':
    main()
