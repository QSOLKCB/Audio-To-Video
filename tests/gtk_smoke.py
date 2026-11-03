"""Exercise real GTK widgets and the real media worker under Xvfb."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from a2v.gui import Adw, Application, GLib, Window
from fixtures import audio, png


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    errors = []
    def exception_hook(kind, value, tb):
        traceback.print_exception(kind, value, tb)
        errors.append(value)
    sys.excepthook = exception_hook
    context = GLib.MainContext.default()

    def spin(seconds=.1):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            while context.pending():
                context.iteration(False)
            time.sleep(.005)
        if errors:
            raise errors[0]

    def screenshot(name):
        if args.screenshots:
            args.screenshots.mkdir(parents=True, exist_ok=True)
            spin(.3)
            subprocess.run(["import", "-window", "root", str(args.screenshots / name)], check=True)

    app = Application()
    app.register(None)
    app.get_style_manager().set_color_scheme(Adw.ColorScheme.PREFER_DARK)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        win = Window(app)
        win.present()
        spin()
        assert not win.export_button.get_sensitive()
        win.set_audio(audio(root / "Studio session.wav", .6))
        win.set_image(png(root / "Cover.png"))
        assert win.export_button.get_sensitive()
        assert win.status.get_text() == "Ready to create MP4."
        assert win.visual.get_visible_child_name() == "cover"
        screenshot("gtk-still.png")

        win.viz_button.set_active(True)
        spin()
        assert win.mode == "visualizer"
        assert not win.image_row.get_visible()
        assert win.visual.get_visible_child_name() == "waveform"
        assert win.style_row.get_visible()
        win.style.set_selected(2)
        win.track_title.set_text("Trent Slade — Quantum Flex")
        spin()
        assert win.preview_key == (2, "Trent Slade — Quantum Flex")
        screenshot("gtk-visualizer.png")
        win.resolution.set_selected(1)
        win.start()
        assert win.controller.busy
        assert not win.audio_button.get_sensitive()
        assert not win.style.get_sensitive()
        assert not win.track_title.get_sensitive()
        assert win.cancel_button.get_visible()
        deadline = time.monotonic() + 30
        while win.controller.busy and time.monotonic() < deadline:
            spin()
        assert not win.controller.busy, "GTK export did not finish"
        assert not win.controller.error, win.controller.error
        assert win.controller.result.output.is_file()
        assert win.open_button.get_visible()
        screenshot("gtk-complete.png")

        win.choose_audio()
        spin(.2)
        win.chooser_cancel.cancel()
        spin(.2)
        assert not win.dialogs
        win.chooser_cancel.reset()

        win.still_button.set_active(True)
        assert not win.open_button.get_visible()
        assert not win.style_row.get_visible()
        win.set_output(root / "still.mp4")
        win.start()
        deadline = time.monotonic() + 30
        while win.controller.busy and time.monotonic() < deadline:
            spin()
        assert not win.controller.busy and not win.controller.error, win.controller.error
        assert win.controller.result.output.name == "still.mp4"

        win.viz_button.set_active(True)
        win.set_audio(audio(root / "long.wav", 10))
        output = win.output
        win.start()
        win.close()
        deadline = time.monotonic() + 10
        while win.controller.busy and time.monotonic() < deadline:
            spin()
        spin()
        assert not win.controller.busy
        assert not output.exists()
        assert not list(root.glob(".audio2video-*"))
        assert not errors, errors
    print("GTK checks passed: both real exports, mode controls, dialog cancellation and close during work")


if __name__ == "__main__":
    main()
