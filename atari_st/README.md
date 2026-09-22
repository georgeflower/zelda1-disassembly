Atari STFM / Hatari port
========================

A native Atari ST port of The Legend of Zelda's overworld, built on top of
aldonunez's NES disassembly in `src/`. It runs as a stock TOS `.PRG` on a
512KB ST in 320x200 sixteen-colour mode, and reads all of its graphics, room
layouts and palettes out of a ROM you supply yourself.

What is working today
---------------------

- native Motorola 68000 program emitted as a TOS `.PRG`, VBL-paced for STFM
  timing
- the full 128-screen overworld decoded from the original data: room layouts,
  16x16 squares, per-area palette
- Link as a masked, run-time-shifted sprite with four-direction walk animation
- pixel movement governed by the original collision rules, including the
  walkable-tile exception list and the two-column test on vertical moves
- room-to-room traversal with a 16-pixel stepped scroll in all four directions
- status ribbon with hearts, and rupee, key and bomb counters, using the
  original glyphs
- background buffer with dirty-rectangle sprite erase, so a frame costs a few
  hundred bytes of copying rather than a full 22KB repaint
- keyboard input through the IKBD ACIA: arrow keys or `W/A/S/D` to walk,
  `Esc` to quit
- headless Hatari harness that captures the framebuffer to a PNG and can drive
  scripted key input
- placeholder asset fallback so the target still builds without any ROM

What this does not do yet
-------------------------

- caves and dungeon entrances, item pickup, the inventory subscreen
- sword, bombs and any other item use
- enemies, combat and damage
- audio, and save handling
- palette cycling (the animated pond)

Prerequisites
-------------

- Python 3
- GNU m68k binutils with `m68k-linux-gnu-as`, `ld`, and `objcopy`
- Hatari (or another TOS-compatible emulator) for execution

Example Debian/Ubuntu packages:

```sh
sudo apt-get install python3 binutils-m68k-linux-gnu hatari
```

Build commands
--------------

From the repository root:

```sh
make -C atari_st all
make -C atari_st check
```

Outputs:

- `atari_st/build/zelda_st.elf`
- `atari_st/build/zelda_st.bin`
- `atari_st/build/ZELDAST.PRG`

Supplying the game data
-----------------------

Put a `(U) (PRG0)` or `(PRG1)` ROM image at `ext/Original.nes`. The build reads
it through `src/bins.xml`, whose offsets are relative to the start of PRG ROM
because Zelda uses CHR-RAM and stores its graphics inside PRG. `ext/` and
`*.nes` are both gitignored, so the ROM never enters version control.

Without it the build still succeeds, but prints a warning and emits
procedurally generated placeholder art. Pass `--require-source` to
`tools/build_assets.py` to make a missing ROM a hard error instead.

The asset pipeline
------------------

`atari_st/tools/build_assets.py` is the boundary between NES data and ST data:

- **pattern tables**: rebuilds the background and sprite pattern tables at the
  tile indices the game loads them to, per `CommonPatternVramAddrs` (`Z_02.asm`)
  and `PatternBlockPpuAddrs` (`Z_03.asm`)
- **rooms**: decodes `RoomLayoutsOW.dat`, the `ColumnHeapOW` tables and
  `LevelBlockOW.dat` into 128 screens of 16x11 squares
- **palette**: every colour in all eight NES palette rows -- four background
  and four sprite -- collapses to exactly sixteen distinct ST values with no
  collisions, so one hardware palette covers tiles and sprites at full fidelity
- **collision**: emits the four raw NES tile indices behind each square, which
  is what lets the engine apply `GetCollidableTile`'s rules at 8-pixel
  resolution without storing a tile grid per room
- **output**: planar metatiles, Link's eight sprite frames with opacity masks,
  HUD glyphs, and an assembler include of the constants lifted from the
  disassembly

Screen layout
-------------

```
y   0.. 23   HUD ribbon, three 8-pixel tile rows, full 320 wide
y  24..199   playfield, 256x176, x = 32..287
```

The NES play area is 256x176, which fits the ST's 200 lines exactly once 24 are
given to the status ribbon. Link keeps NES coordinates internally (X 0..255,
Y `$40`..`$EF`) so the constants taken from the disassembly -- room bounds,
hotspot offsets, the unwalkable tile threshold -- are used unchanged.

Testing
-------

`make check` runs the asset unit tests, verifies the generated files against the
manifest, and validates the PRG header.

For visual and behavioural checks there is a headless Hatari harness:

```sh
export TOS=/path/to/tos.img
python3 atari_st/tools/screenshot.py --vbls 900 --out build/screen.png
python3 atari_st/tools/screenshot.py --vbls 2600 --trace os_base,cpu_exception \
    --keys "620:+left,1100:-left,1100:+up,1600:-up,1600:+right"
```

It breaks on a VBL count, dumps RAM and the video registers, decodes the
four-bitplane framebuffer to a PNG, reports Link's state, and warns about bus
errors or an early `Pterm0`. Key events are injected by poking the key-state
table, which the harness locates through a marker next to the variable block.

`tools/compare_render.py` closes the loop on the renderer by diffing a captured
framebuffer against a reference render of the same room built in Python; they
should agree byte for byte outside Link's sprite.

Notes on the ST implementation
------------------------------

- A `.PRG` is handed the whole TPA by `Pexec`, so `Malloc` returns 0 until the
  program calls `Mshrink`. That also means moving onto a private stack first,
  since the GEMDOS stack sits in the memory about to be released.
- Everything lands in one flat section, so `link.ld` emits `.data` before
  `.rodata`: the 68000's PC-relative displacement is a signed 16 bits, and the
  36KB of tables would otherwise push the variable block out of reach.
- Scroll steps are 16 pixels, exactly one bitplane word, so every copy stays
  byte-aligned and needs no bit shifting.
- Sprites are shifted at run time rather than pre-shifted at build time.
  Sixteen pre-rotated copies would cost 40KB for Link alone; the shift costs a
  few thousand cycles against a 160,000-cycle frame.

Licensing notes
---------------

- No proprietary ROM image or extracted Zelda asset is committed here.
- If you provide `ext/Original.nes`, you are responsible for ensuring you may
  lawfully possess and use that source data.
- The converter and 68000 source are open build inputs; generated artifacts
  stay out of version control.

Next porting milestones
-----------------------

1. caves and dungeon entrances, driven by the same square-type data the
   collision already reads
2. item pickup, the inventory subscreen and item use
3. the enemy object system and combat
4. the underworld, reusing the overworld decoders against the `UW` tables
5. YM2149 audio from the song scripts already listed in `bins.xml`
