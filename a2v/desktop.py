"""Small GTK-independent worker controller."""
import os
from pathlib import Path
import time
import queue
import threading

from .core import convert
from .process import Cancelled


def next_output(audio):
    """Suggest a free name, including broken symlinks; publication still checks."""
    audio = Path(audio)
    candidate, index = audio.with_suffix('.mp4'), 1
    while os.path.lexists(candidate):
        candidate = audio.with_name(f'{audio.stem}-{index}.mp4')
        index += 1
    return candidate


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
        self.started = self.finished = None

    @property
    def busy(self):
        return self.worker is not None

    @property
    def elapsed_text(self):
        if self.started is None:
            return ''
        seconds = int((self.finished if self.finished is not None else time.monotonic()) - self.started)
        return f'Elapsed {seconds//60:02d}:{seconds%60:02d}'

    def start(self, job):
        if self.busy:
            return False
        self.started, self.finished = time.monotonic(), None
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
                self.finished = time.monotonic()
                self.worker.join()
                self.worker = None
        return changed
