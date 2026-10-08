"""Build the report's four ASAP-style error charts from verified artifacts."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from report_paper_evaluation import checked as check_policy
from report_paper_replay import checked as check_replay

ROOT = Path(__file__).resolve().parents[1]
METHODS = ('vanilla', 'ft_only', 'asap_ft', 'sysid_ft', 'active_sysid_ft', 'torque_ft', 'wave_ft')
LABELS = ('Original', 'FT only', 'Delta action', 'Passive SysID', 'Active SysID', 'Common torque', 'Excitation torque')
FIELDS = ('global_position_mm', 'root_relative_position_mm', 'body_acceleration_mm_frame2', 'root_velocity_mm_frame')
TITLES = ('$E_{g-mpjpe}$', '$E_{mpjpe}$', '$E_{acc}$', '$E_{vel}$ (root)')
UNITS = ('mm', 'mm', 'mm/frame²', 'mm/frame')
COLORS = ('#8C8C8C', '#333333', '#3B6EA8', '#56A176', '#A987C3', '#DAA34A', '#BD6372')
TASKS = ('SquatL1', 'CR7', 'StepFBL1')


def style(ax, unit):
    ax.set_ylabel(unit)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=.18)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)


def main():
    output = ROOT / 'results/method_comparison'
    output.mkdir(exist_ok=True)
    policy = {task: json.loads((ROOT / 'results/paper_evaluation' / (task + '.json')).read_text()) for task in TASKS}
    replay = json.loads((ROOT / 'results/paper_replay/comparison.json').read_text())
    sources = ('controlled_squat_20261008__source20_zero',)*2 + (
        'controlled_squat_20261008__controlled_delta', 'sysid_serial_20261008__identified_test',
        'active_20261008__active_test', 'torque_20261008__torque', 'wave_20261008_wave__torque')
    open_rows = [check_replay(replay[key])['metrics'] for key in sources]
    closed = {task: {method: check_policy(policy[task][method]) for method in METHODS} for task in TASKS}
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.4))
    for ax, key, title, unit in zip(axes.flat, FIELDS, TITLES, UNITS):
        values = [row[key] for row in open_rows]
        bars = ax.bar(range(7), values, color=COLORS)
        ax.bar_label(bars, fmt='%.2f', padding=3, fontsize=8)
        ax.set_xticks(range(7), [s.replace(' ', '\n', 1) for s in LABELS], fontsize=8)
        ax.set_title(title)
        style(ax, unit)
        ax.margins(y=.2)
    fig.suptitle('Open-loop calibration replay — one second, 24 measured bodies')
    fig.text(.5, .014, 'Original and FT only share the same uncalibrated simulator. Task and parent weights are equal.\n'
             'Methods use different collection protocols; this is not a controlled ranking of model representations.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .065, 1, .96))
    fig.savefig(output / 'open_loop.png', dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.2))
    x = np.arange(3)
    width = .105
    for ax, key, title, unit in zip(axes.flat, FIELDS, TITLES, UNITS):
        for i, method in enumerate(METHODS):
            vals = [closed[t][method]['prefix_metrics']['1.0']['metrics'][key] for t in TASKS]
            ax.bar(x + (i - 3)*width, vals, width, label=LABELS[i], color=COLORS[i])
        ax.set_xticks(x, ('Squat', 'CR7', 'Step'))
        ax.set_title(title)
        style(ax, unit)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .95), ncol=4, frameon=False, fontsize=9)
    fig.suptitle('Closed-loop target tracking — first second, 27 points')
    fig.text(.5, .014, 'CR7 excludes trials that end before one second; inclusion percentages are in the numeric report.\n'
             'Other task prefixes include all trials. Errors do not describe full-motion performance.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .065, 1, .85))
    fig.savefig(output / 'closed_loop.png', dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11.5, 4))
    for i, method in enumerate(METHODS):
        vals = [closed[t][method]['paper_success_pct'] for t in TASKS]
        bars = ax.bar(x + (i-3)*width, vals, width, label=LABELS[i], color=COLORS[i])
        ax.bar_label(bars, fmt='%.1f', padding=2, fontsize=7, rotation=90)
    ax.set_xticks(x, ('Squat (5.22 s)', 'CR7 (3.92 s)', 'Step (3.92 s)'))
    style(ax, 'Success (%)')
    ax.set_ylim(0, 118)
    ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.18), ncol=4, frameon=False, fontsize=9)
    fig.suptitle('Closed-loop tracking success', y=1.03)
    fig.tight_layout()
    fig.savefig(output / 'success.png', dpi=180, bbox_inches='tight')
    plt.close(fig)
    rows = ['# Method comparison', '',
            'These are the measured results before the training-setting repair. Delta policy training contains the noise mismatch described in the [setting audit](../../docs/settings_audit.md).', '',
            '## Open-loop replay', '',
            'One second, 24 measured bodies. All replay cases reach the horizon. Means give equal weight to tasks and original rollouts. Original and FT-only use the same uncalibrated dynamics; task policy weights do not enter fixed-action replay.', '',
            '| Method | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |',
            '|---|---:|---:|---:|---:|']
    for name, row in zip(LABELS, open_rows):
        rows.append('| ' + name + ' | ' + ' | '.join(f'{row[k]:.3f}' for k in FIELDS) + ' |')
    rows += ['', 'The common and excitation torque datasets differ in rate, duration and phase. Their contrast does not isolate excitation. A separate unchanged-versus-excitation acquisition experiment provides that paired comparison.', '',
             'Torque models have already acted before their first saved frame. The control shares the input and seed, but not that post-step state. Results include startup. SysID fitting and replay protocols also differ from delta action. These bars do not establish a model-family ranking.', '']
    for task in TASKS:
        rows += ['## Closed-loop ' + task, '', 'Errors use the first second. Success uses the complete reference horizon. E_vel is root velocity; whole-body velocity is retained in the raw reports.', '',
                 '| Policy | Success (%) | Included (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |',
                 '|---|---:|---:|---:|---:|---:|---:|']
        for method, name in zip(METHODS, LABELS):
            s = closed[task][method]; prefix = s['prefix_metrics']['1.0']
            rows.append(f"| {name} | {s['paper_success_pct']:.1f} | {100*prefix['valid_trials']/96:.1f} | " + ' | '.join(f"{prefix['metrics'][k]:.3f}" for k in FIELDS) + ' |')
        rows += ['', 'Full-motion errors below use successful trials only. A small error with low inclusion is not evidence of reliable control.', '',
                 '| Policy | Full-motion inclusion (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel, root (mm/frame) |',
                 '|---|---:|---:|---:|---:|---:|']
        for method, name in zip(METHODS, LABELS):
            s=closed[task][method]; m=s['paper_successful_trial_metrics']
            rows.append(f"| {name} | {s['paper_success_pct']:.1f} | " + ' | '.join(f'{m[k]:.3f}' if m else 'N/A' for k in FIELDS) + ' |')
        rows.append('')
    (output/'metrics.md').write_text('\n'.join(rows)+'\n')
    (output/'chart_data.json').write_text(json.dumps({'open_sources':list(sources),'open_metrics':open_rows,
                'closed_summary':closed,'E_vel_definition':'root first-difference error','rate_hz':50},indent=2)+'\n')
    print('Verified all trial identities and replay weights; generated four-error figures and closed-loop success.')


if __name__ == '__main__':
    main()
