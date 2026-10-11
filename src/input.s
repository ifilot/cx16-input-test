;
;   Author: Ivo Filot <ivo@ivofilot.nl>
;
;   CX16-INPUT-TEST is free software:
;   you can redistribute it and/or modify it under the terms of the
;   GNU General Public License as published by the Free Software
;   Foundation, either version 3 of the License, or (at your option)
;   any later version.
;
;   CX16-INPUT-TEST is distributed in the hope that it will be useful,
;   but WITHOUT ANY WARRANTY; without even the implied warranty
;   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
;   See the GNU General Public License for more details.
;
;   You should have received a copy of the GNU General Public License
;   along with this program.  If not, see http://www.gnu.org/licenses/.
;
;   KERNAL glue: keyboard keynum hook, mouse, joysticks and keyboard LEDs.
;

.export _kbd_install, _kbd_remove, _kbd_get, _kbd_leds
.export _mouse_show, _mouse_hide, _mouse_read, _mouse_x, _mouse_y, _mouse_wheel
.export _joy_read, _joy_bytes, _joy_got
.export _cint, _wait_frame

KEYHDL          = $032E         ; keynum handler vector (R43+)
CINT            = $FF81
RDTIM           = $FFDE
JOYSTICK_GET    = $FF56
MOUSE_CONFIG    = $FF68
MOUSE_GET       = $FF6B
EXTAPI          = $FEAB
EXTAPI_KBD_LEDS = 14

QUEUE_SIZE      = 32            ; power of two

.zeropage
mpos:           .res 4          ; mouse_get fills X/Y here

.bss
queue:          .res QUEUE_SIZE
head:           .res 1          ; written by the IRQ handler only
tail:           .res 1          ; written by the main program only
old_handler:    .res 2
_mouse_x:       .res 2
_mouse_y:       .res 2
_mouse_wheel:   .res 1
_joy_bytes:     .res 3
jiffy:          .res 1

.code

;
; Hook the keynum vector so every key down/up event lands in our queue.
; The handler returns 0, so no key ever reaches the KERNAL keyboard buffer.
;
.proc _kbd_install
    sei
    lda KEYHDL
    sta old_handler
    lda KEYHDL+1
    sta old_handler+1
    lda #<handler
    sta KEYHDL
    lda #>handler
    sta KEYHDL+1
    stz head
    stz tail
    cli
    rts
.endproc

.proc _kbd_remove
    sei
    lda old_handler
    sta KEYHDL
    lda old_handler+1
    sta KEYHDL+1
    cli
    rts
.endproc

;
; Called by the KERNAL keyboard driver (in IRQ context) with .A = keynum,
; bit 7 set on key up. A full queue drops the event.
;
.proc handler
    phx
    ldx head
    sta queue,x
    inx
    txa
    and #QUEUE_SIZE-1
    cmp tail
    beq full
    sta head
full:
    plx
    lda #0
    rts
.endproc

;
; unsigned char kbd_get(void): next keynum event, or 0 when the queue is empty
;
.proc _kbd_get
    ldx tail
    cpx head
    beq empty
    lda queue,x
    pha
    inx
    txa
    and #QUEUE_SIZE-1
    sta tail
    pla
    ldx #0
    rts
empty:
    lda #0
    tax
    rts
.endproc

;
; void __fastcall__ kbd_leds(unsigned char leds): bit 0 scroll, 1 num, 2 caps
;
.proc _kbd_leds
    tax
    lda #EXTAPI_KBD_LEDS
    clc
    jmp EXTAPI
.endproc

;
; void mouse_show(void): pointer on, 640x480, keep our own sprite 0 image
;
.proc _mouse_show
    lda #$FF
    ldx #80
    ldy #60
    jmp MOUSE_CONFIG
.endproc

.proc _mouse_hide
    lda #0
    ldx #0
    ldy #0
    jmp MOUSE_CONFIG
.endproc

;
; unsigned char mouse_read(void): returns the buttons, updates mouse_x/y/wheel
;
.proc _mouse_read
    ldx #mpos
    jsr MOUSE_GET
    stx _mouse_wheel
    tay
    lda mpos
    sta _mouse_x
    lda mpos+1
    sta _mouse_x+1
    lda mpos+2
    sta _mouse_y
    lda mpos+3
    sta _mouse_y+1
    tya
    ldx #0
    rts
.endproc

;
; unsigned char __fastcall__ joy_read(unsigned char port): fills joy_bytes,
; returns 0 when a controller is present ($FF otherwise)
;
.proc _joy_read
    jsr JOYSTICK_GET
_joy_got:                       ; label for tests: registers hold the joystick state here
    sta _joy_bytes
    stx _joy_bytes+1
    sty _joy_bytes+2
    tya
    ldx #0
    rts
.endproc
_joy_got = _joy_read::_joy_got

.proc _cint
    jmp CINT
.endproc

;
; void wait_frame(void): wait for the next 60 Hz jiffy (cc65 2.19's waitvsync
; still polls the pre-R39 bank register and never returns on current ROMs)
;
.proc _wait_frame
    jsr RDTIM
    sta jiffy
wait:
    jsr RDTIM
    cmp jiffy
    beq wait
    rts
.endproc
