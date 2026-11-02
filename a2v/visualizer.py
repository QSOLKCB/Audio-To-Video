"""Integer-only waveform bars. No clock, random state, GPU, or FFT dependency."""
from array import array
import sys

WIDTH, HEIGHT = 640, 360
FPS, RATE = 30, 48000
SAMPLES = RATE // FPS
BARS = 80
BACKGROUND = (12, 18, 25)
FOREGROUND = (95, 219, 211)


def peaks(pcm: bytes) -> list[int]:
    """Peak of either stereo channel in each fixed 20-sample time bin.

    Keeping the channels separate avoids cancelling opposite-phase stereo.
    The last, incomplete window is zero padded; even silence has a visible rail.
    """
    values = array("h")
    values.frombytes(pcm.ljust(SAMPLES * 4, b"\0"))
    if sys.byteorder != "little":
        values.byteswap()
    return [max(abs(v) for v in values[i:i + 40]) for i in range(0, SAMPLES * 2, 40)]


def rectangle(frame, x, y, width, height, color):
    row = bytes(color) * width
    for line in range(y, y + height):
        offset = (line * WIDTH + x) * 3
        frame[offset:offset + len(row)] = row


def render(pcm: bytes) -> bytes:
    """640x360 RGB24; frame n consumes samples [1600n, 1600(n+1))."""
    frame = bytearray(bytes(BACKGROUND) * (WIDTH * HEIGHT))
    # Fixed subtle grid, with no decorations that could masquerade as waveform.
    for y in (60, 120, 240, 300):
        rectangle(frame, 40, y, 560, 1, (21, 32, 42))
    for i, value in enumerate(peaks(pcm)):
        half = 3 + value * 132 // 32768
        rectangle(frame, 40 + i * 7, HEIGHT // 2 - half, 5, half * 2, FOREGROUND)
    return bytes(frame)


def reference_thumbnail(pcm: bytes) -> bytes:
    """Expected green-channel 160x90 nearest-neighbour thumbnail.

    The encoder upscales the 640x360 raster by integer 2x or 3x. The verifier
    samples the centres of each four-pixel block after decoding the real MP4.
    """
    frame = render(pcm)
    return bytes(frame[(y * WIDTH + x) * 3 + 1]
                 for y in range(2, HEIGHT, 4) for x in range(2, WIDTH, 4))


def check_thumbnail(actual: bytes, expected: bytes) -> None:
    """Reject absent, blank, or materially different waveform after H.264.

    Small codec rounding differences are allowed; every frame is checked.
    The foreground coverage check also catches blank frames during silence.
    """
    if len(actual) != 160 * 90 * 3 or len(expected) != 160 * 90:
        raise ValueError("Incomplete decoded visualizer frame")
    green = actual[1::3]
    foreground = [i for i, value in enumerate(expected) if value > 150]
    if not foreground or sum(green[i] > 120 for i in foreground) < len(foreground) * .85:
        raise ValueError("Visualizer is missing or incomplete in the encoded MP4")
    # Check the whole waveform region, not the dark border, for frozen frames.
    region = [y * 160 + x for y in range(10, 80) for x in range(10, 150)]
    mismatch = sum(abs(green[i] - expected[i]) > 65 for i in region)
    if mismatch > len(region) * .025:
        raise ValueError("Encoded MP4 does not match the audio-driven waveform")
