ROOT_DIR := ..
BUILD_DIR := build
GENERATED_DIR := $(BUILD_DIR)/generated
SRC_DIR := src
TOOLS_DIR := tools
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
OBJ := $(BUILD_DIR)/demo.o
ASSET_INC := $(GENERATED_DIR)/demo_assets.inc
ASSET_BIN := $(GENERATED_DIR)/demo_metatiles.bin
MANIFEST := $(GENERATED_DIR)/asset_manifest.txt

.PHONY: all assets check clean

all: $(PRG)

assets: $(ASSET_INC) $(ASSET_BIN)

$(ASSET_INC) $(ASSET_BIN) $(MANIFEST): $(TOOLS_DIR)/build_assets.py
	@mkdir -p $(GENERATED_DIR)
	$(PYTHON) $(TOOLS_DIR)/build_assets.py --source-root $(ROOT_DIR) --out-dir $(GENERATED_DIR)

$(OBJ): $(SRC_DIR)/demo.s $(ASSET_INC) $(ASSET_BIN)
	@mkdir -p $(BUILD_DIR)
	$(AS) $(ASFLAGS) -o $@ $(SRC_DIR)/demo.s

$(ELF): $(OBJ) link.ld
	$(LD) $(LDFLAGS) -o $@ $(OBJ)

$(BIN): $(ELF)
	$(OBJCOPY) -O binary $< $@

$(PRG): $(BIN) $(TOOLS_DIR)/make_prg.py
	$(PYTHON) $(TOOLS_DIR)/make_prg.py $< $@

check: all
	$(PYTHON) $(TOOLS_DIR)/build_assets.py --source-root $(ROOT_DIR) --out-dir $(GENERATED_DIR) --verify-only
	$(PYTHON) $(TOOLS_DIR)/make_prg.py --check $(PRG)

clean:
	rm -rf $(BUILD_DIR)
