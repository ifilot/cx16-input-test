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

#ifndef _UI_H
#define _UI_H

#include <stdint.h>

// text rows and columns (8x8 cells on layer 1)
#define ROW_TITLE   1
#define ROW_JOY     19
#define ROW_MOUSE   21
#define ROW_PANEL   23
#define ROW_KEY     25
#define ROW_LOG     27
#define COL_QUIT    63
#define COL_JOY1    2
#define COL_JOY2    50
#define COL_MOUSE   33
#define COL_PANEL   3
#define LOG_WIDTH   74

/**
 * @brief Write a string to the text layer
 *
 * @param col    column (0-79)
 * @param row    row (0-29)
 * @param s      ASCII string
 * @param colour text colour (COL_* from assets.h)
 */
void __fastcall__ text_at(uint8_t col, uint8_t row, const char* s, uint8_t colour);

/**
 * @brief Draw all static captions
 */
void ui_init(void);

/**
 * @brief Show how far ESC has been held (0-16 characters lit)
 */
void ui_quit_progress(uint8_t lit);

/**
 * @brief Append an event token to the log line, e.g. "A+" or "J1:START-"
 */
void ui_log(const char* token);

/**
 * @brief Format a byte as two hex digits into dst
 */
void __fastcall__ hex8(char* dst, uint8_t v);

/**
 * @brief Format a value as `width` decimal digits (zero padded) into dst
 */
void __fastcall__ dec(char* dst, uint16_t v, uint8_t width);

#endif // _UI_H
