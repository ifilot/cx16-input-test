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

#include "ui.h"
#include "video.h"
#include "assets.h"
#include "version.h"

static const char quit_text[] = "HOLD ESC TO QUIT";
static char log_line[LOG_WIDTH + 1];

void __fastcall__ text_at(uint8_t col, uint8_t row, const char* s, uint8_t colour) {
    uint8_t attr = colour << 4;

    VLOCK();
    vset(MAP_L1 + row * MAP_STRIDE + col * 2);
    while(*s) {
        VERA.data0 = *s++;
        VERA.data0 = attr;
    }
    VUNLOCK();
}

void ui_init(void) {
    text_at(1, ROW_TITLE, "COMMANDER X16 INPUT TEST  V" VERSION, COL_TITLE);
    ui_quit_progress(0);
    text_at(2, ROW_PANEL, "LAST EVENTS", COL_TITLE);
    memset(log_line, ' ', LOG_WIDTH);
    log_line[LOG_WIDTH] = 0;
}

void ui_quit_progress(uint8_t lit) {
    uint8_t i;

    VLOCK();
    vset(MAP_L1 + ROW_TITLE * MAP_STRIDE + COL_QUIT * 2);
    for(i = 0; i < sizeof(quit_text) - 1; ++i) {
        VERA.data0 = quit_text[i];
        VERA.data0 = (i < lit ? COL_CYAN : COL_DIM) << 4;
    }
    VUNLOCK();
}

void ui_log(const char* token) {
    uint8_t len = strlen(token) + 1;

    // scroll left and append "token " at the end; the newest event is rightmost
    memmove(log_line, log_line + len, LOG_WIDTH - len);
    memcpy(log_line + LOG_WIDTH - len, token, len - 1);
    log_line[LOG_WIDTH - 1] = ' ';
    text_at(COL_PANEL, ROW_LOG, log_line, COL_DIM);
}

void __fastcall__ hex8(char* dst, uint8_t v) {
    static const char digits[] = "0123456789ABCDEF";

    dst[0] = digits[v >> 4];
    dst[1] = digits[v & 15];
}

void __fastcall__ dec(char* dst, uint16_t v, uint8_t width) {
    while(width--) {
        dst[width] = '0' + v % 10;
        v /= 10;
    }
}
