from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_assets  # noqa: E402


def _write_fake_rom(root: Path, blobs: dict[str, bytes]) -> None:
    """Lay the named blobs into a synthetic iNES image at PRG-relative offsets."""
    (root / "src").mkdir(exist_ok=True)
    (root / "ext").mkdir(exist_ok=True)

    trainer = bytes([0xAA]) * 512
    prg_rom = bytearray([0x55]) * (64 * 1024)
    entries = []
    offset = 0x100
    for name, data in blobs.items():
        prg_rom[offset : offset + len(data)] = data
        entries.append(f"<Binary Offset='{offset}' Length='{len(data)}' FileName='{name}'/>")
        offset += len(data)

    (root / "src" / "bins.xml").write_text(f"<Binaries>{''.join(entries)}</Binaries>", encoding="utf-8")
    (root / "ext" / "Original.nes").write_bytes(
        b"NES\x1a" + bytes([4, 0, 0x04]) + bytes(9) + trainer + bytes(prg_rom)
    )


class ExtractionTests(unittest.TestCase):
    def test_bins_offsets_are_prg_relative(self) -> None:
        # Zelda uses CHR-RAM, so the iNES header reports zero CHR banks and every
        # blob lives inside PRG ROM. Offsets are therefore relative to the end of
        # the header plus trainer, not to the end of PRG.
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            marker = bytes(range(32))
            _write_fake_rom(root, {"dat/Marker.dat": marker})
            self.assertEqual(build_assets.extract_binary(root, "dat/Marker.dat"), marker)

    def test_invalid_rom_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "src").mkdir()
            (root / "ext").mkdir()
            (root / "src" / "bins.xml").write_text(
                "<Binaries><Binary Offset='0' Length='704' FileName='dat/CommonBackgroundPatterns.dat'/></Binaries>",
                encoding="utf-8",
            )
            (root / "ext" / "Original.nes").write_bytes(b"BAD!")

            with self.assertRaises(ValueError):
                build_assets.load_assets(root)


class DisassemblyParsingTests(unittest.TestCase):
    def test_asm_byte_table_parsing(self) -> None:
        asm = "\n".join(
            [
                "Preceding:",
                "    .BYTE $01",
                "",
                "Wanted:",
                "    .BYTE $DB, $5B, $5B",
                "    .BYTE $1B, $0E",
                "",
                "Next:",
                "    .BYTE $FF",
            ]
        )
        self.assertEqual(
            build_assets.parse_asm_byte_table("\n" + asm, "Wanted"), [0xDB, 0x5B, 0x5B, 0x1B, 0x0E]
        )

    def test_column_directory_entries_become_blob_offsets(self) -> None:
        asm = "\nColumnDirectoryOW:\n    .BYTE $D8, $9B, $0D, $9C, $3E, $9C\n"
        self.assertEqual(build_assets.parse_column_directory(asm), [0, 0x35, 0x66])

    def test_column_repeat_flag_draws_a_square_twice(self) -> None:
        # Bit 7 opens the column, bit 6 marks a square that is drawn twice.
        heap = [0x80 | 0x40 | 0x05, 0x06] + [0x07] * 20
        squares = build_assets.decode_column(heap, 0, 0)
        self.assertEqual(len(squares), build_assets.OW_ROOM_ROWS)
        self.assertEqual(squares[:3], [0x05, 0x05, 0x06])

    def test_square_quads_are_reordered_from_column_major(self) -> None:
        primary = [0] * 0x40
        primary[0x10] = 0x40
        # WriteSquareOW stores (col,row), (col,row+1), (col+1,row), (col+1,row+1).
        self.assertEqual(
            build_assets.square_to_tiles(0x10, primary, []), (0x40, 0x42, 0x41, 0x43)
        )

        secondary = [0x10, 0x11, 0x12, 0x13]
        self.assertEqual(
            build_assets.square_to_tiles(0, [], secondary), (0x10, 0x12, 0x11, 0x13)
        )


class PaletteTests(unittest.TestCase):
    def test_all_eight_nes_rows_share_one_st_palette(self) -> None:
        palette = build_assets.build_palette_map(build_assets.PLACEHOLDER_NES_PALETTE)
        self.assertEqual(len(palette.st_colors), build_assets.ST_PALETTE_SIZE)
        for row in range(build_assets.PALETTE_ROWS):
            for pixel in range(build_assets.PALETTE_ROW_COLORS):
                self.assertLess(palette.index(row, pixel), build_assets.ST_PALETTE_SIZE)

    def test_pixel_zero_is_the_shared_backdrop_in_every_row(self) -> None:
        palette = build_assets.build_palette_map(build_assets.PLACEHOLDER_NES_PALETTE)
        backdrop = palette.index(0, 0)
        for row in range(build_assets.PALETTE_ROWS):
            self.assertEqual(palette.index(row, 0), backdrop)

    def test_duplicate_nes_colours_share_one_st_entry(self) -> None:
        # Row 1 pixel 1 repeats row 0 pixel 1, so both must land on the same entry.
        nes_palette = bytes([0x0F, 0x30, 0x00, 0x12] + [0x0F, 0x30, 0x16, 0x27] + [0x0F] * 24)
        palette = build_assets.build_palette_map(nes_palette)
        self.assertEqual(palette.index(0, 1), palette.index(1, 1))

    def test_more_than_sixteen_colours_is_rejected(self) -> None:
        # Seventeen distinct colours cannot fit the ST's single 16-entry palette.
        nes_palette = bytes([0x0F] + list(range(0x01, 0x20)) + [0x0F] * 12)[:32]
        with self.assertRaises(SystemExit):
            build_assets.build_palette_map(nes_palette)


class CollisionTests(unittest.TestCase):
    def test_tiles_below_the_threshold_are_walkable(self) -> None:
        self.assertFalse(build_assets.tile_is_blocking(0x00))
        self.assertFalse(build_assets.tile_is_blocking(build_assets.OW_FIRST_UNWALKABLE_TILE - 1))

    def test_tiles_at_or_above_the_threshold_block(self) -> None:
        self.assertTrue(build_assets.tile_is_blocking(build_assets.OW_FIRST_UNWALKABLE_TILE))
        self.assertTrue(build_assets.tile_is_blocking(0xFF))

    def test_exception_list_stays_walkable(self) -> None:
        # GetCollidableTile rewrites these to a walkable value before the test,
        # even though they sort above ObjectFirstUnwalkableTile.
        for tile in build_assets.OW_WALKABLE_TILES:
            self.assertGreaterEqual(tile, build_assets.OW_FIRST_UNWALKABLE_TILE)
            self.assertFalse(build_assets.tile_is_blocking(tile))


class SpriteTests(unittest.TestCase):
    def _solid_tiles(self) -> list[list[list[int]]]:
        tiles = [[[0] * 8 for _ in range(8)] for _ in range(256)]
        # Mark only the leftmost column of the top-left tile so flipping is visible.
        for row in range(8):
            tiles[0][row][0] = 1
        return tiles

    def test_frame_is_masked_where_the_nes_pixel_is_transparent(self) -> None:
        palette = build_assets.build_palette_map(build_assets.PLACEHOLDER_NES_PALETTE)
        frame = build_assets.build_sprite_frame(self._solid_tiles(), palette, 4, 0, flip=False)
        self.assertEqual(len(frame), build_assets.SPRITE_FRAME_BYTES)
        mask = int.from_bytes(frame[8:10], "big")
        self.assertEqual(mask, 0x8000)

    def test_horizontal_flip_mirrors_the_row(self) -> None:
        palette = build_assets.build_palette_map(build_assets.PLACEHOLDER_NES_PALETTE)
        frame = build_assets.build_sprite_frame(self._solid_tiles(), palette, 4, 0, flip=True)
        mask = int.from_bytes(frame[8:10], "big")
        self.assertEqual(mask, 0x0001)


class OutputTests(unittest.TestCase):
    def test_placeholder_generation_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "source"
            source_root.mkdir()
            out_dir = Path(tmpdir) / "out"

            bundle = build_assets.load_assets(source_root)
            self.assertIn("placeholder", bundle.source_note)

            build_assets.write_outputs(out_dir, bundle)
            build_assets.verify_outputs(out_dir)

            include_text = (out_dir / "assets.inc").read_text(encoding="utf-8")
            manifest_text = (out_dir / "asset_manifest.txt").read_text(encoding="utf-8")
            self.assertIn("room_palette:", include_text)
            self.assertIn("walkable_tiles:", include_text)
            self.assertIn("source=generated placeholder CHR", manifest_text)

    def test_metatile_tiles_match_the_decoded_quads(self) -> None:
        # The runtime derives collision tiles from this table, so it has to hold the
        # raw NES tile indices in the same order the metatiles were built from.
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "source"
            source_root.mkdir()
            out_dir = Path(tmpdir) / "out"

            bundle = build_assets.load_assets(source_root)
            build_assets.write_outputs(out_dir, bundle)

            emitted = list((out_dir / "metatile_tiles.bin").read_bytes())
            expected = [tile for _, quad in bundle.metatiles for tile in quad]
            self.assertEqual(emitted, expected)

    def test_room_maps_are_emitted_row_major(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "source"
            source_root.mkdir()
            out_dir = Path(tmpdir) / "out"

            bundle = build_assets.load_assets(source_root)
            build_assets.write_outputs(out_dir, bundle)

            emitted = list((out_dir / "room_maps.bin").read_bytes())
            self.assertEqual(emitted, [value for room in bundle.rooms for value in room])

    def test_missing_output_file_fails_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "source"
            source_root.mkdir()
            out_dir = Path(tmpdir) / "out"

            build_assets.write_outputs(out_dir, build_assets.load_assets(source_root))
            (out_dir / "link_sprites.bin").unlink()
            with self.assertRaises(SystemExit):
                build_assets.verify_outputs(out_dir)


if __name__ == "__main__":
    unittest.main()
