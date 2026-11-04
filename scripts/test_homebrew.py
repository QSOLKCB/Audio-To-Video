#!/usr/bin/env python3
"""Install the PR's exact source through the real formula in a temporary local tap."""
import hashlib
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='a2v-brew-test-') as directory:
    temp = Path(directory)
    archive = temp/'source.tar.gz'
    subprocess.run(['git', 'archive', '--format=tar.gz', '--prefix=audio2video/', '-o', str(archive), 'HEAD'], cwd=ROOT, check=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    subprocess.run(['brew', 'tap-new', 'a2v-ci/local'], check=True)
    tap = Path(subprocess.check_output(['brew', '--repository', 'a2v-ci/local'], text=True).strip())
    formula = (ROOT/'Formula/audio2video.rb').read_text()
    formula = formula.replace('  head "https://github.com/QSOLKCB/Audio-To-Video.git", branch: "main"',
        f'  url "{archive.as_uri()}"\n  version "1.1.0"\n  sha256 "{digest}"')
    (tap/'Formula/audio2video.rb').write_text(formula)
    subprocess.run(['brew', 'install', '--build-from-source', 'a2v-ci/local/audio2video'], check=True)
    subprocess.run(['brew', 'test', 'a2v-ci/local/audio2video'], check=True)
    subprocess.run(['audio2video', 'doctor', '--gui'], check=True)
