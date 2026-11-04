"""Real Tk window, all previews, successful export, and close-during-work."""
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from a2v.desktop import Controller, next_output
from a2v.process import Cancelled
from a2v.tk_gui import Window
from a2v.visualizer import STYLES
from fixtures import audio


def pump(root, predicate, timeout=45):
    deadline = time.monotonic()+timeout
    while not predicate() and time.monotonic() < deadline:
        root.update()
        time.sleep(.02)
    assert predicate(), 'Tk worker did not finish'
    root.update()


with tempfile.TemporaryDirectory(prefix='a2v tk smoke ') as directory:
    root = tk.Tk()
    window = Window(root)
    try:
        for style in STYLES.values():
            window.style.set(style)
            window.changed()
            root.update()
            assert window.texture.width() == 560
        window.audio = audio(Path(directory)/'signal.wav', .137, 'antiphase')
        window.output = next_output(window.audio)
        window.title.set('Tk — portable export')
        window.style.set(STYLES['trigger-scope'])
        window.resolution.set('720p')
        window.changed()
        window.start()
        assert window.controller.busy
        assert str(window.styles['state']) == 'disabled'
        pump(root, lambda: not window.controller.busy)
        assert not window.controller.error, window.controller.error
        assert window.controller.result.verified_frames == 5
        assert window.output.is_file()
        assert str(window.open_button['state']) == 'normal'
        assert window.controller.elapsed_text.startswith('Elapsed ')
        root.geometry('640x560')
        root.update()
        window.viewport_canvas.yview_moveto(1)
        root.update()
        assert window.export_button.winfo_rooty()+window.export_button.winfo_height() <= root.winfo_rooty()+root.winfo_height()
        assert window.export_button.winfo_rootx()+window.export_button.winfo_width() <= root.winfo_rootx()+root.winfo_width()
    finally:
        root.after_cancel(window.poll_id)
        root.destroy()

root = tk.Tk()
def blocked(job, cancel, progress):
    cancel.wait(5)
    raise Cancelled()
window = Window(root, Controller(blocked))
window.controller.start(None)
window.close()
# close() leaves the root alive until the non-daemon export thread has stopped.
deadline = time.monotonic()+5
while window.controller.busy and time.monotonic() < deadline:
    root.update()
    time.sleep(.02)
assert not window.controller.busy
print('Tk smoke passed: all previews, real verified export, disabled controls, elapsed time, graceful close.')
