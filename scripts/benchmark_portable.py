#!/usr/bin/env python3
"""Compare exact source frames and full exports against an unmodified checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
STYLES = ('bars', 'scope', 'qutrit-galaxy', 'gluball-knot', 'etq-graph-walk')


def worker(folder, output):
    sys.path.insert(0, str(folder))
    sys.path.insert(0, str(ROOT/'tests'))
    import PIL
    from a2v.core import Job, convert
    from a2v.visualizer import SAMPLES, render
    from fixtures import audio
    source = audio(output/'signal.wav', 2.017)
    # WAV fixture has a 44-byte PCM header; wave handles it without assumptions.
    import wave
    with wave.open(str(source)) as stream:
        pcm = stream.readframes(stream.getnframes())
    windows = [pcm[i:i+SAMPLES*4] for i in range(0, len(pcm), SAMPLES*4)]
    result = {'pillow': PIL.__version__, 'styles': {}}
    for style in STYLES:
        digest = hashlib.sha256()
        start = time.perf_counter()
        for index, window in enumerate(windows):
            digest.update(render(window, style, index))
        elapsed = time.perf_counter()-start
        target = output/(style+'.mp4')
        start = time.perf_counter()
        exported = convert(Job(source, target, resolution='720p', style=style, title='Performance — exact output'))
        seconds = time.perf_counter()-start
        assert exported.verified_frames == 61
        result['styles'][style] = {'render_seconds': elapsed, 'export_seconds': seconds,
            'frame_sha256': digest.hexdigest(), 'mp4_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--work', type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker.resolve(), args.work.resolve())
        return
    if not args.reference or not args.output:
        parser.error('--reference and --output are required')
    report = {'baseline_commit': '255794c166f70b535c3a1a8f8a6609882e9b8f17',
        'method': '3 alternating pairs in isolated subprocesses; 61 dynamic stereo frames (2.017 s), 720p with title; same interpreter/Pillow/FFmpeg; complete decode/render/encode/verification/publication. render_seconds also includes SHA-256 of source frames.',
        'environment': {'python': sys.version, 'platform': platform.platform(),
            'cpu': next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                         if line.startswith('model name')), platform.machine()) if Path('/proc/cpuinfo').exists() else platform.processor(),
            'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]},
        'candidate_source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'a2v').glob('*.py'))
            if p.name in ('__init__.py', 'core.py', 'process.py', 'visualizer.py', 'title.py', 'angles.py', 'etq.py', 'runtime.py')},
        'runs': {'reference': [], 'candidate': []}, 'styles': {}}
    with tempfile.TemporaryDirectory(prefix='a2v-benchmark-') as directory:
        for repeat in range(3):
            for kind in (('reference', 'candidate') if repeat%2 == 0 else ('candidate', 'reference')):
                folder = args.reference if kind == 'reference' else ROOT
                work = Path(directory)/f'{kind}-{repeat}'
                work.mkdir()
                raw = subprocess.check_output([sys.executable, str(Path(__file__).resolve()), '--worker', str(folder), '--work', str(work)], text=True)
                report['runs'][kind].append(json.loads(raw))
                print(kind, repeat+1, 'complete', flush=True)
    for style in STYLES:
        all_runs = [run['styles'][style] for runs in report['runs'].values() for run in runs]
        for key in ('frame_sha256', 'mp4_sha256'):
            if len({run[key] for run in all_runs}) != 1:
                raise RuntimeError(f'{style}: exact {key} parity failed')
        row = {'exact_source_frame_parity': True, 'exact_mp4_parity': True,
               'frame_sha256': all_runs[0]['frame_sha256'], 'mp4_sha256': all_runs[0]['mp4_sha256']}
        for metric in ('render_seconds', 'export_seconds'):
            medians = {kind: statistics.median(run['styles'][style][metric] for run in runs)
                       for kind, runs in report['runs'].items()}
            row[metric] = {'median': medians, 'reduction_percent': 100*(1-medians['candidate']/medians['reference'])}
        report['styles'][style] = row
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(args.output)


if __name__ == '__main__':
    main()
