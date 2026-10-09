"""Publish the primary calibration contrast without claiming pending control results."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
parser=argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
root=parser.parse_args().root
read=lambda p:json.loads(p.read_text())
servo=root/'primary/servo'; random=root/'primary/random'
new=read(servo/'learned_paper_metrics.json'); old=read(random/'learned_paper_metrics.json'); zero=read(random/'source20_zero_paper_metrics.json')
audit=read(servo/'calibration_audit.json'); start=read(servo/'replay_start_audit.json'); independent=read(servo/'replay_publication_audit.json')
assert audit['selected_checkpoint']['sha256']==new['checkpoint_sha256'] and audit['selected_transitions']==954
assert start['exact'] and start['learned_sha256']==new['record_sha256'] and start['source_zero_sha256']==zero['record_sha256']
assert new['target_sha256']==old['target_sha256']==zero['target_sha256']
assert len(new['cases'])==66 and new['complete_cases']==66
assert {c['key'] for c in new['cases']}=={c['key'] for c in old['cases']}
assert next(c for c in independent['checks'] if c['label']=='learned')['metrics']==new['paper_metrics']
fields=('global_position_mm','root_relative_position_mm','body_acceleration_mm_frame2','root_velocity_mm_frame')
titles=('$E_{g-mpjpe}$ (mm)','$E_{mpjpe}$ (mm)','$E_{acc}$ (mm/frame²)','$E_{vel}$, root (mm/frame)')
rows=[('Source20, zero correction',zero),('Random-N',old),('Servo-coverage-N',new)]
control_pending=read(servo/'status.json')['status']!='complete'
control_text=('The Step policy is still training.' if control_pending else 'Step control is reported separately in the full results.')
lines=['# Servo-coverage replay','', 'Calibration is complete and independently audited. Validation selects update 500 (49.31 mm) over update 1,000 (59.96 mm). Both candidates complete all validation cases. '+control_text,'',
'![Primary replay errors](../../servo_replay.png)','',
'Test errors use one second and 24 measured bodies. Both learned arms and the source-zero control complete 100% of test replays. Position is in mm, acceleration in mm/frame² and root velocity in mm/frame at 50 Hz.','',
'| Group | E_g-mpjpe | E_mpjpe | E_acc | E_vel |','|---|---:|---:|---:|---:|']
for name,r in rows:lines.append('| '+name+' | '+' | '.join('%.3f'%r['paper_metrics']['metrics'][k] for k in fields)+' |')
lines += ['', 'Servo-coverage has higher error than Random-N and zero correction on all four measures in this training run. The modest coverage increase did not improve calibration here. '+('Closed-loop transfer remains pending; no control ranking is available yet.' if control_pending else 'See the [full results](../../metrics.md) for the separate control comparison.'),'',
'The selected training floor is 19.61 mm, compared with 21.52 mm for Random. These reconstruction errors are retained without subtraction or window replacement. Continuous speed and contact-proxy distributions still differ. This comparison cannot identify a single causal feature.','',
'Actual records were checked for case identities and hashes, and all validation/test metric aggregates were recomputed. Learned and shared source-zero replays have exactly matching stored starts, actions and clocks. Both validation candidates and all raw test cases remain available.','',
'[Per-ankle strata](../../calibration_stratified_metrics.md). Magnitude bins are fixed from training; inclusion varies. Joint errors and body errors are separate measures.']
(servo/'replay_metrics.md').write_text('\n'.join(lines)+'\n')
fig,axes=plt.subplots(1,4,figsize=(14,4.2))
for ax,k,title in zip(axes,fields,titles):
    vals=[r['paper_metrics']['metrics'][k] for _,r in rows]
    bars=ax.bar(np.arange(3),vals,color=['#85919a','#3476A8','#D49A35']);ax.bar_label(bars,fmt='%.2f',fontsize=9,padding=3)
    ax.set_xticks(np.arange(3));ax.set_xticklabels(['Zero','Random-N','Servo coverage'],rotation=20,ha='right',fontsize=9)
    ax.set_title(title,fontsize=11);ax.set_ylim(0,max(vals)*1.22);ax.spines[['top','right']].set_visible(False)
fig.suptitle('Primary calibration: one-second replay; all test cases complete')
fig.tight_layout();fig.savefig(root/'servo_replay.png',dpi=180);plt.close(fig)
lines=['# Calibration replay by ankle servo error','',
'Bins use training-derived magnitude edges and unsaturated target transitions. Each row averages available case errors by parent and task. Inclusion is the share of planned scored samples for that ankle. Samples overlap across ankles; they are not independent trials.','',
'| Group | Ankle | Magnitude | Inclusion (%) | Global body error (mm) | Joint RMSE (rad) | Joint velocity RMSE (rad/s) |','|---|---|---|---:|---:|---:|---:|']
for name,r in rows[1:]:
    for key,s in sorted(r['stratified'].items()):
        a,b=key.split('_');ankle=('Left pitch','Left roll','Right pitch','Right roll')[int(a[1:])];mag=('Small','Medium','Large')[int(b[3:])]
        lines.append('| %s | %s | %s | %.1f | %.3f | %.5f | %.5f |'%(name,ankle,mag,100*s['included_frame_entries']/(66*49),s['global_position_mm'],s['joint_position_rmse_rad'],s['joint_velocity_rmse_rad_s']))
lines+=['','Missing bins remain absent. These bins group error magnitude; they do not separately test sign or prove a causal feature effect. No floor is subtracted.']
(root/'calibration_stratified_metrics.md').write_text('\n'.join(lines)+'\n')
print('PASS selected checkpoint, shared test identity, exact startup audit, recomputed physical metrics')
