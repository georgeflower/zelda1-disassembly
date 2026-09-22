#!/usr/bin/env python3
"""Run the ST build headlessly in Hatari and render what it put on screen.

Hatari is driven through its debugger: a breakpoint on a VBL count dumps RAM
and the video registers, and this script decodes the four-bitplane framebuffer
into a PNG. Keys can be held down for a run so movement and room transitions
can be checked without a human at the keyboard.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

RAM_DUMP = "ram.bin"
MARKER = b"ZELDAST1"
SCREEN_BYTES = 32000
SCREEN_STRIDE = 160
SCREEN_WIDTH = 320
SCREEN_HEIGHT = 200
VBL_MARGIN = 60

# Offsets into the variable block, mirroring src/globals.s. Only the few the
# harness reports on are listed.
OFF_KEY_STATES = None  # resolved from the generated assets at runtime

SCANCODES = {
    "up": 0x48,
    "down": 0x50,
    "left": 0x4B,
    "right": 0x4D,
    "w": 0x11,
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
}


def parse_globals_layout(globals_source: Path) -> dict[str, int]:
    """Replay the gvar macro in src/globals.s to recover the variable offsets."""
    offsets: dict[str, int] = {}
    offset = 0
    for line in globals_source.read_text(encoding="utf-8").splitlines():
        # '|' starts an assembler comment, and most gvar lines carry one.
        stripped = line.split("|", 1)[0].strip()
        match = re.match(r"^gvar\s+(\w+)\s*(?:,\s*(\d+))?$", stripped)
        if match:
            offsets[match.group(1)] = offset
            offset += int(match.group(2) or 1)
        elif stripped == "galign":
            offset = ((offset + 1) // 2) * 2
    if "KEY_STATES" not in offsets:
        raise SystemExit("Failed to parse src/globals.s; the gvar layout did not resolve")
    offsets["__size__"] = offset
    return offsets


def run_hatari(
    hatari: str,
    tos: Path,
    prg: Path,
    work: Path,
    vbls: int,
    debug_script: str,
    trace: str | None = None,
) -> str:
    hd = work / "hd"
    if hd.exists():
        shutil.rmtree(hd)
    hd.mkdir(parents=True)
    shutil.copy(prg, hd / "ZELDAST.PRG")

    script_path = work / "dbg.ini"
    script_path.write_text(debug_script, encoding="utf-8")

    command = [
        hatari,
        "--tos", str(tos),
        "--machine", "st",
        "--memsize", "1",
        "--cpu-exact", "true",
        "--compatible", "true",
        "--fast-boot", "true",
        "--fast-forward", "true",
        "--sound", "off",
        "--disable-video", "true",
        "--harddrive", str(hd),
        "--auto", "C:\\ZELDAST.PRG",
        "--parse", str(script_path),
        "--log-level", "info",
        # Emulation has to outlive the last breakpoint, or it stops before the
        # condition is ever evaluated.
        "--run-vbls", str(vbls + VBL_MARGIN),
    ]
    if trace:
        command += ["--trace", trace]

    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    result = subprocess.run(
        command, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=600
    )
    return result.stdout + result.stderr


def find_globals(ram: bytes) -> int:
    index = ram.find(MARKER)
    if index < 0:
        raise SystemExit("Could not find the globals marker in RAM; did the program start?")
    if ram.find(MARKER, index + 1) >= 0:
        raise SystemExit("Found the globals marker more than once in RAM")
    return index + len(MARKER)


def video_base(log: str) -> int:
    """Read $FF8201/$FF8203 out of a debugger memory dump line."""
    match = re.search(
        r"^00FF8200: ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2})",
        log,
        re.M,
    )
    if not match:
        raise SystemExit("Could not read the video base registers from the Hatari log")
    # The dump starts at $FF8200, so the high and mid base bytes are the
    # second and fourth values.
    return (int(match.group(2), 16) << 16) | (int(match.group(4), 16) << 8)


def write_png(path: Path, pixels: list[list[int]], palette: list[tuple[int, int, int]]) -> None:
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for index in row:
            raw.extend(palette[index])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", len(pixels[0]), len(pixels), 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def decode_screen(ram: bytes, base: int, palette_words: list[int]) -> tuple[list[list[int]], list]:
    screen = ram[base : base + SCREEN_BYTES]
    if len(screen) < SCREEN_BYTES:
        raise SystemExit(f"Video base {base:#08x} is outside the RAM dump")
    palette = [
        (((word >> 8) & 7) * 36, ((word >> 4) & 7) * 36, (word & 7) * 36) for word in palette_words
    ]
    rows = []
    for y in range(SCREEN_HEIGHT):
        offset = y * SCREEN_STRIDE
        row = []
        for group in range(SCREEN_WIDTH // 16):
            planes = struct.unpack(">4H", screen[offset + group * 8 : offset + group * 8 + 8])
            for bit in range(15, -1, -1):
                row.append(sum(((planes[p] >> bit) & 1) << p for p in range(4)))
        rows.append(row)
    return rows, palette


def read_palette(log: str) -> list[int]:
    values: list[int] = []
    for line_base in (0xFF8240, 0xFF8250):
        match = re.search(rf"^00{line_base:04X}: ((?:[0-9a-fA-F]{{2}} ){{16}})", log, re.M)
        if not match:
            raise SystemExit("Could not read the palette from the Hatari log")
        values += [int(token, 16) for token in match.group(1).split()]
    return [(values[i] << 8) | values[i + 1] for i in range(0, 32, 2)]


def parse_key_schedule(spec: str) -> dict[int, list[tuple[str, int]]]:
    """Parse "620:+right,712:-right,712:+up" into {vbl: [(key, state), ...]}."""
    schedule: dict[int, list[tuple[str, int]]] = {}
    for entry in spec.split(","):
        entry = entry.strip()
        if not entry:
            continue
        when, _, action = entry.partition(":")
        action = action.strip()
        if action[:1] not in "+-":
            raise SystemExit(f"Key event '{entry}' must start with + or -, e.g. 620:+right")
        key = action[1:].strip().lower()
        if key not in SCANCODES:
            raise SystemExit(f"Unknown key '{key}'; known keys: {', '.join(sorted(SCANCODES))}")
        schedule.setdefault(int(when), []).append((key, 1 if action[0] == "+" else 0))
    return schedule


def main() -> None:
    here = Path(__file__).resolve().parent
    project = here.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prg", type=Path, default=project / "build" / "ZELDAST.PRG")
    parser.add_argument("--out", type=Path, default=project / "build" / "screen.png")
    parser.add_argument("--tos", type=Path, default=Path(os.environ.get("TOS", "")))
    parser.add_argument("--hatari", default=os.environ.get("HATARI", "hatari"))
    parser.add_argument("--vbls", type=int, default=900, help="frame to capture at")
    parser.add_argument(
        "--keys",
        default="",
        help='key events as "<vbl>:+<key>" / "<vbl>:-<key>", comma separated, '
        'e.g. "620:+right,712:-right,712:+up"',
    )
    parser.add_argument(
        "--hold",
        default="",
        help="shorthand for holding keys from --press-at onwards",
    )
    parser.add_argument("--press-at", type=int, default=620)
    parser.add_argument("--work", type=Path, default=project / "build" / "shots")
    parser.add_argument(
        "--trace",
        default="",
        help="Hatari trace flags for the capture run, e.g. os_base,cpu_exception",
    )
    args = parser.parse_args()

    if not args.tos or not args.tos.exists():
        raise SystemExit("Pass --tos <tos.img> or set the TOS environment variable")

    schedule = parse_key_schedule(args.keys)
    for key in (name.strip() for name in args.hold.split(",")):
        if key:
            schedule.setdefault(args.press_at, []).append((key.lower(), 1))

    args.work.mkdir(parents=True, exist_ok=True)
    ram_path = args.work / RAM_DUMP
    dump = f"m $ff8200-$ff8204\nm $ff8240-$ff8260\nsavebin {ram_path} 0 $100000\ncont\n"
    capture_script = args.work / "capture.ini"
    capture_script.write_text(dump, encoding="utf-8")

    script = ""
    if schedule:
        # Two passes: the first locates the variable block, the second replays
        # the run and pokes the key-state table on schedule. The program only
        # clears a key slot when a release code arrives and TOS' IKBD handler
        # is masked off, so a poke stays held until another poke clears it.
        first = min(schedule)
        run_hatari(
            args.hatari,
            args.tos,
            args.prg,
            args.work,
            first,
            f"b VBL > {first - 1} :once :file {capture_script}\n",
        )
        globals_addr = find_globals(ram_path.read_bytes())
        layout = parse_globals_layout(project / "src" / "globals.s")
        keys_addr = globals_addr + layout["KEY_STATES"]
        print(f"globals at {globals_addr:#08x}, KEY_STATES at {keys_addr:#08x}")

        for index, (vbl, events) in enumerate(sorted(schedule.items())):
            step = args.work / f"keys{index}.ini"
            pokes = [f"w {keys_addr + SCANCODES[key]:#x} {state}" for key, state in events]
            step.write_text("\n".join(pokes) + "\ncont\n", encoding="utf-8")
            script += f"b VBL > {vbl - 1} :once :file {step}\n"

    script += f"b VBL > {args.vbls - 1} :once :file {capture_script}\n"
    log = run_hatari(
        args.hatari, args.tos, args.prg, args.work, args.vbls, script, trace=args.trace or None
    )
    (args.work / "hatari.log").write_text(log, encoding="utf-8")

    if "Pterm0()" in log:
        print("WARNING: the program terminated during the run", file=sys.stderr)
    faults = sorted(
        {
            match.group(1)
            for match in re.finditer(r"^cpu exception [23] currpc (\w+)", log, re.M)
            # $FC0EE2 is the TOS boot-time blitter probe, present on every boot.
            if match.group(1) != "fc0ee2"
        }
    )
    if faults:
        print(f"WARNING: bus/address errors at {', '.join(faults)}", file=sys.stderr)

    ram = ram_path.read_bytes()
    base = video_base(log)
    rows, palette = decode_screen(ram, base, read_palette(log))
    write_png(args.out, rows, palette)

    globals_addr = find_globals(ram)
    layout = parse_globals_layout(project / "src" / "globals.s")
    report = {
        name: ram[globals_addr + layout[name]]
        for name in ("ROOM_ID", "LINK_X", "LINK_Y", "LINK_DIR", "GAME_MODE")
    }
    print(f"video base {base:#08x}, wrote {args.out}")
    print(" ".join(f"{k}={v:#04x}" for k, v in report.items()))


if __name__ == "__main__":
    main()
