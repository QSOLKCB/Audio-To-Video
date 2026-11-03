"""CLI and lazy GTK launcher; headless exports do not import GTK."""
import argparse
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
    commands.add_parser("doctor", help="check the installed local media tools")
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
        print("Missing: " + ", ".join(missing) if missing else "FFmpeg and FFprobe found. Run a short export to check your codecs.")
        return int(bool(missing))
    if args.command is None:
        try:
            from .gui import launch
            return launch()
        except (ImportError, ValueError, RuntimeError) as exc:
            print(f"Cannot open GTK: {exc}\nRun ./install-deps.sh on Ubuntu 24.04+.", file=sys.stderr)
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
