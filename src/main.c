/**************************************************************************
 *                                                                        *
 *   Author: Ivo Filot <ivo@ivofilot.nl>                                  *
 *                                                                        *
 *   CX16-INPUT-TEST is free software:                                    *
 *   you can redistribute it and/or modify it under the terms of the      *
 *   GNU General Public License as published by the Free Software         *
 *   Foundation, either version 3 of the License, or (at your option)     *
 *   any later version.                                                   *
 *                                                                        *
 *   CX16-INPUT-TEST is distributed in the hope that it will be useful,   *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty          *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.              *
 *   See the GNU General Public License for more details.                 *
 *                                                                        *
 *   You should have received a copy of the GNU General Public License    *
 *   along with this program.  If not, see http://www.gnu.org/licenses/.  *
 *                                                                        *
 **************************************************************************/

#include <ascii_charmap.h>
#include <string.h>

#include "assets.h"
#include "input.h"
#include "ui.h"
#include "video.h"

#define ESC_QUIT_FRAMES 90      // hold ESC for 1.5 s to quit
#define WHEEL_FRAMES    12      // how long a wheel arrow stays lit
#define NUM_PAD_BUTTONS 12

static uint8_t region_on[NUM_REGIONS];   // 0 or 1 per input
static uint8_t key_down[128];
static uint8_t keys_held;
static uint8_t leds;
static uint8_t esc_frames;
static uint8_t esc_down;
static uint8_t wheel_timer;
static uint8_t mouse_buttons;
static uint16_t last_mouse_x = 0xFFFF;
static uint16_t last_mouse_y = 0xFFFF;
static uint8_t pad_known[3];
static uint8_t pad_present[3];
static uint16_t pad_raw[3];
static uint16_t pad_pressed[3];
static char buf[48];

static const char* const pad_names[NUM_PAD_BUTTONS] = {
    "B", "Y", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT", "A", "X", "L", "R"
};
static const char* const mouse_names[3] = {"LMB", "RMB", "MMB"};

/**
 * @brief Light or release an input by rewriting the map entries it touches
 */
static void set_region(uint8_t r, uint8_t on) {
    const struct rtile* p = rtiles + region_first[r];
    const struct rtile* end = rtiles + region_first[r + 1];
    const struct stile* s;
    uint16_t w;

    if(region_on[r] == on) {
        return;
    }
    region_on[r] = on;
    VLOCK();
    VERA.control = 0;
    for(; p != end; ++p) {
        VERA.address = p->addr;
        VERA.address_hi = VERA_INC_1;
        w = on ? p->on : p->off;
        VERA.data0 = (uint8_t)w;
        VERA.data0 = (uint8_t)(w >> 8);
    }
    // the few map entries two neighbouring keys share
    for(s = shared; s != shared + NUM_SHARED; ++s) {
        if(s->a == r || s->b == r) {
            w = s->entry[region_on[s->a] | (region_on[s->b] << 1)];
            VERA.address = s->addr;
            VERA.address_hi = VERA_INC_1;
            VERA.data0 = (uint8_t)w;
            VERA.data0 = (uint8_t)(w >> 8);
        }
    }
    VUNLOCK();
}

static void set_leds(void) {
    set_region(R_LED_NUM, (leds & LED_NUM) != 0);
    set_region(R_LED_CAPS, (leds & LED_CAPS) != 0);
    set_region(R_LED_SCROLL, (leds & LED_SCROLL) != 0);
    kbd_leds(leds);
}

/**
 * @brief Name of a key, falling back to "K$5A" for keys without a name
 */
static void key_name(char* dst, uint8_t num) {
    const char* name = keynum_name[num];

    if(name) {
        strcpy(dst, name);
    } else {
        memcpy(dst, "K$", 2);
        hex8(dst + 2, num);
        dst[4] = 0;
    }
}

static void on_key(uint8_t code) {
    uint8_t num = code & 0x7F;
    uint8_t up = code & KEY_UP_FLAG;
    uint8_t r = keynum_region[num];

    if(!up == key_down[num]) {
        return;                     // typematic repeat
    }
    key_down[num] = !up;
    keys_held += up ? -1 : 1;
    if(r != REGION_NONE) {
        set_region(r, !up);
    }
    if(num == KEYNUM_ESC) {
        esc_down = !up;
        esc_frames = 0;
        ui_quit_progress(0);
    }
    if(!up) {
        switch(num) {
            case KEYNUM_CAPS:   leds ^= LED_CAPS;   set_leds(); break;
            case KEYNUM_SCROLL: leds ^= LED_SCROLL; set_leds(); break;
            case KEYNUM_NUM:    leds ^= LED_NUM;    set_leds(); break;
        }
    }

    // "KEY $1F  A        DOWN  HELD 01"
    memset(buf, ' ', 31);
    buf[31] = 0;
    memcpy(buf, "KEY $", 5);
    hex8(buf + 5, num);
    key_name(buf + 32, num);
    memcpy(buf + 9, buf + 32, strlen(buf + 32));
    memcpy(buf + 18, up ? "UP  " : "DOWN", 4);
    memcpy(buf + 24, "HELD ", 5);
    dec(buf + 29, keys_held, 2);
    text_at(COL_PANEL, ROW_KEY, buf, COL_WHITE);

    key_name(buf, num);
    strcat(buf, up ? "-" : "+");
    ui_log(buf);
}

static void poll_mouse(void) {
    uint8_t b = mouse_read();
    uint8_t changed = b ^ mouse_buttons;
    uint8_t i;
    int8_t w = mouse_wheel;

    for(i = 0; i < 3; ++i) {
        if(changed & (1 << i)) {
            set_region(R_MOUSE_LMB + i, (b >> i) & 1);
            strcpy(buf, mouse_names[i]);
            strcat(buf, (b >> i) & 1 ? "+" : "-");
            ui_log(buf);
        }
    }
    mouse_buttons = b;

    // negative = wheel moved away from the user (up)
    if(w) {
        set_region(R_MOUSE_WUP, w < 0);
        set_region(R_MOUSE_WDN, w > 0);
        wheel_timer = WHEEL_FRAMES;
        strcpy(buf, "WHEEL");
        buf[5] = w < 0 ? '-' : '+';
        dec(buf + 6, w < -9 || w > 9 ? 9 : (w < 0 ? -w : w), 1);
        buf[7] = 0;
        ui_log(buf);
    } else if(wheel_timer && !--wheel_timer) {
        set_region(R_MOUSE_WUP, 0);
        set_region(R_MOUSE_WDN, 0);
    }

    if(mouse_x != last_mouse_x || mouse_y != last_mouse_y) {
        last_mouse_x = mouse_x;
        last_mouse_y = mouse_y;
        memcpy(buf, "X 0000  Y 0000", 15);
        dec(buf + 2, mouse_x, 4);
        dec(buf + 10, mouse_y, 4);
        text_at(COL_MOUSE, ROW_MOUSE, buf, COL_WHITE);
    }
}

static void show_veil(uint8_t port, uint8_t on) {
    const struct vtile* v = veil[port - 1];
    const struct vtile* end = v + NUM_VEIL;

    VLOCK();
    VERA.control = 0;
    for(; v != end; ++v) {
        VERA.address = v->addr;
        VERA.address_hi = VERA_INC_1;
        VERA.data0 = on ? (uint8_t)v->entry : 0;
        VERA.data0 = on ? (uint8_t)(v->entry >> 8) : 0;
    }
    VUNLOCK();
}

static void poll_pad(uint8_t port) {
    uint8_t present = joy_read(port) == 0;
    uint16_t raw = ((uint16_t)joy_bytes[0] << 8) | joy_bytes[1];
    uint16_t pressed, changed;
    uint8_t i, on, col = port == 1 ? COL_JOY1 : COL_JOY2;
    uint8_t first = R_PAD_FIRST(port);

    // bits are active low: byte 0 = B Y SEL STA UP DN LT RT, byte 1 = A X L R 1 1 1 1
    pressed = present ? ~raw & 0xFFF0 : 0;
    if(!pad_known[port] || present != pad_present[port]) {
        if(pad_known[port]) {
            strcpy(buf, port == 1 ? "J1:" : "J2:");
            strcat(buf, present ? "ON" : "OFF");
            ui_log(buf);
        }
        pad_known[port] = 1;
        pad_present[port] = present;
        show_veil(port, !present);
        if(present) {
            pad_raw[port] = ~raw;               // force the readout below
        } else {
            strcpy(buf, port == 1 ? "JOY1 NOT PRESENT  " : "JOY2 NOT PRESENT  ");
            text_at(col, ROW_JOY, buf, COL_DIM);
        }
    }
    if(present && raw != pad_raw[port]) {
        pad_raw[port] = raw;
        memcpy(buf, "JOY1 PRESENT $0000", 19);
        buf[3] = '0' + port;
        hex8(buf + 14, joy_bytes[0]);
        hex8(buf + 16, joy_bytes[1]);
        text_at(col, ROW_JOY, buf, COL_WHITE);
    }
    changed = pressed ^ pad_pressed[port];
    for(i = 0; i < NUM_PAD_BUTTONS; ++i) {
        if(changed & (0x8000 >> i)) {
            on = (pressed & (0x8000 >> i)) != 0;
            set_region(first + i, on);
            strcpy(buf, port == 1 ? "J1:" : "J2:");
            strcat(buf, pad_names[i]);
            strcat(buf, on ? "+" : "-");
            ui_log(buf);
        }
    }
    pad_pressed[port] = pressed;
}

void main(void) {
    uint8_t code, err;

    err = video_init();
    if(err) {
        video_report(err);
        return;
    }
    ui_init();
    kbd_install();
    mouse_show();
    video_cursor();
    set_leds();

    while(1) {
        wait_frame();
        while((code = kbd_get()) != 0) {
            on_key(code);
        }
        poll_mouse();
        poll_pad(1);
        poll_pad(2);
        if(esc_down) {
            if(++esc_frames >= ESC_QUIT_FRAMES) {
                break;
            }
            if((esc_frames & 7) == 0) {
                ui_quit_progress((uint16_t)esc_frames * 16 / ESC_QUIT_FRAMES);
            }
        }
    }

    kbd_remove();
    mouse_hide();
    kbd_leds(0);
    video_restore();
    cint();
}
