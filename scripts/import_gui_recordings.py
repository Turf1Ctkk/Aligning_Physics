"""Make three comparison GIFs from the author's actual IsaacGym videos."""
import argparse
import hashlib
import json
import math
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
    parser.add_argument('--starts', type=Path, help='Optional JSON: video key to clip start time in seconds; this does not establish simulator-phase alignment.')
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
                  'viewer': {'domain': 'B', 'ankle_kp': 16, 'seed': 8101, 'num_envs': 1},
                  'alignment': 'Same elapsed recording time, not simulator-phase synchronization.',
                  'editing': 'Fixed spatial crop within each pair; original video speed, sampled to 20 fps. A blank end card replaces an ended recording; no motion frames are synthesized or frozen.',
                  'clips': []}
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
        available = [n / rate - start for n, rate, start in zip(counts, rates, offsets)]
        duration = min(horizon, max(available))
        if min(available) < 1:
            raise ValueError('Less than one second of actual video remains for ' + task)
        dimensions = [(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) for cap in caps]
        if dimensions != [(1600, 900), (1600, 900)]:
            raise ValueError('Review the spatial crop for changed video dimensions before importing')
        # Keep the entire vertical field for CR7's jump and raised hands.
        crop = (400, 0 if task == 'cr7' else 150, 1250, 900)
        height = round((crop[3] - crop[1]) * 480 / (crop[2] - crop[0]))
        frames = []
        for index in range(math.ceil(duration * 20)):
            panels = []
            for cap, start, rate, remaining in zip(caps, offsets, rates, available):
                if index / 20 >= remaining:
                    im = Image.new('RGB', (480, height), '#eeeeee')
                    draw = ImageDraw.Draw(im)
                    draw.text((125, height // 2 - 15), 'Recording ended', font=font, fill='#444444')
                    panels.append(im)
                    continue
                cap.set(cv2.CAP_PROP_POS_FRAMES, int((start + index / 20) * rate))
                ok, frame = cap.read()
                if not ok:
                    raise ValueError('Missing source frame; no frame is invented or repeated')
                im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                im = im.crop(crop).resize((480, height), Image.Resampling.LANCZOS)
                panels.append(im)
            canvas = Image.new('RGB', (960, height + 72), '#ffffff')
            draw = ImageDraw.Draw(canvas)
            draw.text((12, 6), title + ' | local GUI illustration', font=font, fill='#222222')
            for x, label, im in zip((0, 480), ('Left: ' + left_title, 'Right: ' + right_title), panels):
                draw.text((x + 12, 37), label, font=font, fill='#222222')
                canvas.paste(im, (x, 72))
            frames.append(canvas.quantize(colors=256))
        target = output / (task + '.gif')
        durations = [50] * len(frames)
        durations[-1] = max(10, round((duration - (len(frames) - 1) / 20) * 100) * 10)
        frames[0].save(target, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=False)
        if target.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('GIF exceeds 20 MiB; reduce panel width explicitly before publication')
        for cap in caps:
            cap.release()
        provenance['clips'].append({'task': title, 'gif': target.name, 'seconds': sum(durations) / 1000,
            'gif_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'gif_bytes': target.stat().st_size,
            'crop_xyxy': crop, 'output_fps': 20,
            'sources': [{'key': k, 'video_sha256': hashlib.sha256(files[k].read_bytes()).hexdigest(),
                         'start_s': start, 'source_fps': rate, 'source_frames': int(count),
                         'source_seconds': count / rate, 'checkpoint_sha256': models[k]['checkpoint_sha256']}
                        for k, start, rate, count in zip(keys, offsets, rates, counts)]})
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    start_marker, end_marker = '<!-- GUI_VISUALIZATIONS_START -->', '<!-- GUI_VISUALIZATIONS_END -->'
    section = '\n'.join([start_marker, '',
        'Author-recorded IsaacGym clips in target B, using seed 8101 and one robot. These are partial recordings, not full-motion evaluations. Starts are not phase-synchronized. A blank panel marks the end of a recording.', '',
        '**Squat — Left: Original. Right: repaired ASAP delta action.** Both follow the squat and stay upright in these clips. Torso and knee alignment differ during the descent. The aggregate success rates are 44.8% and 91.7%; FT-only remains stronger at 100%.', '',
        '![Squat: Original and repaired ASAP](results/visualizations/squat.gif)', '',
        '**CR7 — Left: Original. Right: FT-only.** Both jump and return to standing. Arm alignment with the reference differs around takeoff. Both reach 100% aggregate success; fine-tuning lowers global error but raises root-relative error.', '',
        '![CR7: Original and FT-only](results/visualizations/cr7.gif)', '',
        '**Step — Left: Original. Right: passive SysID.** The original leans sharply away from the reference points, while SysID stays upright during the step. Aggregate success is 1.0% versus 100%. The fitted gains are a surrogate, not recovery of the target parameters.', '',
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
