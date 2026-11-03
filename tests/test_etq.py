"""Pinned donor conformance, edge legality, random access and real MP4 failures."""
from array import array
from collections import Counter
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from a2v.core import Job, convert
from a2v.etq import (FRAMES_PER_EDGE, dot, graph_background, model, render_graph,
                     roots_doubled, screen_points, triality)
from a2v.process import RenderError
from a2v.visualizer import reference_thumbnail, render
from fixtures import audio


class ETQModelTests(unittest.TestCase):
    def test_exact_ambient_roots_and_triality(self):
        roots = roots_doubled()
        self.assertEqual(len(set(roots)),240)
        self.assertTrue(all(dot(r,r)==8 for r in roots))
        self.assertEqual(sum(any(abs(v)==2 for v in r) for r in roots),112)
        self.assertEqual(sum(triality(r)==r for r in roots),12)
        for root in roots:
            self.assertIn(triality(root),roots)
            self.assertEqual(triality(triality(triality(root))),root)

    def test_independent_javascript_donor_fixture_hashes(self):
        # Obtained by executing pinned VIZ etq-core.js, not the Python port.
        expected = {'selected':'97cfd1f087745422fd66d3640c7b86c3209593c4b53741018c08a5e9cdb15f6f',
                    'edges':'42f6dc6cd014226f1f1b8e59057c083a702cd5639ebd345b21bed6a8280cd8a3',
                    'lifted_edges':'8c48ae287ae30d577894621e4be7120149fd6672e0efd3f782bf15c2a2ee59ef'}
        m = model()
        for name,digest in expected.items():
            encoded = json.dumps(getattr(m,name),separators=(',',':')).encode()
            self.assertEqual(hashlib.sha256(encoded).hexdigest(),digest,name)
        self.assertEqual(Counter(m.degrees),{22:12,23:6,30:12,32:24,33:12,34:6,40:6,42:12,43:6,44:3,55:2})
        self.assertEqual(sum(any(abs(v)==2 for v in r) for r in m.selected),41)
        self.assertEqual(sum(m.degrees),3374)

    def test_lift_and_closed_walk_only_use_real_edges(self):
        m = model()
        self.assertEqual(len(m.lifted_edges),5364)
        self.assertEqual(len(m.walk),604)
        self.assertEqual(set(m.walk),set(range(303)))
        for i,row in enumerate(m.neighbors):
            self.assertEqual(len(row),m.degrees[i//3]+2)
        for a,b in zip(m.walk,m.walk[1:]+m.walk[:1]):
            self.assertIn(b,m.neighbors[a])
            self.assertNotEqual(a,b)
            if a//3 != b//3:
                self.assertEqual(a%3,b%3)
                self.assertEqual(dot(m.selected[a//3],m.selected[b//3]),4)

    def test_bounded_immutable_caches_and_clear_reconstruction(self):
        first = model()
        raster = graph_background()
        self.assertIsInstance(first.selected[0],tuple)
        self.assertIsInstance(raster,bytes)
        with self.assertRaises(FrozenInstanceError):
            first.walk = ()
        for f in (model,screen_points,graph_background):
            self.assertEqual(f.cache_info().maxsize,1)
            f.cache_clear()
        self.assertEqual(model(),first)
        self.assertEqual(graph_background(),raster)

    def test_projection_and_maximum_pulse_fit_title_and_legend(self):
        # Largest core/halo radius is nine, blur adds three pixels.
        for x,y,_ in screen_points():
            self.assertGreaterEqual(x-12,40)
            self.assertLessEqual(x+12,600)
            self.assertGreaterEqual(y-12,56)
            self.assertLessEqual(y+12,317)

    def test_frame_index_controls_motion_and_audio_controls_light(self):
        quiet = render(b'','etq-graph-walk',0)
        moving = render(b'','etq-graph-walk',53)
        self.assertNotEqual(quiet,moving)
        period = len(model().walk)*FRAMES_PER_EDGE
        self.assertEqual(moving,render(b'','etq-graph-walk',53+period*1000000))
        signal = array('h',[24000,-24000]*1600).tobytes()
        self.assertNotEqual(moving,render(signal,'etq-graph-walk',53))
        render(signal,'etq-graph-walk',period-1)
        self.assertEqual(moving,render(b'','etq-graph-walk',53))


class ETQExportTests(unittest.TestCase):
    def test_frozen_or_missing_walk_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=audio(root/'silence.wav',1.1,'silence')
            job=Job(source,root/'bad.mp4',resolution='720p',style='etq-graph-walk',title='ETQ — graph walk')
            for damage in ('frozen','no-walk'):
                with self.subTest(damage=damage):
                    job = Job(source,root/(damage+'.mp4'),resolution='720p',style='etq-graph-walk',title='ETQ — graph walk')
                    def broken(pcm,style,index):
                        return render(pcm,style,0) if damage=='frozen' else graph_background()
                    with patch('a2v.core.render',side_effect=broken):
                        with self.assertRaisesRegex(RenderError,'visualizer|Visualizer'):
                            convert(job)
                    self.assertFalse(job.output.exists())
                    self.assertFalse(list(root.glob('.audio2video-*')))

    def test_real_mp4_across_walk_loop_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=audio(root/'boundary.wav',.237,'antiphase')
            offset=len(model().walk)*FRAMES_PER_EDGE-2
            def frame(pcm,style,index):
                return render(pcm,style,index+offset)
            def thumb(pcm,style,index):
                return reference_thumbnail(pcm,style,index+offset)
            with patch('a2v.core.render',side_effect=frame), patch('a2v.core.reference_thumbnail',side_effect=thumb):
                result=convert(Job(source,root/'boundary.mp4',resolution='720p',style='etq-graph-walk'))
            self.assertEqual(result.verified_frames,8)

    def test_partial_tail_without_title_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=audio(root/'tail.wav',.043,'antiphase')
            result=convert(Job(source,root/'tail.mp4',resolution='1080p',style='etq-graph-walk'))
            self.assertEqual(result.verified_frames,2)


if __name__=='__main__':
    unittest.main()
