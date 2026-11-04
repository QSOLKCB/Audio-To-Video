"""CLI and lazy desktop launchers; headless exports import no GUI toolkit."""
import argparse
import os
from pathlib import Path
import signal
import sys
import threading

from . import __version__
from .core import Job, convert, dependencies
from .process import Cancelled, RenderError
from .visualizer import STYLES


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local audio + still image or deterministic visualizer → MP4")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    doctor = commands.add_parser("doctor", help="check the installed local media tools")
    doctor.add_argument('--gui', action='store_true', help='also check the portable desktop and bundled font')
    gui = commands.add_parser('gui', help='open the desktop app')
    gui.add_argument('--backend', choices=('gtk', 'tk'), default=None)
    export = commands.add_parser("render", help="export without opening GTK")
    export.add_argument("audio", type=Path, help="MP3, M4A or WAV")
    export.add_argument("output", type=Path, help="new .mp4 file (never overwritten)")
    mode = export.add_mutually_exclusive_group(required=True)
    mode.add_argument("--image", type=Path, help="PNG or JPEG still image")
    mode.add_argument("--visualizer", action="store_true", help="deterministic audio-reactive visuals")
    export.add_argument("--style", choices=STYLES, default="bars", help="visualizer style (default: bars)")
    export.add_argument("--title", default="", help="optional top title, up to 120 characters")
    export.add_argument("--resolution", choices=("720p", "1080p"), default="1080p")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        missing = dependencies()
        if args.gui:
            try:
                from .tk_gui import Window
                import tkinter as tk
                from .title import title_image
                title_image('Desktop check', 640)
                root = tk.Tk()
                try:
                    root.withdraw()
                    Window(root)
                    root.update_idletasks()
                finally:
                    root.destroy()
            except Exception as exc:
                missing.append(f'portable desktop: {exc}')
        print("Missing: " + ", ".join(missing) if missing else "FFmpeg and FFprobe found. Run a short export to check your codecs.")
        return int(bool(missing))
    if args.command in (None, 'gui'):
        backend = getattr(args, 'backend', None) or os.environ.get('A2V_GUI_BACKEND') or ('tk' if sys.platform in ('win32', 'darwin') else 'gtk')
        try:
            if backend == 'tk':
                from .tk_gui import launch
            else:
                from .gui import launch
            return launch()
        except Exception as exc:
            print(f"Cannot open {backend} desktop: {exc}\nSee docs/portable.md; CLI render is also available.", file=sys.stderr)
            return 1
    cancel = threading.Event()
    previous = {s: signal.signal(s, lambda *_: cancel.set()) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        result = convert(Job(args.audio, args.output, "still" if args.image else "visualizer",
                             args.image, args.resolution, args.style, args.title), cancel,
                         lambda message, fraction: print(f"{fraction:5.0%}  {message}", file=sys.stderr))
        print(result.output)
        return 0
    except Cancelled as exc:
        print(str(exc), file=sys.stderr)
        return 130
    except (RenderError, OSError) as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
