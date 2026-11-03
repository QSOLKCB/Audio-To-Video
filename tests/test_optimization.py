"""Independent scalar conformance gates for OPT changes; no timing assertions."""
from array import array
import hashlib
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from a2v.title import title_reference
from a2v.visualizer import check_thumbnail, knot_basis, reference_thumbnail, render, ribbon_colors


def scalar_check(actual, expected, header_rows=0):
    """Frozen pre-OPT checker, kept intentionally scalar as the oracle."""
    if len(actual) != 160*90*3 or len(expected) != 160*90*3:
        raise ValueError('Incomplete decoded visualizer frame')
    region = [3*(y*160+x) for y in range(max(16,header_rows),77) for x in range(10,150)]
    foreground = [i for i in region if max(expected[i:i+3]) > 150]
    if not foreground or sum(max(actual[i:i+3]) > 110 for i in foreground) < len(foreground)*.8:
        raise ValueError('Visualizer is missing or incomplete in the encoded MP4')
    mismatch = sum(max(abs(actual[i+c]-expected[i+c]) for c in range(3)) > 75 for i in region)
    if mismatch > len(region)*.025:
        raise ValueError('Encoded MP4 does not match the audio-driven visualizer')


def decision(check, *args):
    try:
        check(*args)
        return 'accept'
    except ValueError as exc:
        return str(exc)


class OptimizationTests(unittest.TestCase):
    def test_source_frames_match_pre_optimization_digests(self):
        samples = {'silence': b'', 'antiphase': array('h',[12000,-12000]*1600).tobytes(),
                   'ramp': array('h',[((i*431)%65536)-32768 for i in range(3200)]).tobytes()}
        golden = json.loads((Path(__file__).parent/'visual-golden.json').read_text())
        knot_basis.cache_clear()
        ribbon_colors.cache_clear()
        for case in golden['cases']:
            with self.subTest(case=case):
                self.assertEqual(hashlib.sha256(render(samples[case['pcm']],case['style'],case['index'])).hexdigest(),
                                 case['sha256'])
        self.assertEqual(knot_basis.cache_info().currsize, 1)
        self.assertEqual(ribbon_colors.cache_info().currsize, 3)
        self.assertIsInstance(knot_basis()[0], tuple)

    def test_knot_geometry_stays_below_title_and_above_legend(self):
        from a2v.angles import TURN, sine, cosine
        # Maximum volume; sweep all quantized tube phases and centreline samples.
        for phase in range(1024):
            for t, cos3, sin3, cos2, sin2 in knot_basis():
                v = phase*TURN//1024 + t*5
                minor = 54 + cosine(v)*13//16384
                radial = 91 + minor*cos3//16384
                y = radial*sin2//16384
                z = minor*sin3//16384 + sine(v)*13//16384
                sy = 187+(y*7//10-z)*4//5
                self.assertGreaterEqual(sy, 64)
                self.assertLessEqual(sy, 309)

    def test_native_sampling_matches_scalar_pixel_centres(self):
        raw = bytes((i*37)%256 for i in range(640*360*3))
        expected = bytes(raw[(y*640+x)*3+c] for y in range(2,360,4)
                         for x in range(2,640,4) for c in range(3))
        with patch('a2v.visualizer.render', return_value=raw):
            self.assertEqual(reference_thumbnail(b''), expected)

    def test_native_checker_matches_scalar_on_boundaries_and_corruption(self):
        expected = bytes((100,200,210))*(160*90)
        rng = random.Random(781)
        cases = [(expected,expected), (b'',expected), (bytes(len(expected)),expected)]
        region = [3*(y*160+x) for y in range(16,77) for x in range(10,150)]
        for count in (0, 1, 213, 214, 1708, 1709):
            for color in ((175,200,210), (176,200,210), (0,0,0), (110,110,110), (111,111,111)):
                actual = bytearray(expected)
                for i in rng.sample(region,count):
                    actual[i:i+3] = bytes(color)
                cases.append((bytes(actual),expected))
        for actual, reference in cases:
            for header in (0,14,60,77):
                self.assertEqual(decision(check_thumbnail,actual,reference,header),
                                 decision(scalar_check,actual,reference,header))

    def test_title_cache_is_immutable_bounded_and_keyed_by_text_and_size(self):
        title_reference.cache_clear()
        first = title_reference('Artist — Track',1280)
        self.assertIsInstance(first[0],bytes)
        self.assertIsInstance(first[1],tuple)
        title_reference('Other track',1280)
        title_reference('Artist — Track',1920)
        self.assertEqual(title_reference.cache_info().currsize,1)
        self.assertEqual(title_reference('Artist — Track',1280),first)
        title_reference.cache_clear()
        self.assertEqual(title_reference('Artist — Track',1280),first)
