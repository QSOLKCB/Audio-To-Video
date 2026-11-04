"""Cancellable subprocesses with bounded pipes on Windows, macOS and Linux."""
from contextlib import contextmanager
import os
import queue
import select
import subprocess
import tempfile
import threading


# Windows select() supports sockets only. POSIX keeps the direct pipe fast path.
THREADED_PIPES = os.name == "nt"


class RenderError(Exception):
    pass


class Cancelled(RenderError):
    pass


def checkpoint(cancel):
    if cancel.is_set():
        raise Cancelled("Cancelled. No output was published.")


class PipeReader:
    """One reader per child, two 64 KiB chunks of backpressure, sticky EOF."""
    def __init__(self, stream, stop):
        self.stream, self.stop = stream, stop
        self.chunks = queue.Queue(maxsize=2)
        self.pending = b''
        self.eof = False
        self.thread = threading.Thread(target=self.pump, name='a2v-pipe-reader')
        self.thread.start()

    def pump(self):
        while not self.stop.is_set():
            try:
                chunk = self.stream.read(65536)
            except OSError as exc:
                chunk = exc
            while not self.stop.is_set():
                try:
                    self.chunks.put(chunk, timeout=.05)
                    break
                except queue.Full:
                    pass
            if not chunk or isinstance(chunk, Exception):
                return

    def read(self, size, cancel):
        data = bytearray()
        while len(data) < size:
            checkpoint(cancel)
            if self.pending:
                count = min(size-len(data), len(self.pending))
                data.extend(self.pending[:count])
                self.pending = self.pending[count:]
            elif self.eof:
                break
            else:
                try:
                    chunk = self.chunks.get(timeout=.05)
                except queue.Empty:
                    continue
                if isinstance(chunk, Exception):
                    raise RenderError(f'Could not read media tool output: {chunk}') from chunk
                self.pending = chunk
                self.eof = not chunk
        return bytes(data)


class PipeWriter:
    """One writer per child. The caller waits for each complete bounded frame."""
    def __init__(self, stream, stop):
        self.stream, self.stop = stream, stop
        self.frames = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self.pump, name='a2v-pipe-writer')
        self.thread.start()

    def pump(self):
        while not self.stop.is_set():
            try:
                request = self.frames.get(timeout=.05)
                if request is None:
                    return
                frame, done, errors = request
            except queue.Empty:
                continue
            try:
                view = memoryview(frame)
                while view and not self.stop.is_set():
                    count = self.stream.write(view)
                    if not count:
                        raise BrokenPipeError('Video input closed')
                    view = view[count:]
            except (OSError, ValueError) as exc:
                errors.append(exc)
            finally:
                done.set()

    def write(self, frame, cancel):
        checkpoint(cancel)
        done, errors = threading.Event(), []
        self.frames.put((frame, done, errors))
        while not done.wait(.05):
            checkpoint(cancel)
        checkpoint(cancel)
        if errors:
            raise RenderError('FFmpeg closed the video input unexpectedly') from errors[0]


@contextmanager
def child(args, cancel, *, input_pipe=False, output_pipe=False):
    checkpoint(cancel)
    with tempfile.TemporaryFile() as errors:
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE if input_pipe else subprocess.DEVNULL,
                                    stdout=subprocess.PIPE if output_pipe else subprocess.DEVNULL,
                                    stderr=errors, bufsize=0,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except OSError as exc:
            raise RenderError(f"Could not start {args[0]}: {exc}") from exc
        stop = threading.Event()
        pipes = []
        try:
            if output_pipe and THREADED_PIPES:
                proc.a2v_reader = PipeReader(proc.stdout, stop)
                pipes.append(proc.a2v_reader)
            if input_pipe and THREADED_PIPES:
                proc.a2v_writer = PipeWriter(proc.stdin, stop)
                pipes.append(proc.a2v_writer)
            elif input_pipe:
                os.set_blocking(proc.stdin.fileno(), False)
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
            stop.set()
            for pipe in pipes:
                if isinstance(pipe, PipeWriter):
                    try:
                        pipe.frames.put_nowait(None)
                    except queue.Full:
                        pass
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            # Child exit releases blocked OS reads/writes; stop releases queues.
            # Join before closing pipe objects to avoid cross-thread close races.
            for pipe in pipes:
                pipe.thread.join()
            for stream in (proc.stdin, proc.stdout):
                if stream and not stream.closed:
                    stream.close()


def read_exact(proc, size, cancel):
    """Read at most one bounded frame, remaining cancellable if a child stalls."""
    if hasattr(proc, 'a2v_reader'):
        return proc.a2v_reader.read(size, cancel)
    data = bytearray()
    while len(data) < size:
        checkpoint(cancel)
        if not select.select([proc.stdout], [], [], .1)[0]:
            continue
        chunk = os.read(proc.stdout.fileno(), min(size-len(data), 65536))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def write_frame(proc, frame, cancel):
    if proc.poll() is not None:
        checkpoint(cancel)
        raise RenderError('FFmpeg stopped while receiving video frames')
    if hasattr(proc, 'a2v_writer'):
        proc.a2v_writer.write(frame, cancel)
        return
    view = memoryview(frame)
    while view:
        checkpoint(cancel)
        if proc.poll() is not None:
            raise RenderError('FFmpeg stopped while receiving video frames')
        if select.select([], [proc.stdin], [], .1)[1]:
            try:
                count = os.write(proc.stdin.fileno(), view)
            except BlockingIOError:
                continue
            except BrokenPipeError as exc:
                raise RenderError('FFmpeg closed the video input unexpectedly') from exc
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
