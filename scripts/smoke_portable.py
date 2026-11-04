#!/usr/bin/env python3
"""Exercise a frozen bundle from another directory, without tools on PATH."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'tests'))
from fixtures import audio, png


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--gui', action='store_true')
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    if sys.platform == 'win32':
        executable = bundle/'AudioToVideo.exe'
    elif sys.platform == 'darwin':
        executable = bundle/'AudioToVideo.app/Contents/MacOS/AudioToVideo'
        # A build-machine-only dylib can make PATH-only smoke tests falsely pass.
        for path in (bundle/'AudioToVideo.app').rglob('*'):
            if not path.is_file() or path.is_symlink():
                continue
            with path.open('rb') as file:
                magic = file.read(4)
            if magic not in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'):
                continue
            links = subprocess.check_output(['/usr/bin/otool', '-L', str(path)], text=True).splitlines()[1:]
            for line in links:
                library = line.strip().split(' (', 1)[0]
                if library.startswith('/') and not library.startswith(('/usr/lib/', '/System/Library/')):
                    raise RuntimeError(f'Nonportable library: {path}: {library}')
    else:
        executable = bundle/'AudioToVideo/AudioToVideo'
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'A2V_FFMPEG_DIR', 'A2V_GUI_BACKEND', 'DYLD_LIBRARY_PATH'):
        env.pop(key, None)
    env['PATH'] = ''
    with tempfile.TemporaryDirectory(prefix='a2v portable smoke ') as directory:
        work = Path(directory)
        def run(*arguments, check=True):
            return subprocess.run([str(executable), *arguments], cwd=work, env=env, check=check,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
        run('doctor', *(['--gui'] if args.gui else []))
        source = audio(work/'tone.wav', .237, 'antiphase')
        png(work/'cover.png')
        for style in ('bars', 'scope', 'qutrit-galaxy', 'gluball-knot', 'etq-graph-walk',
                      'trigger-scope', 'vectorscope', 'radial-scope'):
            common = ('--visualizer', '--style', style, '--title', 'Portable — stereo', '--resolution', '720p')
            run('render', source.name, style+'.mp4', *common)
            run('render', source.name, style+'-again.mp4', *common)
            first = (work/(style+'.mp4')).read_bytes()
            assert first == (work/(style+'-again.mp4')).read_bytes(), style+' not repeatable'
            collision = run('render', source.name, style+'.mp4', *common, check=False)
            assert collision.returncode != 0 and (work/(style+'.mp4')).read_bytes() == first
        run('render', source.name, 'still.mp4', '--image', 'cover.png', '--title', 'Portable still', '--resolution', '720p')
        assert not list(work.glob('.audio2video-*'))
    print('Portable smoke passed: 17 fully verified exports, repeatability, no overwrite, no external PATH.')


if __name__ == '__main__':
    main()
