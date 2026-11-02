"""Small generated signals and images; no downloaded test media."""
import math
from pathlib import Path
import struct
import subprocess
import wave
import zlib


def audio(path, seconds=1, kind="dynamic", rate=48000, channels=2):
    data = bytearray()
    for i in range(round(rate * seconds)):
        t = i / rate
        amplitude = 0 if kind == "silence" or t < seconds / 4 else (3500 if t < seconds / 2 else 24000)
        value = round(amplitude * math.sin(2 * math.pi * 440 * t))
        pair = (value, -value if kind == "antiphase" else value)
        data.extend(struct.pack("<h" if channels == 1 else "<hh", *(pair[:channels])))
    with wave.open(str(path), "wb") as out:
        out.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        out.writeframes(data)
    return Path(path)


def png(path, width=80, height=50, transparent=False):
    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value))
    rows = b"".join(b"\0" + b"".join(bytes((255 if x < width // 2 else 15, 75, 20,
                                          0 if transparent and x < width // 2 else 255))
                                      for x in range(width)) for _ in range(height))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    return Path(path)


def command(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def decoded_frames(path, width=160, height=90):
    data = command("ffmpeg", "-v", "error", "-threads", "1", "-i", str(path), "-map", "0:v:0",
                   "-an", "-vf", f"scale={width}:{height}:flags=neighbor", "-threads", "1",
                   "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1")
    size = width * height * 3
    return [data[i:i + size] for i in range(0, len(data), size)]
