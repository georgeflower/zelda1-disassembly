#!/usr/bin/env python3
from __future__ import annotations

import argparse
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

METATILE_WIDTH = 16
METATILE_HEIGHT = 16
MAP_WIDTH = 20
MAP_HEIGHT = 12
ROOM_BYTES = MAP_WIDTH * MAP_HEIGHT
METATILE_BYTES = METATILE_HEIGHT * 8
CHR_TILE_BYTES = 16
PATTERN_SOURCE_NAME = "dat/CommonBackgroundPatterns.dat"

# Two small demo rooms. The indices refer to the metatile list below.
ROOMS = (
    (
        (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
        (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1),
        (1, 0, 2, 2, 2, 0, 4, 4, 4, 0, 2, 2, 2, 0, 4, 4, 4, 0, 0, 1),
        (1, 0, 2, 3, 2, 0, 4, 5, 4, 0, 2, 3, 2, 0, 4, 5, 4, 0, 0, 1),
        (1, 0, 2, 2, 2, 0, 4, 4, 4, 0, 2, 2, 2, 0, 4, 4, 4, 0, 0, 1),
        (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1),
        (1, 0, 4, 4, 4, 0, 2, 2, 2, 0, 4, 4, 4, 0, 2, 2, 2, 0, 0, 1),
        (1, 0, 4, 5, 4, 0, 2, 3, 2, 0, 4, 5, 4, 0, 2, 3, 2, 0, 0, 1),
        (1, 0, 4, 4, 4, 0, 2, 2, 2, 0, 4, 4, 4, 0, 2, 2, 2, 0, 0, 1),
        (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1),
        (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1),
        (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    ),
    (
        (6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6),
        (6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6),
        (6, 0, 7, 7, 7, 0, 8, 8, 8, 0, 7, 7, 7, 0, 8, 8, 8, 0, 0, 6),
        (6, 0, 7, 9, 7, 0, 8, 10, 8, 0, 7, 9, 7, 0, 8, 10, 8, 0, 0, 6),
        (6, 0, 7, 7, 7, 0, 8, 8, 8, 0, 7, 7, 7, 0, 8, 8, 8, 0, 0, 6),
        (6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6),
        (6, 0, 8, 8, 8, 0, 7, 7, 7, 0, 8, 8, 8, 0, 7, 7, 7, 0, 0, 6),
        (6, 0, 8, 10, 8, 0, 7, 9, 7, 0, 8, 10, 8, 0, 7, 9, 7, 0, 0, 6),
        (6, 0, 8, 8, 8, 0, 7, 7, 7, 0, 8, 8, 8, 0, 7, 7, 7, 0, 0, 6),
        (6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6),
        (6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6),
        (6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6),
    ),
)

ROOM_PALETTES = (
    (0x000, 0x222, 0x442, 0x774, 0x020, 0x360, 0x570, 0x775, 0x004, 0x226, 0x447, 0x667, 0x420, 0x630, 0x752, 0x777),
    (0x000, 0x222, 0x555, 0x777, 0x024, 0x146, 0x257, 0x367, 0x200, 0x420, 0x640, 0x760, 0x402, 0x613, 0x724, 0x777),
)

# Each metatile is an NES-style 16x16 block: palette slot + four 8x8 CHR tile indices.
METATILES = (
    (0, (0, 1, 2, 3)),
    (1, (4, 5, 6, 7)),
    (2, (8, 9, 10, 11)),
    (2, (12, 13, 14, 15)),
    (3, (16, 17, 18, 19)),
    (3, (20, 21, 22, 23)),
    (1, (24, 25, 26, 27)),
    (2, (28, 29, 30, 31)),
    (3, (32, 33, 34, 35)),
    (2, (36, 37, 38, 39)),
    (3, (40, 41, 42, 43)),
)


@dataclass(frozen=True)
class AssetBundle:
    chr_tiles: list[list[list[int]]]
    source_note: str


def find_pattern_source(source_root: Path) -> bytes | None:
    direct = source_root / "bin" / PATTERN_SOURCE_NAME
    if direct.exists():
        return direct.read_bytes()

    rom_path = source_root / "ext" / "Original.nes"
    bins_path = source_root / "src" / "bins.xml"
    if not rom_path.exists() or not bins_path.exists():
        return None

    rom = rom_path.read_bytes()
    if len(rom) < 16 or rom[:4] != b"NES\x1a":
        raise ValueError(f"{rom_path} is not a valid iNES ROM image")
    data_offset = 16 + (512 if (rom[6] & 0x04) else 0)

    xml_root = ET.fromstring(bins_path.read_text(encoding="utf-8"))
    for binary in xml_root.iterfind(".//Binary"):
        if binary.attrib.get("FileName") != PATTERN_SOURCE_NAME:
            continue
        offset = int(binary.attrib["Offset"]) + data_offset
        length = int(binary.attrib["Length"])
        if offset + length > len(rom):
            raise ValueError(
                f"{rom_path} is too short for {PATTERN_SOURCE_NAME}: need {offset + length} bytes, found {len(rom)}"
            )
        return rom[offset : offset + length]

    return None


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


def build_placeholder_chr() -> list[list[list[int]]]:
    tiles: list[list[list[int]]] = []
    for tile_index in range(44):
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


def load_assets(source_root: Path) -> AssetBundle:
    pattern_data = find_pattern_source(source_root)
    if pattern_data is not None:
        return AssetBundle(decode_nes_chr(pattern_data), "ROM-derived CHR from CommonBackgroundPatterns.dat")
    return AssetBundle(build_placeholder_chr(), "generated placeholder CHR (Original.nes not available)")


def pack_st_row(pixels: Iterable[int]) -> bytes:
    plane_words = [0, 0, 0, 0]
    for x, pixel in enumerate(pixels):
        mask = 1 << (15 - x)
        for plane in range(4):
            if pixel & (1 << plane):
                plane_words[plane] |= mask
    return b"".join(word.to_bytes(2, "big") for word in plane_words)


def chr_pixel_to_st_index(pixel: int, palette_slot: int) -> int:
    if pixel == 0:
        return 0
    return palette_slot * 4 + pixel


def build_metatile_bytes(chr_tiles: list[list[list[int]]], palette_slot: int, tile_indices: tuple[int, int, int, int]) -> bytes:
    tl, tr, bl, br = (chr_tiles[index] for index in tile_indices)
    packed = bytearray()
    for row in range(16):
        if row < 8:
            left = tl[row]
            right = tr[row]
        else:
            left = bl[row - 8]
            right = br[row - 8]
        pixels = [chr_pixel_to_st_index(value, palette_slot) for value in (left + right)]
        packed.extend(pack_st_row(pixels))
    return bytes(packed)


def render_metatiles(bundle: AssetBundle) -> bytes:
    tile_count_needed = max(index for _, indices in METATILES for index in indices) + 1
    if len(bundle.chr_tiles) < tile_count_needed:
        raise ValueError(f"Need {tile_count_needed} CHR tiles, got {len(bundle.chr_tiles)}")

    return b"".join(build_metatile_bytes(bundle.chr_tiles, palette_slot, indices) for palette_slot, indices in METATILES)


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
    metatile_bytes = render_metatiles(bundle)
    (out_dir / "demo_metatiles.bin").write_bytes(metatile_bytes)

    include_parts = [
        ".equ DEMO_MAP_WIDTH, 20",
        ".equ DEMO_MAP_HEIGHT, 12",
        ".equ DEMO_ROOM_COUNT, 2",
        f".equ DEMO_ROOM_BYTES, {ROOM_BYTES}",
        f".equ DEMO_METATILE_COUNT, {len(METATILES)}",
        f".equ DEMO_METATILE_BYTES, {METATILE_BYTES}",
        "",
        format_words("room_palettes", (value for room in ROOM_PALETTES for value in room)),
        "",
        format_bytes("room_maps", (value for room in ROOMS for row in room for value in row)),
        "",
    ]
    (out_dir / "demo_assets.inc").write_text("\n".join(include_parts), encoding="utf-8")

    manifest = textwrap.dedent(
        f"""\
        source={bundle.source_note}
        pattern_source_name={PATTERN_SOURCE_NAME}
        room_count={len(ROOMS)}
        room_size={MAP_WIDTH}x{MAP_HEIGHT}
        metatile_count={len(METATILES)}
        metatile_bytes={METATILE_BYTES}
        output_format=Atari ST low-resolution planar 16x16 metatiles
        """
    )
    (out_dir / "asset_manifest.txt").write_text(manifest, encoding="utf-8")


def verify_outputs(out_dir: Path) -> None:
    metatile_path = out_dir / "demo_metatiles.bin"
    include_path = out_dir / "demo_assets.inc"
    manifest_path = out_dir / "asset_manifest.txt"

    if not metatile_path.exists() or not include_path.exists() or not manifest_path.exists():
        raise SystemExit("Missing generated asset files")

    metatile_bytes = metatile_path.read_bytes()
    expected_metatile_size = len(METATILES) * METATILE_BYTES
    if len(metatile_bytes) != expected_metatile_size:
        raise SystemExit(
            f"Unexpected demo_metatiles.bin size: expected {expected_metatile_size}, got {len(metatile_bytes)}"
        )

    include_text = include_path.read_text()
    if (
        "DEMO_MAP_WIDTH" not in include_text
        or "DEMO_METATILE_COUNT" not in include_text
        or "room_palettes:" not in include_text
        or "room_maps:" not in include_text
    ):
        raise SystemExit("demo_assets.inc is missing required symbols")

    manifest_values = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        key, _, value = line.partition("=")
        manifest_values[key] = value

    expected_manifest = {
        "pattern_source_name": PATTERN_SOURCE_NAME,
        "room_count": str(len(ROOMS)),
        "room_size": f"{MAP_WIDTH}x{MAP_HEIGHT}",
        "metatile_count": str(len(METATILES)),
        "metatile_bytes": str(METATILE_BYTES),
        "output_format": "Atari ST low-resolution planar 16x16 metatiles",
    }
    for key, expected in expected_manifest.items():
        if manifest_values.get(key) != expected:
            raise SystemExit(f"asset_manifest.txt has wrong {key}: expected {expected!r}, got {manifest_values.get(key)!r}")

    print(f"Verified generated assets in {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Atari ST demo assets from Zelda source data or placeholders")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        verify_outputs(args.out_dir)
        return

    bundle = load_assets(args.source_root)
    write_outputs(args.out_dir, bundle)
    verify_outputs(args.out_dir)


if __name__ == "__main__":
    main()
