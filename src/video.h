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

#ifndef _VIDEO_H
#define _VIDEO_H

#include <stdint.h>
#include <cx16.h>

// VRAM layout (the KERNAL text screen at $1B000 and charset at $1F000 stay intact)
#define VRAM_L0_MAP     0x00000UL
#define VRAM_L1_MAP     0x04000UL
#define VRAM_L0_TILES   0x08000UL
#define VRAM_L1_TILES   0x10000UL
#define VRAM_CURSOR     0x18000UL
#define VRAM_PALETTE    0x1FA00UL
#define VRAM_SPRITES    0x1FC00UL

// The KERNAL IRQ also talks to VERA (mouse pointer), so VRAM sequences run with IRQs off
#define VLOCK()   __asm__("php"); __asm__("sei")
#define VUNLOCK() __asm__("plp")

/**
 * @brief Point VERA data port 0 at a bank-0 VRAM address, auto-increment 1
 */
#define vset(addr) do { VERA.control = 0; VERA.address = (addr); VERA.address_hi = VERA_INC_1; } while (0)

/**
 * @brief Save the palette, load all graphics and switch to 640x480 tile mode
 *
 * @return 0 on success, otherwise a non-zero error code
 */
uint8_t video_init(void);

/**
 * @brief Print a load error to the KERNAL text screen
 */
void video_report(uint8_t err);

/**
 * @brief Configure sprite 0 as our mouse pointer (call after mouse_show)
 */
void video_cursor(void);

/**
 * @brief Restore the palette saved by video_init
 */
void video_restore(void);

#endif // _VIDEO_H
