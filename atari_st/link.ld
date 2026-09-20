SECTIONS
{
  . = 0;

  .text :
  {
    *(.text*)
    *(.rodata*)
    *(.data*)
  }

  /DISCARD/ :
  {
    *(.comment*)
    *(.note*)
    *(.eh_frame*)
  }
}
