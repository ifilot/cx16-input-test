"""Decode the built VERA assets back into a 640x480 image (a tiny software VERA).

Used by tests to prove that the tiles, maps, palette and generated region tables
reproduce the art exactly, both idle and with inputs pressed.
"""
import re
from pathlib import Path

import numpy as np


def load(build):
    build = Path(build)
    pal = np.frombuffer((build / 'PALETTE.BIN').read_bytes(), np.uint8).reshape(256, 2)
    rgb = np.stack([(pal[:, 1] & 15), pal[:, 0] >> 4, pal[:, 0] & 15], -1) * 17
    tiles = {}
    maps = {}
    for layer in (0, 1):
        t = np.frombuffer((build / f'L{layer}TILES.BIN').read_bytes(), np.uint8).reshape(-1, 8, 4)
        px = np.empty((len(t), 8, 8), np.uint8)
        px[:, :, 0::2] = t >> 4
        px[:, :, 1::2] = t & 15
        tiles[layer] = px
        m = np.frombuffer((build / f'L{layer}MAP.BIN').read_bytes(), '<u2').reshape(60, 128).copy()
        maps[layer] = m
    return dict(rgb=rgb.astype(np.uint8), tiles=tiles, maps=maps)


def parse_tables(gen):
    """Read the region tables back out of the generated C source."""
    src = (Path(gen) / 'assets.c').read_text()

    def body(name):
        return re.search(name + r'\[[^]]*\](?:\[[^]]*\])? = \{(.*?)\n\};', src, re.S).group(1)

    def nums(text):
        return [int(v, 0) for v in re.findall(r'0x[0-9A-Fa-f]+|\d+', text)]
    rt = nums(body('rtiles'))
    sh = nums(body('shared'))
    vl = nums(body('veil'))
    return dict(rtiles=[tuple(rt[i:i + 3]) for i in range(0, len(rt), 3)],
                first=nums(body('region_first')),
                shared=[(sh[i], sh[i + 1], sh[i + 2], sh[i + 3:i + 7]) for i in range(0, len(sh), 7)],
                veil=[tuple(vl[i:i + 2]) for i in range(0, len(vl), 2)])


def set_entry(vera, addr, word):
    layer = 1 if addr >= 0x4000 else 0
    off = (addr - (0x4000 if layer else 0)) // 2
    vera['maps'][layer][off // 128, off % 128] = word


def press(vera, tables, regions):
    """Apply pressed regions to the maps the same way the program does."""
    regions = set(regions)
    for r in regions:
        for addr, _, on in tables['rtiles'][tables['first'][r]:tables['first'][r + 1]]:
            set_entry(vera, addr, on)
    for addr, a, b, entry in tables['shared']:
        set_entry(vera, addr, entry[(a in regions) | (b in regions) << 1])


def render(vera, text_layer_top=False):
    out = np.zeros((480, 640, 3), np.uint8)
    for layer in (0, 1):
        m = vera['maps'][layer]
        for ty in range(60):
            for tx in range(80):
                e = int(m[ty, tx])
                idx = vera['tiles'][layer][e & 0x3FF]
                if e & 0x400:
                    idx = idx[:, ::-1]
                if e & 0x800:
                    idx = idx[::-1]
                col = vera['rgb'][(e >> 12) * 16 + idx]
                block = out[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]
                opaque = idx != 0
                if layer == 0:
                    block[:] = np.where(opaque[..., None], col, vera['rgb'][0])
                else:
                    block[opaque] = col[opaque]
    return out
