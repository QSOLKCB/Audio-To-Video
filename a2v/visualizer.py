"""Bounded, stateless CPU visuals, driven only by PCM, style and frame index."""
from array import array
from functools import lru_cache
from math import isqrt
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .angles import TURN, cosine, sine

WIDTH, HEIGHT = 640, 360
FPS, RATE = 30, 48000
SAMPLES = RATE // FPS
BARS = 80
BACKGROUND = (12, 18, 25)
FOREGROUND = (95, 219, 211)
STYLES = {'bars': 'Waveform bars', 'scope': 'Oscilloscope',
          'qutrit-galaxy': 'Quantum Galaxy', 'gluball-knot': 'GLUBALL Knot'}
PALETTE = ((94, 234, 242), (184, 152, 255), (255, 189, 112))


def values(pcm):
    result = array('h')
    result.frombytes(pcm.ljust(SAMPLES * 4, b'\0'))
    if sys.byteorder != 'little':
        result.byteswap()
    return result


def peaks(pcm):
    """80 time bins; peak of either channel, preserving opposite-phase stereo."""
    data = values(pcm)
    return [max(abs(v) for v in data[i:i+40]) for i in range(0, SAMPLES*2, 40)]


def populations(pcm):
    """Three broad filter energies -> integer populations summing to 1,000,000.

    First-order low passes (1/32 and 1/4) split bass / middle / high motion.
    Filter state resets each 1600-pair window: random access, no hidden history.
    Channel energies add; opposite-phase stereo cannot cancel. These are artistic
    control signals, not a calibrated spectrum, quantum simulation or QCD model.
    """
    low, mid, energy = [0, 0], [0, 0], [0, 0, 0]
    for i, sample in enumerate(values(pcm)):
        channel = i & 1
        low[channel] += (sample - low[channel]) // 32
        mid[channel] += (sample - mid[channel]) // 4
        for band, value in enumerate((low[channel], mid[channel]-low[channel], sample-mid[channel])):
            energy[band] += value * value
    total = sum(energy)
    if not total:
        return (333334, 333333, 333333)
    weights = [e * 1000000 // total for e in energy]
    # Largest remainder, deterministic ties by basis index.
    order = sorted(range(3), key=lambda i: (-(energy[i]*1000000 % total), i))
    for i in order[:1000000-sum(weights)]:
        weights[i] += 1
    return tuple(weights)


def rectangle(frame, x, y, width, height, color):
    row = bytes(color) * width
    for line in range(y, y + height):
        offset = (line * WIDTH + x) * 3
        frame[offset:offset + len(row)] = row


def mix(index):
    """Fixed indexed 32-bit mixer. No random generator or mutable seed."""
    value = (index + 0x9e3779b9) & 0xffffffff
    value = ((value ^ (value >> 16)) * 0x85ebca6b) & 0xffffffff
    value = ((value ^ (value >> 13)) * 0xc2b2ae35) & 0xffffffff
    return value ^ (value >> 16)


@lru_cache(maxsize=1)
def backdrop():
    image = Image.new('RGB', (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for i in range(180):
        code = mix(i)
        x, y = code % WIDTH, 60 + (code >> 10) % 248
        level = 28 + (code >> 20) % 50
        draw.point((x, y), fill=(level*3//4, level*4//5, level))
    return image


def glow(ink):
    base = ImageChops.add(backdrop(), ink.filter(ImageFilter.GaussianBlur(5)))
    return ImageChops.add(base, ink)


def state_legend(image, weights):
    draw = ImageDraw.Draw(image)
    for i, weight in enumerate(weights):
        x = 110 + 154*i
        color = PALETTE[i]
        draw.text((x, 318), f'|{i}>  {weight/10000:.1f}%', fill=color)
        draw.line((x, 337, x+112, 337), fill=(30, 39, 54), width=3)
        draw.line((x, 337, x+max(2, weight*112//1000000), 337), fill=color, width=3)


def galaxy(pcm, index):
    weights = populations(pcm)
    volume = max(peaks(pcm))
    ink = Image.new('RGB', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(ink)
    phase = index * TURN // 720
    # Three coherent spiral arms with fixed indexed dust; finite resident count.
    for state, color in enumerate(PALETTE):
        arm = phase + state*TURN//3
        strength = isqrt(weights[state]*1000000)
        points = []
        for i in range(1, 361):
            radius = 12 + i*202//360
            angle = arm + i*TURN//240
            x = 320 + cosine(angle)*radius//16384
            y = 186 + sine(angle)*radius*46//(16384*100)
            points.append((x, y))
            code = mix(state*1024 + i)
            spread = 2 + i//20
            dx, dy = (code % (2*spread+1))-spread, ((code >> 9) % (2*spread+1))-spread
            light = 75 + strength*120//1000000 + volume*45//32768
            dust = tuple(c*light//255 for c in color)
            size = 1 + int((code >> 20) % 19 == 0)
            draw.ellipse((x+dx-size,y+dy-size,x+dx+size,y+dy+size), fill=dust)
        draw.line(points, fill=tuple(c*(100+strength*140//1000000)//255 for c in color), width=2)
        # Bright moving state packet; its size/brightness follows population.
        angle = arm + index*TURN//180
        radius = 65 + volume*35//32768
        x, y = 320+cosine(angle)*radius//16384, 186+sine(angle)*radius*46//1638400
        size = 3 + strength*5//1000000
        draw.ellipse((x-size,y-size,x+size,y+size), fill=color)
    draw.ellipse((312,178,328,194), fill=(220,242,255))
    image = glow(ink)
    state_legend(image, weights)
    return image


def knot(pcm, index):
    weights = populations(pcm)
    volume = max(peaks(pcm))
    ink = Image.new('RGB', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(ink)
    segments = []
    # Independent adaptation of the public (2,3) torus-knot equation, with three
    # travelling ribbons. Fixed camera; qutrit controls are new, not donor physics.
    for state, color in enumerate(PALETTE):
        for strand in (-1, 0, 1):
            points = []
            for i in range(513):
                t = i*TURN//512
                v = state*TURN//3 + strand*TURN//18 + index*TURN//300 + t*5
                minor = 44 + volume*10//32768 + cosine(v)*13//16384
                radial = 91 + minor*cosine(3*t)//16384
                x = radial*cosine(2*t)//16384
                y = radial*sine(2*t)//16384
                z = minor*sine(3*t)//16384 + sine(v)*13//16384
                # Static orthographic tilt, with depth-sorted ribbon segments.
                sx, sy, depth = 320+x*3//2, 187+y*7//10-z, y+z
                points.append((sx, sy, depth))
            for i, (a,b) in enumerate(zip(points, points[1:])):
                travel = (i*1024//512 - index*7 - state*341) % 1024
                brightness = 110 + isqrt(weights[state]*1000000)*65//1000000
                brightness += max(0, 75-abs(travel-512))
                if strand:
                    brightness = brightness*3//5
                rgb = tuple(min(255,c*brightness//190) for c in color)
                segments.append((a[2], a[:2], b[:2], rgb))
    for _, a, b, color in sorted(segments, key=lambda s:s[0]):
        draw.line((a,b), fill=color, width=2)
    image = glow(ink)
    state_legend(image, weights)
    return image


def scope(pcm):
    ink = Image.new('RGB', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(ink)
    data = values(pcm)
    for channel, color in enumerate(PALETTE[:2]):
        points=[]
        center = 145 + channel*92
        for i in range(560):
            value = data[(i*SAMPLES//560)*2+channel]
            points.append((40+i, center-value*62//32768))
        draw.line(points, fill=color, width=2)
    return glow(ink)


def render(pcm, style='bars', index=0):
    """640x360 RGB24. Frame n uses samples [1600n,1600(n+1)) and index n."""
    if style not in STYLES or index < 0:
        raise ValueError('Unknown visualizer style or negative frame index')
    if style == 'qutrit-galaxy':
        return galaxy(pcm,index).tobytes()
    if style == 'gluball-knot':
        return knot(pcm,index).tobytes()
    if style == 'scope':
        return scope(pcm).tobytes()
    frame = bytearray(bytes(BACKGROUND) * (WIDTH * HEIGHT))
    for y in (60, 120, 240, 300):
        rectangle(frame, 40, y, 560, 1, (21, 32, 42))
    for i, value in enumerate(peaks(pcm)):
        half = 3 + value * 116 // 32768
        rectangle(frame, 40+i*7, HEIGHT//2-half, 5, half*2, FOREGROUND)
    return bytes(frame)


def reference_thumbnail(pcm, style='bars', index=0):
    frame = render(pcm, style, index)
    return bytes(frame[(y*WIDTH+x)*3+c] for y in range(2,HEIGHT,4)
                 for x in range(2,WIDTH,4) for c in range(3))


def check_thumbnail(actual, expected, header_rows=0):
    """Check every RGB thumbnail, excluding optional title and static legend.

    Lossy tolerance: 80% of bright geometry remains bright; no more than 2.5%
    of the visual region differs by >75 in any channel. Title has its own check
    and cannot make an absent visualization pass. Tiny motion below this sampling
    and tolerance is intentionally not certified.
    """
    if len(actual) != 160*90*3 or len(expected) != 160*90*3:
        raise ValueError('Incomplete decoded visualizer frame')
    region = [3*(y*160+x) for y in range(max(16,header_rows),77) for x in range(10,150)]
    foreground = [i for i in region if max(expected[i:i+3]) > 150]
    if not foreground or sum(max(actual[i:i+3]) > 110 for i in foreground) < len(foreground)*.8:
        raise ValueError('Visualizer is missing or incomplete in the encoded MP4')
    mismatch = sum(max(abs(actual[i+c]-expected[i+c]) for c in range(3)) > 75 for i in region)
    if mismatch > len(region)*.025:
        raise ValueError('Encoded MP4 does not match the audio-driven visualizer')
