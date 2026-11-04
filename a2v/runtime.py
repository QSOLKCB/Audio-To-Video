"""Explicit local dependency lookup for source installs and frozen bundles."""
import os
from pathlib import Path
import shutil
import sys


def tool_path(name):
    suffix = '.exe' if sys.platform == 'win32' else ''
    if getattr(sys, 'frozen', False):
        # A frozen build must be self-contained, even on a developer's machine.
        candidate = Path(sys._MEIPASS) / 'media' / (name + suffix)
        return str(candidate) if candidate.is_file() else None
    if os.environ.get('A2V_FFMPEG_DIR'):
        candidate = Path(os.environ['A2V_FFMPEG_DIR']) / (name + suffix)
        return str(candidate.resolve()) if candidate.is_file() else None
    return shutil.which(name)


def font_path():
    return Path(__file__).resolve().parent / 'assets' / 'DejaVuSans.ttf'
