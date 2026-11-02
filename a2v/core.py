"""Local PCM -> video -> decoded-frame verification -> atomic publication."""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import threading

from .process import Cancelled, RenderError, capture, checkpoint, child, read_exact, run, write_frame
from .visualizer import FPS, HEIGHT, RATE, SAMPLES, WIDTH, check_thumbnail, reference_thumbnail, render

AUDIO_FORMATS = {".mp3": "mp3", ".m4a": "mov", ".wav": "wav"}
IMAGE_FORMATS = {".png": "png", ".jpg": "mjpeg", ".jpeg": "mjpeg"}
SIZES = {"720p": (1280, 720), "1080p": (1920, 1080)}


@dataclass(frozen=True)
class Job:
    audio: Path
    output: Path
    mode: str = "visualizer"
    image: Path | None = None
    resolution: str = "1080p"


@dataclass(frozen=True)
class Result:
    output: Path
    frames: int
    seconds: float
    verified_frames: int


def dependencies():
    return [name for name in ("ffmpeg", "ffprobe") if not shutil.which(name)]


def regular(path, extensions, label):
    path = Path(path).expanduser().absolute()
    if path.suffix.lower() not in extensions:
        raise RenderError(f"{label}: choose {', '.join(extensions)}")
    if not path.is_file():
        raise RenderError(f"{label} must be a local regular file: {path}")
    if path.stat().st_size == 0:
        raise RenderError(f"{label} is empty")
    return path


def validate(job):
    if job.mode not in ("still", "visualizer") or job.resolution not in SIZES:
        raise RenderError("Choose Still image or Visualizer, and 720p or 1080p")
    audio = regular(job.audio, AUDIO_FORMATS, "Audio")
    image = regular(job.image, IMAGE_FORMATS, "Image") if job.mode == "still" and job.image else None
    if job.mode == "still" and image is None:
        raise RenderError("Choose a PNG or JPEG still image")
    output = Path(job.output).expanduser().absolute()
    if output.suffix.lower() != ".mp4":
        raise RenderError("The output filename must end in .mp4")
    if os.path.lexists(output):
        raise RenderError("That output already exists. Choose a new filename.")
    if not output.parent.is_dir():
        raise RenderError("Choose an existing output folder")
    missing = dependencies()
    if missing:
        raise RenderError("Install missing tools: " + ", ".join(missing) + " (./install-deps.sh)")
    return Job(audio, output, job.mode, image, job.resolution)


def ffmpeg():
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-xerror",
            "-filter_threads", "1", "-filter_complex_threads", "1"]


def local_input(path, *, demuxer=None):
    args = ["-protocol_whitelist", "file,pipe", "-threads", "1"]
    if demuxer:
        args += ["-f", demuxer]
    return args + ["-i", str(path)]


def probe(path, cancel):
    data = capture(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                    "-show_streams", "-show_format", "-of", "json", str(path)], cancel)
    try:
        return json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise RenderError("FFprobe returned invalid media information") from exc


def prepare_still(job, work, cancel):
    width, height = SIZES[job.resolution]
    output = work / "still.ppm"
    # Flatten transparency explicitly. Fit the whole image without stretching.
    graph = (f"color=c=0x0c1219:s={width}x{height}:r={FPS}[bg];"
             f"[0:v:0]scale={width}:{height}:force_original_aspect_ratio=decrease,setsar=1[fg];"
             "[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,format=rgb24[v]")
    run(ffmpeg() + ["-protocol_whitelist", "file,pipe", "-threads", "1", "-f", "image2",
                   "-pattern_type", "none", "-c:v", IMAGE_FORMATS[job.image.suffix.lower()],
                   "-i", str(job.image), "-filter_complex", graph, "-map", "[v]",
                   "-frames:v", "1", "-c:v", "ppm", "-update", "1", str(output)], cancel)
    return output


def encoder_args(job, pcm, target, frames, still=None):
    width, height = SIZES[job.resolution]
    args = ffmpeg()
    if still:
        args += ["-loop", "1", "-framerate", str(FPS)] + local_input(still)
    else:
        args += ["-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{WIDTH}x{HEIGHT}",
                 "-framerate", str(FPS)] + local_input("pipe:0")
    args += ["-f", "s16le", "-ar", str(RATE), "-ac", "2"] + local_input(pcm)
    # Both streams are explicit. An MP4 containing only AAC is never success.
    args += ["-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "-1", "-map_chapters", "-1",
             "-vf", f"scale={width}:{height}:flags=neighbor,setsar=1,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-threads:v", "1",
             "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "192k", "-threads:a", "1", "-t", f"{frames / FPS:.9f}",
             "-movflags", "+faststart", "-f", "mp4", str(target)]
    return args


def verify_output(path, pcm, job, frame_count, sample_count, cancel, progress):
    """Decode EVERY video frame and all audio before the MP4 is published.

    Each visualizer frame is checked against its sample-derived reference;
    silence is permitted but a missing rail is not. Still images may be black.
    """
    info = probe(path, cancel)
    streams = info.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if len(video) != 1 or len(audio) != 1 or len(streams) != 2:
        raise RenderError("MP4 must contain exactly one video and one audio stream")
    v, a = video[0], audio[0]
    if (v.get("codec_name") != "h264" or v.get("pix_fmt") != "yuv420p"
            or (v.get("width"), v.get("height")) != SIZES[job.resolution]
            or v.get("avg_frame_rate") != "30/1" or a.get("codec_name") != "aac"):
        raise RenderError("Encoded MP4 has unexpected codecs, dimensions, pixel format, or frame rate")
    try:
        audio_seconds = float(a["duration"])
        if not math.isfinite(audio_seconds) or abs(audio_seconds - sample_count / RATE) > .06:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise RenderError("Encoded audio duration does not match the source") from None
    args = ffmpeg() + local_input(path) + ["-map", "0:v:0", "-an", "-vf",
            "scale=160:90:flags=neighbor", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
    count = 0
    with pcm.open("rb") as samples, child(args, cancel, output_pipe=True) as proc:
        while True:
            frame = read_exact(proc, 160 * 90 * 3, cancel)
            if not frame:
                break
            if len(frame) != 160 * 90 * 3 or count >= frame_count:
                raise RenderError("MP4 contains an incomplete or unexpected video frame")
            if job.mode == "visualizer":
                expected = reference_thumbnail(samples.read(SAMPLES * 4))
                try:
                    check_thumbnail(frame, expected)
                except ValueError as exc:
                    raise RenderError(f"Video verification failed at frame {count}: {exc}") from exc
            count += 1
            if count % FPS == 0:
                progress("Checking encoded video", .72 + .25 * count / frame_count)
    if count != frame_count:
        raise RenderError(f"Missing video frames: expected {frame_count}, decoded {count}")
    progress("Checking encoded audio", .98)
    # Decode the audio too; stream metadata alone does not prove it is playable.
    run(ffmpeg() + local_input(path) + ["-map", "0:a:0", "-vn", "-f", "null", "-"], cancel)
    return count


def convert(job: Job, cancel=None, progress=lambda message, fraction: None) -> Result:
    cancel = cancel if cancel is not None else threading.Event()
    checkpoint(cancel)
    job = validate(job)
    # All temporary media stay on the output filesystem; no partial final file.
    with tempfile.TemporaryDirectory(prefix=".audio2video-", dir=job.output.parent) as directory:
        work = Path(directory)
        pcm, target = work / "audio.s16le", work / "video.mp4"
        progress("Reading audio", .02)
        run(ffmpeg() + local_input(job.audio, demuxer=AUDIO_FORMATS[job.audio.suffix.lower()])
            + ["-map", "0:a:0", "-vn", "-sn", "-dn", "-ar", str(RATE), "-ac", "2",
               "-c:a", "pcm_s16le", "-f", "s16le", str(pcm)], cancel)
        size = pcm.stat().st_size
        if size == 0 or size % 4:
            raise RenderError("Audio did not decode to complete stereo samples")
        samples = size // 4
        frames = (samples + SAMPLES - 1) // SAMPLES
        seconds = samples / RATE
        still = prepare_still(job, work, cancel) if job.mode == "still" else None
        progress("Rendering video", .10)
        # Round VIDEO up to a complete frame. Audio ends at its real sample count.
        # A source-duration -t can round down and silently discard the final frame.
        args = encoder_args(job, pcm, target, frames, still)
        if still:
            run(args, cancel)
        else:
            with pcm.open("rb") as source, child(args, cancel, input_pipe=True) as proc:
                for index in range(frames):
                    write_frame(proc, render(source.read(SAMPLES * 4)), cancel)
                    if index % FPS == 0:
                        progress("Rendering visualizer", .10 + .60 * index / frames)
                proc.stdin.close()
        progress("Checking encoded video", .72)
        verified = verify_output(target, pcm, job, frames, samples, cancel, progress)
        checkpoint(cancel)
        # link is atomic and fails if another job/user created this name meanwhile.
        # No overwrite flag: an existing file is never silently replaced.
        try:
            os.link(target, job.output)
        except FileExistsError as exc:
            raise RenderError("Output appeared while rendering. Choose a new filename.") from exc
        except OSError as exc:
            raise RenderError(f"Could not publish MP4 (choose a local filesystem supporting hard links): {exc}") from exc
    progress("Saved and verified", 1.0)
    return Result(job.output, frames, seconds, verified)
