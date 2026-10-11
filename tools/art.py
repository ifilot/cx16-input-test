"""Procedural pixel art for the CX16 input tester (640x480, style B "chunky pixel art").

Everything is drawn from masks, so the asset builder can render any combination of
pressed inputs and diff it against the idle screen. Colours are 12-bit VERA colours
('rgb' hex nibbles). Run directly to write a mockup to design/mockups/screen.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

W, H = 640, 480
ROOT = Path(__file__).resolve().parent
CHARSET = ROOT.parent / 'assets' / 'font' / 'x16-charset.bin'   # ROM bank 6: PETSCII, then ISO
YY, XX = np.mgrid[0:H, 0:W]


def C(h):
    if not isinstance(h, str):
        return tuple(h)
    return tuple(int(c, 16) * 17 for c in h)


# ---------------------------------------------------------------- fonts
_rom = CHARSET.read_bytes()
FONT_PET = [_rom[c * 8:c * 8 + 8] for c in range(256)]
FONT_ISO = [_rom[0x800 + c * 8:0x800 + c * 8 + 8] for c in range(256)]

TINY_ROWS = {
    'A': '.#. #.# ### #.# #.#', 'B': '##. #.# ##. #.# ##.', 'C': '.## #.. #.. #.. .##',
    'D': '##. #.# #.# #.# ##.', 'E': '### #.. ##. #.. ###', 'F': '### #.. ##. #.. #..',
    'G': '.## #.. #.# #.# .##', 'H': '#.# #.# ### #.# #.#', 'I': '### .#. .#. .#. ###',
    'J': '..# ..# ..# #.# .#.', 'K': '#.# #.# ##. #.# #.#', 'L': '#.. #.. #.. #.. ###',
    'M': '#.# ### ### #.# #.#', 'N': '##. #.# #.# #.# #.#', 'O': '.#. #.# #.# #.# .#.',
    'P': '##. #.# ##. #.. #..', 'Q': '.#. #.# #.# ##. .##', 'R': '##. #.# ##. #.# #.#',
    'S': '.## #.. .#. ..# ##.', 'T': '### .#. .#. .#. .#.', 'U': '#.# #.# #.# #.# ###',
    'V': '#.# #.# #.# #.# .#.', 'W': '#.# #.# ### ### #.#', 'X': '#.# #.# .#. #.# #.#',
    'Y': '#.# #.# .#. .#. .#.', 'Z': '### ..# .#. #.. ###',
    '0': '### #.# #.# #.# ###', '1': '.#. ##. .#. .#. ###', '2': '##. ..# .#. #.. ###',
    '3': '##. ..# .#. ..# ##.', '4': '#.# #.# ### ..# ..#', '5': '### #.. ##. ..# ##.',
    '6': '.## #.. ### #.# ###', '7': '### ..# .#. .#. .#.', '8': '### #.# ### #.# ###',
    '9': '### #.# ### ..# ##.', '/': '..# ..# .#. #.. #..', '.': '... ... ... ... .#.',
    '-': '... ... ### ... ...', '+': '... .#. ### .#. ...', ':': '... .#. ... .#. ...',
    ' ': '... ... ... ... ...',
}
TINY = {k: v.replace(' ', '') for k, v in TINY_ROWS.items()}
assert all(len(v) == 15 for v in TINY.values())


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self):
        self.a = np.zeros((H, W, 3), np.uint8)

    def fill(self, mask, col):
        self.a[mask] = C(col) if isinstance(col, str) else col

    def px(self, x, y, col):
        if 0 <= x < W and 0 <= y < H:
            self.a[y, x] = C(col)

    def glyph(self, x, y, rows, col, scale=1):
        for gy, bits in enumerate(rows):
            for gx in range(8):
                if bits & (0x80 >> gx):
                    for sy in range(scale):
                        for sx in range(scale):
                            self.px(x + gx * scale + sx, y + gy * scale + sy, col)

    def text(self, x, y, s, col, font='iso'):
        f = FONT_ISO if font == 'iso' else FONT_PET
        for i, ch in enumerate(s):
            self.glyph(x + i * 8, y, f[ord(ch) if font == 'iso' else ch], col)

    def tiny(self, x, y, s, col):
        for i, ch in enumerate(s.upper()):
            g = TINY.get(ch, TINY[' '])
            for j, b in enumerate(g):
                if b == '#':
                    self.px(x + i * 4 + j % 3, y + j // 3, col)

    def image(self):
        return Image.fromarray(self.a)


def tiny_width(s):
    return len(s) * 4 - 1


# ---------------------------------------------------------------- masks
def m_rect(x0, y0, x1, y1):
    return (XX >= x0) & (XX < x1) & (YY >= y0) & (YY < y1)


def m_circle(cx, cy, r):
    return (XX + 0.5 - cx) ** 2 + (YY + 0.5 - cy) ** 2 <= r * r


def m_ellipse(cx, cy, rx, ry):
    return ((XX + 0.5 - cx) / rx) ** 2 + ((YY + 0.5 - cy) / ry) ** 2 <= 1


def m_rrect(x0, y0, x1, y1, r):
    m = m_rect(x0, y0, x1, y1)
    if r <= 0:
        return m
    cx = np.clip(XX + 0.5, x0 + r, x1 - r)
    cy = np.clip(YY + 0.5, y0 + r, y1 - r)
    return m & ((XX + 0.5 - cx) ** 2 + (YY + 0.5 - cy) ** 2 <= r * r + 0.3)


def m_capsule(x0, y0, x1, y1, r):
    dx, dy = x1 - x0, y1 - y0
    t = np.clip(((XX + 0.5 - x0) * dx + (YY + 0.5 - y0) * dy) / (dx * dx + dy * dy), 0, 1)
    return (XX + 0.5 - x0 - t * dx) ** 2 + (YY + 0.5 - y0 - t * dy) ** 2 <= r * r


def m_poly(points):
    im = Image.new('1', (W, H))
    ImageDraw.Draw(im).polygon(points, fill=1)
    return np.array(im, bool)


def m_line(points, width):
    im = Image.new('1', (W, H))
    ImageDraw.Draw(im).line(points, fill=1, width=width, joint='curve')
    return np.array(im, bool)


def edge(mask):
    return mask & ~ndimage.binary_erosion(mask)


def shift(mask, dx, dy):
    return np.roll(np.roll(mask, dy, 0), dx, 1)


BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16
CHECK = (XX + YY) % 2 == 0


# ---------------------------------------------------------------- styles
class Style:
    """Parameters that change the look while keeping all geometry."""

    def __init__(self, name, **kw):
        self.name = name
        self.dither = True       # ordered dither inside gradients
        self.outline = None      # colour of a hard outline around every part
        self.shadow = 'soft'     # soft | hard | glow
        self.bevel_k = 1.6       # how strong bevel lighting is
        self.ramps = {}
        self.__dict__.update(kw)

    def ramp(self, name):
        return self.ramps[name]


BASE_RAMPS = {
    'grey':   ['666', '888', 'aaa', 'bbb', 'ccc', 'ddd', 'eee'],   # SNES body
    'disc':   ['444', '555', '666', '777', '888', '999', 'aaa'],
    'pill':   ['777', '888', '999', 'aaa', 'bbb', 'ccc', 'ddd'],
    'dpad':   ['111', '222', '333', '444', '555', '666', '777'],
    'white':  ['999', 'aaa', 'ccc', 'ddd', 'eee', 'fff', 'fff'],   # keyboard / mouse plastic
    'keydk':  ['333', '444', '555', '666', '777', '888', '888'],
    'well':   ['888', '999', 'aaa', 'bbb', 'ccc', 'ddd', 'eee'],
    'red':    ['600', '911', 'b12', 'd22', 'e44', 'f77', 'faa'],
    'yellow': ['850', 'a70', 'c90', 'eb1', 'fc3', 'fe6', 'ffa'],
    'blue':   ['014', '127', '23a', '34c', '56e', '89f', 'bcf'],
    'green':  ['031', '052', '173', '294', '4b6', '7d8', 'aeb'],
    'cyan':   ['057', '079', '09b', '2bd', '5de', '9ef', 'dff'],
    'purple': ['202', '414', '626', '848', 'a6a', 'c8c', 'eae'],
    'teal':   ['021', '043', '265', '387', '4a9', '7cb', 'aed'],
    'cable':  ['888', '999', 'bbb', 'ccc', 'ddd', 'eee', 'fff'],
}

STYLES = {
    'B': Style('B  Chunky pixel art  (black outlines, cel shading, hard shadows)',
               ramps=dict(BASE_RAMPS), dither=False, outline='112', shadow='hard', bevel_k=1.1,
               bg=('47a', '36a'), bg_shadow='225', panel=('112', 'fff', 'ff6'), text='fff', dim='9bd',
               legend='556', legend_dk='000', title='ff6'),
}
STYLE = STYLES['B']


# ---------------------------------------------------------------- shading
def shade(cv, st, mask, ramp, base=3, bevel=2, k=None, inset=False, curve=0.0,
          outline=True, dither=None):
    """Bevel-light a mask with a colour ramp; light comes from the top-left."""
    if not mask.any():
        return
    ramp = st.ramp(ramp) if isinstance(ramp, str) else ramp
    k = st.bevel_k if k is None else k
    dither = st.dither if dither is None else dither
    ys, xs = np.nonzero(mask)
    y0, y1 = max(ys.min() - 3, 0), min(ys.max() + 4, H)
    x0, x1 = max(xs.min() - 3, 0), min(xs.max() + 4, W)
    m = mask[y0:y1, x0:x1]
    d = ndimage.distance_transform_edt(m)
    ds = ndimage.gaussian_filter(np.minimum(d, bevel + 1.5), 1.0)
    gy, gx = np.gradient(ds)
    n = np.hypot(gx, gy) + 1e-6
    dot = (gx * 0.6 + gy * 0.8) / n          # inward normal . (down-right) == outward . light
    w = np.clip((bevel + 0.5 - d) / bevel, 0, 1)
    v = base + k * dot * w * (-1 if inset else 1) * 1.6
    if curve:                                 # gentle top-to-bottom dome
        rel = (np.arange(y0, y1)[:, None] - ys.min()) / max(1, ys.max() - ys.min())
        v = v + curve * (0.5 - rel) * (-1 if inset else 1)
    if dither:
        idx = np.floor(v + BAYER[np.arange(y0, y1)[:, None] % 4, np.arange(x0, x1)[None, :] % 4] - 0.5 + 0.5)
    else:
        idx = np.round(v)
    idx = np.clip(idx, 0, len(ramp) - 1).astype(int)
    cols = np.array([C(c) for c in ramp], np.uint8)
    sub = cv.a[y0:y1, x0:x1]
    sub[m] = cols[idx[m]]
    if outline and st.outline:
        sub[edge(m)] = C(st.outline)


def drop_shadow(cv, st, mask, dx=3, dy=4):
    if st.shadow == 'soft':
        core = shift(ndimage.binary_erosion(mask, iterations=1), dx, dy) & ~mask
        soft = shift(ndimage.binary_dilation(mask, iterations=2), dx, dy) & ~mask & ~core
        cv.fill(core, st.bg_shadow)
        cv.fill(soft & CHECK, st.bg_shadow)
    elif st.shadow == 'hard':
        cv.fill(shift(mask, dx, dy) & ~mask, st.bg_shadow)
    else:                                     # glow: faint dithered rim of light
        ring = ndimage.binary_dilation(mask, iterations=2) & ~mask
        cv.fill(ring & CHECK, st.bg_shadow)


def glow(cv, st, mask, col, width=3):
    """Dithered halo used for pressed buttons (always within the button's own tiles)."""
    ring1 = ndimage.binary_dilation(mask, iterations=1) & ~mask
    ring2 = ndimage.binary_dilation(mask, iterations=width) & ~mask & ~ring1
    cv.fill(ring1, col)
    if st.dither:
        cv.fill(ring2 & CHECK, col)


# ---------------------------------------------------------------- devices
FACE_LABELS = {
    'X': ['#...#', '#...#', '.#.#.', '..#..', '.#.#.', '#...#', '#...#'],
    'A': ['..#..', '.#.#.', '#...#', '#...#', '#####', '#...#', '#...#'],
    'B': ['####.', '#...#', '#...#', '####.', '#...#', '#...#', '####.'],
    'Y': ['#...#', '#...#', '.#.#.', '..#..', '..#..', '..#..', '..#..'],
}

def snes_pad(cv, st, ox, oy, port, pressed=(), connected=True):
    P = lambda x, y: (ox + x, oy + y)
    xs, ys = XX - ox, YY - oy
    # dog-bone body: two round lobes, a flat top and a broad, smooth waist at the bottom
    waist = 92 + 13 * (1 - np.cos(np.pi * np.clip(np.abs(xs + 0.5 - 120) / 68, 0, 1))) / 2
    body = (m_circle(*P(52, 56), 49) | m_circle(*P(188, 56), 49)
            | ((xs >= 52) & (xs < 188) & (ys >= 7) & (ys + 0.5 < waist)))
    # shoulder buttons: thin slivers hugging the top edge and following the lobe curve
    rim = (ndimage.distance_transform_edt(~body) <= 5.2) & ~body & (ys < 34)
    shL = rim & (xs >= 24) & (xs < 86)
    shR = rim & (xs >= 154) & (xs < 216)
    drop_shadow(cv, st, body | shL | shR)
    for name, m in (('L', shL), ('R', shR)):
        shade(cv, st, m, 'cyan' if name in pressed else 'grey', base=5, bevel=2, k=0.8)
    shade(cv, st, body, 'grey', base=4, bevel=3, curve=1.0)

    # d-pad dish and cross
    dish = m_circle(*P(52, 57), 33)
    shade(cv, st, dish, 'grey', base=4, bevel=4, inset=True, k=0.8, outline=False)
    if not st.dither:
        cv.fill(edge(dish), st.ramp('grey')[2])
    cross = m_rrect(*P(45, 35), *P(60, 80), 2) | m_rrect(*P(30, 50), *P(75, 65), 2)
    shade(cv, st, cross, 'dpad', base=3, bevel=2, curve=0.6)
    cx, cy = ox + 52, oy + 57
    tri = {
        'UP': [(cx - 4, cy - 15), (cx + 3, cy - 15), (cx - 0.5, cy - 19)],
        'DOWN': [(cx - 4, cy + 14), (cx + 3, cy + 14), (cx - 0.5, cy + 18)],
        'LEFT': [(cx - 15, cy - 4), (cx - 15, cy + 3), (cx - 19, cy - 0.5)],
        'RIGHT': [(cx + 14, cy - 4), (cx + 14, cy + 3), (cx + 18, cy - 0.5)],
    }
    for name, pts in tri.items():
        m = m_poly(pts)
        if name in pressed:
            glow(cv, st, m, C(st.ramp('cyan')[4]), 2)
            cv.fill(m, st.ramp('cyan')[6])
        else:
            cv.fill(m, st.ramp('dpad')[5])
    shade(cv, st, m_circle(cx, cy, 4), 'dpad', base=3, bevel=3, inset=True, outline=False)

    # logo area: "PORT n" + reversed bar
    cv.text(ox + 96, oy + 19, f'PORT {port}', C(st.ramp('grey')[0]))
    bar = m_rect(*P(92, 30), *P(148, 38))
    cv.fill(bar, st.ramp('grey')[0])
    cv.tiny(ox + 101, oy + 32, 'CONTROLLER', st.ramp('grey')[5])

    # select / start
    for name, (sx, sy) in (('SELECT', (98, 63)), ('START', (123, 63))):
        m = m_capsule(ox + sx - 5, oy + sy + 3, ox + sx + 5, oy + sy - 3, 3.6)
        shade(cv, st, m, 'cyan' if name in pressed else 'dpad', base=4, bevel=2)
        cv.tiny(ox + sx - tiny_width(name) // 2, oy + 74, name, st.ramp('grey')[0])

    # face buttons
    fx, fy = ox + 188, oy + 57
    disc = m_circle(fx, fy, 44)
    shade(cv, st, disc, 'disc', base=3, bevel=3, inset=True, k=1.0)
    pos = {'X': (0, -17), 'Y': (-23, 0), 'A': (23, 0), 'B': (0, 17)}
    for a, b in (('Y', 'X'), ('B', 'A')):
        shade(cv, st, m_capsule(fx + pos[a][0], fy + pos[a][1], fx + pos[b][0], fy + pos[b][1], 12.5),
              'pill', base=3, bevel=2, inset=True, k=1.0)
    colours = {'X': 'blue', 'Y': 'green', 'A': 'red', 'B': 'yellow'}
    for name, (dx, dy) in pos.items():
        m = m_circle(fx + dx, fy + dy, 9.5)
        ramp = st.ramp(colours[name])
        if name in pressed:
            glow(cv, st, m, C(ramp[5]), 3)
            shade(cv, st, m, [ramp[3], ramp[4], ramp[5], ramp[6], 'fff'], base=2, bevel=6)
        else:
            shade(cv, st, m, colours[name], base=3, bevel=6)
    # X/A/Y/B printed on the disc, centred where the original has them (measured from the photo)
    for name, (lx, ly) in {'X': (16.7, -29.6), 'A': (37.0, -9.9), 'Y': (-37.9, 9.2), 'B': (-16.8, 28.3)}.items():
        gx, gy = round(fx + lx * 0.95 - 2.5), round(fy + ly * 0.95 - 3.5)
        for j, row in enumerate(FACE_LABELS[name]):
            for i, b in enumerate(row):
                if b == '#':
                    cv.px(gx + i, gy + j, st.ramp('pill')[5])

    if not connected:                         # dim everything that is not background
        reg = (body | shL | shR)
        reg = ndimage.binary_dilation(reg, iterations=4)
        sub = cv.a[reg].astype(int)
        bg = np.array(C(st.bg[0]))
        cv.a[reg] = ((sub + bg * 2) // 3).astype(np.uint8)


# half-width of the top surface (inside the side contour lines), traced from the photo
MOUSE_TOP_HW = ([0, 10.9, 32.3, 39.4, 48.9, 58.4, 67.9, 77.4, 86.9, 96.4, 105.9, 115.4, 128],
                [26, 28.5, 30.6, 30.4, 29.6, 28.3, 26.8, 25.4, 24.1, 22.9, 22.2, 21.9, 21.5])


def mouse(cv, st, ox, oy, pressed=()):
    """Top view of the X16 PS/2 mouse, traced from the product photo (70 x 128 px)."""
    w, h, cx = 70, 128, 35
    xs, ys = XX + 0.5 - ox, YY + 0.5 - oy
    xr = xs - cx
    body = m_rect(ox, oy, ox + w, oy + h)
    for r, yc in ((22, 22), (25, h - 25)):              # big front and rear corner radii
        zone = (ys < yc) if yc == 22 else (ys > yc)
        body &= ~(zone & (np.abs(xr) > cx - r) & ((np.abs(xr) - (cx - r)) ** 2 + (ys - yc) ** 2 > r * r))
    cable = m_line([(ox + cx, oy + 2), (ox + cx, oy - 12), (ox + cx + 10, oy - 22), (ox + cx + 10, 0)], 3)
    shade(cv, st, cable & ~body, 'cable', base=4, bevel=1)
    drop_shadow(cv, st, body)
    white = st.ramp('white')
    shade(cv, st, body, 'white', base=3, bevel=3, curve=0.6)          # side panels
    top = body & (np.abs(xr) <= np.interp(ys, *MOUSE_TOP_HW))
    shade(cv, st, top, 'white', base=5, bevel=2, k=0.6, outline=False)
    line = white[1]
    cv.fill(edge(top) & ndimage.binary_erosion(body, iterations=2), line)

    # centre ridge: rounded tab that tapers towards the palm
    ridge = m_poly([(ox + cx - 9, oy + 11), (ox + cx - 6, oy + 7), (ox + cx + 6, oy + 7), (ox + cx + 9, oy + 11),
                    (ox + cx + 5.5, oy + 62), (ox + cx + 2.5, oy + 65), (ox + cx - 2.5, oy + 65),
                    (ox + cx - 5.5, oy + 62)])
    # buttons: everything on the top surface in front of the chevron seam, split by the ridge
    seam_y = 60 + (np.abs(xr) - 6) * (11 / 20.5)
    for name, side_m in (('LMB', xr < 0), ('RMB', xr >= 0)):
        if name in pressed:
            m = top & side_m & (ys < seam_y) & ~ridge
            shade(cv, st, m, 'cyan', base=4, bevel=2, k=0.6, outline=False)
    cv.fill(m_line([(ox + 8, oy + 71), (ox + 29, oy + 60)], 1) | m_line([(ox + 41, oy + 60), (ox + 62, oy + 71)], 1)
            | m_rect(ox + cx, oy, ox + cx + 1, oy + 8), line)
    cv.fill(ndimage.binary_dilation(ridge) & ~ridge, line)
    shade(cv, st, ridge, 'white', base=5, bevel=2, k=0.7, outline=False)
    # wheel in its slot
    lit = 'MMB' in pressed
    slot = m_rrect(ox + cx - 4.5, oy + 14, ox + cx + 4.5, oy + 37, 4.5)
    shade(cv, st, slot, 'dpad', base=1, bevel=2, inset=True, outline=False)
    wheel_m = m_rrect(ox + cx - 2.5, oy + 16, ox + cx + 2.5, oy + 35, 2.5)
    shade(cv, st, wheel_m, 'cyan' if lit else 'pill', base=4, bevel=2, outline=False)
    cv.fill(wheel_m & ((YY - oy) % 3 == 0), st.ramp('cyan' if lit else 'pill')[1])
    if st.outline:
        cv.fill(edge(body), st.outline)
    # scroll indicators to the right of the wheel
    for name, pts in (('WUP', [(ox + 76, oy + 21), (ox + 86, oy + 21), (ox + 81, oy + 15)]),
                      ('WDN', [(ox + 76, oy + 27), (ox + 86, oy + 27), (ox + 81, oy + 33)])):
        shade(cv, st, m_poly(pts), 'cyan' if name in pressed else 'pill', base=4, bevel=1, k=0.6)


def keyboard_layout():
    """Return rows of (label, units, kind, legend) for the Commander X16 keyboard."""
    nums = [('1', '!', 'BLK', 'ORG'), ('2', '@', 'WHT', 'BRN'), ('3', '#', 'RED', 'LRD'),
            ('4', '$', 'CYN', 'DGY'), ('5', '%', 'PUR', 'MGY'), ('6', '^', 'GRN', 'LGN'),
            ('7', '&', 'BLU', 'LBL'), ('8', '*', 'YEL', 'LGY'), ('9', '(', 'RVS', 'ON'),
            ('0', ')', 'RVS', 'OFF')]
    row0 = [(n, 16 / 17, 'dark', ('tiny', n)) for n in
            ['ESC'] + [f'F{i}' for i in range(1, 13)] + ['RESTORE', '40/80', 'RUN', 'DEL']]
    row0[14] = ('40/80', 16 / 17, 'dark', ('tiny2', '40/80', 'DISP'))
    row0[15] = ('RUN', 16 / 17, 'dark', ('tiny2', 'RUN', 'STOP'))
    row0[13] = ('RESTORE', 16 / 17, 'dark', ('tiny', 'RESTR'))
    row1 = [('`', 1, 'light', ('sym', 0x1F, 0x5E))]
    row1 += [(d, 1, 'light', ('num', s, d, a, b)) for d, s, a, b in nums]
    row1 += [('-', 1, 'light', ('one', '-')), ('=', 1, 'light', ('two', '+', '=')),
             ('BACKSPACE', 2, 'light', ('tiny', 'BACKSPACE')), ('HOME', 1, 'light', ('tiny2', 'CLR', 'HOME'))]
    row2 = [('TAB', 1.5, 'light', ('tiny', 'TAB'))]
    row2 += [(c, 1, 'light', ('alpha', c)) for c in 'QWERTYUIOP']
    row2 += [('[', 1, 'light', ('two', '{', '[')), (']', 1, 'light', ('two', '}', ']')),
             ('\\', 1.5, 'light', ('two', '\xa3', '\\')), ('PGUP', 1, 'light', ('tiny2', 'PAGE', 'UP'))]
    row3 = [('CAPS', 1.75, 'light', ('tiny', 'SHIFT LOCK'))]
    row3 += [(c, 1, 'light', ('alpha', c)) for c in 'ASDFGHJKL']
    row3 += [(';', 1, 'light', ('two', ':', ';')), ("'", 1, 'light', ('two', '"', "'")),
             ('RETURN', 2.25, 'light', ('tiny', 'RETURN')), ('PGDN', 1, 'light', ('tiny2', 'PAGE', 'DN'))]
    row4 = [('LSHIFT', 2.25, 'light', ('tiny', 'SHIFT'))]
    row4 += [(c, 1, 'light', ('alpha', c)) for c in 'ZXCVBNM']
    row4 += [(',', 1, 'light', ('two', '<', ',')), ('.', 1, 'light', ('two', '>', '.')),
             ('/', 1, 'light', ('two', '?', '/')), ('RSHIFT', 1.75, 'light', ('tiny', 'SHIFT')),
             ('UP', 1, 'dark', ('arrow', 'U')), ('END', 1, 'light', ('tiny', 'END'))]
    row5 = [('LCTRL', 1, 'light', ('tiny', 'CTRL')), ('LOGO', 1, 'light', ('logo',)),
            ('FN', 1, 'dark', ('tiny', 'FN')), ('LALT', 1, 'light', ('tiny', 'ALT')),
            ('SPACE', 5, 'light', ('none',)), ('RALT', 1, 'light', ('tiny', 'ALT')),
            ('MENU', 1, 'light', ('tiny', 'MENU')), ('RCTRL', 1, 'light', ('tiny', 'CTRL')),
            ('INST', 1, 'light', ('tiny', 'INST')), ('LEFT', 1, 'dark', ('arrow', 'L')),
            ('DOWN', 1, 'dark', ('arrow', 'D')), ('RIGHT', 1, 'dark', ('arrow', 'R'))]
    return [row0, row1, row2, row3, row4, row5]


ARROWS = {
    'U': [0x00, 0x18, 0x3C, 0x7E, 0x18, 0x18, 0x18, 0x00],
    'D': [0x00, 0x18, 0x18, 0x18, 0x7E, 0x3C, 0x18, 0x00],
    'L': [0x00, 0x10, 0x30, 0x7E, 0x7E, 0x30, 0x10, 0x00],
    'R': [0x00, 0x08, 0x0C, 0x7E, 0x7E, 0x0C, 0x08, 0x00],
}
X16_LOGO = [0x00, 0x81, 0x42, 0x24, 0x00, 0x24, 0x42, 0x81]


def keycap(cv, st, x, y, w, h, kind, legend, lit):
    ramp = 'cyan' if lit else ('keydk' if kind == 'dark' else 'white')
    cap = m_rrect(x + 1, y + 1, x + w - 1, y + h - 1, 3)
    shade(cv, st, cap, ramp, base=1, bevel=2, k=1.0)
    face = m_rrect(x + 2, y + 1, x + w - 2, y + h - 5, 3)
    shade(cv, st, face, ramp, base=4, bevel=2, k=0.8, curve=0.5, outline=False)
    if lit:
        ink = C(st.ramp('cyan')[0])
        dim = C(st.ramp('cyan')[2])
    else:
        ink = C(st.legend_dk if kind == 'dark' else st.legend)
        dim = C(st.ramp('white')[1]) if kind == 'light' else C(st.legend_dk)
    tx, ty = x + 4, y + 3
    t = legend[0]
    if t == 'tiny':
        cv.tiny(tx, ty + 1, legend[1], ink)
    elif t == 'tiny2':
        cv.tiny(tx, ty + 1, legend[1], ink)
        cv.tiny(tx, ty + 7, legend[2], ink)
    elif t in ('alpha', 'one'):
        cv.glyph(tx, ty, FONT_ISO[ord(legend[1])], ink)
    elif t == 'num':
        _, s, d, a, b = legend
        cv.glyph(tx, ty, FONT_ISO[ord(s)], ink)
        cv.glyph(tx, ty + 11, FONT_ISO[ord(d)], ink)
        cv.tiny(tx + 10, ty + 11, a, dim)
        cv.tiny(tx + 10, ty + 17, b, dim)
    elif t == 'two':
        cv.glyph(tx, ty, FONT_ISO[ord(legend[1])], ink)
        cv.glyph(tx, ty + 11, FONT_ISO[ord(legend[2])], ink)
    elif t == 'sym':
        cv.glyph(tx, ty, FONT_PET[legend[1]], ink)
        cv.glyph(tx, ty + 11, FONT_PET[legend[2]], dim)
    elif t == 'arrow':
        cv.glyph(x + (w - 8) // 2, y + 8, ARROWS[legend[1]], ink)
    elif t == 'logo':
        cv.glyph(x + (w - 8) // 2, y + 9, X16_LOGO, C(st.ramp('cyan')[2]))


KB_ORIGIN = (56, 240)
LED_ICONS = (('LED_NUM', '1'), ('LED_CAPS', 'A'), ('LED_SCROLL', 'V'))


def keyboard_cells(ox=KB_ORIGIN[0], oy=KB_ORIGIN[1]):
    """Yield (label, kind, legend, x0, y0, x1, y1) for every key cap cell."""
    ky = oy + 40
    for r, row in enumerate(keyboard_layout()):
        h = 24 if r == 0 else 32
        x = 0.0
        for label, units, kind, legend in row:
            x0 = ox + 8 + round(x * 32)
            x += units
            yield label, kind, legend, x0, ky, ox + 8 + round(x * 32), ky + h
        ky += h


def led_boxes(ox=KB_ORIGIN[0], oy=KB_ORIGIN[1]):
    """Yield (name, icon, x0, y0, x1, y1) for the three lock indicators."""
    for i, (name, icon) in enumerate(LED_ICONS):
        lx = ox + 24 + i * 22
        yield name, icon, lx, oy + 7, lx + 7, oy + 16


def keyboard(cv, st, ox=KB_ORIGIN[0], oy=KB_ORIGIN[1], pressed=(), leds=()):
    kw, kh = 528, 232
    body = m_rrect(ox, oy, ox + kw, oy + kh, 8)
    drop_shadow(cv, st, body, 4, 5)
    shade(cv, st, body, 'white', base=4, bevel=4, curve=0.8)
    # top bezel details: LED legends, slot, logo
    for name, icon, x0, y0, x1, y1 in led_boxes(ox, oy):
        box = m_rect(x0, y0, x1, y1)
        led = C(st.ramp('cyan')[3])
        if name in leds:
            cv.fill(box, st.ramp('cyan')[5])
            cv.tiny(x0 + 2, y0 + 2, icon, C(st.ramp('cyan')[0]))
        else:
            cv.fill(edge(box), led)
            cv.tiny(x0 + 2, y0 + 2, icon, led)
    cv.fill(m_rrect(ox + 16, oy + 19, ox + 84, oy + 22, 1), '111')
    logo_c = C(st.ramp('cyan')[3])
    cv.text(ox + kw - 128, oy + 16, 'COMMANDER', logo_c)
    cv.glyph(ox + kw - 54, oy + 16, X16_LOGO, logo_c)
    cv.text(ox + kw - 44, oy + 16, '16', logo_c)
    # key well
    well = m_rect(ox + 7, oy + 39, ox + kw - 7, oy + kh - 7)
    shade(cv, st, well, 'well', base=3, bevel=2, inset=True, outline=False)
    for label, kind, legend, x0, y0, x1, y1 in keyboard_cells(ox, oy):
        keycap(cv, st, x0, y0, x1 - x0, y1 - y0, kind, legend, label in pressed)
    if st.outline:
        cv.fill(edge(body), st.outline)


def cable(cv, st, pts, plug_at, plug_ramp, vertical=True):
    m = m_line(pts, 3)
    shade(cv, st, m, 'cable', base=4, bevel=1)
    px, py = plug_at
    boot = m_rrect(px - 6, py, px + 6, py + 22, 3)
    shade(cv, st, boot, plug_ramp, base=3, bevel=3, curve=1.0)
    for i in range(4):
        cv.fill(m_rect(px - 6, py + 3 + i * 3, px + 6, py + 4 + i * 3) & boot, st.ramp(plug_ramp)[1])
    metal = m_rrect(px - 5, py + 22, px + 5, py + 28, 1)
    shade(cv, st, metal, 'grey', base=4, bevel=2)


# ---------------------------------------------------------------- screen
PAD_ORIGIN = {1: (8, 40), 2: (392, 40)}       # 384 px apart, so both pads share their tiles
MOUSE_ORIGIN = (285, 34)
PANEL = (8, 188, 632, 232)                     # event panel; its title sits in text row 23
PANEL_TITLE = (16, 'LAST EVENTS')


def background(cv, st):
    cv.a[:] = C(st.bg[0])
    cv.fill((XX % 16 == 0) | (YY % 16 == 0), st.bg[1])


def panel(cv, st, x0, y0, x1, y1, notch=None):
    """Dark panel with a light frame; `notch` = (x, chars) leaves a gap in the top edge for a title."""
    face, frame, _ = st.panel
    m = m_rrect(x0, y0, x1, y1, 4)
    cv.fill(m, face)
    cv.fill(edge(m), frame)
    if notch:
        nx, chars = notch
        cv.fill(m_rect(nx - 2, y0 - 1, nx + len(chars) * 8 + 2, y0 + 1), face)


def scene(st=STYLE, pad1=(), pad2=(), mouse_btn=(), keys=(), leds=()):
    """The full idle/pressed screen without any dynamic text or the cursor."""
    cv = Canvas()
    background(cv, st)
    snes_pad(cv, st, *PAD_ORIGIN[1], 1, pad1)
    snes_pad(cv, st, *PAD_ORIGIN[2], 2, pad2)
    mouse(cv, st, *MOUSE_ORIGIN, mouse_btn)
    cable(cv, st, [(212, 241), (212, 234), (30, 234), (30, 250)], (30, 248), 'purple')
    keyboard(cv, st, pressed=keys, leds=leds)
    panel(cv, st, *PANEL, notch=PANEL_TITLE)
    return cv


CURSOR = ['X..........', 'XX.........', 'XWX........', 'XWWX.......', 'XWWWX......', 'XWWWWX.....',
          'XWWWWWX....', 'XWWWWWWX...', 'XWWWWWWWX..', 'XWWWWWXXXX.', 'XWWXWWX....', 'XWX.XWWX...',
          'XX..XWWX...', 'X....XWWX..', '.....XWWX..', '......XX...']
CURSOR_COLOURS = {'X': '112', 'W': 'fff'}


def cursor(cv, x, y):
    for j, row in enumerate(CURSOR):
        for i, ch in enumerate(row):
            if ch in CURSOR_COLOURS:
                cv.px(x + i, y + j, CURSOR_COLOURS[ch])


def text_cell(cv, col, row, s, col_hex):
    """Mockup stand-in for the program's text layer (8x8 cells)."""
    cv.text(col * 8, row * 8, s, C(col_hex))


def main():
    st = STYLE
    cv = scene(st, pad1={'A', 'RIGHT', 'L'}, mouse_btn={'LMB', 'WUP'}, keys={'A', 'LSHIFT', 'UP', 'F5'},
               leds={'LED_CAPS'})
    text_cell(cv, 1, 1, 'COMMANDER X16 INPUT TEST  V' + (ROOT.parent / 'VERSION').read_text().strip(), st.title)
    text_cell(cv, 63, 1, 'HOLD ESC TO QUIT', st.dim)
    text_cell(cv, 2, 19, 'JOY1 PRESENT $7EFE', st.text)
    text_cell(cv, 50, 19, 'JOY2 NOT PRESENT', st.dim)
    text_cell(cv, 33, 21, 'X 0347  Y 0215', st.text)
    text_cell(cv, 2, 23, PANEL_TITLE[1], st.title)
    text_cell(cv, 3, 25, 'KEY $1F A        DOWN   HELD 4', st.text)
    text_cell(cv, 3, 27, 'LSHIFT+ F5+ UP+ A+ LMB+ WHEEL-1 J1:A+', st.dim)
    cursor(cv, 470, 206)
    out = Path(__file__).resolve().parents[1] / 'design' / 'mockups'
    out.mkdir(parents=True, exist_ok=True)
    img = cv.image()
    img.save(out / 'screen.png')
    img.resize((1280, 960), Image.NEAREST).save(out / 'screen_2x.png')


if __name__ == '__main__':
    main()
