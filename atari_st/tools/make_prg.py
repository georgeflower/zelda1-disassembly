#!/usr/bin/env python3
from __future__ import annotations

import argparse
import struct
from pathlib import Path

HEADER_MAGIC = 0x601A
HEADER_SIZE = 0x1C


def build_prg(payload: bytes) -> bytes:
    header = struct.pack(
        ">HLLLLLLH",
        HEADER_MAGIC,
        len(payload),
        0,
        0,
        0,
        0,
        0,
        1,
    )
    return header + payload


def check_prg(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < HEADER_SIZE:
        raise SystemExit(f"{path} is too small to be a TOS executable")

    magic, text_len, data_len, bss_len, sym_len, reserved, prg_flags, abs_flag = struct.unpack(
        ">HLLLLLLH", data[:HEADER_SIZE]
    )

    if magic != HEADER_MAGIC:
        raise SystemExit(f"{path} has wrong magic: 0x{magic:04x}")
    if abs_flag != 1:
        raise SystemExit(f"{path} has absflag={abs_flag}, expected 1 for a relocation-free PRG")

    expected_size = HEADER_SIZE + text_len + data_len + sym_len
    if expected_size != len(data):
        raise SystemExit(
            f"{path} header size mismatch: header expects {expected_size} bytes, found {len(data)}"
        )

    print(
        f"Validated {path}: text={text_len} data={data_len} bss={bss_len} symbols={sym_len} flags={prg_flags}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Wrap a flat 68000 binary in a minimal Atari TOS PRG header")
    parser.add_argument("input", nargs="?")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--check", dest="check", type=Path)
    args = parser.parse_args()

    if args.check is not None:
        check_prg(args.check)
        return

    if not args.input or not args.output:
        parser.error("input and output are required unless --check is used")

    payload = Path(args.input).read_bytes()
    Path(args.output).write_bytes(build_prg(payload))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
