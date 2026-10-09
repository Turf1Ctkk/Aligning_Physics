"""Make three comparison GIFs from the author's actual IsaacGym videos."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

PAIRS = (
    ('squat', 'SquatL1', 'original', 'Original', 'asap', 'ASAP (repaired)', 5.22),
    ('cr7', 'CR7', 'original', 'Original', 'ft', 'FT-only', 3.92),
    ('step', 'StepFBL1', 'original', 'Original', 'sysid', 'Passive SysID', 3.92),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recordings', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--starts', type=Path, help='Optional JSON: video key to start time in seconds.')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    manifest = json.loads(args.manifest.read_text())
    models = {r['key']: r for r in manifest['policies']}
    starts = json.loads(args.starts.read_text()) if args.starts else {}
    files = {f'{task}_{method}': args.recordings / f'{task}_{method}.mp4'
             for task, _, left, _, right, _, _ in PAIRS for method in (left, right)}
    missing = [str(p) for p in files.values() if not p.is_file()]
    if missing:
        raise SystemExit('Record these videos first; no GIF or README edit was made:\n' + '\n'.join(missing))
    output = repo / 'results' / 'visualizations'
    output.mkdir(parents=True, exist_ok=True)
    font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    font = ImageFont.truetype(str(font_path), 20) if font_path.exists() else ImageFont.load_default()
    provenance = {'scope': 'Author-recorded local GUI examples, not aggregate evaluation or a selected trial ranking.',
                  'viewer': {'domain': 'B', 'ankle_kp': 16, 'seed': 8101, 'num_envs': 1}, 'clips': []}
    for task, title, left, left_title, right, right_title, horizon in PAIRS:
        keys = [f'{task}_{left}', f'{task}_{right}']
        caps = [cv2.VideoCapture(str(files[k])) for k in keys]
        rates = [cap.get(cv2.CAP_PROP_FPS) for cap in caps]
        counts = [cap.get(cv2.CAP_PROP_FRAME_COUNT) for cap in caps]
        if any(not cap.isOpened() for cap in caps) or min(rates) <= 0:
            raise ValueError('Cannot decode the actual recordings for ' + task)
        offsets = [float(starts.get(k, 0)) for k in keys]
        if min(offsets) < 0:
            raise ValueError('Clip offsets must be nonnegative')
        duration = min([horizon] + [n / rate - start for n, rate, start in zip(counts, rates, offsets)])
        if duration < 1:
            raise ValueError('Less than one second of actual video remains for ' + task)
        frames = []
        for index in range(int(duration * 20)):
            panels = []
            for cap, start in zip(caps, offsets):
                cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * (start + index / 20))
                ok, frame = cap.read()
                if not ok:
                    raise ValueError('Missing source frame; no frame is invented or repeated')
                im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                im = im.resize((480, round(im.height * 480 / im.width)), Image.Resampling.LANCZOS)
                panels.append(im)
            height = max(im.height for im in panels)
            canvas = Image.new('RGB', (960, height + 72), '#ffffff')
            draw = ImageDraw.Draw(canvas)
            draw.text((12, 6), title + ' | local GUI illustration', font=font, fill='#222222')
            for x, label, im in zip((0, 480), (left_title, right_title), panels):
                draw.text((x + 12, 37), label, font=font, fill='#222222')
                canvas.paste(im, (x, 72))
            frames.append(canvas.quantize(colors=128))
        target = output / (task + '.gif')
        frames[0].save(target, save_all=True, append_images=frames[1:], duration=50, loop=0, optimize=False)
        if target.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('GIF exceeds 20 MiB; reduce panel width explicitly before publication')
        for cap in caps:
            cap.release()
        provenance['clips'].append({'task': title, 'gif': target.name, 'seconds': len(frames) / 20,
            'sources': [{'key': k, 'video_sha256': hashlib.sha256(files[k].read_bytes()).hexdigest(),
                         'start_s': start, 'checkpoint_sha256': models[k]['checkpoint_sha256']}
                        for k, start in zip(keys, offsets)]})
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    start_marker, end_marker = '<!-- GUI_VISUALIZATIONS_START -->', '<!-- GUI_VISUALIZATIONS_END -->'
    section = '\n'.join([start_marker, '',
        'Local IsaacGym demonstrations in target B. Each pair uses seed 8101 and one robot. These clips illustrate behavior; the figures above report aggregate results.', '',
        'Squat: Original and repaired ASAP. FT-only remains the stronger success baseline in the quantitative comparison.', '',
        '![Squat: Original and repaired ASAP](results/visualizations/squat.gif)', '',
        'CR7: Original and FT-only. Both have 100% success. Global error improves, while relative error increases.', '',
        '![CR7: Original and FT-only](results/visualizations/cr7.gif)', '',
        'Step: Original and passive SysID. The fitted gains are a surrogate, not recovery of the target parameters.', '',
        '![Step: Original and passive SysID](results/visualizations/step.gif)', '', end_marker])
    readme = repo / 'README.md'
    text = readme.read_text()
    if start_marker in text:
        before, rest = text.split(start_marker, 1)
        _, after = rest.split(end_marker, 1)
        text = before + section + after
    else:
        anchor = '\n## 6. Observations that motivate the question'
        if anchor not in text:
            raise ValueError('README insertion point changed; inspect before editing')
        text = text.replace(anchor, '\n' + section + '\n' + anchor, 1)
    readme.write_text(text)
    print('Created three GIFs and README embeds from actual videos. Visually review before committing.')


if __name__ == '__main__':
    main()
