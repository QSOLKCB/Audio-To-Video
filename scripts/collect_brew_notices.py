#!/usr/bin/env python3
"""Record exact Homebrew media dependencies and preserve their installed notices."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
names = ['ffmpeg'] + subprocess.check_output(['brew', 'deps', '--installed', 'ffmpeg'], text=True).split()
info = subprocess.check_output(['brew', 'info', '--json=v2', *names])
(args.output/'homebrew-builds.json').write_bytes(info)
for name in names:
    prefix = Path(subprocess.check_output(['brew', '--prefix', name], text=True).strip())
    for path in prefix.rglob('*'):
        if path.is_file() and path.name.lower().startswith(('license', 'licence', 'copying', 'copyright', 'notice', 'authors')):
            target = args.output/name/path.relative_to(prefix)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
(args.output/'SOURCES.md').write_text('''# Bundled media components

FFmpeg and the linked libraries recorded in homebrew-builds.json are distributed
under their respective licences. Installed copyright/licence notices are included
in the matching subdirectories. The JSON records the formula source URLs, versions,
source checksums and installed build options. The Homebrew formulae describe the
builds: https://github.com/Homebrew/homebrew-core/tree/main/Formula
FFmpeg source and build guidance: https://ffmpeg.org/download.html

This directory is provenance for this native build, not a claim that Homebrew
bottles or the resulting app are bit-reproducible across changing runner images.
''', encoding='utf-8')
