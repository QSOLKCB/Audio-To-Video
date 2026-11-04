"""Signal geometry, scalar parity, and adversarial export checks."""
from array import array
from dataclasses import replace
import hashlib
import random
import struct
import tempfile
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from a2v import visualizer as v
from a2v.core import Job, convert
from a2v.process import RenderError, capture, child, read_exact, write_frame
from a2v.scopes import stereo_point, trigger_start
from fixtures import audio


def scalar_populations(pcm):
    low, mid, energy = [0, 0], [0, 0], [0, 0, 0]
    for i, sample in enumerate(v.values(pcm)):
        c = i & 1
        low[c] += (sample-low[c])//32
        mid[c] += (sample-mid[c])//4
        for band, value in enumerate((low[c], mid[c]-low[c], sample-mid[c])):
            energy[band] += value*value
    total = sum(energy)
    if not total:
        return (333334, 333333, 333333)
    weights = [e*1000000//total for e in energy]
    order = sorted(range(3), key=lambda i: (-(energy[i]*1000000 % total), i))
    for i in order[:1000000-sum(weights)]:
        weights[i] += 1
    return tuple(weights)


def scalar_bars(pcm):
    frame = bytearray(bytes(v.BACKGROUND)*(v.WIDTH*v.HEIGHT))
    for y in (60, 120, 240, 300):
        v.rectangle(frame, 40, y, 560, 1, (21, 32, 42))
    for i, peak in enumerate(v.peaks(pcm)):
        half = 3 + peak*116//32768
        v.rectangle(frame, 40+i*7, v.HEIGHT//2-half, 5, half*2, v.FOREGROUND)
    return bytes(frame)


class ScopeTests(unittest.TestCase):
    def test_optimized_paths_match_scalar_oracles(self):
        rng = random.Random(4515)
        for count in (0, 1, 17, 799, 1600):
            for kind in ('min', 'max', 'random'):
                samples = [(-32768 if kind == 'min' else 32767 if kind == 'max' else rng.randrange(-32768, 32768))
                           for _ in range(count*2)]
                pcm = struct.pack('<'+'h'*len(samples), *samples)
                with self.subTest(count=count, kind=kind):
                    self.assertEqual(v.render(pcm, 'bars'), scalar_bars(pcm))
                    self.assertEqual(v.populations(pcm), scalar_populations(pcm))

    def test_galaxy_cache_is_bounded_and_immutable(self):
        v.galaxy_basis.cache_clear()
        for state in range(3):
            self.assertIsInstance(v.galaxy_basis(state), tuple)
            self.assertIsInstance(v.galaxy_basis(state)[0], tuple)
        self.assertEqual(v.galaxy_basis.cache_info().currsize, 3)
        self.assertEqual(v.galaxy_basis.cache_info().maxsize, 3)

    def test_trigger_preserves_shared_channel_offset_and_bounds(self):
        data = array('h', [-100, -200]*1600)
        data[37*2+1] = 200
        self.assertEqual(trigger_start(data), 37)
        self.assertEqual(trigger_start(v.values(b'')), 0)
        data = array('h', [100, 0]*1600)
        self.assertEqual(trigger_start(data), 0)
        data = array('h', [-100, -200]*1600)
        data[801*2+1] = 200
        self.assertEqual(trigger_start(data), 0)

    def test_vectorscope_distinguishes_mono_antiphase_and_silence(self):
        self.assertEqual(stereo_point(0, 0), (320, 184))
        self.assertEqual(stereo_point(16384, 16384), (320, 128))
        self.assertEqual(stereo_point(16384, -16384), (376, 184))
        for style in ('trigger-scope', 'vectorscope', 'radial-scope'):
            cases = [b'', struct.pack('<hh', 12000, 12000)*1600, struct.pack('<hh', 12000, -12000)*1600]
            frames = [v.render(pcm, style) for pcm in cases]
            self.assertEqual(len(set(frames)), 3)
            self.assertEqual(frames[-1], v.render(cases[-1], style, 9000000))
            for pcm in cases:
                thumb = v.reference_thumbnail(pcm, style)
                v.check_thumbnail(thumb, thumb)

    def test_new_styles_reject_frozen_blank_and_wrong_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = audio(root/'signal.wav', .437)
            for style in ('trigger-scope', 'vectorscope', 'radial-scope'):
                job = Job(source, root/'out.mp4', resolution='720p', style=style, title='Scope check')
                for wrong in ('blank', 'frozen', 'wrong-style'):
                    def damaged(pcm, selected, index):
                        if wrong == 'blank':
                            return bytes(v.BACKGROUND)*640*360
                        return v.render(b'' if wrong == 'frozen' else pcm,
                                        'bars' if wrong == 'wrong-style' else selected, index)
                    with self.subTest(style=style, wrong=wrong), patch('a2v.core.render', side_effect=damaged):
                        with self.assertRaises(RenderError):
                            convert(job)
                    self.assertFalse(job.output.exists())


class PortablePipeTests(unittest.TestCase):
    def setUp(self):
        # Exercise the actual Windows strategy even on a POSIX development host.
        threaded = patch('a2v.process.THREADED_PIPES', True)
        threaded.start()
        self.addCleanup(threaded.stop)

    def test_fragmented_reads_sticky_eof_and_backpressure(self):
        import sys
        cancel = threading.Event()
        source = "import sys; sys.stdout.buffer.write(bytes(range(256))*2048); sys.stdout.flush()"
        with child([sys.executable, '-c', source], cancel, output_pipe=True) as proc:
            result = b''.join(read_exact(proc, size, cancel) for size in (1, 3, 100000, 524284))
            self.assertEqual(result, bytes(range(256))*2048)
            self.assertEqual(read_exact(proc, 10, cancel), b'')
            self.assertEqual(read_exact(proc, 10, cancel), b'')
        self.assertFalse(proc.a2v_reader.thread.is_alive())

    def test_full_frame_writes_reach_child_and_reader_threads_finish(self):
        import sys
        cancel = threading.Event()
        source = 'import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())'
        frame = bytes(range(256))*4000
        with child([sys.executable, '-c', source], cancel, input_pipe=True, output_pipe=True) as proc:
            write_frame(proc, frame, cancel)
            proc.stdin.close()
            digest = read_exact(proc, 100, cancel).decode().strip()
        self.assertEqual(digest, hashlib.sha256(frame).hexdigest())
        self.assertFalse(proc.a2v_writer.thread.is_alive())
        self.assertFalse(proc.a2v_reader.thread.is_alive())

    def test_tool_output_limit_terminates_child(self):
        import sys
        with self.assertRaisesRegex(RenderError, 'exceeded'):
            capture([sys.executable, '-c', "import sys; sys.stdout.buffer.write(b'x'*1000000)"], threading.Event(), limit=10)
