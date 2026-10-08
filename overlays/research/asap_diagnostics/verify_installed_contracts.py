"""Check the installed source directly; never apply patches to patched files."""
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace

import torch
from verify_contracts import method, torque_env
from verify_replay_fidelity import action_indices, velocity_checks

ROOT = Path(__file__).resolve().parents[2]


def main():
    torch.manual_seed(0)
    nominal, delta = torch.rand(5, 23) + .1, torch.randn(5, 23) * .2
    open_path = ROOT / 'humanoidverse/envs/delta_a/delta_a_open_loop.py'
    closed_path = ROOT / 'humanoidverse/envs/delta_a/delta_a_closed_loop.py'
    with contextlib.redirect_stdout(io.StringIO()):
        a = method(open_path, '_compute_torques')(torque_env(nominal, delta), delta.clone())
        b = method(closed_path, '_compute_torques')(torque_env(nominal, delta), nominal.clone())
    assert torch.allclose(a, b), 'Installed open/closed residual units differ'
    fake = SimpleNamespace(episode_length_buf=torch.tensor([1]), dt=.02, motion_start_times=torch.tensor([0.]))
    time = method(open_path, '_get_reference_motion_times')(fake)
    assert torch.allclose(time, torch.tensor([.02]))
    source = ROOT / 'humanoidverse/utils/motion_lib/motion_lib_base.py'
    action_indices(source, 188, 50.00000111758712, 55)
    velocity_checks(source)
    from controlled_sampling import hierarchical_weights, summarize_weights
    fixture = {'a': {'dataset_task':'A', 'dataset_group':'A0'},
               'b': {'dataset_task':'A', 'dataset_group':'A0'},
               'c': {'dataset_task':'A', 'dataset_group':'A1'},
               'd': {'dataset_task':'B', 'dataset_group':'B0'}}
    totals = summarize_weights(fixture, hierarchical_weights(fixture))
    assert totals['tasks'] == {'A': .5, 'B': .5}
    assert totals['groups'] == {'A0': .25, 'A1': .25, 'B0': .5}
    print('PASS: installed residual units, post-step replay time, action grid, recorded velocities, hierarchical weights')
    print('Scope: CPU only; subsequent physical eval/training is required')


if __name__ == '__main__':
    main()
