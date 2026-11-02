"""Cancellable local subprocesses; no shell and no unbounded pipe buffering."""
from contextlib import contextmanager
import os
import select
import subprocess
import tempfile


class RenderError(Exception):
    pass


class Cancelled(RenderError):
    pass


def checkpoint(cancel):
    if cancel.is_set():
        raise Cancelled("Cancelled. No output was published.")


@contextmanager
def child(args, cancel, *, input_pipe=False, output_pipe=False):
    checkpoint(cancel)
    with tempfile.TemporaryFile() as errors:
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE if input_pipe else subprocess.DEVNULL,
                                    stdout=subprocess.PIPE if output_pipe else subprocess.DEVNULL,
                                    stderr=errors, bufsize=0)
        except OSError as exc:
            raise RenderError(f"Could not start {args[0]}: {exc}") from exc
        try:
            yield proc
            while proc.poll() is None:
                checkpoint(cancel)
                cancel.wait(.05)
            checkpoint(cancel)
            if proc.returncode:
                errors.seek(0, os.SEEK_END)
                errors.seek(max(0, errors.tell() - 4000))
                detail = errors.read().decode("utf-8", "replace").strip()
                raise RenderError(detail or f"{args[0]} exited with status {proc.returncode}")
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            for stream in (proc.stdin, proc.stdout):
                if stream and not stream.closed:
                    stream.close()


def read_exact(proc, size, cancel):
    """Read at most one bounded frame, remaining cancellable when a child stalls."""
    data = bytearray()
    while len(data) < size:
        checkpoint(cancel)
        if not select.select([proc.stdout], [], [], .1)[0]:
            continue
        chunk = os.read(proc.stdout.fileno(), min(size - len(data), 65536))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def write_frame(proc, frame, cancel):
    view = memoryview(frame)
    os.set_blocking(proc.stdin.fileno(), False)
    while view:
        checkpoint(cancel)
        if proc.poll() is not None:
            raise RenderError("FFmpeg stopped while receiving video frames")
        if select.select([], [proc.stdin], [], .1)[1]:
            try:
                count = os.write(proc.stdin.fileno(), view)
            except BlockingIOError:
                continue
            except BrokenPipeError as exc:
                raise RenderError("FFmpeg closed the video input unexpectedly") from exc
            view = view[count:]


def run(args, cancel):
    with child(args, cancel):
        pass


def capture(args, cancel, limit=2_000_000):
    with child(args, cancel, output_pipe=True) as proc:
        data = read_exact(proc, limit + 1, cancel)
        if len(data) > limit:
            raise RenderError("Tool output exceeded the expected size")
    return data
