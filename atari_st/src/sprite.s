| Masked sprite blitting.
|
| A 16-pixel-wide sprite at an arbitrary X straddles two 16-pixel bitplane
| groups, so each row is widened to a 32-bit value, shifted into place, and
| merged into both groups under the sprite's own opacity mask. Shifting at run
| time rather than pre-shifting at build time costs a few thousand cycles per
| sprite -- negligible against a 160,000-cycle frame -- and avoids spending
| 40KB per character on sixteen pre-rotated copies.

| Merge one 16-pixel group. a2 points at the group's four bitplane words,
| d1..d4 hold the shifted bitplane data and d5 the shifted mask, all in their
| low words. d6 is scratch and a2 advances past the group.
    .macro sprite_merge_group plane
    move.w %d5, %d6
    not.w %d6
    and.w (%a2), %d6
    or.w \plane, %d6
    move.w %d6, (%a2)+
    .endm

| Widen one 16-bit row into a shifted 32-bit value.
    .macro sprite_shift_word reg
    move.w (%a0)+, \reg
    swap \reg
    clr.w \reg
    lsr.l %d0, \reg
    .endm

| a0 = frame data, a1 = top-left group in the destination, d0.w = shift 0..15
draw_sprite:
    movem.l %d0-%d7/%a0-%a2, -(%sp)
    moveq #(SPRITE_HEIGHT - 1), %d7
1:  sprite_shift_word %d1
    sprite_shift_word %d2
    sprite_shift_word %d3
    sprite_shift_word %d4
    sprite_shift_word %d5

    | After the shift the left-hand pixels sit in the high halves, so swap them
    | down, merge, then swap again for the right-hand group.
    swap %d1
    swap %d2
    swap %d3
    swap %d4
    swap %d5
    movea.l %a1, %a2
    sprite_merge_group %d1
    sprite_merge_group %d2
    sprite_merge_group %d3
    sprite_merge_group %d4

    swap %d1
    swap %d2
    swap %d3
    swap %d4
    swap %d5
    lea 8(%a1), %a2
    sprite_merge_group %d1
    sprite_merge_group %d2
    sprite_merge_group %d3
    sprite_merge_group %d4

    adda.w #SCREEN_STRIDE, %a1
    dbra %d7, 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a2
    rts

| Put back the background the sprite covered last frame.
erase_sprite:
    tst.b OFF_ERASE_VALID(%a5)
    beq 9f
    movem.l %d0/%d7/%a0-%a1, -(%sp)
    move.l OFF_ERASE_OFFSET(%a5), %d0
    movea.l OFF_BG_CUR(%a5), %a0
    adda.l %d0, %a0
    movea.l OFF_SCREEN_PTR(%a5), %a1
    adda.l %d0, %a1
    moveq #(SPRITE_HEIGHT - 1), %d7
1:  move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    adda.w #(SCREEN_STRIDE - SPRITE_SPAN_BYTES), %a0
    adda.w #(SCREEN_STRIDE - SPRITE_SPAN_BYTES), %a1
    dbra %d7, 1b
    clr.b OFF_ERASE_VALID(%a5)
    movem.l (%sp)+, %d0/%d7/%a0-%a1
9:  rts

| Draw Link at his current position, recording where so the next frame can
| put the background back.
draw_link:
    movem.l %d0-%d2/%a0-%a1, -(%sp)

    | Pick the frame: direction chooses the pair, the walk counter the phase.
    moveq #LINK_FRAME_UP_A, %d0
    move.b OFF_LINK_DIR(%a5), %d1
    btst #0, %d1
    beq 1f
    moveq #LINK_FRAME_RIGHT_A, %d0
    bra 4f
1:  btst #1, %d1
    beq 2f
    moveq #LINK_FRAME_LEFT_A, %d0
    bra 4f
2:  btst #2, %d1
    beq 4f
    moveq #LINK_FRAME_DOWN_A, %d0
4:  add.b OFF_LINK_ANIM_FRAME(%a5), %d0
    mulu.w #SPRITE_FRAME_BYTES, %d0
    lea link_sprites(%pc), %a0
    adda.l %d0, %a0

    | Screen X, then split into a group offset and a shift within the group.
    moveq #0, %d0
    move.b OFF_LINK_X(%a5), %d0
    add.w #(PLAYFIELD_LEFT * 2), %d0
    move.w %d0, %d2
    and.w #15, %d2
    lsr.w #4, %d0
    lsl.w #3, %d0

    moveq #0, %d1
    move.b OFF_LINK_Y(%a5), %d1
    sub.w #LINK_Y_BIAS, %d1
    mulu.w #SCREEN_STRIDE, %d1
    add.l %d1, %d0

    move.l %d0, OFF_ERASE_OFFSET(%a5)
    move.b #1, OFF_ERASE_VALID(%a5)

    movea.l OFF_SCREEN_PTR(%a5), %a1
    adda.l %d0, %a1
    move.w %d2, %d0
    bsr draw_sprite

    movem.l (%sp)+, %d0-%d2/%a0-%a1
    rts
