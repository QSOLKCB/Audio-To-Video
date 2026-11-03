"""Real MP4 regressions for new styles and independent title verification."""
from array import array
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image

from a2v.angles import TURN, sine
from a2v.core import Job, convert, validate, verify_output
from a2v.process import RenderError
from a2v.title import HEADER, check_title, normalize_title, title_image
from a2v.visualizer import STYLES, check_thumbnail, populations, reference_thumbnail, render
from fixtures import audio, command, decoded_frames, png


class StyleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='a2v styles ')
        self.root = Path(self.temp.name)
        self.source = audio(self.root/'signal.wav', .437)
        self.job = Job(self.source, self.root/'out.mp4', resolution='720p', title="Name: 50% 'Track' — café [live] \\ end")

    def tearDown(self):
        self.temp.cleanup()

    def test_every_style_survives_real_mp4_and_is_repeatable(self):
        for style in STYLES:
            with self.subTest(style=style):
                job = replace(self.job, style=style, output=self.root/(style+'.mp4'))
                a = convert(job)
                b = convert(replace(job, output=self.root/(style+'-again.mp4')))
                self.assertEqual(a.frames, 14)
                self.assertEqual(a.verified_frames, 14)
                self.assertEqual(a.output.read_bytes(), b.output.read_bytes())
                self.assertGreater(len(set(decoded_frames(a.output))), 2)

    def test_silence_and_antiphase_at_1080p_for_each_new_style(self):
        for kind in ('silence', 'antiphase'):
            source = audio(self.root/(kind+'.wav'), .101, kind)
            for style in list(STYLES)[1:]:
                with self.subTest(kind=kind, style=style):
                    result = convert(replace(self.job, audio=source, resolution='1080p', style=style,
                                             output=self.root/(kind+style+'.mp4')))
                    self.assertEqual(result.verified_frames, 4)

    def test_title_on_still_preserves_art_below_header(self):
        picture = png(self.root/'cover.png', 160, 90)
        result = convert(replace(self.job, mode='still', image=picture))
        frames = decoded_frames(result.output)
        self.assertGreater(max(frames[0][:160*14*3]), 200)
        self.assertGreater(max(frames[0][160*14*3:]), 150)
        self.assertLess(sum(abs(a-b) for a,b in zip(frames[0],frames[-1])) / len(frames[0]), 1)

    def test_title_cannot_hide_missing_visualizer(self):
        # Real H.264 encode with the legitimate title but no geometry.
        with patch('a2v.core.render', return_value=bytes((12,18,25))*640*360):
            with self.assertRaisesRegex(RenderError, 'Visualizer is missing'):
                convert(replace(self.job, style='qutrit-galaxy'))
        self.assertFalse(self.job.output.exists())

    def test_missing_title_is_rejected_on_actual_mp4(self):
        # Preserve geometry, remove just the title input from the encoder.
        with patch('a2v.core.prepare_title', return_value=None):
            with self.assertRaisesRegex(RenderError, 'Title is missing'):
                convert(replace(self.job, style='gluball-knot'))
        self.assertFalse(self.job.output.exists())

    def test_frozen_galaxy_and_wrong_style_are_rejected(self):
        source = audio(self.root/'quiet.wav', 1.1, 'silence')
        for wrong in ('frozen', 'wrong-style'):
            with self.subTest(wrong=wrong):
                def damaged(pcm, style, index):
                    return render(pcm, 'bars' if wrong == 'wrong-style' else style, 0)
                with patch('a2v.core.render', side_effect=damaged):
                    with self.assertRaisesRegex(RenderError, 'visualizer|Visualizer'):
                        convert(replace(self.job, audio=source, style='qutrit-galaxy'))
                self.assertFalse(self.job.output.exists())

    def test_narrow_title_glyphs_survive_sampling_and_encoding(self):
        source = audio(self.root/'short.wav', .043)
        for text in ('.', 'i', '·'):
            for resolution in ('720p', '1080p'):
                result = convert(replace(self.job, audio=source, title=text, resolution=resolution,
                                         output=self.root/(text+resolution+'.mp4')))
                self.assertEqual(result.verified_frames, 2)

    def test_title_validation_and_fit(self):
        self.assertEqual(normalize_title('   '), '')
        for title in ('a\nb', '\0', 'x'*121):
            with self.assertRaises(RenderError):
                validate(replace(self.job, title=title))
        for text in ("Artist's 100% [track]: \\ $text", 'é' * 70, 'i' * 120):
            for width in (1280,1920):
                im = title_image(text, width)
                self.assertEqual(im.size, (width, HEADER*(width//640)))
                # Auto fit leaves dark margins, not clipped glyphs.
                self.assertLess(max(im.crop((0,0,16,im.height)).getdata())[0], 30)
        with self.assertRaises(RenderError):
            title_image('W' * 120, 1280)
        with self.assertRaises(RenderError):
            validate(replace(self.job, style='unsupported'))

    def test_qutrit_normalization_wrapping_and_random_access(self):
        self.assertEqual(populations(b''), (333334,333333,333333))
        pcm = array('h', [12000,-12000]*1600).tobytes()
        self.assertEqual(sum(populations(pcm)), 1000000)
        self.assertEqual(sine(0), 0)
        self.assertEqual(sine(TURN//4), 16384)
        self.assertEqual(sine(TURN//4 + TURN*1000), 16384)
        for style in ('qutrit-galaxy','gluball-knot'):
            a = render(pcm,style,90)
            render(pcm,style,900000)
            self.assertEqual(a, render(pcm,style,90))
            self.assertNotEqual(a, render(pcm,style,0))


if __name__ == '__main__':
    unittest.main()
