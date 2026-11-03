#!/usr/bin/env python3
"""Paired full-export benchmark against the pre-OPT source, with exact parity."""
import argparse
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
import PIL
from a2v import core, visualizer, title
from fixtures import audio


def module(path, name):
    spec = importlib.util.spec_from_file_location(name,path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True, help='folder with pre-OPT visualizer.py and title.py')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Compare both paths with the same post-review viewport correction. This
    # common geometry change is not credited to OPT and is recorded in the report.
    original_source = (args.reference/'visualizer.py').read_text()
    old = 'sx, sy, depth = 320+x*3//2, 187+y*7//10-z, y+z'
    new = 'sx, sy, depth = 320+x*6//5, 187+(y*7//10-z)*4//5, y+z'
    reference = module(args.reference/'visualizer.py','a2v.reference_visualizer')
    effective_source = original_source.replace(old, new)
    if effective_source != original_source:
        exec(compile(effective_source, str(args.reference/'visualizer.py'), 'exec'), reference.__dict__)
    reference_title = module(args.reference/'title.py','a2v.reference_title')
    report = {'environment': {'python':sys.version, 'pillow':PIL.__version__, 'platform':platform.platform(),
        'cpu':next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                    if line.startswith('model name')),platform.machine()),
        'ffmpeg':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0]},
        'baseline_viewport': 'same final 4/5 scale in both paths, common layout correction excluded from OPT credit',
        'effective_reference_visualizer_sha256':hashlib.sha256(effective_source.encode()).hexdigest(),
        'source_hashes':{}, 'method':'3 alternating pairs per style, 2.017 s stereo fixture, 720p, title; includes PCM decode, cold caches, render, encode, every-frame verification and atomic publication',
        'styles':{}}
    for kind,folder in [('reference',args.reference),('optimized',ROOT/'a2v')]:
        report['source_hashes'][kind] = {name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
                                       for name in ('visualizer.py','title.py')}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = audio(root/'signal.wav',2.017)
        for style in ('qutrit-galaxy','gluball-knot'):
            samples = {'reference':[], 'optimized':[]}
            digests = set()
            for repeat in range(3):
                for kind in (('reference','optimized') if repeat%2==0 else ('optimized','reference')):
                    renderer = reference if kind=='reference' else visualizer
                    titles = reference_title if kind=='reference' else title
                    for obj in vars(renderer).values():
                        if callable(obj) and hasattr(obj,'cache_clear'):
                            obj.cache_clear()
                    for obj in vars(titles).values():
                        if callable(obj) and hasattr(obj,'cache_clear'):
                            obj.cache_clear()
                    output = root/f'{style}-{repeat}-{kind}.mp4'
                    with ExitStack() as stack:
                        for name in ('render','reference_thumbnail','check_thumbnail'):
                            stack.enter_context(patch.object(core,name,getattr(renderer,name)))
                        for name in ('check_title','title_image','prepare_title'):
                            stack.enter_context(patch.object(core,name,getattr(titles,name)))
                        start = time.perf_counter()
                        result = core.convert(core.Job(source,output,resolution='720p',style=style,title='OPT — Quantum Flex'))
                        elapsed = time.perf_counter()-start
                    assert result.verified_frames==61
                    samples[kind].append(elapsed)
                    digests.add(hashlib.sha256(output.read_bytes()).hexdigest())
                    print(style,kind,round(elapsed,4),flush=True)
            if len(digests)!=1:
                raise RuntimeError('OPT parity failed: MP4 bytes differ')
            medians = {k:statistics.median(v) for k,v in samples.items()}
            report['styles'][style] = {'seconds':samples, 'median_seconds':medians,
                'reduction_percent':100*(1-medians['optimized']/medians['reference']),
                'mp4_sha256':next(iter(digests)), 'exact_mp4_parity':True}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
