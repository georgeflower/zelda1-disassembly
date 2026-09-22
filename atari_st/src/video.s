| Video setup, room rendering and scroll composition.

init_video:
    | Stop TOS' IKBD handler from consuming the scan codes we poll for.
    movea.l #MFP_IERB, %a0
    move.b (%a0), OFF_OLD_IERB(%a5)
    andi.b #~MFP_IKBD_BIT, (%a0)
    movea.l #MFP_IMRB, %a0
    move.b (%a0), OFF_OLD_IMRB(%a5)
    andi.b #~MFP_IKBD_BIT, (%a0)

    movea.l #IKBD_ACIA_STATUS, %a0
    movea.l #IKBD_ACIA_DATA, %a1
1:  move.b (%a0), %d0
    btst #0, %d0
    beq 2f
    tst.b (%a1)
    bra 1b
2:
    lea OFF_OLD_PALETTE(%a5), %a0
    movea.l #PALETTE_BASE, %a1
    moveq #15, %d7
3:  move.w (%a1)+, (%a0)+
    dbra %d7, 3b

    movea.l #VIDEO_BASE_HI, %a0
    move.b (%a0), OFF_OLD_SCREEN_HI(%a5)
    movea.l #VIDEO_BASE_MID, %a0
    move.b (%a0), OFF_OLD_SCREEN_MID(%a5)
    movea.l #VIDEO_BASE_LOW, %a0
    move.b (%a0), OFF_OLD_SCREEN_LOW(%a5)
    movea.l #SHIFT_MODE, %a0
    move.b (%a0), OFF_OLD_SHIFT_MODE(%a5)

    | Point the shifter at our buffer. $FF820D is STE-only, but a plain ST's
    | base is inherently 256-byte aligned so writing it is harmless.
    move.l OFF_SCREEN_PTR(%a5), %d0
    movea.l #VIDEO_BASE_LOW, %a1
    move.b %d0, (%a1)
    lsr.l #8, %d0
    movea.l #VIDEO_BASE_MID, %a1
    move.b %d0, (%a1)
    lsr.l #8, %d0
    movea.l #VIDEO_BASE_HI, %a1
    move.b %d0, (%a1)

    movea.l #SHIFT_MODE, %a1
    clr.b (%a1)                 | 320x200, four bitplanes

    | One ST palette covers every NES background and sprite row; see
    | build_palette_map in tools/build_assets.py.
    lea room_palette(%pc), %a0
    movea.l #PALETTE_BASE, %a1
    moveq #15, %d7
4:  move.w (%a0)+, (%a1)+
    dbra %d7, 4b
    rts

restore_video:
    lea OFF_OLD_PALETTE(%a5), %a0
    movea.l #PALETTE_BASE, %a1
    moveq #15, %d7
1:  move.w (%a0)+, (%a1)+
    dbra %d7, 1b

    movea.l #SHIFT_MODE, %a1
    move.b OFF_OLD_SHIFT_MODE(%a5), (%a1)
    movea.l #VIDEO_BASE_LOW, %a1
    move.b OFF_OLD_SCREEN_LOW(%a5), (%a1)
    movea.l #VIDEO_BASE_MID, %a1
    move.b OFF_OLD_SCREEN_MID(%a5), (%a1)
    movea.l #VIDEO_BASE_HI, %a1
    move.b OFF_OLD_SCREEN_HI(%a5), (%a1)

    movea.l #MFP_IMRB, %a0
    move.b OFF_OLD_IMRB(%a5), (%a0)
    movea.l #MFP_IERB, %a0
    move.b OFF_OLD_IERB(%a5), (%a0)
    rts

wait_vbl:
    movea.l #FR_CLOCK, %a0
    move.l (%a0), %d0
1:  cmp.l (%a0), %d0
    beq 1b
    rts

| Draw one room's 16x11 metatiles into a full-screen buffer.
|
| d0.w = room id, a1 = destination buffer
render_room:
    movem.l %d0-%d7/%a0-%a4, -(%sp)
    lea room_maps(%pc), %a0
    mulu.w #ROOM_BYTES, %d0
    adda.l %d0, %a0
    adda.l #PLAYFIELD_ORIGIN, %a1

    moveq #(MAP_HEIGHT - 1), %d7
1:  movea.l %a1, %a2
    moveq #(MAP_WIDTH - 1), %d6
2:  moveq #0, %d0
    move.b (%a0)+, %d0
    mulu.w #METATILE_BYTES, %d0
    lea metatiles(%pc), %a3
    adda.l %d0, %a3
    movea.l %a2, %a4
    moveq #(SPRITE_HEIGHT - 1), %d5
3:  move.l (%a3)+, (%a4)+
    move.l (%a3)+, (%a4)+
    adda.w #(SCREEN_STRIDE - 8), %a4
    dbra %d5, 3b
    adda.w #8, %a2
    dbra %d6, 2b
    movea.l %a2, %a1
    adda.l #(SCREEN_STRIDE * 16 - PLAYFIELD_BYTES), %a1
    dbra %d7, 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a4
    rts

| Copy a rectangle between two screen-shaped buffers.
|
| a0 = source, a1 = destination, d0.w = rows, d1.w = bytes per row (mult. of 4)
| All registers are preserved; both pointers step by SCREEN_STRIDE per row.
|
| The inner loop moves four longs per dbra: a move.l pair is 20 cycles and the
| dbra another 10, so unrolling cuts roughly a quarter off a full-screen copy.
blit_rect:
    movem.l %d0-%d4/%a0-%a1, -(%sp)
    tst.w %d0
    beq 9f
    move.w %d1, %d2
    lsr.w #2, %d2               | longs per row
    beq 9f
    move.w %d2, %d4
    and.w #3, %d4
    lsr.w #2, %d2               | whole groups of four longs
    subq.w #1, %d2              | -1 when there are none
    subq.w #1, %d4
    move.w #SCREEN_STRIDE, %d3
    sub.w %d1, %d3
    subq.w #1, %d0

1:  move.w %d2, %d1
    bmi 3f
2:  move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    dbra %d1, 2b
3:  move.w %d4, %d1
    bmi 5f
4:  move.l (%a0)+, (%a1)+
    dbra %d1, 4b
5:  adda.w %d3, %a0
    adda.w %d3, %a1
    dbra %d0, 1b

9:  movem.l (%sp)+, %d0-%d4/%a0-%a1
    rts

| Compose one frame of a sideways scroll.
|
| d0.w = step, 1..SCROLL_STEPS_H. Steps are 16 pixels, which is exactly one
| bitplane word, so both halves stay byte-aligned and need no shifting.
compose_horizontal:
    movem.l %d0-%d4/%a0-%a4, -(%sp)
    mulu.w #SCROLL_STEP_BYTES, %d0
    move.w %d0, %d3             | bytes of the new room already on screen
    move.w #PLAYFIELD_BYTES, %d4
    sub.w %d3, %d4              | bytes of the old room still on screen

    movea.l OFF_SCREEN_PTR(%a5), %a4
    adda.l #PLAYFIELD_ORIGIN, %a4
    movea.l OFF_BG_CUR(%a5), %a2
    adda.l #PLAYFIELD_ORIGIN, %a2
    movea.l OFF_BG_NEXT(%a5), %a3
    adda.l #PLAYFIELD_ORIGIN, %a3
    move.w #PLAYFIELD_HEIGHT, %d0

    btst #0, OFF_SCROLL_DIR(%a5)
    beq 2f

    | Leaving to the right: the old room slides off to the left and the new
    | room follows it in.
    movea.l %a2, %a0
    adda.w %d3, %a0
    movea.l %a4, %a1
    move.w %d4, %d1
    bsr blit_rect
    movea.l %a3, %a0
    movea.l %a4, %a1
    adda.w %d4, %a1
    move.w %d3, %d1
    bsr blit_rect
    bra 9f

2:  | Leaving to the left: the new room's right-hand edge appears first.
    movea.l %a3, %a0
    adda.w %d4, %a0
    movea.l %a4, %a1
    move.w %d3, %d1
    bsr blit_rect
    movea.l %a2, %a0
    movea.l %a4, %a1
    adda.w %d3, %a1
    move.w %d4, %d1
    bsr blit_rect
9:  movem.l (%sp)+, %d0-%d4/%a0-%a4
    rts

| Compose one frame of a vertical scroll. d0.w = step, 1..SCROLL_STEPS_V.
compose_vertical:
    movem.l %d0-%d6/%a0-%a4, -(%sp)
    mulu.w #SCROLL_STEP_PIXELS, %d0
    move.w %d0, %d3             | lines of the new room already on screen
    move.w #PLAYFIELD_HEIGHT, %d4
    sub.w %d3, %d4              | lines of the old room still on screen

    move.w %d3, %d5
    mulu.w #SCREEN_STRIDE, %d5
    move.w %d4, %d6
    mulu.w #SCREEN_STRIDE, %d6

    movea.l OFF_SCREEN_PTR(%a5), %a4
    adda.l #PLAYFIELD_ORIGIN, %a4
    movea.l OFF_BG_CUR(%a5), %a2
    adda.l #PLAYFIELD_ORIGIN, %a2
    movea.l OFF_BG_NEXT(%a5), %a3
    adda.l #PLAYFIELD_ORIGIN, %a3
    move.w #PLAYFIELD_BYTES, %d1

    btst #2, OFF_SCROLL_DIR(%a5)
    beq 2f

    | Leaving downwards: the old room slides up, the new room follows below.
    movea.l %a2, %a0
    adda.l %d5, %a0
    movea.l %a4, %a1
    move.w %d4, %d0
    bsr blit_rect
    movea.l %a3, %a0
    movea.l %a4, %a1
    adda.l %d6, %a1
    move.w %d3, %d0
    bsr blit_rect
    bra 9f

2:  | Leaving upwards: the new room's bottom edge appears first.
    movea.l %a3, %a0
    adda.l %d6, %a0
    movea.l %a4, %a1
    move.w %d3, %d0
    bsr blit_rect
    movea.l %a2, %a0
    movea.l %a4, %a1
    adda.l %d5, %a1
    move.w %d4, %d0
    bsr blit_rect
9:  movem.l (%sp)+, %d0-%d6/%a0-%a4
    rts
