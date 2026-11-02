from pathlib import Path
import threading
import time
import unittest

from a2v.core import Job, Result
from a2v.desktop import Controller
from a2v.process import Cancelled, RenderError, child, read_exact, write_frame


class DesktopTests(unittest.TestCase):
    def drain(self, controller):
        deadline = time.monotonic() + 5
        while controller.busy and time.monotonic() < deadline:
            controller.drain()
            time.sleep(.01)
        self.assertFalse(controller.busy)

    def test_success_can_be_repeated_and_busy_start_is_rejected(self):
        release = threading.Event()
        def renderer(job, cancel, progress):
            release.wait(2)
            progress("Checking", .8)
            return Result(job.output, 30, 1, 30)
        controller = Controller(renderer)
        job = Job(Path("sound.wav"), Path("movie.mp4"))
        self.assertTrue(controller.start(job))
        self.assertFalse(controller.start(job))
        release.set()
        self.drain(controller)
        self.assertEqual(controller.result.verified_frames, 30)
        self.assertTrue(controller.start(job))
        self.drain(controller)

    def test_cancelled_worker_joins_and_can_retry(self):
        def renderer(job, cancel, progress):
            cancel.wait(2)
            raise Cancelled()
        controller = Controller(renderer)
        controller.start(None)
        controller.stop()
        self.drain(controller)
        self.assertIsNone(controller.result)
        self.assertIn("Cancelled", controller.status)
        controller.renderer = lambda *_: Result(Path("ok.mp4"), 1, 1/30, 1)
        controller.start(None)
        self.drain(controller)
        self.assertIsNotNone(controller.result)
        self.assertFalse(controller.cancel.is_set())

    def test_error_is_reported_without_leaving_busy_state(self):
        def renderer(*_):
            raise RenderError("failed export check")
        controller = Controller(renderer)
        controller.start(None)
        self.drain(controller)
        self.assertEqual(controller.error, "failed export check")

    def test_blocked_pipe_read_and_write_are_cancellable(self):
        import sys
        for output in (True, False):
            with self.subTest(output=output):
                cancel = threading.Event()
                timer = threading.Timer(.2, cancel.set)
                timer.start()
                started = time.monotonic()
                proc = None
                try:
                    with self.assertRaises(Cancelled):
                        with child([sys.executable, "-c", "import time; time.sleep(30)"], cancel,
                                   input_pipe=not output, output_pipe=output) as proc:
                            if output:
                                read_exact(proc, 100, cancel)
                            else:
                                write_frame(proc, b"x" * 1_000_000, cancel)
                    self.assertLess(time.monotonic() - started, 3)
                    self.assertIsNotNone(proc.poll())
                finally:
                    timer.cancel()


if __name__ == "__main__":
    unittest.main()
