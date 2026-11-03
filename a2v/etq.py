# SPDX-License-Identifier: MPL-2.0
# Copyright 2026 Trent Slade / QSOL-IMC.
"""ETQ finite model ported from QSOLKCB/VIZ; authored local graph-walk receiver.

Donor: VIZ/js/etq-core.js at 90a3ab3e72d7f46f3e8e99b1dbd5a68182f4c363.
The model retains the donor's exact selector and graph. The edge walk, quantized
projection, raster and audio mapping are new receiver choices. See docs/etq.md.
This Source Code Form is subject to the Mozilla Public License, v. 2.0.
A copy is provided in LICENSES/MPL-2.0.txt, or https://mozilla.org/MPL/2.0/.
"""
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, product

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .process import RenderError

TRIALITY = ((1,1,1,1), (1,1,-1,-1), (1,-1,1,-1), (-1,1,1,-1))
# Q14 quantization of VIZ's authored golden orthonormal frame. No runtime trig.
PROJECTION = ((12883,7962,4921,3041,1880,1162,718,444),
              (771,-2536,3307,-3981,5426,-5684,9248,-9346),
              (-3674,-731,2455,3641,6521,6497,9180,8131))
FRAMES_PER_EDGE = 8
TRAIL_EDGES = 18
WIDTH, HEIGHT = 640, 360


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def roots_doubled():
    roots = []
    for i,j in combinations(range(8),2):
        for a,b in product((-2,2), repeat=2):
            root = [0]*8
            root[i],root[j] = a,b
            roots.append(tuple(root))
    for signs in product((-1,1), repeat=8):
        if signs.count(-1) % 2 == 0:
            roots.append(signs)
    return tuple(sorted(roots))


def triality(root):
    result = []
    for offset in (0,4):
        for row in TRIALITY:
            numerator = dot(row, root[offset:offset+4])
            if numerator % 2:
                raise ValueError('ETQ triality left the doubled-integer lattice')
            result.append(numerator//2)
    return tuple(result)


@dataclass(frozen=True)
class Model:
    selected: tuple
    edges: tuple
    degrees: tuple
    lifted_edges: tuple
    neighbors: tuple
    walk: tuple


def edge_walk(neighbors):
    """Closed DFS walk with a fixed neighbor ranking; every move is an edge.

    This visits all vertices, including backtracking. It is not the donor's
    303-step CRT event orbit, which is not generally an adjacency walk.
    """
    ordered = tuple(tuple(sorted(row, key=lambda v: ((u*1103+v*1999+u*v*83)%65521,v)))
                    for u,row in enumerate(neighbors))
    seen, route, stack = {0}, [0], [(0,iter(ordered[0]))]
    while stack:
        node, candidates = stack[-1]
        target = next((v for v in candidates if v not in seen), None)
        if target is None:
            stack.pop()
            if stack:
                route.append(stack[-1][0])
        else:
            seen.add(target)
            route.append(target)
            stack.append((target,iter(ordered[target])))
    if len(seen) != len(neighbors) or route[-1] != route[0]:
        raise RenderError('ETQ graph walk is not connected and closed')
    return tuple(route[:-1])


@lru_cache(maxsize=1)
def model():
    roots = roots_doubled()
    root_set = set(roots)
    seen, fixed, cycles = set(), [], []
    for root in roots:
        if root in seen:
            continue
        once, twice = triality(root), triality(triality(root))
        if once not in root_set or twice not in root_set or triality(twice) != root:
            raise RenderError('ETQ triality invariant failed')
        if once == root:
            fixed.append(root)
            seen.add(root)
        else:
            orbit = (root,once,twice)
            representative = min(orbit)
            cycles.append((representative,triality(representative),triality(triality(representative))))
            seen.update(orbit)
    fixed.sort()
    cycles.sort(key=lambda orbit:orbit[0])
    selected = tuple(fixed[:2]) + tuple(root for orbit in cycles[:33] for root in orbit)
    edges = tuple((a,b) for a,b in combinations(range(101),2) if dot(selected[a],selected[b]) == 4)
    degrees = tuple(sum(a==i or b==i for a,b in edges) for i in range(101))
    lifted = tuple((3*a+f,3*b+f) for f in range(3) for a,b in edges)
    lifted += tuple((3*i+a,3*i+b) for i in range(101) for a,b in ((0,1),(1,2),(2,0)))
    rows = [set() for _ in range(303)]
    for a,b in lifted:
        rows[a].add(b)
        rows[b].add(a)
    neighbors = tuple(tuple(sorted(row)) for row in rows)
    if (len(roots),len(fixed),len(cycles),len(selected),len(edges),sum(degrees),
        min(degrees),max(degrees),len(lifted)) != (240,12,76,101,1687,3374,22,55,5364):
        raise RenderError('ETQ finite graph fixtures failed')
    walk = edge_walk(neighbors)
    if len(walk) != 604 or any(b not in neighbors[a] for a,b in zip(walk,walk[1:]+walk[:1])):
        raise RenderError('ETQ walk failed its edge invariant')
    return Model(selected,edges,degrees,lifted,neighbors,walk)


@lru_cache(maxsize=1)
def screen_points():
    """Fixed Q14 view (yaw -.62, pitch .46, quarter-turn roll), title-safe."""
    raw = []
    for root in model().selected:
        x,y,z = (dot(root,axis) for axis in PROJECTION)
        yaw_x = (x*13335-z*9520)//16384
        yaw_z = (x*9520+z*13335)//16384
        pitch_y = (y*14681-yaw_z*7274)//16384
        depth = (y*7274+yaw_z*14681)//16384
        raw.append((-pitch_y,-yaw_x,depth))
    lo_x,hi_x = min(p[0] for p in raw),max(p[0] for p in raw)
    lo_y,hi_y = min(p[1] for p in raw),max(p[1] for p in raw)
    extent = max((hi_x-lo_x)*208,(hi_y-lo_y)*440)
    points = []
    # Independent external-fibre offsets make 303 tensor states over 101 labels.
    for x,y,z in raw:
        x = 320+(2*x-lo_x-hi_x)*440*208//(2*extent)
        y = 187+(2*y-lo_y-hi_y)*440*208//(2*extent)
        for dx,dy in ((0,-6),(5,3),(-5,3)):
            points.append((x+dx,y+dy,z))
    return tuple(points)


@lru_cache(maxsize=1)
def graph_background():
    """Immutable RGB cache: all 5,364 edges, finite size independent of track."""
    image = Image.new('RGB',(WIDTH,HEIGHT),(12,18,25))
    draw = ImageDraw.Draw(image)
    points = screen_points()
    for a,b in model().lifted_edges:
        color = (31,43,54) if a//3 != b//3 else (53,57,68)
        draw.line((points[a][:2],points[b][:2]), fill=color, width=1)
    for x,y,_ in points:
        draw.ellipse((x-1,y-1,x+1,y+1),fill=(74,85,99))
    return image.tobytes()


def render_graph(weights, volume, index, palette):
    """Three phase-offset walkers; audio changes light, never graph topology."""
    graph, points = model(), screen_points()
    route = graph.walk
    ink = Image.new('RGB',(WIDTH,HEIGHT))
    draw = ImageDraw.Draw(ink)
    period = len(route)*FRAMES_PER_EDGE
    tick = index % period
    # Cold random access reconstructs a bounded trail without replaying history.
    for walker in range(3):
        step,fraction = divmod(tick+walker*(period//3),FRAMES_PER_EDGE)
        for age in range(TRAIL_EDGES,0,-1):
            a,b = route[(step-age)%len(route)],route[(step-age+1)%len(route)]
            fibre = b%3
            level = 60+(TRAIL_EDGES-age)*130//TRAIL_EDGES + weights[fibre]*45//1000000 + volume*35//32768
            color = tuple(min(255,c*level//210) for c in palette[fibre])
            draw.line((points[a][:2],points[b][:2]),fill=color,width=2)
        a,b = route[step%len(route)],route[(step+1)%len(route)]
        x = (points[a][0]*(FRAMES_PER_EDGE-fraction)+points[b][0]*fraction)//FRAMES_PER_EDGE
        y = (points[a][1]*(FRAMES_PER_EDGE-fraction)+points[b][1]*fraction)//FRAMES_PER_EDGE
        color = palette[b%3]
        draw.line((points[a][:2],(x,y)), fill=color, width=3)
        radius = 3+volume*3//32768
        draw.ellipse((x-radius-3,y-radius-3,x+radius+3,y+radius+3),outline=color,width=1)
        draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(236,245,255))
        # Neighbourhood illumination makes the current graph connection legible.
        for neighbor in graph.neighbors[b]:
            nx,ny,_ = points[neighbor]
            glow_color = tuple(c*(40+weights[neighbor%3]*90//1000000)//255 for c in palette[neighbor%3])
            draw.point((nx,ny),fill=glow_color)
    base = Image.frombytes('RGB',(WIDTH,HEIGHT),graph_background())
    haze = ink.filter(ImageFilter.GaussianBlur(3))
    return ImageChops.add(ImageChops.add(base,haze),ink)


def check_walkers(actual, expected):
    """Require moving white packet cores, independently of the static graph.

    A dense backdrop and overlapping trails can satisfy the generic 2.5% image
    tolerance even when packets freeze. Check the expected bright, neutral cores
    at every sampled frame: at least 80% must still be bright and neutral.
    """
    if len(actual) != 160*90*3 or len(expected) != 160*90*3:
        raise ValueError('Incomplete decoded ETQ visualizer frame')
    def mask(raw, threshold):
        image = Image.frombytes('RGB',(160,90),raw).crop((10,16,150,77))
        r,g,b = image.split()
        neutral = ImageChops.darker(ImageChops.darker(r,g),b)
        return neutral.point([0]*(threshold+1)+[255]*(255-threshold))
    wanted = mask(expected,210)
    found = mask(actual,175)
    total = wanted.histogram()[255]
    matched = ImageChops.multiply(wanted,found).histogram()[255]
    if not total or matched*5 < total*4:
        raise ValueError('ETQ visualizer walk is missing, frozen or misplaced in the encoded MP4')
