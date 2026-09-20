from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_assets  # noqa: E402


class BuildAssetsTests(unittest.TestCase):
    def test_placeholder_generation_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "source"
            source_root.mkdir()
            out_dir = Path(tmpdir) / "out"

            bundle = build_assets.load_assets(source_root)
            self.assertIn("placeholder", bundle.source_note)

            build_assets.write_outputs(out_dir, bundle)
            build_assets.verify_outputs(out_dir)

            include_text = (out_dir / "demo_assets.inc").read_text(encoding="utf-8")
            manifest_text = (out_dir / "asset_manifest.txt").read_text(encoding="utf-8")
            self.assertIn("room_palettes:", include_text)
            self.assertIn("source=generated placeholder CHR", manifest_text)

    def test_rom_derived_generation_from_valid_ines_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "src").mkdir()
            (root / "ext").mkdir()
            out_dir = root / "out"

            chr_data = bytes([0x00, 0xFF] * (16 * 44 // 2))
            trainer = bytes([0xAA]) * 512
            (root / "src" / "bins.xml").write_text(
                "<Binaries><Binary Offset='0x0' Length='0x2c0' FileName='dat/CommonBackgroundPatterns.dat'/></Binaries>",
                encoding="utf-8",
            )
            (root / "ext" / "Original.nes").write_bytes(b"NES\x1a" + bytes([0, 0, 0x04]) + bytes(9) + trainer + chr_data)

            bundle = build_assets.load_assets(root)
            self.assertIn("ROM-derived", bundle.source_note)
            self.assertEqual(len(bundle.chr_tiles), 44)

            build_assets.write_outputs(out_dir, bundle)
            build_assets.verify_outputs(out_dir)

            manifest_text = (out_dir / "asset_manifest.txt").read_text(encoding="utf-8")
            self.assertIn("source=ROM-derived CHR", manifest_text)

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


if __name__ == "__main__":
    unittest.main()
