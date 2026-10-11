"""Decode the built VERA assets and check them pixel-exact against the art.

Covers the idle screen, every region pressed on its own (in batches of regions that
share no tiles), everything pressed at once, and both orders of tile-sharing
neighbours. Run after `make`.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import build_assets  # noqa: E402
import vera_preview  # noqa: E402


def screen(vera, tables, pressed):
    v = dict(vera, maps={k: m.copy() for k, m in vera['maps'].items()})
    vera_preview.press(v, tables, pressed)
    return build_assets.c12(vera_preview.render(v))


def check(an, vera, tables, pressed, label):
    got = screen(vera, tables, pressed)
    want = an.reference(pressed)
    bad = got != want
    assert not bad.any(), f'{label}: {int(bad.sum())} pixels differ, first at {np.argwhere(bad)[0][::-1]}'


def main():
    an = build_assets.Analysis()
    vera = vera_preview.load(ROOT / 'build')
    tables = vera_preview.parse_tables(ROOT / 'build' / 'gen')
    assert len(tables['first']) == len(an.names) + 1, 'region tables do not match the art'

    check(an, vera, tables, set(), 'idle')
    check(an, vera, tables, set(range(len(an.names))), 'everything pressed')

    # every region alone; regions sharing no tile can be tested in the same pass
    tiles_of = {r: {t for t, regs in an.tile_regions.items() if r in regs} for r in range(len(an.names))}
    remaining = list(range(len(an.names)))
    passes = 0
    while remaining:
        batch, used = [], set()
        for r in remaining:
            if not tiles_of[r] & used:
                batch.append(r)
                used |= tiles_of[r]
        check(an, vera, tables, set(batch), 'batch ' + ' '.join(an.names[r] for r in batch[:3]))
        remaining = [r for r in remaining if r not in batch]
        passes += 1

    # neighbours that share tiles, each with and without the other
    shared = {tuple(regs) for regs in an.tile_regions.values() if len(regs) == 2}
    for a, b in sorted(shared):
        check(an, vera, tables, {a}, an.names[a])
        check(an, vera, tables, {b}, an.names[b])
        check(an, vera, tables, {a, b}, an.names[a] + '+' + an.names[b])
    print(f'assets OK: idle, all pressed, {len(an.names)} regions in {passes} passes, '
          f'{len(shared)} shared-tile pairs')


if __name__ == '__main__':
    main()
