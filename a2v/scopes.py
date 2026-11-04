"""Frame-local oscilloscope views: no mutable history or playback clock."""
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .angles import TURN, cosine, sine
from .visualizer import BACKGROUND, HEIGHT, PALETTE, SAMPLES, WIDTH, values


@lru_cache(maxsize=3)
def grid(style):
    image = Image.new('RGB', (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for x in range(40, 601, 40):
        draw.line((x, 64, x, 304), fill=(23, 36, 44))
    for y in range(64, 305, 40):
        draw.line((40, y, 600, y), fill=(23, 36, 44))
    if style == 'trigger-scope':
        for center in (124, 244):
            draw.line((40, center, 600, center), fill=(40, 63, 70))
    else:
        draw.line((200, 184, 440, 184), fill=(40, 63, 70))
        draw.line((320, 64, 320, 304), fill=(40, 63, 70))
        for radius in (40, 80, 120):
            draw.ellipse((320-radius, 184-radius, 320+radius, 184+radius), outline=(32, 48, 58))
    labels = {'trigger-scope': 'L / R   •   rising-edge trigger   •   16.7 ms',
              'vectorscope': 'STEREO   •   horizontal: L − R   •   vertical: L + R',
              'radial-scope': 'L / R   •   one audio window per circle'}
    # ASCII labels remain independent of system font fallback.
    draw.text((40, 324), labels[style].replace('•', '|').replace('−', '-'), fill=(132, 166, 180))
    return image


def trigger_start(data):
    """First rising zero crossing of the stronger channel, leaving 800 pairs.

    Triggering is confined to this frame's first half. Silence/DC fall back to
    offset zero. Channel traces share the offset, preserving their phase.
    """
    channel = max(range(2), key=lambda c: max(abs(v) for v in data[c::2]))
    return next((i for i in range(1, SAMPLES//2 + 1)
                 if data[(i-1)*2+channel] <= 0 < data[i*2+channel]), 0)


def stereo_point(left, right):
    # Mid/side projection, preserving antiphase stereo rather than downmixing.
    return (320 + (left-right)*112//65536, 184 - (left+right)*112//65536)


@lru_cache(maxsize=1)
def radial_basis():
    return tuple((cosine(i*TURN//560), sine(i*TURN//560)) for i in range(560))


def render_scope(pcm, style):
    data = values(pcm)
    ink = Image.new('RGB', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(ink)
    if style == 'trigger-scope':
        start = trigger_start(data)
        for channel, color in enumerate(PALETTE[:2]):
            center = 124 + channel*120
            points = [(40+x, center-data[(start+x*800//560)*2+channel]*48//32768)
                      for x in range(560)]
            draw.line(points, fill=color, width=5)
    elif style == 'vectorscope':
        points = [stereo_point(data[i*2], data[i*2+1]) for i in range(SAMPLES)]
        draw.line(points, fill=PALETTE[0], width=3)
        # DC/silence is a real point: make it visible to the export checker.
        x, y = points[-1]
        draw.ellipse((x-3, y-3, x+3, y+3), fill=PALETTE[1])
    elif style == 'radial-scope':
        for channel, color in enumerate(PALETTE[:2]):
            points = []
            for i, (c, s) in enumerate(radial_basis()):
                radius = 74 + channel*12 + data[(i*SAMPLES//560)*2+channel]*22//32768
                points.append((320+c*radius//16384, 184+s*radius//16384))
            draw.line(points + points[:1], fill=color, width=3)
    else:
        raise ValueError('Unknown oscilloscope style')
    glow = ink.filter(ImageFilter.GaussianBlur(3))
    return ImageChops.add(ImageChops.add(grid(style), glow), ink)
