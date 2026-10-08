"""Check metric units and failure handling without physics or learned models."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'overlays'))
from research.asap_diagnostics.paper_metrics import errors, trial_metrics, summarize

p = np.zeros((8, 27, 3))
r = p.copy()
p[..., 0] = .1
m = errors(p, r)
assert np.isclose(m['global_position_mm'], 100)
assert m['root_relative_position_mm'] == 0
assert m['body_velocity_mm_frame'] == 0
p[..., 0] = np.arange(8)[:, None] * .002
m = errors(p, r)
assert np.isclose(m['body_velocity_mm_frame'], 2)
assert np.isclose(m['root_velocity_mm_frame'], 2)
assert np.isclose(m['body_acceleration_mm_frame2'], 0)
p[..., 0] = np.arange(8)[:, None] ** 2 * .001
assert np.isclose(errors(p, r)['body_acceleration_mm_frame2'], 2)
# A single point at 0.6 m does not violate a mean-body 0.5 m rule.
p[:] = 0
p[:, 1, 0] = .6
record = dict(paper_body_pos=p, paper_reference_body_pos=r, fps=50,
              terminate=np.zeros(8), motion_times=np.arange(8) / 50)
a = trial_metrics(record)
assert a['paper_tracking_success']
# The reset row and later records have huge jumps; they must never enter scores.
record['terminate'][5] = 1
record['paper_body_pos'][5:] = 1000
b = trial_metrics(record)
assert not b['complete'] and b['scored_frames'] == 4
assert b['metrics']['body_velocity_mm_frame'] == 0
assert b['metrics']['body_acceleration_mm_frame2'] == 0
assert summarize([a, b])['completion_pct'] == 50
record['terminate'][:] = 0
record['paper_body_pos'][:] = .6
assert not trial_metrics(record)['paper_tracking_success']
print('PASS: body/root formulas, per-frame units, mean-distance success, reset exclusion and percentage reporting. CPU only.')
from research.asap_diagnostics.paper_replay_queue import score
ref = dict(body_pos=np.zeros((60,24,3)), fps=50, body_names=[str(i) for i in range(24)])
pred = dict(body_pos=ref['body_pos'].copy(), fps=50, body_names=ref['body_names'],
            motion_times=(np.arange(55)+1)/50, terminate=np.zeros(55))
pred['body_pos'] = pred['body_pos'][:55]
pred['body_pos'][:, :, 0] = np.arange(55)[:,None] * .002
check = score(ref, pred, 1.)
assert check['complete'] and check['scored_frames'] == 49
assert np.isclose(check['metrics']['body_velocity_mm_frame'], 2)
assert np.isclose(check['metrics']['body_acceleration_mm_frame2'], 0)
pred['terminate'][20] = 1
pred['body_pos'][20:] = 1000
check = score(ref, pred, 1.)
assert not check['complete'] and check['scored_frames'] == 19
assert np.isclose(check['metrics']['body_velocity_mm_frame'], 2)
print('PASS: replay interpolation grid, measured 24-body scope, warm-frame exclusion and reset handling. CPU only.')
