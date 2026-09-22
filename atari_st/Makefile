ROOT_DIR := ..
BUILD_DIR := build
GENERATED_DIR := $(BUILD_DIR)/generated
SRC_DIR := src
TOOLS_DIR := tools
ASSET_INPUTS := $(ROOT_DIR)/src/bins.xml $(ROOT_DIR)/src/Z_05.asm $(ROOT_DIR)/src/Z_06.asm \
	$(wildcard $(ROOT_DIR)/bin/dat/CommonBackgroundPatterns.dat $(ROOT_DIR)/ext/Original.nes)
TOOLCHAIN_PREFIX ?= m68k-linux-gnu-
AS := $(TOOLCHAIN_PREFIX)as
LD := $(TOOLCHAIN_PREFIX)ld
OBJCOPY := $(TOOLCHAIN_PREFIX)objcopy
PYTHON ?= python3

ASFLAGS := -m68000 -I $(GENERATED_DIR) -I $(SRC_DIR)
LDFLAGS := -T link.ld -nostdlib -e _start

ELF := $(BUILD_DIR)/zelda_st.elf
BIN := $(BUILD_DIR)/zelda_st.bin
PRG := $(BUILD_DIR)/ZELDAST.PRG
OBJ := $(BUILD_DIR)/zelda_st.o
MAIN_SRC := $(SRC_DIR)/main.s
SOURCES := $(wildcard $(SRC_DIR)/*.s)
# main.s .includes the other modules, so one assembler run covers them all.
GENERATED := $(GENERATED_DIR)/assets.inc $(GENERATED_DIR)/metatiles.bin \
	$(GENERATED_DIR)/metatile_tiles.bin $(GENERATED_DIR)/room_maps.bin \
	$(GENERATED_DIR)/link_sprites.bin $(GENERATED_DIR)/hud_tiles.bin \
	$(GENERATED_DIR)/asset_manifest.txt

.PHONY: all assets check clean run screenshot

all: $(PRG)

assets: $(GENERATED)

$(GENERATED) &: $(TOOLS_DIR)/build_assets.py $(ASSET_INPUTS)
	@mkdir -p $(GENERATED_DIR)
	$(PYTHON) $(TOOLS_DIR)/build_assets.py --source-root $(ROOT_DIR) --out-dir $(GENERATED_DIR)

$(OBJ): $(SOURCES) $(GENERATED)
	@mkdir -p $(BUILD_DIR)
	$(AS) $(ASFLAGS) -o $@ $(MAIN_SRC)

$(ELF): $(OBJ) link.ld
	$(LD) $(LDFLAGS) -o $@ $(OBJ)

$(BIN): $(ELF)
	$(OBJCOPY) -O binary $< $@

$(PRG): $(BIN) $(TOOLS_DIR)/make_prg.py
	$(PYTHON) $(TOOLS_DIR)/make_prg.py $< $@

check: all
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	$(PYTHON) $(TOOLS_DIR)/build_assets.py --source-root $(ROOT_DIR) --out-dir $(GENERATED_DIR) --verify-only
	$(PYTHON) $(TOOLS_DIR)/make_prg.py --check $(PRG)

# Headless Hatari run that renders the framebuffer to a PNG. TOS=<path to a
# TOS image> is required; see tools/screenshot.py --help for the other options.
screenshot: all
	$(PYTHON) $(TOOLS_DIR)/screenshot.py --prg $(PRG) --out $(BUILD_DIR)/screen.png

clean:
	rm -rf $(BUILD_DIR)
