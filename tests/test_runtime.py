from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

from a2v.desktop import next_output
from a2v.runtime import font_path, tool_path


class RuntimeTests(unittest.TestCase):
    def test_frozen_tools_never_fall_back_to_developer_path(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(sys, 'frozen', True, create=True), \
                patch.object(sys, '_MEIPASS', directory, create=True):
            self.assertIsNone(tool_path('ffmpeg'))
            suffix = '.exe' if sys.platform == 'win32' else ''
            media = Path(directory)/'media'
            media.mkdir()
            binary = media/('ffmpeg'+suffix)
            binary.write_bytes(b'fixture')
            self.assertEqual(tool_path('ffmpeg'), str(binary))

    def test_bundled_font_and_numbered_output(self):
        self.assertTrue(font_path().is_file())
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory)/'track.wav'
            self.assertEqual(next_output(audio).name, 'track.mp4')
            audio.with_suffix('.mp4').touch()
            self.assertEqual(next_output(audio).name, 'track-1.mp4')
            audio.with_name('track-1.mp4').touch()
            self.assertEqual(next_output(audio).name, 'track-2.mp4')
