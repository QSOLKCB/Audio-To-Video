"""Literal text rasterization: no shell, FFmpeg expression, or markup expansion."""
from functools import lru_cache
from pathlib import Path
import unicodedata

from PIL import Image, ImageDraw, ImageFont

from .process import RenderError

FONT = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
HEADER = 56  # Source pixels; exactly 14 verification thumbnail rows.
COLOR = (12, 18, 25)


def normalize_title(text):
    if not isinstance(text, str) or any(unicodedata.category(c) in ('Cc', 'Cs') for c in text):
        raise RenderError('Title must be one line of plain text, without control characters')
    text = text.strip()
    if len(text) > 120:
        raise RenderError('Keep the title to 120 characters or fewer')
    return text


@lru_cache(maxsize=8)
def title_image(text, width):
    """Native-resolution, centred title, fitted by measured glyph bounds."""
    scale = width // 640
    image = Image.new('RGB', (width, HEADER * scale), COLOR)
    if not text:
        return image
    if not FONT.is_file():
        raise RenderError('Title font is missing. Run ./install-deps.sh (fonts-dejavu-core).')
    draw = ImageDraw.Draw(image)
    for size in range(22 * scale, 9 * scale, -1):
        font = ImageFont.truetype(str(FONT), size, layout_engine=ImageFont.Layout.BASIC)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= width - 64 * scale and bottom - top <= HEADER * scale - 16 * scale:
            break
    else:
        raise RenderError('Title is too wide to fit legibly. Please shorten it.')
    draw.text(((width - right + left) // 2 - left,
               (HEADER * scale - bottom + top) // 2 - top), text, font=font, fill=(244, 246, 255))
    draw.line((32 * scale, HEADER * scale - 1, width - 32 * scale, HEADER * scale - 1),
              fill=(42, 54, 70), width=scale)
    return image


def prepare_title(text, width, work):
    if not text:
        return None
    path = work / 'title.ppm'
    title_image(text, width).save(path)
    return path


def check_title(actual, text, width):
    expected = title_image(text, width).resize((160, HEADER // 4), Image.Resampling.NEAREST).tobytes()
    actual = actual[:len(expected)]
    bright = [i for i in range(0, len(expected), 3) if min(expected[i:i+3]) > 180]
    if (len(actual) != len(expected) or not bright
            or sum(min(actual[i:i+3]) > 140 for i in bright) < len(bright) * .85
            or sum(abs(a-b) for a,b in zip(actual, expected)) / len(expected) > 8):
        raise ValueError('Title is missing or different in the encoded MP4')
