#!/usr/bin/env python3
"""Generate icon.png (512x512 hub-and-spokes) and fanart.png (1280x720 gradient)
for the addon without needing PIL. Pure stdlib."""

import math
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(HERE, '..', 'plugin.video.jacobshub')

BG_TOP = (16, 20, 33)
BG_BOT = (30, 39, 64)
ACCENT = (86, 156, 214)     # spoke blue
ACCENT2 = (243, 178, 71)    # hub amber
NODE = (220, 226, 235)


def png_write(path, width, height, rows):
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b''.join(b'\x00' + bytes(row) for row in rows)
    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(raw, 9))
    out += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(out)
    print('wrote %s (%dx%d)' % (path, width, height))


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def dist_to_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def make_icon(path, size=512):
    cx = cy = size / 2.0
    hub_r = size * 0.11
    node_r = size * 0.055
    spoke_w = size * 0.018
    orbit = size * 0.32
    nodes = [(cx + orbit * math.cos(math.radians(a - 90)),
              cy + orbit * math.sin(math.radians(a - 90)))
             for a in range(0, 360, 60)]

    rows = []
    for y in range(size):
        row = []
        base = lerp(BG_TOP, BG_BOT, y / size)
        for x in range(size):
            c = base
            # rounded-square vignette edge
            d_spoke = min(dist_to_segment(x, y, cx, cy, nx, ny) for nx, ny in nodes)
            if d_spoke < spoke_w:
                c = ACCENT
            for nx, ny in nodes:
                if math.hypot(x - nx, y - ny) < node_r:
                    c = NODE
            d_hub = math.hypot(x - cx, y - cy)
            if d_hub < hub_r:
                c = ACCENT2
            elif d_hub < hub_r + spoke_w * 0.9:
                c = lerp(ACCENT2, base, 0.45)
            row.extend(c)
        rows.append(row)
    png_write(path, size, size, rows)


def make_fanart(path, w=1280, h=720):
    # playful multi-color "spotlight" bands over the dark gradient
    bands = [((243, 178, 71), 0.30), ((86, 156, 214), 0.55), ((120, 200, 120), 0.80)]
    rows = []
    for y in range(h):
        row = []
        base = lerp(BG_TOP, BG_BOT, y / h)
        for x in range(w):
            c = base
            for color, cx in bands:
                d = abs((x - w * cx) - (y - h * 0.5) * 0.5)
                if d < w * 0.10:
                    c = lerp(color, c, min(1.0, d / (w * 0.10)))
            row.extend(c)
        rows.append(row)
    png_write(path, w, h, rows)


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else ADDON
    make_icon(os.path.join(target, 'icon.png'))
    make_fanart(os.path.join(target, 'fanart.png'))
