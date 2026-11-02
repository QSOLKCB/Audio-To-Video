import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from a2v.core import Job, convert, probe, validate, verify_output
from a2v.process import Cancelled, RenderError
from a2v.visualizer import check_thumbnail, peaks, render
from fixtures import audio, command, decoded_frames, png


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="audio2video tests ")
        self.root = Path(self.temp.name)
        self.source = audio(self.root / "voice ; $literal.wav")
        self.cancel = threading.Event()

    def tearDown(self):
        self.temp.cleanup()

    def job(self, name="out.mp4", **kwargs):
        return Job(self.source, self.root / name, resolution="720p", **kwargs)

    def test_encoded_visualizer_is_visible_moving_and_repeatable(self):
        original = self.source.read_bytes()
        a = convert(self.job("a.mp4"))
        b = convert(self.job("b.mp4"))
        frames = decoded_frames(a.output)
        self.assertEqual(len(frames), 30)
        self.assertEqual(a.verified_frames, 30)
        self.assertTrue(all(max(frame) > 150 for frame in frames))
        self.assertGreater(len({hashlib.sha256(frame).digest() for frame in frames}), 3)
        self.assertEqual(frames, decoded_frames(b.output))
        self.assertEqual(a.output.read_bytes(), b.output.read_bytes())
        self.assertEqual(original, self.source.read_bytes())
        self.assertFalse(list(self.root.glob(".audio2video-*")))

    def test_1080p_output_and_all_silence(self):
        self.source = audio(self.root / "quiet.wav", .2, "silence")
        result = convert(Job(self.source, self.root / "silent.mp4"))
        info = probe(result.output, self.cancel)
        self.assertEqual((info["streams"][0]["width"], info["streams"][0]["height"]), (1920, 1080))
        frames = decoded_frames(result.output)
        self.assertEqual(len(frames), 6)
        self.assertTrue(all(max(frame) > 150 for frame in frames))

    def test_antiphase_stereo_does_not_hide_waveform(self):
        self.source = audio(self.root / "stereo.wav", .4, "antiphase")
        result = convert(self.job())
        frames = decoded_frames(result.output)
        self.assertGreater(sum(frames[-1]), sum(frames[0]) * 2)

    def test_partial_frame_and_very_short_audio(self):
        for length in (.01, .043, .237, 1.001):
            with self.subTest(length=length):
                self.source = audio(self.root / f"{length}.wav", length)
                result = convert(self.job(f"{length}.mp4"))
                self.assertEqual(result.frames, (round(length * 48000) + 1599) // 1600)

    def test_mono_44100_mp3_and_m4a(self):
        source = audio(self.root / "mono.wav", .4, rate=44100, channels=1)
        for extension, codec in (("mp3", "libmp3lame"), ("m4a", "aac")):
            with self.subTest(extension=extension):
                self.source = self.root / ("mono." + extension)
                command("ffmpeg", "-v", "error", "-i", str(source), "-c:a", codec, str(self.source))
                result = convert(self.job(extension + ".mp4"))
                self.assertGreater(result.verified_frames, 0)

    def test_png_and_jpeg_are_static_and_fitted(self):
        image = png(self.root / "art.png", 55, 101)
        jpeg = self.root / "art.jpg"
        command("ffmpeg", "-v", "error", "-i", str(image), "-frames:v", "1", str(jpeg))
        for picture in (image, jpeg):
            with self.subTest(picture=picture.suffix):
                result = convert(self.job(picture.suffix + ".mp4", mode="still", image=picture))
                frames = decoded_frames(result.output)
                self.assertEqual(len(frames), 30)
                # All frames remain the same within lossy H.264 rounding.
                self.assertLess(sum(abs(a-b) for a,b in zip(frames[0],frames[-1])) / len(frames[0]), 1)
                self.assertLess(frames[0][0], 30)  # letterbox, not stretched art
                self.assertGreater(max(frames[0]), 150)

    def test_transparent_png_is_flattened(self):
        image = png(self.root / "alpha.png", 160, 90, transparent=True)
        result = convert(self.job(mode="still", image=image))
        frame = decoded_frames(result.output)[0]
        # Transparent left half contains red RGB data, which must stay hidden.
        left = (45 * 160 + 30) * 3
        self.assertLess(max(frame[left:left+3]), 35)

    def test_existing_output_and_symlink_are_preserved(self):
        target = self.root / "out.mp4"
        target.write_bytes(b"keep me")
        with self.assertRaises(RenderError):
            convert(self.job())
        self.assertEqual(target.read_bytes(), b"keep me")
        target.unlink()
        target.symlink_to(self.root / "does-not-exist")
        with self.assertRaises(RenderError):
            convert(self.job())
        self.assertTrue(target.is_symlink())

    def test_output_collision_at_publication_is_not_overwritten(self):
        def progress(message, fraction):
            if message == "Checking encoded audio":
                self.job().output.write_bytes(b"concurrent file")
        with self.assertRaisesRegex(RenderError, "appeared"):
            convert(self.job(), progress=progress)
        self.assertEqual(self.job().output.read_bytes(), b"concurrent file")

    def test_cancel_during_render_and_verify_cleans_partial_files(self):
        for phase in ("Rendering visualizer", "Checking encoded video"):
            with self.subTest(phase=phase):
                self.cancel.clear()
                def progress(message, fraction):
                    if message == phase:
                        self.cancel.set()
                with self.assertRaises(Cancelled):
                    convert(self.job(), self.cancel, progress)
                self.assertFalse(self.job().output.exists())
                self.assertFalse(list(self.root.glob(".audio2video-*")))

    def test_bad_inputs_are_errors_without_partial_output(self):
        bad = self.root / "corrupt.m4a"
        bad.write_bytes(b"this is not audio")
        self.source = bad
        with self.assertRaises(RenderError):
            convert(self.job())
        self.assertFalse(self.job().output.exists())
        self.assertFalse(list(self.root.glob(".audio2video-*")))

    def test_reject_unrequested_formats_fifo_and_missing_image(self):
        with self.assertRaises(RenderError):
            validate(self.job(mode="still"))
        fifo = self.root / "fifo.wav"
        os.mkfifo(fifo)
        with self.assertRaises(RenderError):
            validate(Job(fifo, self.root / "out.mp4"))
        wrong = self.root / "song.ogg"
        wrong.write_bytes(self.source.read_bytes())
        with self.assertRaises(RenderError):
            validate(Job(wrong, self.root / "out.mp4"))

    def prepare_pcm(self):
        pcm = self.root / "audio.s16le"
        command("ffmpeg", "-v", "error", "-i", str(self.source), "-ar", "48000", "-ac", "2", "-f", "s16le", str(pcm))
        return pcm

    def verify_bad(self, path):
        pcm = self.prepare_pcm()
        with self.assertRaises(RenderError):
            verify_output(path, pcm, self.job(), 30, 48000, self.cancel, lambda *_: None)

    def test_reject_audio_only_mp4(self):
        path = self.root / "audio-only.mp4"
        command("ffmpeg", "-v", "error", "-i", str(self.source), "-c:a", "aac", str(path))
        self.verify_bad(path)

    def test_reject_black_video_even_when_encoder_succeeds(self):
        path = self.root / "blank.mp4"
        command("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=1280x720:r=30:d=1",
                "-i", str(self.source), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path))
        self.verify_bad(path)

    def test_reject_frozen_visualizer_with_valid_audio_video_streams(self):
        valid = convert(self.job("valid.mp4"))
        image = self.root / "frozen.png"
        path = self.root / "frozen.mp4"
        command("ffmpeg", "-v", "error", "-i", str(valid.output), "-frames:v", "1", str(image))
        command("ffmpeg", "-v", "error", "-loop", "1", "-framerate", "30", "-i", str(image),
                "-i", str(self.source), "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(path))
        self.verify_bad(path)

    def test_missing_tail_frames_are_rejected(self):
        valid = convert(self.job("valid.mp4"))
        path = self.root / "short.mp4"
        command("ffmpeg", "-v", "error", "-i", str(valid.output), "-t", "0.3", "-c", "copy", str(path))
        self.verify_bad(path)

    def test_verification_failure_never_publishes(self):
        with patch("a2v.core.verify_output", side_effect=RenderError("bad video")):
            with self.assertRaises(RenderError):
                convert(self.job())
        self.assertFalse(self.job().output.exists())
        self.assertFalse(list(self.root.glob(".audio2video-*")))


if __name__ == "__main__":
    unittest.main()
