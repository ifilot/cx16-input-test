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

#include <cbm.h>
#include <stdio.h>

#include "video.h"
#include "assets.h"

// 4bpp tiles, 8x8, map 128 x 64
#define LAYER_CONFIG    ((1 << 6) | (2 << 4) | 0x02)
#define DC_LAYER0       0x10
#define DC_LAYER1       0x20
#define DC_SPRITES      0x40

static uint8_t saved_palette[512];
static uint8_t saved_video;

static void vset_long(uint32_t addr) {
    VERA.control = 0;
    VERA.address = (uint16_t)addr;
    VERA.address_hi = (uint8_t)(addr >> 16) | VERA_INC_1;
}

/**
 * @brief Headerless load of a file from device 8 straight into VRAM
 *
 * File names are written in lower case: the PETSCII charmap turns them into
 * the unshifted (upper case) names the X16 file systems expect.
 *
 * @return non-zero unless exactly `size` bytes were loaded
 */
static uint8_t load_vram(const char* name, uint32_t addr, uint16_t size) {
    cbm_k_setnam(name);
    cbm_k_setlfs(0, 8, 2);
    return cbm_k_load(2 + (uint8_t)(addr >> 16), (uint16_t)addr) != (uint16_t)(addr + size);
}

uint8_t video_init(void) {
    uint16_t i;

    VERA.control = 0;
    saved_video = VERA.display.video;

    // the palette registers read back the last values written (the KERNAL's)
    vset_long(VRAM_PALETTE);
    for(i = 0; i < sizeof(saved_palette); ++i) {
        saved_palette[i] = VERA.data0;
    }

    // hide the layers while loading
    VERA.display.video = saved_video & 0x0F;
    if(load_vram("l0tiles.bin", VRAM_L0_TILES, SIZE_L0TILES) ||
       load_vram("l1tiles.bin", VRAM_L1_TILES, SIZE_L1TILES) ||
       load_vram("l0map.bin", VRAM_L0_MAP, SIZE_L0MAP) ||
       load_vram("l1map.bin", VRAM_L1_MAP, SIZE_L1MAP) ||
       load_vram("cursor.bin", VRAM_CURSOR, SIZE_CURSOR)) {
        VERA.display.video = saved_video;
        return 1;
    }
    if(load_vram("palette.bin", VRAM_PALETTE, SIZE_PALETTE)) {
        video_restore();
        VERA.display.video = saved_video;
        return 2;
    }

    VERA.control = 0;
    VERA.display.hscale = 128;
    VERA.display.vscale = 128;
    VERA.display.border = 0;
    VERA.layer0.config = LAYER_CONFIG;
    VERA.layer0.mapbase = VRAM_L0_MAP >> 9;
    VERA.layer0.tilebase = VRAM_L0_TILES >> 9;
    VERA.layer0.hscroll = 0;
    VERA.layer0.vscroll = 0;
    VERA.layer1.config = LAYER_CONFIG;
    VERA.layer1.mapbase = VRAM_L1_MAP >> 9;
    VERA.layer1.tilebase = VRAM_L1_TILES >> 9;
    VERA.layer1.hscroll = 0;
    VERA.layer1.vscroll = 0;
    VERA.display.video = (saved_video & 0x0F) | DC_LAYER0 | DC_LAYER1 | DC_SPRITES;
    return 0;
}

void video_report(uint8_t err) {
    // this file keeps the PETSCII charmap: file names and KERNAL output need it
    printf("could not load graphics (error %u)\n", err);
}

void video_cursor(void) {
    VLOCK();
    vset_long(VRAM_SPRITES);
    VERA.data0 = (uint8_t)(VRAM_CURSOR >> 5);
    VERA.data0 = (uint8_t)(VRAM_CURSOR >> 13);      // 4bpp
    vset_long(VRAM_SPRITES + 6);
    VERA.data0 = 3 << 2;                            // in front of both layers
    VERA.data0 = (1 << 6) | (1 << 4) | CURSOR_ROW;  // 16 x 16
    VUNLOCK();
}

void video_restore(void) {
    uint16_t i;

    VLOCK();
    vset_long(VRAM_PALETTE);
    for(i = 0; i < sizeof(saved_palette); ++i) {
        VERA.data0 = saved_palette[i];
    }
    VUNLOCK();
}
