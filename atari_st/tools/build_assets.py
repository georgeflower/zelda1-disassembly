#!/usr/bin/env python3
"""Convert Zelda 1 ROM data into Atari ST planar assets.

Everything here reads the original data through `src/bins.xml` (or an already
extracted `bin/dat/` tree) and re-encodes it for a 320x200 four-bitplane ST
screen. No Nintendo data is stored in this repository; the ROM stays local.
"""
from __future__ import annotations

import argparse
import re
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

METATILE_WIDTH = 16
METATILE_HEIGHT = 16
METATILE_BYTES = METATILE_HEIGHT * 8
CHR_TILE_BYTES = 16

# Pattern blocks are raw CHR streams that the game copies to fixed PPU addresses.
# CommonPatternVramAddrs (Z_02.asm) and PatternBlockPpuAddrs (Z_03.asm) fix where
# each one lands, which in turn fixes the tile index each blob starts at.
OW_BG_COMMON_NAME = "dat/CommonBackgroundPatterns.dat"
OW_BG_BLOCK_NAME = "dat/PatternBlockOWBG.dat"
OW_BG_MISC_NAME = "dat/CommonMiscPatterns.dat"
OW_SP_COMMON_NAME = "dat/CommonSpritePatterns.dat"
OW_SP_BLOCK_NAME = "dat/PatternBlockOWSP.dat"
OW_BG_COMMON_FIRST_TILE = 0x00  # PPU $1000
OW_BG_BLOCK_FIRST_TILE = 0x70  # PPU $1700
OW_BG_MISC_FIRST_TILE = 0xF2  # PPU $1F20
OW_SP_COMMON_FIRST_TILE = 0x00  # PPU $0000
OW_SP_BLOCK_FIRST_TILE = 0x8E  # PPU $08E0

ROOM_LAYOUTS_OW_NAME = "dat/RoomLayoutsOW.dat"
LEVEL_BLOCK_OW_NAME = "dat/LevelBlockOW.dat"
LEVEL_INFO_OW_NAME = "dat/LevelInfoOW.dat"

OW_ROOM_COLS = 16
OW_ROOM_ROWS = 11
OW_ROOM_COUNT = 128
OW_COLUMNS_PER_ROOM = 0x10
LEVEL_BLOCK_TABLE_SIZE = 128
# NextRoomIdOffsets (Z_05.asm) adds -16/+16/-1/+1, so the overworld map is a
# 16-wide grid of the 128 rooms.
OW_GRID_WIDTH = 16
OW_GRID_HEIGHT = OW_ROOM_COUNT // OW_GRID_WIDTH

# LevelInfo begins at $6B7E and opens with a 36-byte PPU transfer buffer:
# a 3-byte header, 8 palette rows of 4 NES colour indices, then a $FF terminator.
LEVEL_INFO_BASE = 0x6B7E
LEVEL_INFO_PALETTE_OFFSET = 3
LEVEL_INFO_START_Y = 0x6BA6 - LEVEL_INFO_BASE
LEVEL_INFO_START_ROOM_ID = 0x6BAD - LEVEL_INFO_BASE
PALETTE_ROWS = 8
PALETTE_ROW_COLORS = 4
BACKGROUND_PALETTE_ROWS = 4
ST_PALETTE_SIZE = 16

# InitMode3_Sub8 (Z_05.asm) drops Link in the middle horizontally, facing up,
# at the Y the level info supplies.
LINK_START_X = 0x78
LINK_START_DIR = 0x08
# Zelda's direction bits, used throughout the disassembly.
DIR_RIGHT, DIR_LEFT, DIR_DOWN, DIR_UP = 0x01, 0x02, 0x04, 0x08

# Squares covered by the "inner" palette selector rather than the "outer" one,
# derived from FillPlayAreaAttrs in Z_05.asm.
OW_INNER_COL_RANGE = range(2, 14)
OW_INNER_ROW_RANGE = range(2, 9)

# Link's walking frames. ObjAnimations[0] points at ObjAnimFrameHeap[0], whose
# first four entries are the left tile of each frame (Z_01.asm). The NES draws him
# as two 8x16 sprites, so a frame covers tiles T, T+1 (left) and T+2, T+3 (right).
LINK_FRAME_TILES = (0x00, 0x04, 0x08, 0x0C)
# ObjAnimAttrHeap[0..3] are all 0, i.e. sprite palette row 0 == NES palette row 4.
LINK_PALETTE_ROW = 4
# SetUpWalkingSprites picks tile $00/$04 for horizontal and flips for left; for
# vertical it uses one tile and flips on the second walk frame.
LINK_FRAMES = (
    ("right_a", 0x00, False),
    ("right_b", 0x04, False),
    ("left_a", 0x00, True),
    ("left_b", 0x04, True),
    ("down_a", 0x08, False),
    ("down_b", 0x08, True),
    ("up_a", 0x0C, False),
    ("up_b", 0x0C, True),
)
SPRITE_FRAME_WORDS = 5  # four bitplanes plus an opacity mask
SPRITE_FRAME_BYTES = METATILE_HEIGHT * SPRITE_FRAME_WORDS * 2

# HUD glyphs. Zelda's font puts '0'-'9' at $00-$09 and 'A'-'Z' at $0A-$23, so 'X'
# (the multiplication sign in the counters) is $21 and blank is $24. Heart tiles
# come from Z_01.asm:3277; the counter icons from StatusBarStaticsTransferBuf.
# The attribute bytes at the head of that buffer put text on palette row 0 and
# the hearts and icons on row 1.
HUD_TEXT_ROW = 0
HUD_ACCENT_ROW = 1
HUD_TILE_BYTES = 8 * 4  # eight rows, one byte per bitplane
HUD_GLYPHS = (
    ("BLANK", 0x24, HUD_TEXT_ROW),
    *((f"DIGIT{digit}", digit, HUD_TEXT_ROW) for digit in range(10)),
    ("X", 0x21, HUD_TEXT_ROW),
    ("L", 0x15, HUD_TEXT_ROW),
    ("I", 0x12, HUD_TEXT_ROW),
    ("F", 0x0F, HUD_TEXT_ROW),
    ("E", 0x0E, HUD_TEXT_ROW),
    ("HEART_FULL", 0xF2, HUD_ACCENT_ROW),
    ("HEART_HALF", 0x65, HUD_ACCENT_ROW),
    ("HEART_EMPTY", 0x66, HUD_ACCENT_ROW),
    ("RUPEE", 0xF7, HUD_ACCENT_ROW),
    ("KEY", 0xF9, HUD_ACCENT_ROW),
    ("BOMB", 0x61, HUD_ACCENT_ROW),
)

# GetCollidableTile (Z_07.asm) treats a tile as blocking when it is at or above
# ObjectFirstUnwalkableTile, except for the tiles in this list, which it rewrites
# to a walkable value first. ObjectRoomBoundsOW (Z_05.asm) supplies both the
# threshold and the room bounds the engine uses.
OW_FIRST_UNWALKABLE_TILE = 0x89
OW_WALKABLE_TILES = (0x8D, 0x91, 0x9C, 0xAC, 0xAD, 0xCC, 0xD2, 0xD5, 0xDF)
OW_ROOM_BOUNDS = (0x11, 0xE0, 0x4E, 0xCD)

# 2C02 PPU colour output, used to map NES colour indices onto the ST's 3-bit RGB.
NES_RGB = (
    (0x74, 0x74, 0x74), (0x24, 0x18, 0x8C), (0x00, 0x00, 0xA8), (0x44, 0x00, 0x9C),
    (0x8C, 0x00, 0x74), (0xA8, 0x00, 0x10), (0xA4, 0x00, 0x00), (0x7C, 0x08, 0x00),
    (0x40, 0x2C, 0x00), (0x00, 0x44, 0x00), (0x00, 0x50, 0x00), (0x00, 0x3C, 0x14),
    (0x18, 0x3C, 0x5C), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
    (0xBC, 0xBC, 0xBC), (0x00, 0x70, 0xEC), (0x20, 0x38, 0xEC), (0x80, 0x00, 0xF0),
    (0xBC, 0x00, 0xBC), (0xE4, 0x00, 0x58), (0xD8, 0x28, 0x00), (0xC8, 0x4C, 0x0C),
    (0x88, 0x70, 0x00), (0x00, 0x94, 0x00), (0x00, 0xA8, 0x00), (0x00, 0x90, 0x38),
    (0x00, 0x80, 0x88), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
    (0xFC, 0xFC, 0xFC), (0x3C, 0xBC, 0xFC), (0x5C, 0x94, 0xFC), (0xCC, 0x88, 0xFC),
    (0xF4, 0x78, 0xFC), (0xFC, 0x74, 0xB4), (0xFC, 0x74, 0x60), (0xFC, 0x98, 0x38),
    (0xF0, 0xBC, 0x3C), (0x80, 0xD0, 0x10), (0x4C, 0xDC, 0x48), (0x58, 0xF8, 0x98),
    (0x00, 0xE8, 0xD8), (0x78, 0x78, 0x78), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
    (0xFC, 0xFC, 0xFC), (0xA8, 0xE4, 0xFC), (0xC4, 0xD4, 0xFC), (0xD4, 0xC8, 0xFC),
    (0xFC, 0xC4, 0xFC), (0xFC, 0xC4, 0xD8), (0xFC, 0xBC, 0xB0), (0xFC, 0xD8, 0xA8),
    (0xFC, 0xE4, 0xA0), (0xE0, 0xFC, 0xA0), (0xA8, 0xF0, 0xBC), (0xB0, 0xFC, 0xCC),
    (0x9C, 0xFC, 0xF0), (0xC4, 0xC4, 0xC4), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
)

# Stand-in NES palette used when no ROM is available. Sixteen distinct colours so
# the placeholder build exercises exactly the same merged-palette path.
PLACEHOLDER_NES_PALETTE = bytes(
    (
        0x0F, 0x30, 0x00, 0x12,
        0x0F, 0x16, 0x27, 0x36,
        0x0F, 0x1A, 0x37, 0x17,
        0x0F, 0x29, 0x02, 0x22,
        0x0F, 0x0C, 0x1C, 0x2C,
        0x0F, 0x30, 0x27, 0x17,
        0x0F, 0x16, 0x27, 0x30,
        0x0F, 0x0C, 0x1C, 0x2C,
    )
)


def nes_color_to_st(color_index: int) -> int:
    red, green, blue = NES_RGB[color_index & 0x3F]
    return ((red >> 5) << 8) | ((green >> 5) << 4) | (blue >> 5)


@dataclass(frozen=True)
class PaletteMap:
    """One ST palette shared by every NES palette row.

    The NES gives four background rows and four sprite rows of three colours each
    plus a universal backdrop. For the overworld those collapse to sixteen
    distinct ST colours, so a single hardware palette covers tiles and sprites
    with no loss. `table[row][pixel]` is the ST entry a CHR pixel value maps to.
    """

    st_colors: tuple[int, ...]
    table: tuple[tuple[int, ...], ...]

    def index(self, row: int, pixel: int) -> int:
        return self.table[row][pixel]


def build_palette_map(palette_bytes: Sequence[int]) -> PaletteMap:
    """Merge all eight NES palette rows into one 16-entry ST palette."""
    backdrop = palette_bytes[0]
    order: list[int] = []
    table: list[tuple[int, ...]] = []
    for row in range(PALETTE_ROWS):
        entries = []
        for pixel in range(PALETTE_ROW_COLORS):
            # Pixel 0 always shows the universal backdrop, whichever row it is.
            color = backdrop if pixel == 0 else palette_bytes[row * PALETTE_ROW_COLORS + pixel]
            if color not in order:
                order.append(color)
            entries.append(order.index(color))
        table.append(tuple(entries))

    if len(order) > ST_PALETTE_SIZE:
        raise SystemExit(
            f"NES palette needs {len(order)} distinct colours but the ST only has {ST_PALETTE_SIZE}"
        )

    st_colors = [nes_color_to_st(color) for color in order]
    st_colors.extend([0] * (ST_PALETTE_SIZE - len(st_colors)))
    return PaletteMap(st_colors=tuple(st_colors), table=tuple(table))


def extract_binary(source_root: Path, name: str) -> bytes | None:
    """Read a named blob listed in src/bins.xml, preferring an already-extracted copy."""
    direct = source_root / "bin" / name
    if direct.exists():
        return direct.read_bytes()

    rom_path = source_root / "ext" / "Original.nes"
    bins_path = source_root / "src" / "bins.xml"
    if not rom_path.exists() or not bins_path.exists():
        return None

    rom = rom_path.read_bytes()
    if len(rom) < 16 or rom[:4] != b"NES\x1a":
        raise ValueError(f"{rom_path} is not a valid iNES ROM image")
    trainer_bytes = 512 if (rom[6] & 0x04) else 0
    # bins.xml offsets are relative to the start of PRG ROM (see build.ps1).
    data_offset = 16 + trainer_bytes

    xml_root = ET.fromstring(bins_path.read_text(encoding="utf-8"))
    for binary in xml_root.iterfind(".//Binary"):
        if binary.attrib.get("FileName") != name:
            continue
        offset = int(binary.attrib["Offset"], 0) + data_offset
        length = int(binary.attrib["Length"], 0)
        if offset + length > len(rom):
            raise ValueError(
                f"{rom_path} is too short for {name}: need {offset + length} bytes, found {len(rom)}"
            )
        return rom[offset : offset + length]

    return None


def require_binary(source_root: Path, name: str) -> bytes:
    data = extract_binary(source_root, name)
    if data is None:
        raise SystemExit(f"Could not obtain {name} from bin/ or ext/Original.nes")
    return data


_BYTE_LINE = re.compile(r"^\s*\.BYTE\s+(.+?)\s*$", re.IGNORECASE)


def parse_asm_byte_table(asm_text: str, label: str) -> list[int]:
    """Read a contiguous run of .BYTE directives following `label:` in a disassembly file."""
    marker = f"\n{label}:"
    start = asm_text.find(marker)
    if start < 0:
        raise SystemExit(f"Could not find label {label} in the disassembly")

    values: list[int] = []
    for line in asm_text[start + len(marker) :].splitlines()[1:]:
        if not line.strip():
            continue
        match = _BYTE_LINE.match(line)
        if not match:
            break
        for item in match.group(1).split(","):
            item = item.strip()
            if item:
                values.append(int(item.replace("$", "0x"), 0))
    return values


def parse_column_heaps(asm_text: str) -> list[int]:
    """The ColumnHeapOW tables are laid out contiguously and indexed via ColumnDirectoryOW."""
    blob: list[int] = []
    for digit in "0123456789ABCDEF":
        label = f"ColumnHeapOW{digit}"
        if f"\n{label}:" not in asm_text:
            break
        blob.extend(parse_asm_byte_table(asm_text, label))
    if not blob:
        raise SystemExit("Could not find any ColumnHeapOW tables in the disassembly")
    return blob


def parse_column_directory(asm_text: str) -> list[int]:
    """Convert the directory's absolute addresses into offsets into the heap blob."""
    raw = parse_asm_byte_table(asm_text, "ColumnDirectoryOW")
    addresses = [raw[i] | (raw[i + 1] << 8) for i in range(0, len(raw), 2)]
    base = addresses[0]
    return [address - base for address in addresses]


def decode_column(heap: list[int], start: int, column_index: int) -> list[int]:
    """Walk a column heap to the requested column and expand it to OW_ROOM_ROWS squares."""
    remaining = column_index
    pos = start - 1
    while True:
        pos += 1
        if pos >= len(heap):
            raise SystemExit(f"Ran off the end of a column heap looking for column {column_index}")
        if heap[pos] & 0x80:
            remaining -= 1
            if remaining < 0:
                break

    squares: list[int] = []
    repeat_state = 0
    while len(squares) < OW_ROOM_ROWS:
        descriptor = heap[pos]
        squares.append(descriptor & 0x3F)
        if descriptor & 0x40:
            # Bit 6 means "draw this square twice"; the toggle mirrors [$0C] in LayoutRoomOW.
            repeat_state ^= 0x40
            if repeat_state == 0:
                pos += 1
        else:
            pos += 1
    return squares


def square_to_tiles(square_index: int, primary: list[int], secondary: list[int]) -> tuple[int, int, int, int]:
    """Return (top-left, top-right, bottom-left, bottom-right) CHR indices for a square."""
    if square_index >= 0x10:
        base = primary[square_index]
        quad = (base, base + 1, base + 2, base + 3)
    else:
        offset = square_index * 4
        quad = tuple(secondary[offset : offset + 4])
    # WriteSquareOW stores the quad column-major: (col,row), (col,row+1), (col+1,row), (col+1,row+1).
    return quad[0], quad[2], quad[1], quad[3]


def tile_is_blocking(tile: int) -> bool:
    """Apply GetCollidableTile's walkability rule to a single background tile."""
    if tile in OW_WALKABLE_TILES:
        return False
    return tile >= OW_FIRST_UNWALKABLE_TILE


def decode_nes_chr(data: bytes) -> list[list[list[int]]]:
    if len(data) % CHR_TILE_BYTES != 0:
        raise ValueError(f"CHR data length {len(data)} is not divisible by {CHR_TILE_BYTES}")

    tiles: list[list[list[int]]] = []
    for tile_offset in range(0, len(data), CHR_TILE_BYTES):
        plane0 = data[tile_offset : tile_offset + 8]
        plane1 = data[tile_offset + 8 : tile_offset + 16]
        tile_rows: list[list[int]] = []
        for row in range(8):
            row_pixels = []
            lo = plane0[row]
            hi = plane1[row]
            for bit in range(7, -1, -1):
                pixel = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)
                row_pixels.append(pixel)
            tile_rows.append(row_pixels)
        tiles.append(tile_rows)
    return tiles


def assemble_pattern_table(blocks: Iterable[tuple[int, bytes]]) -> list[list[list[int]]]:
    """Lay CHR blobs into a 256-entry pattern table at their runtime tile indices."""
    tiles: list[list[list[int]]] = [[[0] * 8 for _ in range(8)] for _ in range(256)]
    for base, data in blocks:
        for offset, tile in enumerate(decode_nes_chr(data)):
            index = base + offset
            if index < len(tiles):
                tiles[index] = tile
    return tiles


def build_placeholder_tiles() -> list[list[list[int]]]:
    """Procedural stand-in art so the target still builds without any ROM."""
    tiles: list[list[list[int]]] = []
    for tile_index in range(256):
        rows: list[list[int]] = []
        for y in range(8):
            row = []
            for x in range(8):
                selector = tile_index % 6
                if selector == 0:
                    pixel = 1 + ((x + y + tile_index) % 3)
                elif selector == 1:
                    pixel = 1 + ((x // 2 + tile_index) % 3)
                elif selector == 2:
                    pixel = 1 + ((y // 2 + tile_index) % 3)
                elif selector == 3:
                    pixel = 1 + (((x ^ y) + tile_index) % 3)
                elif selector == 4:
                    pixel = 3 if x in (0, 7) or y in (0, 7) else 1
                else:
                    pixel = 2 if (x - 3) * (x - 3) + (y - 3) * (y - 3) <= 8 else 0
                row.append(pixel)
            rows.append(row)
        tiles.append(rows)
    return tiles


def build_placeholder_rooms() -> tuple[list[list[int]], list[tuple[int, tuple[int, int, int, int]]]]:
    """A handful of synthetic rooms with the same shape as the decoded overworld."""
    metatiles = [
        (0, (0x10, 0x11, 0x12, 0x13)),
        (1, (0x20, 0x21, 0x22, 0x23)),
        (2, (0x30, 0x31, 0x32, 0x33)),
        (3, (0x90, 0x91, 0x92, 0x93)),
    ]
    rooms: list[list[int]] = []
    for room_id in range(4):
        grid: list[int] = []
        for row in range(OW_ROOM_ROWS):
            for col in range(OW_ROOM_COLS):
                edge = row in (0, OW_ROOM_ROWS - 1) or col in (0, OW_ROOM_COLS - 1)
                grid.append(3 if edge else (room_id + col + row) % 3)
        rooms.append(grid)
    return rooms, metatiles


@dataclass(frozen=True)
class AssetBundle:
    source_note: str
    palette: PaletteMap
    bg_tiles: list[list[list[int]]]
    sprite_tiles: list[list[list[int]]]
    rooms: list[list[int]]
    metatiles: list[tuple[int, tuple[int, int, int, int]]]
    start_room: int
    start_y: int


def load_ow_background_tiles(source_root: Path) -> list[list[list[int]]] | None:
    """Rebuild the background pattern table that the overworld sees at runtime."""
    common = extract_binary(source_root, OW_BG_COMMON_NAME)
    block = extract_binary(source_root, OW_BG_BLOCK_NAME)
    if common is None or block is None:
        return None
    misc = extract_binary(source_root, OW_BG_MISC_NAME) or b""
    return assemble_pattern_table(
        (
            (OW_BG_COMMON_FIRST_TILE, common),
            (OW_BG_BLOCK_FIRST_TILE, block),
            (OW_BG_MISC_FIRST_TILE, misc),
        )
    )


def load_ow_sprite_tiles(source_root: Path) -> list[list[list[int]]] | None:
    """Rebuild the sprite pattern table that the overworld sees at runtime."""
    common = extract_binary(source_root, OW_SP_COMMON_NAME)
    if common is None:
        return None
    block = extract_binary(source_root, OW_SP_BLOCK_NAME) or b""
    return assemble_pattern_table(
        ((OW_SP_COMMON_FIRST_TILE, common), (OW_SP_BLOCK_FIRST_TILE, block))
    )


def decode_overworld(
    source_root: Path, chr_tiles: list[list[list[int]]]
) -> tuple[list[list[int]], list[tuple[int, tuple[int, int, int, int]]], bytes, int, int]:
    asm_text = (source_root / "src" / "Z_05.asm").read_text(encoding="utf-8", errors="replace")
    primary = parse_asm_byte_table(asm_text, "PrimarySquaresOW")
    secondary = parse_asm_byte_table(asm_text, "SecondarySquaresOW")
    heap = parse_column_heaps(asm_text)
    directory = parse_column_directory(
        (source_root / "src" / "Z_06.asm").read_text(encoding="utf-8", errors="replace")
    )

    layouts = require_binary(source_root, ROOM_LAYOUTS_OW_NAME)
    level_block = require_binary(source_root, LEVEL_BLOCK_OW_NAME)
    level_info = require_binary(source_root, LEVEL_INFO_OW_NAME)

    attrs_a = level_block[0:LEVEL_BLOCK_TABLE_SIZE]
    attrs_b = level_block[LEVEL_BLOCK_TABLE_SIZE : LEVEL_BLOCK_TABLE_SIZE * 2]
    attrs_d = level_block[LEVEL_BLOCK_TABLE_SIZE * 3 : LEVEL_BLOCK_TABLE_SIZE * 4]

    palette_bytes = level_info[
        LEVEL_INFO_PALETTE_OFFSET : LEVEL_INFO_PALETTE_OFFSET + PALETTE_ROWS * PALETTE_ROW_COLORS
    ]

    metatile_ids: dict[tuple[int, tuple[int, int, int, int]], int] = {}
    metatiles: list[tuple[int, tuple[int, int, int, int]]] = []
    rooms: list[list[int]] = []

    for room_id in range(OW_ROOM_COUNT):
        unique_id = attrs_d[room_id] & 0x3F
        base = unique_id * OW_COLUMNS_PER_ROOM
        descriptors = layouts[base : base + OW_COLUMNS_PER_ROOM]
        if len(descriptors) < OW_COLUMNS_PER_ROOM:
            raise SystemExit(f"RoomLayoutsOW is too short for unique room {unique_id}")

        outer = attrs_a[room_id] & 0x03
        inner = attrs_b[room_id] & 0x03

        columns = [decode_column(heap, directory[d >> 4], d & 0x0F) for d in descriptors]

        grid: list[int] = []
        for row in range(OW_ROOM_ROWS):
            for col in range(OW_ROOM_COLS):
                slot = inner if (col in OW_INNER_COL_RANGE and row in OW_INNER_ROW_RANGE) else outer
                quad = square_to_tiles(columns[col][row], primary, secondary)
                key = (slot, quad)
                index = metatile_ids.get(key)
                if index is None:
                    index = len(metatiles)
                    metatile_ids[key] = index
                    metatiles.append(key)
                grid.append(index)
        rooms.append(grid)

    if len(metatiles) > 256:
        raise SystemExit(f"Overworld needs {len(metatiles)} metatiles, which exceeds the 256 a byte index allows")

    highest = max(tile for _, quad in metatiles for tile in quad)
    if highest >= len(chr_tiles):
        raise SystemExit(f"Overworld references CHR tile {highest:#04x} but only {len(chr_tiles)} were loaded")

    return rooms, metatiles, palette_bytes, level_info[LEVEL_INFO_START_ROOM_ID], level_info[LEVEL_INFO_START_Y]


def load_assets(source_root: Path, require_source: bool = False) -> AssetBundle:
    bg_tiles = load_ow_background_tiles(source_root)
    sprite_tiles = load_ow_sprite_tiles(source_root)
    if bg_tiles is not None and sprite_tiles is not None:
        rooms, metatiles, palette_bytes, start_room, start_y = decode_overworld(source_root, bg_tiles)
        return AssetBundle(
            source_note="ROM-derived overworld tiles, sprites, rooms and palette",
            palette=build_palette_map(palette_bytes),
            bg_tiles=bg_tiles,
            sprite_tiles=sprite_tiles,
            rooms=rooms,
            metatiles=metatiles,
            start_room=start_room,
            start_y=start_y,
        )

    if require_source:
        raise SystemExit(
            f"No pattern source found. Provide {source_root / 'bin'} "
            f"or {source_root / 'ext' / 'Original.nes'}, or drop --require-source to build with placeholders."
        )

    print(
        "WARNING: the ROM pattern blocks and ext/Original.nes are both missing.\n"
        "         Building with procedurally generated placeholder tiles -- the\n"
        "         result will NOT resemble the original game artwork.",
    )
    placeholder_tiles = build_placeholder_tiles()
    rooms, metatiles = build_placeholder_rooms()
    return AssetBundle(
        source_note="generated placeholder CHR (Original.nes not available)",
        palette=build_palette_map(PLACEHOLDER_NES_PALETTE),
        bg_tiles=placeholder_tiles,
        sprite_tiles=placeholder_tiles,
        rooms=rooms,
        metatiles=metatiles,
        start_room=0,
        start_y=0x8D,
    )


def pack_st_row(pixels: Iterable[int]) -> bytes:
    """Pack 16 palette indices into four big-endian bitplane words."""
    plane_words = [0, 0, 0, 0]
    for x, pixel in enumerate(pixels):
        mask = 1 << (15 - x)
        for plane in range(4):
            if pixel & (1 << plane):
                plane_words[plane] |= mask
    return b"".join(word.to_bytes(2, "big") for word in plane_words)


def pack_hud_row(pixels: Sequence[int]) -> bytes:
    """Pack 8 palette indices into one byte per bitplane.

    An 8-pixel tile is exactly one byte of an ST plane word, so the HUD can be
    drawn with plain byte stores instead of the shifting sprite blitter.
    """
    planes = [0, 0, 0, 0]
    for x, pixel in enumerate(pixels):
        mask = 1 << (7 - x)
        for plane in range(4):
            if pixel & (1 << plane):
                planes[plane] |= mask
    return bytes(planes)


def build_metatile_bytes(
    chr_tiles: list[list[list[int]]],
    palette: PaletteMap,
    palette_row: int,
    tile_indices: tuple[int, int, int, int],
) -> bytes:
    tl, tr, bl, br = (chr_tiles[index] for index in tile_indices)
    packed = bytearray()
    for row in range(METATILE_HEIGHT):
        if row < 8:
            left, right = tl[row], tr[row]
        else:
            left, right = bl[row - 8], br[row - 8]
        packed.extend(pack_st_row(palette.index(palette_row, value) for value in (left + right)))
    return bytes(packed)


def build_sprite_frame(
    chr_tiles: list[list[list[int]]],
    palette: PaletteMap,
    palette_row: int,
    first_tile: int,
    flip: bool,
) -> bytes:
    """Encode one 16x16 NES sprite pair as four bitplane words plus an opacity mask.

    The NES draws Link as two 8x16 sprites, so the frame covers tiles T, T+1 on
    the left and T+2, T+3 on the right.
    """
    top_left, bottom_left, top_right, bottom_right = (
        chr_tiles[first_tile + offset] for offset in range(4)
    )
    packed = bytearray()
    for row in range(METATILE_HEIGHT):
        if row < 8:
            pixels = top_left[row] + top_right[row]
        else:
            pixels = bottom_left[row - 8] + bottom_right[row - 8]
        if flip:
            pixels = pixels[::-1]
        packed.extend(pack_st_row(palette.index(palette_row, value) for value in pixels))
        # NES sprite pixel 0 is transparent rather than a colour.
        mask = 0
        for x, pixel in enumerate(pixels):
            if pixel:
                mask |= 1 << (15 - x)
        packed.extend(mask.to_bytes(2, "big"))
    return bytes(packed)


def render_metatiles(bundle: AssetBundle) -> bytes:
    return b"".join(
        build_metatile_bytes(bundle.bg_tiles, bundle.palette, palette_row, quad)
        for palette_row, quad in bundle.metatiles
    )


def render_sprites(bundle: AssetBundle) -> bytes:
    return b"".join(
        build_sprite_frame(bundle.sprite_tiles, bundle.palette, LINK_PALETTE_ROW, first_tile, flip)
        for _, first_tile, flip in LINK_FRAMES
    )


def render_hud_tiles(bundle: AssetBundle) -> bytes:
    packed = bytearray()
    for _, tile_index, palette_row in HUD_GLYPHS:
        tile = bundle.bg_tiles[tile_index]
        for row in range(8):
            packed.extend(
                pack_hud_row([bundle.palette.index(palette_row, value) for value in tile[row]])
            )
    return bytes(packed)


def format_words(label: str, values: Iterable[int]) -> str:
    values = list(values)
    chunks = [values[index : index + 8] for index in range(0, len(values), 8)]
    lines = [f"{label}:"]
    for chunk in chunks:
        lines.append("    .word " + ", ".join(f"0x{value:03x}" for value in chunk))
    return "\n".join(lines)


def format_bytes(label: str, values: Iterable[int]) -> str:
    values = list(values)
    chunks = [values[index : index + 20] for index in range(0, len(values), 20)]
    lines = [f"{label}:"]
    for chunk in chunks:
        lines.append("    .byte " + ", ".join(str(value) for value in chunk))
    return "\n".join(lines)


def write_outputs(out_dir: Path, bundle: AssetBundle) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metatiles.bin").write_bytes(render_metatiles(bundle))
    (out_dir / "link_sprites.bin").write_bytes(render_sprites(bundle))
    (out_dir / "hud_tiles.bin").write_bytes(render_hud_tiles(bundle))
    # The big tables ship as binaries rather than .byte directives: 22KB of
    # assembler text is slow to assemble, and keeping .rodata compact matters
    # because every reference to it is a PC-relative displacement limited to
    # the 68000's signed 16 bits.
    (out_dir / "metatile_tiles.bin").write_bytes(
        bytes(tile for _, quad in bundle.metatiles for tile in quad)
    )
    (out_dir / "room_maps.bin").write_bytes(
        bytes(value for room in bundle.rooms for value in room)
    )

    room_count = len(bundle.rooms)
    metatile_count = len(bundle.metatiles)
    room_bytes = OW_ROOM_COLS * OW_ROOM_ROWS

    include_parts = [
        "| Generated by tools/build_assets.py -- do not edit.",
        "",
        f".equ MAP_WIDTH, {OW_ROOM_COLS}",
        f".equ MAP_HEIGHT, {OW_ROOM_ROWS}",
        f".equ ROOM_COUNT, {room_count}",
        f".equ ROOM_BYTES, {room_bytes}",
        f".equ ROOM_GRID_WIDTH, {OW_GRID_WIDTH}",
        f".equ ROOM_GRID_HEIGHT, {OW_GRID_HEIGHT}",
        f".equ METATILE_COUNT, {metatile_count}",
        f".equ METATILE_BYTES, {METATILE_BYTES}",
        f".equ SPRITE_FRAME_COUNT, {len(LINK_FRAMES)}",
        f".equ SPRITE_FRAME_BYTES, {SPRITE_FRAME_BYTES}",
        f".equ HUD_TILE_BYTES, {HUD_TILE_BYTES}",
        f".equ HUD_TILE_COUNT, {len(HUD_GLYPHS)}",
        "",
        "| Overworld collision constants, from ObjectRoomBoundsOW and WalkableTiles.",
        f".equ FIRST_UNWALKABLE_TILE, 0x{OW_FIRST_UNWALKABLE_TILE:02x}",
        f".equ WALKABLE_TILE_COUNT, {len(OW_WALKABLE_TILES)}",
        f".equ ROOM_BOUND_LEFT, 0x{OW_ROOM_BOUNDS[0]:02x}",
        f".equ ROOM_BOUND_RIGHT, 0x{OW_ROOM_BOUNDS[1]:02x}",
        f".equ ROOM_BOUND_UP, 0x{OW_ROOM_BOUNDS[2]:02x}",
        f".equ ROOM_BOUND_DOWN, 0x{OW_ROOM_BOUNDS[3]:02x}",
        "",
        "| Zelda's direction bits, and where InitMode3_Sub8 puts Link at game start.",
        f".equ DIR_RIGHT, {DIR_RIGHT}",
        f".equ DIR_LEFT, {DIR_LEFT}",
        f".equ DIR_DOWN, {DIR_DOWN}",
        f".equ DIR_UP, {DIR_UP}",
        f".equ DIR_HORIZONTAL, {DIR_RIGHT | DIR_LEFT}",
        f".equ DIR_VERTICAL, {DIR_DOWN | DIR_UP}",
        f".equ START_ROOM_ID, 0x{bundle.start_room:02x}",
        f".equ START_X, 0x{LINK_START_X:02x}",
        f".equ START_Y, 0x{bundle.start_y:02x}",
        f".equ START_DIR, 0x{LINK_START_DIR:02x}",
        "",
    ]
    for index, (name, _, _) in enumerate(HUD_GLYPHS):
        include_parts.append(f".equ HUD_{name}, {index}")
    for index, (name, _, _) in enumerate(LINK_FRAMES):
        include_parts.append(f".equ LINK_FRAME_{name.upper()}, {index}")
    include_parts.extend(
        [
            "",
            "| The tables land in .rodata; the equates above stay visible either way.",
            "    .section .rodata",
            "    .align 2",
            format_words("room_palette", bundle.palette.st_colors),
            "",
            format_bytes("walkable_tiles", OW_WALKABLE_TILES),
            "    .align 2",
            "    .section .text",
            "",
        ]
    )
    (out_dir / "assets.inc").write_text("\n".join(include_parts), encoding="utf-8")

    manifest = textwrap.dedent(
        f"""\
        source={bundle.source_note}
        room_count={room_count}
        room_size={OW_ROOM_COLS}x{OW_ROOM_ROWS}
        room_bytes={room_bytes}
        metatile_count={metatile_count}
        metatile_bytes={METATILE_BYTES}
        sprite_frame_count={len(LINK_FRAMES)}
        sprite_frame_bytes={SPRITE_FRAME_BYTES}
        hud_tile_count={len(HUD_GLYPHS)}
        hud_tile_bytes={HUD_TILE_BYTES}
        output_format=Atari ST low-resolution planar 16x16 metatiles
        """
    )
    (out_dir / "asset_manifest.txt").write_text(manifest, encoding="utf-8")


def verify_outputs(out_dir: Path) -> None:
    manifest_path = out_dir / "asset_manifest.txt"
    include_path = out_dir / "assets.inc"
    if not manifest_path.exists() or not include_path.exists():
        raise SystemExit("Missing generated asset files")

    manifest_values = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        key, _, value = line.partition("=")
        manifest_values[key] = value

    required = (
        "room_count",
        "room_size",
        "room_bytes",
        "metatile_count",
        "metatile_bytes",
        "sprite_frame_count",
        "sprite_frame_bytes",
        "hud_tile_count",
        "hud_tile_bytes",
    )
    for key in required:
        if key not in manifest_values:
            raise SystemExit(f"asset_manifest.txt is missing {key}")

    if manifest_values["output_format"] != "Atari ST low-resolution planar 16x16 metatiles":
        raise SystemExit("asset_manifest.txt has the wrong output_format")

    expected_sizes = {
        "metatiles.bin": int(manifest_values["metatile_count"]) * int(manifest_values["metatile_bytes"]),
        "link_sprites.bin": int(manifest_values["sprite_frame_count"])
        * int(manifest_values["sprite_frame_bytes"]),
        "hud_tiles.bin": int(manifest_values["hud_tile_count"]) * int(manifest_values["hud_tile_bytes"]),
        "metatile_tiles.bin": int(manifest_values["metatile_count"]) * 4,
        "room_maps.bin": int(manifest_values["room_count"]) * int(manifest_values["room_bytes"]),
    }
    for name, expected in expected_sizes.items():
        path = out_dir / name
        if not path.exists():
            raise SystemExit(f"Missing generated asset file {name}")
        actual = len(path.read_bytes())
        if actual != expected:
            raise SystemExit(f"Unexpected {name} size: expected {expected}, got {actual}")

    if int(manifest_values["metatile_bytes"]) != METATILE_BYTES:
        raise SystemExit("asset_manifest.txt has wrong metatile_bytes")

    width, _, height = manifest_values["room_size"].partition("x")
    if int(width) * int(height) != int(manifest_values["room_bytes"]):
        raise SystemExit("asset_manifest.txt room_size and room_bytes disagree")

    include_text = include_path.read_text()
    for symbol in ("MAP_WIDTH", "METATILE_COUNT", "HUD_HEART_FULL", "room_palette:", "walkable_tiles:"):
        if symbol not in include_text:
            raise SystemExit(f"assets.inc is missing {symbol}")

    palette_entries = sum(
        len(line.partition(".word")[2].split(","))
        for line in include_text.splitlines()
        if line.strip().startswith(".word")
    )
    if palette_entries != ST_PALETTE_SIZE:
        raise SystemExit(f"room_palette holds {palette_entries} entries, expected {ST_PALETTE_SIZE}")

    print(f"Verified generated assets in {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Atari ST assets from Zelda source data or placeholders")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--require-source",
        action="store_true",
        help="fail instead of falling back to placeholder tiles",
    )
    args = parser.parse_args()

    if args.verify_only:
        verify_outputs(args.out_dir)
        return

    bundle = load_assets(args.source_root, require_source=args.require_source)
    write_outputs(args.out_dir, bundle)
    verify_outputs(args.out_dir)


if __name__ == "__main__":
    main()
