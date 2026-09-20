# The Legend of Zelda for Atari ST

This project is a native Atari ST adaptation of The Legend of Zelda built around the original Zelda 1 disassembly work. The current focus is a playable Atari ST-compatible target that preserves the underlying disassembly while adding a 68000/TOS build path.

This project builds on the disassembly work of Aldo Núñez, whose reverse-engineering efforts and documentation helped establish the foundation for this codebase.

## Current project

- Atari ST native target in `atari_st/`
- 68000 / TOS `.PRG` build path
- Hatari-compatible demo environment
- Experimental vertical slice for rendering and input
- Original Zelda 1 disassembly preserved as a reference for the port

## Build

From the repository root:

```sh
make -C atari_st all
make -C atari_st check
```

See `atari_st/README.md` for prerequisites, build details, and Hatari launch instructions.

## Credits

Aldo Núñez and his disassembly work are an important foundation for this project.
