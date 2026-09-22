#!/usr/bin/env python3
"""Compare a captured ST framebuffer against a reference render of the same room.

This is the end-to-end check on the 68000 renderer: build_assets.py and the
assembler both lay out the same metatiles, so any disagreement outside the
sprite is a bug in render_room or the metatile data.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_assets as B  # noqa: E402

STRIDE = 160
PLAYFIELD_TOP = 24
PLAYFIELD_LEFT = 16
PLAYFIELD_HEIGHT = 176
PLAYFIELD_BYTES = 128
SPRITE_SIZE = 16


def reference_screen(bundle: B.AssetBundle, room_id: int) -> bytearray:
    metatiles = B.render_metatiles(bundle)
    room = bundle.rooms[room_id]
    screen = bytearray(32000)
    for square_y in range(B.OW_ROOM_ROWS):
        for square_x in range(B.OW_ROOM_COLS):
            index = room[square_y * B.OW_ROOM_COLS + square_x]
            for row in range(16):
                start = index * B.METATILE_BYTES + row * 8
                offset = (PLAYFIELD_TOP + square_y * 16 + row) * STRIDE
                offset += PLAYFIELD_LEFT + square_x * 8
                screen[offset : offset + 8] = metatiles[start : start + 8]
    return screen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ram", type=Path, required=True, help="RAM dump from screenshot.py")
    parser.add_argument("--base", required=True, help="video base address, e.g. 0x1da00")
    parser.add_argument("--room", required=True, help="room id the capture was taken in")
    parser.add_argument("--link-x", required=True)
    parser.add_argument("--link-y", required=True)
    parser.add_argument("--source-root", type=Path, default=HERE.parent.parent)
    args = parser.parse_args()

    bundle = B.load_assets(args.source_root)
    reference = reference_screen(bundle, int(args.room, 0))

    base = int(args.base, 0)
    live = args.ram.read_bytes()[base : base + 32000]
    if len(live) < 32000:
        raise SystemExit("RAM dump does not contain a whole screen at that base")

    # Link is drawn over the background, so skip the two bitplane groups his
    # 16-pixel sprite can straddle.
    link_x = int(args.link_x, 0) + PLAYFIELD_LEFT * 2
    left = (link_x // 16) * 8
    top = int(args.link_y, 0) - (0x40 - PLAYFIELD_TOP - 2)

    differing = 0
    for y in range(PLAYFIELD_TOP, PLAYFIELD_TOP + PLAYFIELD_HEIGHT):
        for x in range(PLAYFIELD_LEFT, PLAYFIELD_LEFT + PLAYFIELD_BYTES):
            if top <= y < top + SPRITE_SIZE and left <= x < left + SPRITE_SIZE:
                continue
            if reference[y * STRIDE + x] != live[y * STRIDE + x]:
                differing += 1

    print(f"playfield bytes differing outside Link's sprite: {differing}")
    if differing:
        raise SystemExit("the 68000 render does not match the reference")


if __name__ == "__main__":
    main()
