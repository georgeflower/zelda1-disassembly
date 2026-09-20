Atari STFM / Hatari vertical slice
==================================

This directory contains a first native Atari ST vertical slice for the Zelda 1
disassembly project. It is intentionally scoped as a foundation layer: it keeps
the original NES disassembly untouched while adding a reproducible open-source
68000 build path and a small hardware demonstrator that subsequent work can
extend.

What is working today
---------------------

- native Motorola 68000 program emitted as a TOS `.PRG`
- stock Atari ST low-resolution setup: 320x200, 4 bitplanes, 16 colors
- VBL-paced main loop suitable for STFM / Hatari timing
- keyboard polling through the IKBD ACIA
- navigable 20x12 metatile room demonstrator
- action/start/select input plumbing:
  - movement: arrow keys or `W/A/S/D`
  - action: `Space` or `Control` toggles the player marker color
  - start: `Return` pauses/resumes movement
  - select: `Right Shift` or `Tab` cycles between demo rooms
  - quit: `Esc`
- asset build step that converts NES-style 2bpp CHR into Atari ST planar
  16x16 metatiles when lawful source data is available locally
- placeholder asset fallback so the target remains buildable without any ROM

What this does not claim yet
----------------------------

- no gameplay-accurate Zelda logic port
- no 6502-to-68000 game logic migration yet
- no sprite system, scrolling, collision, audio, save handling, or UI port
- no full ROM-data decoder for real overworld room layouts or attribute tables

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

About the asset pipeline
------------------------

`atari_st/tools/build_assets.py` demonstrates the representation boundary
between NES source data and Atari ST rendering data:

- **CHR input**: reads `dat/CommonBackgroundPatterns.dat` either from
  `bin/dat/` or directly from `ext/Original.nes` using `src/bins.xml`
- **metatile layer**: combines 8x8 CHR tiles into 16x16 NES-style metatiles
- **palette layer**: maps those metatiles into Atari ST 12-bit palette entries
- **map layer**: emits compact room maps for the current demonstrator
- **output**: writes planar ST-ready metatile graphics plus an assembler include

If the ROM is unavailable, the same interfaces emit generated placeholder art so
the build still succeeds without distributing copyrighted content.

Hatari launch examples
----------------------

If Hatari already has a TOS or EmuTOS ROM configured:

```sh
hatari --machine st --memsize 1 --monitor rgb --auto atari_st/build/ZELDAST.PRG
```

If you prefer to pass a ROM explicitly:

```sh
hatari --machine st --memsize 1 --monitor rgb --tos /path/to/tos.img --auto atari_st/build/ZELDAST.PRG
```

Assumptions and licensing notes
-------------------------------

- The existing repository does not include a formal license file; this ST work
  follows the repository's existing source-sharing model.
- No proprietary ROM image or extracted Zelda binary asset is committed here.
- If you provide `ext/Original.nes`, you are responsible for ensuring you may
  lawfully possess and use that source data.
- The checked-in converter and 68000 source are open build inputs; generated
  artifacts stay out of version control.

Memory / video constraints
--------------------------

- targets low-resolution ST video memory: 320x200x4bpp = 32,000 bytes
- uses a single software-owned screen buffer aligned for the ST shifter
- redraws a 20x12 metatile room each frame, which is suitable for a simple
  first slice but should be optimized or partially invalidated later

Next porting milestones
-----------------------

1. replace the placeholder room maps with decoders for real Zelda layout data
2. separate platform services from game-state logic for gradual 6502 migration
3. add sprite composition, HUD rendering, and collision-aware movement
4. investigate YM2149/SNDH-friendly audio playback for Zelda music adaptation
5. add automated emulator smoke coverage where the CI environment permits it
