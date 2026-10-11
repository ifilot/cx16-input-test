"""Turn the procedural art into VERA tiles, maps, a palette and C lookup tables.

The screen is 640x480 in 4bpp tile mode. Rows 0-29 (devices, panel) live on layer 0,
rows 30-59 (keyboard) on layer 1. Layer 1 also carries the text overlay and the
"not connected" veil in its upper half.

Highlighting works by palette swapping: for every input ("region") the screen is
rendered with only that input pressed and diffed against the idle screen. Every tile
touched by a region gets a palette row per state; pressing an input only rewrites the
palette nibble of its map entries. A tile may be touched by at most two regions.

Usage: build_assets.py <outdir> <gendir>
"""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

import art

ART_INDICES = 14          # palette indices 1..14 hold art; 15 is the text colour
TEXT_COLOURS = {'WHITE': 'fff', 'DIM': '9bd', 'TITLE': 'ff6', 'CYAN': '5de'}
L0_MAP, L1_MAP = 0x0000, 0x4000
MAP_STRIDE = 256          # 128 entries of 2 bytes
SPLIT_ROW = 30            # first tile row drawn by layer 1
FONT_TILES = 128          # layer 1 tiles 0..127: tile n is ASCII character n
PAD_BITS = ['B', 'Y', 'SELECT', 'START', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'A', 'X', 'L', 'R']
MOUSE_REGIONS = ['LMB', 'RMB', 'MMB', 'WUP', 'WDN']

KEYNUM = {'ESC': 110, 'RESTORE': 124, '40/80': 125, 'RUN': 126, 'DEL': 76, '`': 1, '-': 12, '=': 13,
          'BACKSPACE': 15, 'HOME': 80, 'TAB': 16, '[': 27, ']': 28, '\\': 29, 'PGUP': 85, 'CAPS': 30,
          ';': 40, "'": 41, 'RETURN': 43, 'PGDN': 86, 'LSHIFT': 44, ',': 53, '.': 54, '/': 55,
          'RSHIFT': 57, 'UP': 83, 'END': 81, 'LCTRL': 58, 'LOGO': 59, 'LALT': 60, 'SPACE': 61,
          'RALT': 62, 'MENU': 65, 'RCTRL': 64, 'INST': 75, 'LEFT': 79, 'DOWN': 84, 'RIGHT': 89}
KEYNUM.update({f'F{i}': 111 + i for i in range(1, 13)})
KEYNUM.update({str(d): 2 + (d - 1) % 10 for d in range(10)})
KEYNUM.update({c: n for c, n in zip('QWERTYUIOP', range(17, 27))})
KEYNUM.update({c: n for c, n in zip('ASDFGHJKL', range(31, 40))})
KEYNUM.update({c: n for c, n in zip('ZXCVBNM', range(46, 53))})

# short names for the event log, by keynum (also covers keys a PC keyboard may add)
LOG_NAMES = {110: 'ESC', 124: 'RESTORE', 125: '40/80', 126: 'RUNSTOP', 76: 'DEL', 1: '`', 12: '-',
             13: '=', 15: 'BKSP', 80: 'HOME', 16: 'TAB', 27: '[', 28: ']', 29: 'POUND', 85: 'PGUP',
             30: 'CAPS', 40: ';', 41: "'", 43: 'RETURN', 86: 'PGDN', 44: 'LSHIFT', 53: ',', 54: '.',
             55: '/', 57: 'RSHIFT', 83: 'UP', 81: 'END', 58: 'LCTRL', 59: 'LOGO', 60: 'LALT',
             61: 'SPACE', 62: 'RALT', 65: 'MENU', 64: 'RCTRL', 75: 'INST', 79: 'LEFT', 84: 'DOWN',
             89: 'RIGHT', 45: 'NUSBSL', 56: 'INTL', 63: 'RLOGO', 90: 'NUMLK', 108: 'KPENT',
             95: 'KP/', 100: 'KP*', 105: 'KP-', 106: 'KP+', 104: 'KP.', 99: 'KP0'}
LOG_NAMES.update({111 + i: f'F{i}' for i in range(1, 13)})
LOG_NAMES.update({n: c for c, n in KEYNUM.items() if len(c) == 1 and c.isalnum()})
LOG_NAMES.update({93: 'KP1', 98: 'KP2', 103: 'KP3', 92: 'KP4', 97: 'KP5', 102: 'KP6', 91: 'KP7',
                  96: 'KP8', 101: 'KP9'})

# "pressed" is one global recolouring: every idle colour lights up to exactly one colour,
# so all interactive tiles share (idle, lit) pairs and fit in few palette rows
LIT = {'000': '000', '111': '111', '112': '112',
       '222': '057', '333': '057', '444': '079', '555': '09b', '666': '2bd', '777': '5de', '888': '9ef',
       '999': '057', 'aaa': '079', 'bbb': '09b', 'ccc': '2bd', 'ddd': '2bd', 'eee': '5de', 'fff': '5de',
       '556': '057', '2bd': '057', '09b': '057', '57a': '5de'}
for _ramp in ('red', 'yellow', 'blue', 'green'):
    _r = art.BASE_RAMPS[_ramp] + ['fff', 'fff']
    LIT.update({c: _r[i + 2] for i, c in enumerate(art.BASE_RAMPS[_ramp])})
LIT = {int(k, 16): int(v, 16) for k, v in LIT.items()}

C_NAMES = {'`': 'GRAVE', '-': 'MINUS', '=': 'EQUAL', '[': 'LBRACKET', ']': 'RBRACKET', '\\': 'POUND',
           ';': 'SEMICOLON', "'": 'QUOTE', ',': 'COMMA', '.': 'PERIOD', '/': 'SLASH', '40/80': '4080'}


def c12(img):
    """RGB888 image -> 12-bit colour ints."""
    a = img.astype(np.int32) // 17
    return (a[..., 0] << 8) | (a[..., 1] << 4) | a[..., 2]


def hex12(h):
    return int(h, 16)


# ---------------------------------------------------------------- rendering
def render_regions():
    st = art.STYLE
    idle = art.scene(st).a.copy()

    def variant(draw):
        cv = art.Canvas()
        cv.a = idle.copy()
        draw(cv)
        return cv.a

    regions = []                       # (c_name, image with only this region pressed)
    keys = [(label, cell) for label, *cell in art.keyboard_cells() if label in KEYNUM]
    every = variant(lambda cv: art.keyboard(cv, st, pressed={label for label, _ in keys}))
    for label, (_, _, x0, y0, x1, y1) in keys:
        img = idle.copy()
        img[y0:y1, x0:x1] = every[y0:y1, x0:x1]
        regions.append(('KEY_' + C_NAMES.get(label, label), img))
    leds = variant(lambda cv: art.keyboard(cv, st, leds={n for n, _ in art.LED_ICONS}))
    for name, _, x0, y0, x1, y1 in art.led_boxes():
        img = idle.copy()
        img[y0 - 1:y1 + 1, x0 - 1:x1 + 1] = leds[y0 - 1:y1 + 1, x0 - 1:x1 + 1]
        regions.append((name, img))
    for b in MOUSE_REGIONS:
        regions.append(('MOUSE_' + b, variant(lambda cv: art.mouse(cv, st, *art.MOUSE_ORIGIN, {b}))))
    for port in (1, 2):
        for b in PAD_BITS:
            regions.append((f'P{port}_{b}',
                            variant(lambda cv: art.snes_pad(cv, st, *art.PAD_ORIGIN[port], port, {b}))))
    # the veil for an absent pad: every pad pixel (incl. shadow) on a checkerboard
    bg = art.Canvas()
    art.background(bg, st)
    pad_masks = {}
    for port, (ox, oy) in art.PAD_ORIGIN.items():
        m = np.zeros((art.H, art.W), bool)
        m[oy - 8:oy + 120, ox - 4:ox + 248] = True
        pad_masks[port] = m & np.any(idle != bg.a, axis=2) & art.CHECK
    return idle, regions, keys, pad_masks


# ---------------------------------------------------------------- palette packing
class Family:
    """Consecutive palette rows sharing index assignments; each index holds a tuple of k colours."""

    def __init__(self, k):
        self.k = k
        self.tuples = []
        self.lookup = {}

    def missing(self, sigs):
        return [s for s in sigs if s not in self.lookup]

    def add(self, sigs):
        for s in sigs:
            if s not in self.lookup:
                self.lookup[s] = len(self.tuples) + 1
                self.tuples.append(s)
        assert len(self.tuples) <= ART_INDICES


def embed(sigs, k, slot):
    """Express a 1-region tile's (idle, pressed) pairs inside a 4-row family."""
    if k == 2:
        return set(sigs)
    if slot == 0:
        return {(i, p, i, p) for i, p in sigs}
    return {(i, i, p, p) for i, p in sigs}


def pack(items):
    """items: list of dicts with 'n' (regions) and 'sigs' (set of tuples, len 2**n; 1-tuples for static)."""
    fams = []

    def best(cands):
        cands = [c for c in cands if len(c[0].tuples) + c[1] <= ART_INDICES]
        return min(cands, key=lambda c: (c[1], c[0].k)) if cands else None

    for it in sorted([i for i in items if i['n'] == 2], key=lambda i: -len(i['sigs'])):
        choice = best([(f, len(f.missing(it['sigs']))) for f in fams if f.k == 4])
        if not choice:
            fams.append(Family(4))
            choice = (fams[-1], 0)
        choice[0].add(it['sigs'])
        it['fam'], it['slot'] = choice[0], None
    for it in sorted([i for i in items if i['n'] == 1], key=lambda i: -len(i['sigs'])):
        cands = []
        for f in fams:
            for slot in ((0, 1) if f.k == 4 else (None,)):
                if f.k in (2, 4):
                    sig = embed(it['sigs'], f.k, slot)
                    cands.append((f, len(f.missing(sig)), slot))
        choice = best(cands)
        if not choice:
            fams.append(Family(2))
            choice = (fams[-1], 0, None)
        f, _, slot = choice
        f.add(embed(it['sigs'], f.k, slot))
        it['fam'], it['slot'] = f, slot
    for it in sorted([i for i in items if i['n'] == 0], key=lambda i: -len(i['sigs'])):
        cols = {s[0] for s in it['sigs']}
        cands = []
        for f in fams:
            for r in range(f.k):
                have = {t[r] for t in f.tuples}
                cands.append((f, len(cols - have), r))
        choice = best(cands)
        if not choice:
            fams.append(Family(1))
            choice = (fams[-1], len(cols), 0)
        f, _, r = choice
        have = {t[r] for t in f.tuples}
        f.add([(c,) * f.k for c in sorted(cols - have)])
        it['fam'], it['row'] = f, r
    base = 0
    for f in fams:
        f.base = base
        base += f.k
    return fams, base


def static_index(fam, row, colour):
    for i, t in enumerate(fam.tuples):
        if t[row] == colour:
            return i + 1
    raise KeyError(colour)


# ---------------------------------------------------------------- analysis
class Analysis:
    """Idle screen plus, per region, the pixels it changes and their pressed colours."""

    def __init__(self):
        self.idle, self.regions, self.keys, self.pad_masks = render_regions()
        self.names = [n for n, _ in self.regions]
        self.base = c12(self.idle)
        self.diffs = []                           # (mask, LIT-recoloured, art-rendered)
        for name, img in self.regions:
            mask = np.any(img != self.idle, axis=2)
            lit = self.base.copy()
            lit[mask] = [LIT.get(c, c) for c in self.base[mask]]
            self.diffs.append((mask, lit, c12(img)))
        self.tile_regions = defaultdict(list)
        for r, (mask, _, _) in enumerate(self.diffs):
            assert mask.any(), f'region {self.names[r]} changes nothing'
            for ty, tx in {(y // 8, x // 8) for y, x in zip(*np.nonzero(mask))}:
                self.tile_regions[(ty, tx)].append(r)

    def pal_mode(self, ty, regs):
        """Keyboard keys swap palette rows (pressed = global LIT recolouring); everything
        else swaps whole pre-rendered tiles and can use the art's own pressed look."""
        return len(regs) == 1 and ty >= SPLIT_ROW and self.names[regs[0]].startswith('KEY_')

    def tile_state(self, ty, tx, pressed):
        """12-bit colours of one tile with the given set of region indices pressed."""
        regs = self.tile_regions.get((ty, tx), [])
        sl = np.s_[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]
        img = self.base[sl].copy()
        version = 1 if self.pal_mode(ty, regs) else 2
        for r in regs:
            if r in pressed:
                m = self.diffs[r][0][sl]
                img[m] = self.diffs[r][version][sl][m]
        return img

    def reference(self, pressed=()):
        """The whole screen (without text/cursor) as the program should show it."""
        out = self.base.copy()
        for ty, tx in self.tile_regions:
            out[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] = self.tile_state(ty, tx, set(pressed))
        return out


# ---------------------------------------------------------------- main build
def build(outdir, gendir):
    an = Analysis()
    regions, keys, pad_masks, tile_regions = an.regions, an.keys, an.pad_masks, an.tile_regions

    # tile items for the art
    items = {}
    for ty in range(60):
        for tx in range(80):
            regs = tile_regions.get((ty, tx), [])
            assert len(regs) <= 2, f'tile {tx},{ty} touched by {[regions[r][0] for r in regs]}'
            pal_mode = an.pal_mode(ty, regs)
            states = [an.tile_state(ty, tx, {r for bit, r in enumerate(regs) if s >> bit & 1})
                      for s in range(1 << len(regs))]
            if len(regs) == 2:
                overlap = an.diffs[regs[0]][0] & an.diffs[regs[1]][0]
                assert not overlap[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].any(), f'regions overlap in tile {tx},{ty}'
            sig = np.stack(states, -1).reshape(64, -1)
            it = dict(n=len(regs), regs=regs, pix=[tuple(p) for p in sig], sigs={tuple(p) for p in sig})
            if regs and not pal_mode:
                it['subs'] = [dict(n=0, pix=[(c,) for c in st.flatten()], sigs={(c,) for c in st.flatten()})
                              for st in states]
            items[(ty, tx)] = it
    extras = {'veil': dict(n=0, sigs={(hex12(art.STYLE.bg[0]),)}),
              'cursor': dict(n=0, sigs={(hex12(c),) for c in art.CURSOR_COLOURS.values()})}
    packable = [s for it in items.values() for s in it.get('subs', [it])]
    fams, rows = pack(packable + list(extras.values()))
    print(f'palette rows used: {rows} of 16 ({len(fams)} families: '
          f'{[f.k for f in fams]})', file=sys.stderr)
    assert rows <= 16, 'palette rows exhausted'

    # palette
    pal = np.zeros((16, 16), np.int32)
    for f in fams:
        for i, t in enumerate(f.tuples):
            for r in range(f.k):
                pal[f.base + r, i + 1] = t[r]
    for r, h in enumerate(TEXT_COLOURS.values()):
        pal[r, 15] = hex12(h)
    pal[0, 0] = hex12(art.STYLE.bg[0])
    pal_bytes = bytearray()
    for v in pal.flatten():
        pal_bytes += bytes([v & 0xFF, v >> 8])

    # tiles and maps
    font_list = []                                # layer 1 tile n is ASCII character n
    for ch in range(FONT_TILES):
        g = art.FONT_ISO[ch] if ch >= 32 else bytes(8)
        data = bytearray()
        for y in range(8):
            for x in range(0, 8, 2):
                hi = 15 if g[y] & (0x80 >> x) else 0
                lo = 15 if g[y] & (0x80 >> (x + 1)) else 0
                data.append(hi << 4 | lo)
        font_list.append(bytes(data))
    tilesets = {0: {bytes(32): 0}, 1: {}}
    for i, data in enumerate(font_list):
        tilesets[1].setdefault(data, i)

    def tile_bytes(indices):
        data = bytearray()
        for y in range(8):
            for x in range(0, 8, 2):
                data.append(indices[y * 8 + x] << 4 | indices[y * 8 + x + 1])
        return bytes(data)

    order = {0: [bytes(32)], 1: font_list}

    def intern(layer, data):
        ts = tilesets[layer]
        if data not in ts:
            ts[data] = len(order[layer])
            order[layer].append(data)
        return ts[data]

    maps = {0: np.zeros((64, 128), np.int32), 1: np.zeros((64, 128), np.int32)}
    rtiles = defaultdict(list)                    # region -> [(map address, released, pressed)]
    shared = []                                   # (map address, region a, region b, [entry per state])
    def static_tile(layer, sub):
        f, r = sub['fam'], sub['row']
        tile = intern(layer, tile_bytes([static_index(f, r, p[0]) for p in sub['pix']]))
        return tile | (f.base + r) << 12

    for (ty, tx), it in items.items():
        layer = 0 if ty < SPLIT_ROW else 1
        if 'subs' in it:                          # one pre-rendered tile per state
            words = [static_tile(layer, s) for s in it['subs']]
        elif it['n'] == 0:
            words = [static_tile(layer, it)]
        else:                                     # one tile, palette row per state
            f = it['fam']
            pix = [embed({p}, f.k, it['slot']).pop() for p in it['pix']]
            tile = intern(layer, tile_bytes([f.lookup[p] for p in pix]))
            rows_by_state = [f.base, f.base + (1 if f.k == 2 or it['slot'] == 0 else 2)]
            words = [tile | row << 12 for row in rows_by_state]
        maps[layer][ty, tx] = words[0]
        if it['n']:
            addr = (L0_MAP if layer == 0 else L1_MAP) + ty * MAP_STRIDE + tx * 2
            if it['n'] == 1:
                rtiles[it['regs'][0]].append((addr, words[0], words[1]))
            else:
                shared.append((addr, *it['regs'], words))

    # veil tiles (layer 1, top half) and cursor sprite
    vf, vr = extras['veil']['fam'], extras['veil']['row']
    vidx = static_index(vf, vr, hex12(art.STYLE.bg[0]))
    veils = {}
    for port, m in pad_masks.items():
        entries = []
        for ty, tx in sorted({(y // 8, x // 8) for y, x in zip(*np.nonzero(m))}):
            sub = m[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].flatten()
            tile = intern(1, tile_bytes([vidx if v else 0 for v in sub]))
            entries.append((L1_MAP + ty * MAP_STRIDE + tx * 2, tile & 0xFF, (vf.base + vr) << 4 | tile >> 8))
        veils[port] = entries
    cf, cr = extras['cursor']['fam'], extras['cursor']['row']
    cursor = bytearray()
    for y in range(16):
        row = (art.CURSOR[y] + '.' * 16)[:16]
        for x in range(0, 16, 2):
            v = [static_index(cf, cr, hex12(art.CURSOR_COLOURS[c])) if c in art.CURSOR_COLOURS else 0
                 for c in row[x:x + 2]]
            cursor.append(v[0] << 4 | v[1])
    for layer in (0, 1):
        print(f'layer {layer}: {len(order[layer])} tiles', file=sys.stderr)
        assert len(order[layer]) <= 1024, 'too many tiles'
    print(f'interactive tiles: {sum(map(len, rtiles.values()))} + {len(shared)} shared', file=sys.stderr)

    # binaries
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / 'PALETTE.BIN').write_bytes(pal_bytes)
    (outdir / 'CURSOR.BIN').write_bytes(bytes(cursor))
    for layer in (0, 1):
        (outdir / f'L{layer}TILES.BIN').write_bytes(b''.join(order[layer]))
        m = maps[layer][:60].flatten()
        (outdir / f'L{layer}MAP.BIN').write_bytes(b''.join(int(v).to_bytes(2, 'little') for v in m))

    sizes = {f.stem: f.stat().st_size for f in outdir.glob('*.BIN')}
    write_c(gendir, regions, rtiles, shared, veils, (cf.base + cr), keys, sizes)


def write_c(gendir, regions, rtiles, shared, veils, cursor_row, keys, sizes):
    gendir.mkdir(parents=True, exist_ok=True)
    names = [n for n, _ in regions]
    keynum_region = [0xFF] * 128
    for label, _ in keys:
        keynum_region[KEYNUM[label]] = names.index('KEY_' + C_NAMES.get(label, label))
    first, flat = [0], []
    for r in range(len(names)):
        flat += rtiles[r]
        first.append(len(flat))
    assert len(veils[1]) == len(veils[2])
    h = ['/* Generated by tools/build_assets.py - do not edit. */', '#ifndef ASSETS_H', '#define ASSETS_H', '',
         '#include <stdint.h>', '',
         f'#define NUM_REGIONS {len(names)}', f'#define NUM_RTILES {len(flat)}', f'#define NUM_SHARED {len(shared)}',
         f'#define NUM_VEIL {len(veils[1])}', f'#define CURSOR_ROW {cursor_row}',
         f'#define MAP_L0 0x{L0_MAP:04X}', f'#define MAP_L1 0x{L1_MAP:04X}', f'#define MAP_STRIDE {MAP_STRIDE}',
         f'#define REGION_NONE 0xFF', '']
    h += [f'#define SIZE_{k} {v}u' for k, v in sorted(sizes.items())] + ['']
    for i, k in enumerate(TEXT_COLOURS):
        h.append(f'#define COL_{k} {i}')
    h += ['', 'enum region {'] + [f'    R_{n},' for n in names] + ['};', '',
          '#define R_PAD_FIRST(port) ((port) == 1 ? R_P1_B : R_P2_B)', '',
          '/* a map entry owned by one region: its released and pressed values */',
          'struct rtile { uint16_t addr; uint16_t off; uint16_t on; };',
          '/* a map entry shared by regions a and b: entry[a pressed | b pressed << 1] */',
          'struct stile { uint16_t addr; uint8_t a; uint8_t b; uint16_t entry[4]; };',
          '/* a veil entry drawn over an absent controller */',
          'struct vtile { uint16_t addr; uint16_t entry; };', '',
          'extern const struct rtile rtiles[NUM_RTILES];',
          'extern const uint16_t region_first[NUM_REGIONS + 1];',
          'extern const struct stile shared[NUM_SHARED];',
          'extern const struct vtile veil[2][NUM_VEIL];',
          'extern const uint8_t keynum_region[128];',
          'extern const char * const keynum_name[128];', '', '#endif', '']
    (gendir / 'assets.h').write_text('\n'.join(h))

    def arr(vals, fmt='{}', per=12):
        vals = [fmt.format(v) for v in vals]
        return ',\n'.join('    ' + ', '.join(vals[i:i + per]) for i in range(0, len(vals), per))

    def structs(rows):
        return ',\n'.join('    {' + ', '.join(rows_) + '}' for rows_ in rows)

    hx = '0x{:04X}'.format
    c = ['/* Generated by tools/build_assets.py - do not edit. */', '#include <ascii_charmap.h>',
         '#include "assets.h"', '',
         'const struct rtile rtiles[NUM_RTILES] = {', structs([[hx(a), hx(o), hx(n)] for a, o, n in flat]), '};', '',
         'const uint16_t region_first[NUM_REGIONS + 1] = {', arr(first), '};', '',
         'const struct stile shared[NUM_SHARED] = {',
         structs([[hx(a), str(ra), str(rb), '{' + ', '.join(map(hx, w)) + '}'] for a, ra, rb, w in shared]), '};', '',
         'const struct vtile veil[2][NUM_VEIL] = {',
         ',\n'.join('  {\n' + structs([[hx(a), hx(b0 | b1 << 8)] for a, b0, b1 in veils[p]]) + '\n  }'
                     for p in (1, 2)), '};', '',
         'const uint8_t keynum_region[128] = {', arr(keynum_region, '0x{:02X}', 16), '};', '',
         'const char * const keynum_name[128] = {',
         arr([('"' + LOG_NAMES[k].replace('\\', '\\\\').replace('"', '\\"') + '"') if k in LOG_NAMES else '0'
              for k in range(128)], per=8), '};', '']
    (gendir / 'assets.c').write_text('\n'.join(c))


if __name__ == '__main__':
    build(Path(sys.argv[1]), Path(sys.argv[2]))
