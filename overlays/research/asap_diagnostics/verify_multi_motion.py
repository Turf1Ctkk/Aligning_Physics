"""CPU tests for split boundaries, grid starts, recording, and orchestration."""
import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import joblib
import numpy as np
import torch
import yaml

from dataset_tools import continuous_segments, replay_metrics, slice_motion
import multi_motion_pipeline as pipeline


HERE = Path(__file__).resolve().parent
NAMES = ['pelvis'] + ['body' + str(i) for i in range(1,24)]
NAMES[6], NAMES[12] = 'left_ankle_roll_link', 'right_ankle_roll_link'


def motion(n=80, offset=0.):
    return {'fps': 50., 'dof': np.full((n,23), offset, dtype=np.float32),
            'dof_vel': np.zeros((n,23), dtype=np.float32),
            'action': np.full((n,23), offset/2, dtype=np.float32),
            'root_trans_offset': np.zeros((n,3), dtype=np.float32),
            'root_rot': np.tile([0.,0.,0.,1.], (n,1)),
            'root_lin_vel': np.zeros((n,3)), 'root_ang_vel': np.zeros((n,3)),
            'body_pos': np.zeros((n,24,3)), 'body_names': NAMES,
            'pose_aa': np.zeros((n,27,3)), 'terminate': np.zeros(n, dtype=bool),
            'motion_times': np.arange(n, dtype=np.float32)/50}


def runtime_functions():
    tree = ast.parse((HERE / 'dataset_runtime.py').read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    from scipy.spatial.transform import Rotation
    namespace = {'torch': torch, 'np': np, 'Rotation': Rotation}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 'dataset_runtime.py', 'exec'), namespace)
    return namespace


def main():
    # A reset row belongs to a reset state with a preceding-episode action:
    # drop it and never create a transition across it.
    m = motion(140)
    m['terminate'][65] = True
    m['motion_times'][66:] = np.arange(74)/50
    segments, audit = continuous_segments(m)
    assert [(a,b) for a,b,_ in segments] == [(0,65), (66,140)]
    assert audit['reset_rows'] == [65]
    assert all(not s['terminate'].any() for _,_,s in segments)
    assert all(s['motion_times'][0] == 0 for _,_,s in segments)

    functions = runtime_functions()
    frames = torch.tensor([52,188] * 1000)
    dt = torch.ones_like(frames, dtype=torch.float32)*0.02
    times = functions['sample_grid_starts'](frames, dt, 1.0, .02)
    assert torch.allclose(times/dt, torch.round(times/dt), atol=1e-5)
    assert torch.all(times + 51*.02 <= (frames-1)*dt + 1e-6)
    assert not times[::2].any()

    class FakeReplayBase:
        def set_is_evaluating(self):
            self.is_evaluating = True
    runtime_tree = ast.parse((HERE/'dataset_runtime.py').read_text())
    grid_class = next(node for node in runtime_tree.body if isinstance(node,ast.ClassDef) and node.name=='GridDeltaReplay')
    namespace = {'DeltaA_OpenLoop':FakeReplayBase, 'sample_grid_starts':functions['sample_grid_starts']}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[grid_class],type_ignores=[])), 'grid-env', 'exec'),namespace)
    ordered_calls = []
    grid = namespace['GridDeltaReplay']()
    grid._motion_lib = SimpleNamespace(load_motions=lambda **kw: ordered_calls.append(kw),_motion_dt=torch.ones(3)*.02)
    grid.set_is_evaluating()
    assert grid.is_evaluating and ordered_calls == [{'random_sample':False,'start_idx':0}]

    # Independently check world-coordinate origin normalization in the live
    # recorder function, including body positions and world root velocities.
    root = torch.zeros(2,13)
    root[:,3:7] = torch.tensor([0.,0.,0.,1.])
    origins = torch.tensor([[0.,0.,0.],[20.,40.,0.]])
    root[:,:3] = origins + torch.tensor([.1,.2,.8])
    root[:,7:10] = torch.tensor([1.,2.,3.])
    env = SimpleNamespace(
        num_envs=2, dt=.02, env_origins=origins,
        config=SimpleNamespace(simulator=SimpleNamespace(config=SimpleNamespace(name='isaacgym')),
                               robot=SimpleNamespace(motion=SimpleNamespace(extend_config=[1,2,3]))),
        simulator=SimpleNamespace(robot_root_states=root, dof_pos=torch.zeros(2,23),
                                  dof_vel=torch.ones(2,23), _rigid_body_pos=root[:,:3,None].transpose(1,2).repeat(1,24,1)),
        _motion_lib=SimpleNamespace(mesh_parsers=SimpleNamespace(dof_axis=torch.tensor([[1.,0.,0.]]*23))),
        actions=torch.ones(2,23), reset_buf=torch.zeros(2),
        episode_length_buf=torch.tensor([1,1]), motion_start_times=torch.zeros(2))
    snap = functions['snapshot'](env)
    np.testing.assert_allclose(snap['root_trans_offset'][0], snap['root_trans_offset'][1], atol=2e-6)
    np.testing.assert_allclose(snap['body_pos'][0], snap['body_pos'][1], atol=2e-6)
    np.testing.assert_array_equal(snap['root_lin_vel'][0], [1,2,3])
    assert snap['pose_aa'].shape == (2,27,3)

    ref = motion()
    pred = slice_motion(ref, 1,56)
    pred['motion_times'] = np.arange(1,56)/50
    pred['body_pos'] += .001
    pred['root_trans_offset'] += .001
    score = replay_metrics(ref, pred, 1.0)
    assert score['complete'] and score['frames'] == 50
    np.testing.assert_allclose(score['global_body_mpjpe_mm'], np.sqrt(3), rtol=1e-6)
    assert score['root_relative_body_mpjpe_mm'] < 1e-6
    pred['terminate'][20] = True
    assert not replay_metrics(ref, pred, 1.)['complete']

    with tempfile.TemporaryDirectory(prefix='asap-multi-data-') as temp:
        work = Path(temp)
        (work/'raw').mkdir()
        for task_index, task in enumerate(pipeline.TASKS):
            raw = {'motion'+str(i): motion(offset=1 + task_index + i*.001) for i in range(40)}
            joblib.dump(raw, work/'raw'/(task+'.pkl'))
        plan = {'rollouts_per_motion':40, 'horizon_s':1., 'training_seed':0,
                'iterations':1000, 'validation_checkpoints':[500,1000]}
        with contextlib.redirect_stdout(io.StringIO()):
            datasets = pipeline.build(work, plan)
        assert [datasets[name]['rollout_groups'] for name in ('balanced1','balanced10','balanced_full')] == [3,30,90]
        groups = [set(datasets[name]['groups']) for name in ('balanced1','balanced10','balanced_full')]
        assert groups[0] <= groups[1] <= groups[2]
        val = joblib.load(work/'datasets/val.pkl')
        test = joblib.load(work/'datasets/test.pkl')
        vg, tg = [{m['dataset_group'] for m in data.values()} for data in (val,test)]
        assert not (groups[2]&vg or groups[2]&tg or vg&tg)
        assert datasets['val']['cases'] == datasets['test']['cases'] == 45

        # Exercise command generation and report mapping with a fake evaluator.
        # This does not simulate physics or execute a checkpoint.
        def fake_launch(workdir, mode, seed, overrides, log_path):
            args = dict(arg.lstrip('+').split('=',1) for arg in overrides)
            assert args['algo._target_'] == pipeline.RECORDER
            assert args['env._target_'] == pipeline.REPLAY_ENV
            refs = joblib.load(args['robot.motion.motion_file'])
            predictions = {}
            for i, case in enumerate(refs.values()):
                # Export valid first 50 frames plus reset at the clip end.
                pred = dict(case)
                for field in ('dof','dof_vel','root_trans_offset','body_pos'):
                    arr = case[field]
                    pred[field] = arr[np.minimum(np.arange(1,56),len(arr)-1)].copy()
                pred['motion_times'] = np.arange(1,56)/50
                pred['terminate'] = np.zeros(55,dtype=bool)
                pred['terminate'][51] = True
                predictions['motion'+str(i)] = pred
            output = Path(args['env.config.dataset_record_path'])
            output.parent.mkdir(parents=True,exist_ok=True)
            joblib.dump(predictions,output)
        pipeline.launch = fake_launch
        report = pipeline.evaluate_batch(work,plan,work/'fake.pt','val','fixture',zero=True)
        assert report['summary']['1.0']['complete_cases'] == 45
        assert report['summary']['1.0']['equal_task_mean']['global_body_mpjpe_mm'] == 0

        # The full controller only selects checkpoints from validation scores.
        original_fake = pipeline.launch
        commands = []
        def fake_full_launch(workdir, mode, seed, overrides, log_path):
            args = dict(arg.lstrip('+').split('=',1) for arg in overrides)
            commands.append((mode,args))
            if mode == 'train':
                assert args['env._target_'] == pipeline.REPLAY_ENV
                assert args['checkpoint'] == 'null'
                assert args['robot.motion.use_recorded_velocities'] == 'True'
                output = Path(args['experiment_dir'])
                output.mkdir(parents=True,exist_ok=True)
                (output/'model_500.pt').touch()
                (output/'model_1000.pt').touch()
            else:
                original_fake(workdir,mode,seed,overrides,log_path)
                output = Path(args['env.config.dataset_record_path'])
                predictions = joblib.load(output)
                # Favor 1000 on validation; test output does not affect selection.
                if args['env.config.zero_delta_a'] == 'False':
                    shift = .001 if args['checkpoint'].endswith('model_1000.pt') else .002
                    for pred in predictions.values():
                        pred['body_pos'] += shift
                joblib.dump(predictions,output)
        plan['training_num_envs'] = 2048
        pipeline.launch = fake_full_launch
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.train(work,plan,datasets)
            pipeline.evaluate(work,plan)
        choices = json.loads((work/'selected_checkpoints.json').read_text())
        assert all(it == 1000 for it in choices.values())
        assert len([mode for mode,_ in commands if mode=='train']) == 3
        assert len([mode for mode,_ in commands if mode=='eval']) == 13

        # Check live recorder callback timing and export layout with a fake PPO.
        recorder_class = next(node for node in runtime_tree.body if isinstance(node,ast.ClassDef)
                              and node.name=='RolloutRecorderPPO')
        class FakePPO:
            def __init__(self,env): self.env=env
            def _pre_eval_env_step(self,state): return state
            def _post_eval_env_step(self,state): return state
        snapshots = []
        def fake_snapshot(env):
            i = len(snapshots)
            values = {key:np.repeat(np.asarray(value[i])[None],2,axis=0)
                      for key,value in motion(3).items() if key not in ('fps','body_names')}
            values['motion_times'] = np.full(2,(i+1)*.02)
            snapshots.append(values)
            return values
        env = SimpleNamespace(num_envs=2,dt=.02,config=SimpleNamespace(
            dataset_record_steps=3,dataset_record_path=str(work/'callback_record.pkl'),
            robot=SimpleNamespace(body_names=NAMES)))
        namespace = {'PPO':FakePPO,'snapshot':fake_snapshot,'np':np,'Path':Path,'joblib':joblib}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[recorder_class],type_ignores=[])),
                     'recorder', 'exec'),namespace)
        recorder = namespace['RolloutRecorderPPO'](env)
        recorder._pre_eval_env_step({})
        recorder._pre_eval_env_step({'step':0})
        assert len(recorder.dataset_frames)==1
        recorder._post_eval_env_step({'step':0})
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                recorder._post_eval_env_step({'step':1})
        except SystemExit as exit:
            assert exit.code == 0
        else:
            raise AssertionError('Recorder did not stop at its requested frame count')
        recorded = joblib.load(work/'callback_record.pkl')
        assert len(recorded)==2 and len(recorded['motion0']['dof'])==3
        np.testing.assert_allclose(recorded['motion0']['motion_times'],[.02,.04,.06])

        # Actual rg inventory and source metadata resolution; synthetic .pt
        # placeholders are never loaded or executed.
        fixture_root = work/'prepare_fixture'
        # Self-contained metadata fixture: no user checkpoint/config is read.
        config_template = {
            'env': {'_target_':'humanoidverse.envs.motion_tracking.motion_tracking.LeggedRobotMotionTracking'},
            'robot': {
                'dof_obs_size':23, 'dof_names':['joint'+str(i) for i in range(23)],
                'motion':{'motion_file':''},
                'control':{'action_scale':.25, 'stiffness':{'ankle_pitch':20,'ankle_roll':20}},
                'asset':{'self_collisions':0},
                'init_state':{'default_joint_angles':{'joint'+str(i):0. for i in range(23)}},
            },
            'simulator':{'config':{'sim':{'fps':200,'control_decimation':4}}},
        }
        for i,task in enumerate(pipeline.TASKS):
            folder = fixture_root/'logs'/task
            folder.mkdir(parents=True)
            ref_path = fixture_root/'refs'/(task+'.pkl')
            ref_path.parent.mkdir(exist_ok=True)
            joblib.dump({'motion':motion()},ref_path)
            config = yaml.safe_load(yaml.safe_dump(config_template))
            config['experiment_name']='MotionTracking_'+task
            config['robot']['motion']['motion_file']=str(ref_path)
            (folder/'config.yaml').write_text(yaml.safe_dump(config))
            (folder/('model_'+str(6000+i*1000)+'.pt')).touch()
        markers = {'humanoidverse/envs/delta_a/delta_a_open_loop.py':'def _get_reference_motion_times',
                   'humanoidverse/utils/motion_lib/motion_lib_base.py':'nearest_frame _apply_recorded_velocities'}
        for filename,content in markers.items():
            path=fixture_root/filename
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content)
        original_root=pipeline.ROOT
        pipeline.ROOT=fixture_root
        args=SimpleNamespace(work_dir=fixture_root/'result',rollouts=40,cr7=None,squat=None,step=None,
                             seed=0,iterations=1000,num_envs=2048)
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.prepare(args)
        pipeline.ROOT=original_root
        frozen=json.loads((args.work_dir/'plan.json').read_text())
        assert set(frozen['tasks'])==set(pipeline.TASKS)

        # Explicit paths may live outside logs; they must bypass discovery.
        external = fixture_root/'external_training'
        external.mkdir()
        explicit_paths = {}
        for task in pipeline.TASKS:
            folder=external/task
            folder.mkdir()
            source_folder=fixture_root/'logs'/task
            (folder/'config.yaml').write_text((source_folder/'config.yaml').read_text())
            checkpoint=folder/'model_6000.pt'
            checkpoint.touch()
            explicit_paths[task]=checkpoint
        pipeline.ROOT=fixture_root
        args.work_dir=fixture_root/'explicit_result'
        args.cr7,args.squat,args.step=[explicit_paths[t] for t in pipeline.TASKS]
        original_run=pipeline.subprocess.run
        def forbid_discovery(*a,**kw):
            raise AssertionError('Explicit checkpoint paths must not scan logs')
        pipeline.subprocess.run=forbid_discovery
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.prepare(args)
        finally:
            pipeline.subprocess.run=original_run
            pipeline.ROOT=original_root
        frozen=json.loads((args.work_dir/'plan.json').read_text())
        assert all(frozen['tasks'][t]['checkpoint']==str(explicit_paths[t]) for t in pipeline.TASKS)
    print('PASS: episode splitting, group isolation, nested 3/30/90 datasets, grid/full-horizon starts,')
    print('world-coordinate recording, 24-body metrics, and mocked evaluation orchestration.')
    print('Scope: CPU checks only; no IsaacGym physics, GPU training, or server execution.')


if __name__ == '__main__':
    main()
