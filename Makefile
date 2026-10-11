EMU ?= $(abspath ../x16-emulator/build/x16emu)
ROM ?= $(abspath ../emulator/rom.bin)
EMU_FLAGS ?= -scale 2
PYTHON ?= python3

CC = cl65
CFLAGS ?= -O
TARGET = -t cx16

BUILD = build
GEN = $(BUILD)/gen
OBJ = $(BUILD)/obj
PRG = $(BUILD)/X16INPUT.PRG
DIST = $(BUILD)/CX16-INPUT-TEST.ZIP
ASSETS = $(addprefix $(BUILD)/,L0TILES.BIN L1TILES.BIN L0MAP.BIN L1MAP.BIN PALETTE.BIN CURSOR.BIN)
OBJS = $(patsubst src/%.c,$(OBJ)/%.o,$(wildcard src/*.c)) \
       $(patsubst src/%.s,$(OBJ)/%.o,$(wildcard src/*.s)) $(OBJ)/assets.o
HEADERS = $(wildcard src/*.h) $(GEN)/assets.h $(GEN)/version.h

.PHONY: all run dist test test-assets font mockup clean

all: $(PRG) $(ASSETS)

$(ASSETS) $(GEN)/assets.c $(GEN)/assets.h &: tools/art.py tools/build_assets.py assets/font/x16-charset.bin
	$(PYTHON) tools/build_assets.py $(BUILD) $(GEN)

$(GEN)/version.h: VERSION
	mkdir -p $(GEN)
	printf '#define VERSION "%s"\n' "$$(cat VERSION)" > $@

$(OBJ)/%.o: src/%.c $(HEADERS) | $(OBJ)
	$(CC) -c $(TARGET) $(CFLAGS) -I src -I $(GEN) -o $@ $<

$(OBJ)/%.o: src/%.s | $(OBJ)
	$(CC) -c $(TARGET) -o $@ $<

$(OBJ)/assets.o: $(GEN)/assets.c $(GEN)/assets.h | $(OBJ)
	$(CC) -c $(TARGET) $(CFLAGS) -I $(GEN) -o $@ $<

$(PRG): $(OBJS)
	$(CC) $(TARGET) -o $@ -m $(BUILD)/X16INPUT.map -Ln $(BUILD)/X16INPUT.sym $(OBJS)

$(OBJ):
	mkdir -p $@

run: all
	cd $(BUILD) && "$(EMU)" -rom "$(ROM)" -prg X16INPUT.PRG -run $(EMU_FLAGS)

dist: all
	rm -f $(DIST)
	zip -q --junk-paths $(DIST) $(PRG) $(ASSETS)
	unzip -tq $(DIST)
	@echo "Distribution: $(DIST)"

test: test-assets
	$(PYTHON) tests/test_emulator.py

# no emulator needed (used by CI)
test-assets: all
	$(PYTHON) tests/test_assets.py

# refresh the 8x8 character sets from the X16 ROM
font:
	$(PYTHON) -c "import sys; d = open(sys.argv[1], 'rb').read(); open(sys.argv[2], 'wb').write(d[6 * 16384:6 * 16384 + 4096])" "$(ROM)" assets/font/x16-charset.bin

mockup:
	$(PYTHON) tools/art.py

clean:
	rm -rf $(BUILD)
