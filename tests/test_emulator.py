"""Drive the real program in x16emu through AgentBridge.

Checks the start-up state, every keyboard key the emulator can send, the lock LEDs,
the mouse buttons/wheel/readout, a simulated SNES controller on port 1 (registers
patched right after joystick_get) and quitting with a held ESC, which must hand a
clean KERNAL text screen back. Screenshots go to build/screenshots/.

Run after `make`.
"""
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'
sys.path.insert(0, str(ROOT.parent / 'x16-emulator' / 'api' / 'python'))
sys.path.insert(0, str(ROOT / 'tools'))

from x16agent import X16Agent  # noqa: E402
import vera_preview  # noqa: E402

EMU = Path(os.environ.get('EMU', ROOT.parent / 'x16-emulator' / 'build' / 'x16emu'))
ROM = Path(os.environ.get('ROM', ROOT.parent / 'emulator' / 'rom.bin'))

# keyboard labels (as in the region names) -> SDL key names the emulator understands
SDL_KEYS = {'ESC': 'Escape', '4080': 'ScrollLock', 'RUN': 'Pause', 'DEL': 'Delete', 'GRAVE': '`',
            'MINUS': '-', 'EQUAL': '=', 'BACKSPACE': 'Backspace', 'HOME': 'Home', 'TAB': 'Tab',
            'LBRACKET': '[', 'RBRACKET': ']', 'POUND': '\\', 'PGUP': 'PageUp', 'CAPS': 'CapsLock',
            'SEMICOLON': ';', 'QUOTE': "'", 'RETURN': 'Return', 'PGDN': 'PageDown', 'LSHIFT': 'Left Shift',
            'COMMA': ',', 'PERIOD': '.', 'SLASH': '/', 'RSHIFT': 'Right Shift', 'UP': 'Up', 'END': 'End',
            'LCTRL': 'Left Ctrl', 'LOGO': 'Left GUI', 'LALT': 'Left Alt', 'SPACE': 'Space',
            'RALT': 'Right Alt', 'MENU': 'Application', 'RCTRL': 'Right Ctrl', 'INST': 'Insert',
            'LEFT': 'Left', 'DOWN': 'Down', 'RIGHT': 'Right'}
SDL_KEYS.update({f'F{i}': f'F{i}' for i in range(1, 13)})
SDL_KEYS.update({c: c for c in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'})
NOT_EMULATED = {'RESTORE'}      # PrintScreen has no keynum in x16emu


class Tester:
    def __init__(self, emu):
        self.emu = emu
        self.sym = {n: int(a, 16) for a, n in
                    re.findall(r'al ([0-9A-Fa-f]+) \.(\S+)', (BUILD / 'X16INPUT.sym').read_text())}
        self.tables = vera_preview.parse_tables(BUILD / 'gen')
        header = (BUILD / 'gen' / 'assets.h').read_text()
        self.names = re.findall(r'^    R_(\w+),$', header, re.M)

    def frames(self, n=1):
        r = self.emu.advance(n)
        assert r['reason'] == 'target', r

    def until(self, symbol, frames=600):
        self.emu.advance(1, unit='instructions')    # step off a breakpoint we may sit on
        self.emu.request('breakpoint', address=self.sym[symbol])
        r = self.emu.advance(frames)
        self.emu.request('breakpoint', action='clear')
        assert r['reason'] == 'breakpoint', f'{symbol} not reached: {r}'
        return r['state']

    def vram(self, addr, n):
        return self.emu.read_memory(addr, n, space='vram')

    def region(self, name):
        """True/False when every map entry of the region shows the pressed/released state."""
        r = self.names.index(name)
        t = self.tables
        states = set()
        for addr, off, on in t['rtiles'][t['first'][r]:t['first'][r + 1]]:
            word = int.from_bytes(self.vram(addr, 2), 'little')
            assert word in (off, on), f'{name}: entry at {addr:04x} is {word:04x}'
            states.add(word == on)
        assert len(states) == 1, f'{name}: tiles disagree'
        return states.pop()

    def check_shared(self):
        """Shared entries must match the states of both of their regions."""
        for addr, a, b, entry in self.tables['shared']:
            mask = self.region(self.names[a]) | self.region(self.names[b]) << 1
            word = int.from_bytes(self.vram(addr, 2), 'little')
            assert word == entry[mask], f'shared entry {addr:04x}: {word:04x} != {entry[mask]:04x}'

    def text(self, row, col=0, n=80):
        raw = self.vram(0x4000 + row * 256 + col * 2, n * 2)
        return bytes(raw[0::2]).decode('ascii', 'replace').replace('\x00', ' ')

    def veil(self, port):
        """(fully drawn, fully cleared) for the veil over a controller."""
        n = len(self.tables['veil']) // 2
        entries = [int.from_bytes(self.vram(a, 2), 'little') == e
                   for a, e in self.tables['veil'][(port - 1) * n:port * n]]
        return all(entries), not any(entries)

    def key(self, name, down):
        self.emu.request('key', key=name, down=down)
        self.frames(2)

    def mouse(self, **packet):
        self.emu.request('mouse', **packet)
        self.frames(2)


def test_startup(t, shots):
    assert t.vram(0x1FA00, 512) == (BUILD / 'PALETTE.BIN').read_bytes(), 'palette not loaded'
    assert t.vram(0x0000, 15360) == (BUILD / 'L0MAP.BIN').read_bytes(), 'layer 0 map differs'
    l1 = (BUILD / 'L1MAP.BIN').read_bytes()
    assert t.vram(0x4000 + 30 * 256, 30 * 256) == l1[30 * 256:], 'keyboard map differs'
    regs = t.emu.read_memory(0x9F29, 0x12)
    assert regs[0] & 0x70 == 0x70 and regs[4] == 0x62 and regs[11] == 0x62, regs.hex()
    version = (ROOT / 'VERSION').read_text().strip()
    assert f'COMMANDER X16 INPUT TEST  V{version}' in t.text(1), t.text(1)
    assert 'HOLD ESC TO QUIT' in t.text(1)
    # no controllers in the emulator: both pads are veiled and say so
    for port in (1, 2):
        assert t.veil(port)[0], f'port {port} veil missing'
    assert 'JOY1 NOT PRESENT' in t.text(19) and 'JOY2 NOT PRESENT' in t.text(19)
    assert not any(t.region(n) for n in t.names), 'something is lit at start-up'
    t.emu.screenshot(shots / 'idle.png')


def test_keyboard(t):
    tested = 0
    for name in t.names:
        if not name.startswith('KEY_'):
            continue
        label = name[4:]
        if label in NOT_EMULATED:
            continue
        sdl = SDL_KEYS[label]
        t.key(sdl, True)
        assert t.region(name), f'{name} did not light up'
        line = t.text(25)
        assert 'DOWN' in line and 'HELD 01' in line, line
        t.key(sdl, False)
        assert not t.region(name), f'{name} stayed lit'
        assert 'UP' in t.text(25) and 'HELD 00' in t.text(25)
        tested += 1
        if label == 'CAPS':                     # toggles the caps LED
            assert t.region('LED_CAPS')
        if label == '4080':                     # scroll lock key
            assert t.region('LED_SCROLL')
    # two keys sharing tiles, held together
    t.key('F5', True)
    t.key('F6', True)
    assert t.region('KEY_F5') and t.region('KEY_F6')
    t.check_shared()
    t.key('F5', False)
    assert not t.region('KEY_F5') and t.region('KEY_F6')
    t.check_shared()
    t.key('F6', False)
    t.key('A', True)
    assert 'KEY $1F  A ' in t.text(25), t.text(25)
    t.key('A', False)
    assert t.text(27).rstrip().endswith('F6- A+ A-'), t.text(27)
    # second press switches the LEDs off again
    t.key('CapsLock', True)
    t.key('CapsLock', False)
    t.key('ScrollLock', True)
    t.key('ScrollLock', False)
    assert not t.region('LED_CAPS') and not t.region('LED_SCROLL')
    return tested


def test_mouse(t):
    t.mouse(dx=120, dy=100)
    x, y = (int.from_bytes(t.emu.read_memory(t.sym[s], 2), 'little') for s in ('_mouse_x', '_mouse_y'))
    assert t.text(21, 33, 14) == f'X {x:04d}  Y {y:04d}', t.text(21, 33, 14)
    for buttons, lit in ((1, 'MOUSE_LMB'), (2, 'MOUSE_RMB'), (4, 'MOUSE_MMB')):
        t.mouse(buttons=buttons)
        for name in ('MOUSE_LMB', 'MOUSE_RMB', 'MOUSE_MMB'):
            assert t.region(name) == (name == lit), name
    t.mouse(buttons=0)
    assert not any(t.region(n) for n in ('MOUSE_LMB', 'MOUSE_RMB', 'MOUSE_MMB'))
    t.mouse(wheel=-1)
    up, down = t.region('MOUSE_WUP'), t.region('MOUSE_WDN')
    assert up != down, 'one wheel arrow should light'
    t.frames(20)
    assert not t.region('MOUSE_WUP') and not t.region('MOUSE_WDN'), 'wheel arrow stuck'
    assert 'WHEEL' in t.text(27)


def joystick_frame(t, a, x, y):
    """Let one frame poll port 1 with the given joystick_get result."""
    t.until('_joy_got')
    t.emu.request('set_registers', a=a, x=x, y=y)
    t.until('_joy_got')                         # port 2 poll: port 1 is fully processed


def test_joystick(t):
    joystick_frame(t, 0xFF, 0x7F, 0x00)         # controller present, A held
    assert t.veil(1)[1] and t.veil(2)[0], 'veils wrong with pad 1 present'
    assert t.region('P1_A') and not t.region('P1_B')
    assert 'JOY1 PRESENT $FF7F' in t.text(19), t.text(19)
    joystick_frame(t, 0x7E, 0xDF, 0x00)         # B + RIGHT + L
    for name in t.names:
        if name.startswith('P1_'):
            assert t.region(name) == (name in ('P1_B', 'P1_RIGHT', 'P1_L')), name
    assert not any(t.region(n) for n in t.names if n.startswith('P2_'))
    t.frames(3)                                 # unplugged again
    assert t.veil(1)[0] and not any(t.region(n) for n in t.names if n.startswith('P1_'))
    assert 'J1:OFF' in t.text(27), t.text(27)


def showcase(t, shots):
    """Screenshot with a controller on port 1: joystick_get is redirected to a stub in
    golden RAM ($0400) that reports B + RIGHT + A + L held on port 1."""
    stub = bytes([0xC9, 0x01,               # cmp #1
                  0xD0, 0x07,               # bne real
                  0xA9, 0x7E,               # lda #$7E   B + RIGHT
                  0xA2, 0x5F,               # ldx #$5F   A + L
                  0xA0, 0x00,               # ldy #0     present
                  0x60,                     # rts
                  0x4C, 0x56, 0xFF])        # real: jmp joystick_get
    call = t.sym['_joy_read']
    original = t.emu.read_memory(call, 3)
    assert original == bytes([0x20, 0x56, 0xFF]), original.hex()
    t.emu.write_memory(0x0400, stub)
    t.emu.write_memory(call, bytes([0x20, 0x00, 0x04]))
    t.key('A', True)
    t.key('Left Shift', True)
    t.key('F5', True)
    t.mouse(dx=-90, dy=-120, buttons=1)
    t.frames(4)
    assert t.region('P1_A') and t.region('P1_RIGHT') and t.veil(1)[1]
    t.emu.screenshot(shots / 'showcase.png')
    t.emu.write_memory(call, original)
    for k in ('A', 'Left Shift', 'F5'):
        t.key(k, False)
    t.mouse(buttons=0)
    t.frames(4)
    assert t.veil(1)[0] and not t.region('P1_A')


def test_quit(t, kernal_vector, kernal_palette, shots):
    t.emu.request('key', key='Escape', down=True)
    t.frames(60)
    assert 'HOLD' in t.text(1)                  # still running, progress shown
    t.frames(60)
    t.emu.request('key', key='Escape', down=False)
    t.frames(30)
    assert t.emu.read_memory(0x032E, 2) == kernal_vector, 'key handler vector not restored'
    assert t.vram(0x1FA00, 512) == kernal_palette, 'palette not restored'
    assert t.emu.read_memory(0x9F34, 1)[0] != 0x62, 'still in tile mode'
    t.emu.screenshot(shots / 'after_quit.png')


def test_led_api_versions(tmp, log):
    """Run the compiled LED wrapper against old/new, release/prerelease ROMs.

    Replace EXTAPI with a recording stub so this checks dispatch independently
    of the ROM's implementation, including restoration of bank and IRQ state.
    """
    sym = dict((n, int(a, 16)) for a, n in
               re.findall(r'al ([0-9A-Fa-f]+) \.(\S+)', (BUILD / 'X16INPUT.sym').read_text()))
    entry = sym['_kbd_leds']
    for version in (46, 47, -47, 48, -48, 49):
        rom = bytearray(ROM.read_bytes())
        rom[0x3F80] = version & 255
        for bank in (0, 4):
            rom[bank * 16384 + 0x3EAB:bank * 16384 + 0x3EAE] = bytes([0x4C, 0x10, 0x04])
        path = Path(tmp) / 'led-test-rom.bin'
        path.write_bytes(rom)
        with X16Agent(EMU, path, fsroot=BUILD, stderr=log) as emu:
            emu.request('load_prg', path=str(BUILD / 'X16INPUT.PRG'))
            emu.write_memory(0x0400, bytes([0x20, entry & 255, entry >> 8, 0xEA]))
            # Record EXTAPI's A, X, carry and number of calls, then return.
            emu.write_memory(0x0410, bytes([0x8D, 0x20, 0x04, 0x8E, 0x21, 0x04,
                                          0x08, 0x68, 0x8D, 0x22, 0x04,
                                          0xEE, 0x23, 0x04, 0x60]))
            emu.request('breakpoint', address=0x0403)
            for bank in (0, 4):
                for flags in (0x20, 0x24):
                    emu.write_memory(0x0420, bytes(4))
                    emu.request('set_registers', pc=0x0400, a=5, p=flags,
                                sp=0x01FF, rom_bank=bank)
                    result = emu.advance(200, unit='instructions')
                    assert result['reason'] == 'breakpoint', (version, result)
                    state = result['state']
                    assert state['rom_bank'] == bank and state['sp'] == 0x01FF, state
                    assert state['p'] & 4 == flags & 4, state
                    a, x, p, calls = emu.read_memory(0x0420, 4)
                    assert calls == (abs(version) >= 48), (version, calls)
                    if calls:
                        assert (a, x, p & 1) == (14, 5, 0), (a, x, p)


def main():
    shots = BUILD / 'screenshots'
    shots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='x16input-') as tmp, \
            open(Path(tmp) / 'led-test.log', 'w') as log:
        test_led_api_versions(tmp, log)
    with tempfile.TemporaryDirectory(prefix='x16input-') as tmp, \
            open(Path(tmp) / 'emulator.log', 'w') as log, \
            X16Agent(EMU, ROM, fsroot=BUILD, stderr=log) as emu:
        t = Tester(emu)
        t.frames(200)                           # boot to READY
        kernal_vector = emu.read_memory(0x032E, 2)
        kernal_palette = t.vram(0x1FA00, 512)
        emu.request('paste', text='LOAD"X16INPUT.PRG",8,1\rRUN\r')
        t.until('_kbd_get', 1200)
        t.frames(5)
        test_startup(t, shots)
        keys = test_keyboard(t)
        test_mouse(t)
        test_joystick(t)
        showcase(t, shots)
        test_quit(t, kernal_vector, kernal_palette, shots)
    print(f'emulator OK: start-up, {keys} keys, LEDs, mouse, joystick, quit; screenshots in {shots}')


if __name__ == '__main__':
    main()
