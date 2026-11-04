#!/usr/bin/env python3
"""Build on the target OS. No downloads, cross-compilation, or release upload."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from a2v import __version__


def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg-dir', type=Path, required=True, help='matching native ffmpeg and ffprobe binaries')
    parser.add_argument('--notices', type=Path, required=True, help='directory with media-tool licences and source/build provenance')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'dist')
    args = parser.parse_args()
    if sys.platform not in ('win32', 'darwin', 'linux'):
        parser.error('Supported builders: Windows, macOS, Linux')
    # Import before building: packaging a desktop without Tcl/Tk must fail early.
    import tkinter
    from PIL import ImageTk
    suffix = '.exe' if sys.platform == 'win32' else ''
    binaries = [args.ffmpeg_dir.resolve()/(name+suffix) for name in ('ffmpeg', 'ffprobe')]
    for binary in binaries:
        if not binary.is_file():
            parser.error(f'Missing native media tool: {binary}')
    if not args.notices.is_dir() or not any(path.is_file() for path in args.notices.rglob('*')):
        parser.error('--notices must contain the redistributed media-tool licences and provenance')
    label = {'win32': 'windows', 'darwin': 'macos', 'linux': 'linux'}[sys.platform]
    name = f'Audio-To-Video-{__version__}-{label}-{platform.machine().lower()}'
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    target = output/name
    if target.exists():
        parser.error(f'Build destination exists: {target}')
    with tempfile.TemporaryDirectory(prefix='a2v-build-') as directory:
        work = Path(directory)
        runtime_notices = work/'runtime-licences'
        runtime_notices.mkdir()
        for package in ('pillow', 'pyinstaller'):
            distribution = importlib.metadata.distribution(package)
            for relative in distribution.files or []:
                if relative.name.lower().startswith(('license', 'copying', 'notice', 'authors')):
                    target_notice = runtime_notices/package/Path(str(relative)).name
                    target_notice.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(distribution.locate_file(relative), target_notice)
        for candidate in (Path(sys.base_prefix)/'LICENSE.txt', Path(sys.base_prefix)/'lib/python3.12/LICENSE.txt'):
            if candidate.is_file():
                shutil.copy2(candidate, runtime_notices/'Python-LICENSE.txt')
                break
        tcl = tkinter.Tcl()
        tcl_library = Path(tcl.eval('info library'))
        for runtime_name, folder in (('Tcl', tcl_library), ('Tk', tcl_library.with_name('tk'+str(tkinter.TkVersion)))):
            if (folder/'license.terms').is_file():
                shutil.copy2(folder/'license.terms', runtime_notices/(runtime_name+'-license.terms'))
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--noupx',
                   '--name', 'AudioToVideo', '--distpath', str(work/'dist'),
                   '--workpath', str(work/'build'), '--specpath', str(work),
                   '--paths', str(ROOT), '--exclude-module', 'gi',
                   '--add-data', f'{ROOT / "a2v/assets"}:a2v/assets',
                   '--add-data', f'{ROOT / "LICENSES"}:LICENSES',
                   '--add-data', f'{args.notices.resolve()}:THIRD_PARTY',
                   '--add-data', f'{ROOT / "LICENSE"}:.',
                   '--add-data', f'{runtime_notices}:RUNTIME_LICENSES']
        for binary in binaries:
            command += ['--add-binary', f'{binary}:media']
        if sys.platform == 'win32':
            command += ['--onefile', '--console', '--hide-console', 'hide-early']
        elif sys.platform == 'darwin':
            command += ['--onedir', '--windowed', '--osx-bundle-identifier', 'org.qsolkcb.AudioToVideo']
        else:
            command += ['--onedir']  # Local packaging smoke check; GTK source package remains default.
        command += [str(ROOT/'a2v/launcher.py')]
        subprocess.run(command, check=True, cwd=ROOT)
        target.mkdir()
        if sys.platform == 'win32':
            shutil.copy2(work/'dist/AudioToVideo.exe', target)
        elif sys.platform == 'darwin':
            shutil.copytree(work/'dist/AudioToVideo.app', target/'AudioToVideo.app', symlinks=True)
        else:
            shutil.copytree(work/'dist/AudioToVideo', target/'AudioToVideo', symlinks=True)
        shutil.copytree(runtime_notices, target/'RUNTIME_LICENSES')
        shutil.copytree(ROOT/'LICENSES', target/'LICENSES')
        shutil.copytree(args.notices, target/'THIRD_PARTY')
        shutil.copy2(ROOT/'LICENSE', target)
        shutil.copy2(ROOT/'docs/portable.md', target/'README.md')
        receipt = {'version': __version__, 'platform': platform.platform(), 'architecture': platform.machine(),
                   'python': sys.version, 'packages': {package: importlib.metadata.version(package)
                               for package in ('pillow', 'pyinstaller')},
                   'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   'worktree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
                   'media': {binary.name: {'sha256': digest(binary),
                        'version': subprocess.check_output([str(binary), '-version'], text=True).splitlines()[0]}
                        for binary in binaries}}
        (target/'BUILD.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
        checks = ''.join(f'{digest(path)}  {path.relative_to(target).as_posix()}\n'
                         for path in sorted(target.rglob('*')) if path.is_file() and not path.is_symlink())
        (target/'SHA256SUMS').write_text(checks, encoding='utf-8')
    # ditto preserves the symlinks and permissions in signed/ad-hoc macOS bundles.
    archive = output/(name+'.zip')
    if sys.platform == 'darwin':
        subprocess.run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(target), str(archive)], check=True)
    else:
        shutil.make_archive(str(output/name), 'zip', output, name)
    archive.with_suffix('.zip.sha256').write_text(f'{digest(archive)}  {archive.name}\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
