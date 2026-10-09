"""Report audited servo-selection arms without choosing favorable results."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from report_paper_evaluation import checked

FIELDS = ('global_position_mm', 'root_relative_position_mm', 'body_acceleration_mm_frame2', 'root_velocity_mm_frame')
TITLES = ('$E_{g-mpjpe}$ (mm)', '$E_{mpjpe}$ (mm)', '$E_{acc}$ (mm/frame²)', '$E_{vel}$, root (mm/frame)')
NAMES = {'random': 'Random-N', 'servo': 'Servo-coverage-N', 'ft_only': 'FT-only', 'low_error': 'Low-error-N'}


def load(path):
    return json.loads(path.read_text())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    plan, selection = load(a.root / 'queue_plan.json'), load(a.root / 'selection_manifest.json')
    rows, pending, contrasts = {}, [], {}
    for run in ('primary', 'repeat'):
        run_status = a.root / run / 'status.json'
        if run_status.exists() and load(run_status)['status'] == 'skipped':
            pending.append(run + ': skipped by cutoff gate')
            continue
        rows[run] = {}
        for arm in ('random', 'servo', 'ft_only') if run == 'primary' else ('random', 'servo'):
            work = a.root / run / arm
            if not (work / 'status.json').exists() or load(work / 'status.json')['status'] != 'complete':
                pending.append(run + '/' + arm)
                continue
            report, audit = load(work / 'comparison.json'), load(work / 'publication_audit.json')
            if audit['training_seed'] != plan['policy_seeds'][int(run == 'repeat')] or audit['final_checkpoint_sha256'] != report['checkpoint_sha256']:
                raise ValueError('Policy seed/checkpoint audit mismatch')
            if len(audit['evaluation_audit']) != 3 or len(report['trials']) != 96 or {(t['seed'], t['trial']) for t in report['trials']} != {(s,t) for s in (8101,8102,8103) for t in range(32)}:
                raise ValueError('Policy identities incomplete')
            summary = checked(report)
            item = {'control': summary, 'policy_seed': audit['training_seed'], 'audit': audit}
            if arm != 'ft_only':
                calibration = load(work / 'calibration_audit.json')
                replay = load(work / 'learned_paper_metrics.json')
                if calibration['selected_checkpoint']['sha256'] != replay['checkpoint_sha256'] or len(replay['cases']) != 66:
                    raise ValueError('Calibration/checkpoint/case audit mismatch')
                identities = {(c['task'],c['group'],c['key']) for c in replay['cases']}
                if len(identities) != 66 or {c['task'] for c in replay['cases']} != {'CR7','SquatL1','StepFBL1'}:
                    raise ValueError('Replay identities incomplete')
                start = load(work / 'replay_start_audit.json')
                if not start['exact'] or start['learned_sha256'] != replay['record_sha256']:
                    raise ValueError('Shared replay startup audit missing')
                item.update(replay=replay, calibration=calibration)
            rows[run][arm] = item
    if not any(rows.values()):
        raise ValueError('No audited main policy arm complete; do not report pending results')
    lines = ['# Servo-error selection results', '',
        'The selectors were frozen before learning. The planned arms use the same parents and selected data budget. Results include completed audited conditions only. Replay and Step control are separate endpoints. Scheduled policies use repaired inputs and reset.', '',
        'Replay has 24 measured bodies. Step tracking has 27 points. Errors use the first second. Velocity is root velocity at 50 Hz. Units are mm for position, mm/frame² for acceleration and mm/frame for velocity. Early terminations change inclusion; full-motion means include successful trials only.', '']
    if pending:
        lines += ['Pending policy evaluation or skipped: ' + ', '.join(pending) + '.', '']
    for run, arms in rows.items():
        if not arms:
            continue
        lines += ['## ' + run.capitalize(), '', '| Group | Replay E_g-mpjpe | Replay E_mpjpe | Replay E_acc | Replay E_vel | Complete replay (%) |', '|---|---:|---:|---:|---:|---:|']
        for arm, item in arms.items():
            if 'replay' in item:
                replay = item['replay']['paper_metrics']
                lines += ['| ' + NAMES[arm] + ' | ' + ' | '.join(f'{replay["metrics"][k]:.3f}' for k in FIELDS) + f' | {replay["completion_pct"]:.1f} |']
        lines += ['', '| Group | Success (%) | Completion (%) | First-second inclusion (%) | E_g-mpjpe | E_mpjpe | E_acc | E_vel |', '|---|---:|---:|---:|---:|---:|---:|---:|']
        for arm, item in arms.items():
            s = item['control']; prefix = s['prefix_metrics']['1.0']
            lines += [f'| {NAMES[arm]} | {s["paper_success_pct"]:.1f} | {s["completion_pct"]:.1f} | {100*prefix["valid_trials"]/s["total_trials"]:.1f} | ' + ' | '.join(f'{prefix["metrics"][k]:.3f}' if prefix['metrics'] else 'N/A' for k in FIELDS) + ' |']
        lines += ['', '| Group | Successful full-motion inclusion (%) | E_g-mpjpe | E_mpjpe | E_acc | E_vel |', '|---|---:|---:|---:|---:|---:|']
        for arm, item in arms.items():
            s = item['control']; m = s['paper_successful_trial_metrics']
            lines += [f'| {NAMES[arm]} | {s["paper_success_pct"]:.1f} | ' + ' | '.join(f'{m[k]:.3f}' if m else 'N/A' for k in FIELDS) + ' |']
        fig, axes = plt.subplots(2,4,figsize=(15,7))
        for row, scope in enumerate(('replay','control')):
            labels = [arm for arm,item in arms.items() if scope in item]
            for ax,k,title in zip(axes[row],FIELDS,TITLES):
                values = []
                for arm in labels:
                    metrics = (arms[arm]['replay']['paper_metrics']['metrics'] if scope=='replay'
                               else arms[arm]['control']['prefix_metrics']['1.0']['metrics'])
                    values.append(metrics[k] if metrics is not None else np.nan)
                bars=ax.bar(np.arange(len(labels)),values,color=['#3476A8','#D49A35','#6D9671'][:len(labels)])
                ax.bar_label(bars,fmt='%.2f',fontsize=8,padding=3)
                ax.set_xticks(np.arange(len(labels)),[NAMES[x] for x in labels],rotation=20,ha='right',fontsize=8)
                ax.set_title(('Replay: ' if row==0 else 'Step: ')+title,fontsize=10);ax.set_ylim(bottom=0);ax.margins(y=.2)
                ax.spines[['top','right']].set_visible(False)
        fig.suptitle(run.capitalize()+': four errors; first second')
        fig.tight_layout();fig.savefig(a.output/(run+'_errors.png'),dpi=180);plt.close(fig)
        fig,ax=plt.subplots(figsize=(6,4));labels=list(arms)
        bars=ax.bar([NAMES[x] for x in labels],[arms[x]['control']['paper_success_pct'] for x in labels],color=['#3476A8','#D49A35','#6D9671'][:len(labels)])
        ax.bar_label(bars,fmt='%.1f%%');ax.set_ylim(0,115);ax.set_ylabel('Step full-motion success (%)')
        fig.tight_layout();fig.savefig(a.output/(run+'_success.png'),dpi=180);plt.close(fig)
        lines += ['', f'![{run.capitalize()} four-error comparison]({run}_errors.png)', '',
            f'![{run.capitalize()} Step success]({run}_success.png)', '']
        if {'random', 'servo'} <= set(arms):
            contrast = {}
            for scope in ('replay', 'control'):
                def metrics(arm):
                    item = arms[arm]
                    return (item['replay']['paper_metrics']['metrics'] if scope == 'replay'
                            else item['control']['prefix_metrics']['1.0']['metrics'])
                random, servo = metrics('random'), metrics('servo')
                contrast[scope] = {k: servo[k] - random[k] if servo and random else None for k in FIELDS}
            contrast['success_percentage_points'] = arms['servo']['control']['paper_success_pct'] - arms['random']['control']['paper_success_pct']
            contrast['mean_survival_seconds'] = arms['servo']['control']['mean_survival_s'] - arms['random']['control']['mean_survival_s']
            contrasts[run] = contrast
            lines += ['', 'Servo minus Random at the same planned training seed. Positive error differences mean higher error.', '',
                '| Endpoint | E_g-mpjpe | E_mpjpe | E_acc | E_vel |', '|---|---:|---:|---:|---:|']
            for scope, name in (('replay', 'Replay'), ('control', 'Step first second')):
                lines += ['| ' + name + ' | ' + ' | '.join(f'{contrast[scope][k]:+.3f}' if contrast[scope][k] is not None else 'N/A' for k in FIELDS) + ' |']
            lines += ['', f'Success changes by {contrast["success_percentage_points"]:+.1f} percentage points; mean survival changes by {contrast["mean_survival_seconds"]:+.3f} seconds. This is one whole-training-run contrast, not an isolated feature effect.', '']
        if 'ft_only' in arms:
            base = arms['ft_only']['control']
            matched = {}
            lines += ['', 'Matched primary-seed control contrast: each arm minus FT-only. Positive error differences mean higher error.', '',
                '| Group | Success difference (percentage points) | E_g-mpjpe | E_mpjpe | E_acc | E_vel |',
                '|---|---:|---:|---:|---:|---:|']
            for arm in ('random', 'servo'):
                if arm not in arms:
                    continue
                current = arms[arm]['control']
                cm, bm = current['prefix_metrics']['1.0']['metrics'], base['prefix_metrics']['1.0']['metrics']
                values = {k: cm[k] - bm[k] if cm and bm else None for k in FIELDS}
                success = current['paper_success_pct'] - base['paper_success_pct']
                matched[arm] = {'first_second_errors': values, 'success_percentage_points': success,
                    'mean_survival_seconds': current['mean_survival_s'] - base['mean_survival_s']}
                lines += [f'| {NAMES[arm]} | {success:+.1f} | ' + ' | '.join(f'{values[k]:+.3f}' if values[k] is not None else 'N/A' for k in FIELDS) + ' |']
            contrasts.setdefault(run, {})['matched_ft_only'] = matched
    strata={run:{arm:item['replay']['stratified'] for arm,item in arms.items() if 'replay' in item} for run,arms in rows.items()}
    supplemental = {}
    low_status = a.root / 'low_error/status.json'
    if low_status.exists():
        supplemental['status'] = load(low_status)
        if supplemental['status']['status'] == 'complete':
            low = a.root / 'low_error'
            calibration, replay = load(low / 'calibration_audit.json'), load(low / 'learned_paper_metrics.json')
            if calibration['selected_checkpoint']['sha256'] != replay['checkpoint_sha256'] or len(replay['cases']) != 66 or not load(low / 'replay_start_audit.json')['exact']:
                raise ValueError('Supplemental calibration audit incomplete')
            supplemental.update(calibration=calibration, replay=replay)
            m = replay['paper_metrics']['metrics']
            lines += ['', '## Supplemental Low-error calibration', '',
                'This arm has no policy training or control result.', '',
                '| Group | E_g-mpjpe | E_mpjpe | E_acc | E_vel | Complete replay (%) |',
                '|---|---:|---:|---:|---:|---:|---:|',
                '| Low-error-N | ' + ' | '.join(f'{m[k]:.3f}' for k in FIELDS) + f' | {replay["paper_metrics"]["completion_pct"]:.1f} |']
            strata['supplemental_low_error'] = replay['stratified']
    (a.output/'stratified_metrics.json').write_text(json.dumps(strata,indent=2)+'\n')
    strata_lines = ['# Per-ankle servo-error strata', '',
        'Magnitude edges are fixed from training data. Errors use available samples with equal parent and task means. Bins can include different tasks. Entries overlap across ankles and are not independent trials.', '',
        'Inclusion is the percentage of planned scored samples for that ankle. Missing bins stay absent. Joint position and velocity below are not body errors.', '']
    stratum_runs = list(rows.items())
    if 'replay' in supplemental:
        stratum_runs.append(('supplemental', {'low_error': {'replay': supplemental['replay']}}))
    for run, arms in stratum_runs:
        if not any('replay' in item for item in arms.values()):
            continue
        strata_lines += ['## ' + run.capitalize(), '',
            '| Group | Ankle | Magnitude | Inclusion (%) | Global body error (mm) | Joint RMSE (rad) | Joint velocity RMSE (rad/s) |',
            '|---|---|---|---:|---:|---:|---:|']
        for arm, item in arms.items():
            if 'replay' not in item:
                continue
            for key, s in sorted(item['replay']['stratified'].items()):
                parts = key.split('_')
                ankle = ('Left pitch','Left roll','Right pitch','Right roll')[int(parts[0][1:])]
                magnitude = ('Small','Medium','Large')[int(parts[1][3:])]
                inclusion = 100*s['included_frame_entries']/(66*49)
                strata_lines.append(f'| {NAMES[arm]} | {ankle} | {magnitude} | {inclusion:.1f} | {s["global_position_mm"]:.3f} | {s["joint_position_rmse_rad"]:.5f} | {s["joint_velocity_rmse_rad_s"]:.5f} |')
    (a.output/'stratified_metrics.md').write_text('\n'.join(strata_lines).rstrip()+'\n')
    ft_text = ('The first run includes a matched FT-only policy.' if 'ft_only' in rows.get('primary', {})
               else 'The new matched FT-only policy is pending; no comparison against it is available yet.')
    lines += ['', 'Stratified replay uses separate ankle magnitude bins from the training pool. Missing bins are not filled. Frame entries can overlap across ankles. Joint-error tables are in stratified_metrics.md; raw strata and inclusion are in stratified_metrics.json.', '',
        'Phase quotas cover the available training pool, rather than the full reference. Contact uses a height/speed proxy. Continuous speed and contact distributions still differ. No same-domain floor is subtracted. The selected budget is not total acquisition cost.', '',
        ft_text + ' The repeat compares two selectors at its own shared seed; it has no new matched FT-only. Runs are reported separately. Two seeds do not establish a reliable ranking.', '']
    if (a.root / 'repeat/replay_metrics.md').exists():
        lines += ['[Second-seed calibration report](repeat/replay_metrics.md). Calibration can finish before its policy evaluation; these endpoints remain separate.', '']
    (a.output/'metrics.md').write_text('\n'.join(lines).rstrip()+'\n')
    (a.output/'chart_data.json').write_text(json.dumps({'runs':rows,'pending':pending,'selection':selection,'supplemental':supplemental},indent=2)+'\n')
    (a.output/'paired_contrasts.json').write_text(json.dumps(contrasts,indent=2)+'\n')
    print('Reported completed audited arms; pending/skipped:',pending)


if __name__=='__main__':
    main()
