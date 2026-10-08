"""Report every audited repair task, including worse results and pending tasks."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from report_paper_evaluation import checked

ROOT = Path(__file__).resolve().parents[1]
TASKS = ('SquatL1', 'CR7', 'StepFBL1')
FIELDS = ('global_position_mm', 'root_relative_position_mm', 'body_acceleration_mm_frame2', 'root_velocity_mm_frame')
TITLES = ('$E_{g-mpjpe}$ (mm)', '$E_{mpjpe}$ (mm)', '$E_{acc}$ (mm/frame²)', '$E_{vel}$, root (mm/frame)')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT / 'results/noise_repair')
    parser.add_argument('--baseline-root', type=Path, help='Use a completed earlier repair as the before condition')
    parser.add_argument('--repair-kind', choices=('noise', 'reset'), default='noise')
    args = parser.parse_args()
    results = {}
    for task in TASKS:
        work = args.root / task
        if not (work / 'status.json').exists() or json.loads((work / 'status.json').read_text())['status'] != 'complete':
            continue
        audit = json.loads((work / 'publication_audit.json').read_text())
        after = json.loads((work / 'comparison.json').read_text())
        before = (json.loads((args.baseline_root / task / 'comparison.json').read_text())
                  if args.baseline_root else json.loads((ROOT / 'results/paper_evaluation' / (task + '.json')).read_text())['asap_ft'])
        if audit['task'] != task or audit['final_checkpoint_sha256'] != after['checkpoint_sha256'] or len(audit['evaluation_audit']) != 3:
            raise ValueError('Missing repair audit')
        expected = ({'env._target_', 'experiment_dir', 'experiment_name'} if args.repair_kind == 'reset' else
                    {'obs.noise_scales.base_pos_z', 'obs.noise_scales.feet_contact_force', 'experiment_dir', 'experiment_name'})
        if set(audit['training_config_changes']) != expected:
            raise ValueError('Repair kind does not match the audited intervention')
        results[task] = {'before': checked(before), 'after': checked(after)}
    if not results:
        raise ValueError('No audited repair task is complete')
    missing = [task for task in TASKS if task not in results]
    if args.repair_kind == 'reset' and args.baseline_root is None:
        raise ValueError('Reset report requires the prior noise-repair baseline')
    description = ('The repair clears the previous delta action when an environment resets. Both conditions already use zero height and foot-force noise. Data, source and calibration checkpoints, seeds and 1,000-update budgets stay the same. Other saved training settings match.'
                   if args.repair_kind == 'reset' else
                   'The repair sets height and foot-force noise to zero during policy fine-tuning. Calibration already used zero noise. Data, input checkpoints, seeds and 1,000-update budgets stay the same. All other saved training settings match.')
    title = '# Frozen-delta reset repair' if args.repair_kind == 'reset' else '# Frozen-delta input-noise repair'
    lines = [title, '', description, '',
             'This is one paired training run per task. Three evaluation seeds measure deployment variation, not training replication. All stored starts and effective deployment settings match the historical evaluation. Metrics were recomputed from the new 27-point recordings.', '']
    if missing:
        lines += ['Pending tasks: ' + ', '.join(missing) + '. The table contains completed tasks only.', '']
    lines += ['Errors use the first second. Success and completion use the full motion. E_vel is root velocity at 50 Hz.', '',
              '| Task | Setting | Success (%) | Completion (%) | Included (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel (mm/frame) |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for task, pair in results.items():
        for setting, summary in pair.items():
            prefix = summary['prefix_metrics']['1.0']
            lines.append(f"| {task} | {setting.capitalize()} | {summary['paper_success_pct']:.1f} | {summary['completion_pct']:.1f} | {100*prefix['valid_trials']/summary['total_trials']:.1f} | " + ' | '.join(f"{prefix['metrics'][key]:.3f}" for key in FIELDS) + ' |')
    lines += ['', 'Full-motion errors below include successful trials only. The two settings can have different successful trials, so these means do not compare the same cohort.', '',
              '| Task | Setting | Full-motion inclusion (%) | E_g-mpjpe (mm) | E_mpjpe (mm) | E_acc (mm/frame²) | E_vel (mm/frame) |',
              '|---|---|---:|---:|---:|---:|---:|']
    for task, pair in results.items():
        for setting, summary in pair.items():
            metrics = summary['paper_successful_trial_metrics']
            lines.append(f"| {task} | {setting.capitalize()} | {summary['paper_success_pct']:.1f} | " + ' | '.join(f'{metrics[key]:.3f}' if metrics else 'N/A' for key in FIELDS) + ' |')
    lines += ['', 'The calibrator was not retrained, so open-loop calibration results stay unchanged. The subset policies were not repaired. Their earlier transfer results still carry the input-noise and reset caveats.', '']
    (args.root / 'metrics.md').write_text('\n'.join(lines) + '\n')
    (args.root / 'chart_data.json').write_text(json.dumps({'completed': results, 'pending_tasks': missing}, indent=2) + '\n')
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    x = np.arange(len(results))
    panels = list(zip(FIELDS, TITLES)) + [('paper_success_pct', 'Full-motion success (%)')]
    for ax, (key, title) in zip(axes.flat, panels):
        for offset, setting, color in [(-.18, 'before', '#3B6EA8'), (.18, 'after', '#DAA34A')]:
            values = [pair[setting][key] if key == 'paper_success_pct' else pair[setting]['prefix_metrics']['1.0']['metrics'][key] for pair in results.values()]
            bars = ax.bar(x + offset, values, .36, label=setting.capitalize(), color=color)
            ax.bar_label(bars, fmt='%.2f', padding=3, fontsize=8)
        ax.set_xticks(x, list(results))
        ax.set_title(title, fontsize=10)
        ax.set_ylim(bottom=0)
        ax.margins(y=.2)
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
        if key == 'paper_success_pct':
            ax.set_ylim(0, 115)
    axes.flat[-1].axis('off')
    axes.flat[-1].legend(*axes.flat[0].get_legend_handles_labels(), loc='center', frameon=False)
    fig.suptitle('Frozen-delta reset repair' if args.repair_kind == 'reset' else 'Frozen-delta input-noise repair')
    caption = 'First-second errors; full-motion success. One paired training seed per task.'
    if missing:
        caption += '\nPending: ' + ', '.join(missing) + '.'
    fig.text(.5, .025, caption, ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .09, 1, .95))
    fig.savefig(args.root / 'before_after.png', dpi=180)
    plt.close(fig)
    print('Reported audited tasks:', ', '.join(results), '; pending:', ', '.join(missing) or 'none')


if __name__ == '__main__':
    main()
