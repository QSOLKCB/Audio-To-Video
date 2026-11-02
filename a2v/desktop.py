"""Small GTK-independent worker controller."""
import queue
import threading

from .core import convert
from .process import Cancelled


class Controller:
    def __init__(self, renderer=convert):
        self.renderer = renderer
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.result = None
        self.error = ""
        self.status = "Choose an audio file to begin."
        self.fraction = 0.0

    @property
    def busy(self):
        return self.worker is not None

    def start(self, job):
        if self.busy:
            return False
        self.cancel.clear()
        self.result, self.error = None, ""
        self.status, self.fraction = "Starting…", 0.0

        def work():
            try:
                result = self.renderer(job, self.cancel,
                    lambda message, fraction: self.events.put(("progress", message, fraction)))
                self.events.put(("success", result))
            except Cancelled:
                self.events.put(("cancelled",))
            except Exception as exc:
                self.events.put(("error", str(exc)))
            finally:
                self.events.put(("done",))

        self.worker = threading.Thread(target=work, name="audio2video-render", daemon=False)
        self.worker.start()
        return True

    def stop(self):
        self.cancel.set()
        if self.busy:
            self.status = "Cancelling…"

    def drain(self):
        changed = False
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            changed = True
            if event[0] == "progress":
                if not self.cancel.is_set():
                    self.status, self.fraction = event[1:]
            elif event[0] == "success":
                self.result = event[1]
                self.status = f"Saved MP4 · checked all {self.result.verified_frames:,} video frames."
                self.fraction = 1.0
            elif event[0] == "cancelled":
                self.status = "Cancelled. No output was saved."
                self.fraction = 0.0
            elif event[0] == "error":
                self.error = event[1]
                self.status = "Could not create the video."
                self.fraction = 0.0
            elif event[0] == "done":
                self.worker.join()
                self.worker = None
        return changed
