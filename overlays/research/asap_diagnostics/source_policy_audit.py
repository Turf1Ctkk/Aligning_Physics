"""Evaluate frozen original/FT policies in source A; preserve the B protocol."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from research.asap_diagnostics.controlled_pipeline import launch, write
from research.asap_diagnostics.paper_metrics import summarize


def run(root, predecessor, cutoff):
    if root.exists():
        raise RuntimeError('Existing audit root; refuse silent resume')
    if json.loads((predecessor / 'status.json').read_text())['status'] != 'complete':
        raise RuntimeError('Predecessor incomplete')
    root.mkdir(parents=True)
    deadline = datetime.fromisoformat(cutoff).timestamp()
    manifest = json.loads((predecessor / 'frozen_manifest.json').read_text())
    entries = [e for e in manifest if e['method'] in ('vanilla', 'ft_only')]
    if len(entries) != 18:
        raise ValueError('Expected three tasks, two policies, three seeds')
    plan = {'created_utc': datetime.now(timezone.utc).isoformat(), 'cutoff_utc': cutoff,
            'purpose': 'Source-domain quality diagnostic; no training or model selection',
            'changes_from_B': ['ankle pitch and roll stiffness 16 to 20', 'output paths'],
            'source': str(predecessor), 'jobs': entries}
    write(root / 'queue_plan.json', plan)
    results = {}
    for i, entry in enumerate(entries):
        if subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip():
            raise RuntimeError('Unexpected GPU process')
        checkpoint = Path(entry['checkpoint'])
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != entry['checkpoint_sha256']:
            raise ValueError('Checkpoint changed')
        work = root / entry['task'] / entry['method']
        work.mkdir(parents=True, exist_ok=True)
        label = entry['label']
        replacement = {'robot.control.stiffness.ankle_pitch': '20', 'robot.control.stiffness.ankle_roll': '20',
                       'eval_log_dir': str(work / 'tracking' / (label + '_config')),
                       'env.config.dataset_record_path': str(work / 'tracking' / (label + '.pkl'))}
        overrides = []
        for arg in entry['overrides']:
            key = arg.split('=', 1)[0].lstrip('+')
            overrides.append('++' + key + '=' + replacement.pop(key) if key in replacement else arg)
        if replacement:
            raise ValueError('Missing expected override')
        write(root / 'status.json', {'status': 'running', 'completed_jobs': i, 'total_jobs': len(entries)})
        launch(work, 'eval', entry['seed'], overrides, label, deadline)
        report = json.loads((work / 'tracking' / (label + '.json')).read_text())
        results.setdefault(entry['task'], {}).setdefault(entry['method'], []).append((entry['seed'], report))
        write(root / 'status.json', {'status': 'running', 'completed_jobs': i + 1, 'total_jobs': len(entries)})
    combined = {}
    for task, methods in results.items():
        combined[task] = {}
        for method, reports in methods.items():
            trials = [dict(row, seed=seed) for seed, report in reports for row in report['trials']]
            combined[task][method] = {'summary': summarize(trials), 'trials': trials}
    write(root / 'comparison.json', combined)
    write(root / 'status.json', {'status': 'complete', 'completed_jobs': len(entries), 'total_jobs': len(entries)})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work-dir', type=Path, required=True)
    p.add_argument('--predecessor', type=Path, required=True)
    p.add_argument('--cutoff', default='2026-10-09T09:00:00+00:00')
    a = p.parse_args()
    try:
        run(a.work_dir, a.predecessor, a.cutoff)
    except Exception as exc:
        if a.work_dir.exists() and not (a.work_dir / 'status.json').exists():
            write(a.work_dir / 'failure.json', {'status': 'failed', 'error': repr(exc)})
        elif a.work_dir.exists() and json.loads((a.work_dir / 'status.json').read_text()).get('status') == 'running':
            write(a.work_dir / 'status.json', {'status': 'failed', 'error': repr(exc)})
        raise
