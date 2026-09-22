| The status ribbon.
|
| An 8x8 tile is exactly one byte of an ST bitplane word, so HUD glyphs are
| stored as eight rows of four bytes and drawn with plain byte stores -- no
| shifting, and no need to go through the sprite blitter.

draw_hud:
    movem.l %d0-%d4, -(%sp)
    clr.b OFF_HUD_DIRTY(%a5)

    moveq #HUD_RUPEE, %d3
    moveq #0, %d4
    move.b OFF_INV_RUPEES(%a5), %d4
    moveq #0, %d2
    bsr draw_hud_counter

    moveq #HUD_KEY, %d3
    moveq #0, %d4
    move.b OFF_INV_KEYS(%a5), %d4
    moveq #1, %d2
    bsr draw_hud_counter

    moveq #HUD_BOMB, %d3
    moveq #0, %d4
    move.b OFF_INV_BOMBS(%a5), %d4
    moveq #2, %d2
    bsr draw_hud_counter

    | "LIFE" sits above the two rows of hearts, as it does on the NES.
    moveq #0, %d2
    moveq #HUD_HEART_COL, %d1
    moveq #HUD_L, %d0
    bsr draw_hud_tile
    addq.w #1, %d1
    moveq #HUD_I, %d0
    bsr draw_hud_tile
    addq.w #1, %d1
    moveq #HUD_F, %d0
    bsr draw_hud_tile
    addq.w #1, %d1
    moveq #HUD_E, %d0
    bsr draw_hud_tile

    bsr draw_hud_hearts
    movem.l (%sp)+, %d0-%d4
    rts

| One "<icon> X nn" counter. d3.w = icon tile, d4.b = value, d2.w = HUD row.
draw_hud_counter:
    movem.l %d0-%d2/%d4-%d5, -(%sp)
    moveq #HUD_COUNTER_COL, %d1
    move.w %d3, %d0
    bsr draw_hud_tile

    addq.w #1, %d1
    moveq #HUD_X, %d0
    bsr draw_hud_tile

    | divu.w divides the whole 32-bit register, so clear it down to the byte
    | the caller actually passed.
    and.l #0xFF, %d4
    divu.w #10, %d4
    move.l %d4, %d5
    swap %d5                    | remainder: the units digit
    addq.w #1, %d1
    move.w %d4, %d0
    and.w #0xFF, %d0
    add.w #HUD_DIGIT0, %d0
    bsr draw_hud_tile

    addq.w #1, %d1
    move.w %d5, %d0
    add.w #HUD_DIGIT0, %d0
    bsr draw_hud_tile
    movem.l (%sp)+, %d0-%d2/%d4-%d5
    rts

draw_hud_hearts:
    movem.l %d0-%d4, -(%sp)
    moveq #0, %d4               | heart slot 0..15
1:  moveq #HUD_HEART_EMPTY, %d0
    move.b OFF_HEART_CONTAINERS(%a5), %d3
    and.w #0xFF, %d3
    cmp.w %d3, %d4
    blo 2f
    moveq #HUD_BLANK, %d0       | past the containers Link owns
    bra 4f
2:  move.b OFF_HEART_FILLED(%a5), %d3
    and.w #0xFF, %d3
    cmp.w %d3, %d4
    bhs 4f
    moveq #HUD_HEART_FULL, %d0

4:  move.w %d4, %d1
    and.w #(HUD_HEARTS_PER_ROW - 1), %d1
    add.w #HUD_HEART_COL, %d1
    move.w %d4, %d2
    lsr.w #3, %d2
    addq.w #1, %d2              | hearts occupy HUD rows 1 and 2
    bsr draw_hud_tile

    addq.w #1, %d4
    cmp.w #HUD_HEART_SLOTS, %d4
    blo 1b
    movem.l (%sp)+, %d0-%d4
    rts

| Draw one 8x8 glyph. d0.w = tile index, d1.w = column 0..39, d2.w = HUD row.
draw_hud_tile:
    movem.l %d0-%d3/%d7/%a0-%a1, -(%sp)
    lea hud_tiles(%pc), %a0
    mulu.w #HUD_TILE_BYTES, %d0
    adda.l %d0, %a0

    movea.l OFF_SCREEN_PTR(%a5), %a1
    move.w %d2, %d3
    mulu.w #(8 * SCREEN_STRIDE), %d3
    adda.l %d3, %a1

    | Two tile columns share one 16-pixel group; the odd one is its low byte.
    move.w %d1, %d3
    lsr.w #1, %d3
    lsl.w #3, %d3
    adda.w %d3, %a1
    btst #0, %d1
    beq 1f
    addq.l #1, %a1

1:  moveq #7, %d7
2:  move.b (%a0)+, 0(%a1)
    move.b (%a0)+, 2(%a1)
    move.b (%a0)+, 4(%a1)
    move.b (%a0)+, 6(%a1)
    adda.w #SCREEN_STRIDE, %a1
    dbra %d7, 2b
    movem.l (%sp)+, %d0-%d3/%d7/%a0-%a1
    rts
