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

#ifndef _INPUT_H
#define _INPUT_H

#include <stdint.h>

#define KEY_UP_FLAG   0x80
#define KEYNUM_ESC    110
#define KEYNUM_CAPS   30
#define KEYNUM_SCROLL 125
#define KEYNUM_NUM    90

#define LED_SCROLL    0x01
#define LED_NUM       0x02
#define LED_CAPS      0x04

/**
 * @brief Hook the KERNAL keynum vector; all key events go to our queue
 */
void kbd_install(void);

/**
 * @brief Restore the original keynum vector
 */
void kbd_remove(void);

/**
 * @brief Fetch the next key event
 *
 * @return keynum (bit 7 set on release), or 0 when no event is waiting
 */
uint8_t kbd_get(void);

/**
 * @brief Set the keyboard lock LEDs (LED_* flags)
 */
void __fastcall__ kbd_leds(uint8_t leds);

/**
 * @brief Enable the mouse pointer for 640x480 using our own sprite 0 image
 */
void mouse_show(void);

/**
 * @brief Disable the mouse pointer
 */
void mouse_hide(void);

/**
 * @brief Read the mouse; updates mouse_x, mouse_y and mouse_wheel
 *
 * @return button bits (0 left, 1 right, 2 middle)
 */
uint8_t mouse_read(void);

extern uint16_t mouse_x;
extern uint16_t mouse_y;
extern int8_t mouse_wheel;

/**
 * @brief Read one SNES controller port (1 or 2); fills joy_bytes
 *
 * @return 0 when a controller is present
 */
uint8_t __fastcall__ joy_read(uint8_t port);

extern uint8_t joy_bytes[3];

/**
 * @brief Wait for the next frame (60 Hz KERNAL jiffy)
 */
void wait_frame(void);

/**
 * @brief Reset the KERNAL screen to its default text mode
 */
void cint(void);

#endif // _INPUT_H
