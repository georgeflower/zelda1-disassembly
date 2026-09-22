/*
 * A TOS .PRG is a flat image, so everything lands in one output section.
 *
 * Order matters twice over:
 *  - .data holds the small variable block and must come before the large
 *    .rodata tables, or PC-relative references to it overflow the 68000's
 *    signed 16-bit displacement.
 *  - .stack goes last for the same reason: it is 4KB of zeros nothing needs
 *    to reach with a displacement.
 */
SECTIONS
{
  . = 0;

  .text :
  {
    *(.text*)
    *(.data*)
    *(.rodata*)
    *(.stack*)
  }

  /DISCARD/ :
  {
    *(.comment*)
    *(.note*)
    *(.eh_frame*)
  }
}
