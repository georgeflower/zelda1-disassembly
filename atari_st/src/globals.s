| Variable block layout.
|
| Offsets are generated rather than hand-counted so adding a variable cannot
| silently overlap its neighbour. Longs come first, then words, then bytes,
| so everything that needs even alignment gets it.

    .set gvar_offset, 0

    .macro gvar name, size=1
    .equ OFF_\name, gvar_offset
    .set gvar_offset, gvar_offset + \size
    .endm

    .macro galign
    .set gvar_offset, ((gvar_offset + 1) / 2) * 2
    .endm

    gvar SCREEN_PTR, 4          | visible screen
    gvar BG_CUR, 4              | clean render of the current room
    gvar BG_NEXT, 4             | room being scrolled in
    gvar BASEPAGE, 4
    gvar OLD_SSP, 4
    gvar ERASE_OFFSET, 4        | where the sprite was drawn last frame

    gvar FRAME_COUNTER, 2
    gvar SCROLL_STEP, 2

    gvar ROOM_ID, 1
    gvar NEXT_ROOM_ID, 1
    gvar LINK_X, 1
    gvar LINK_Y, 1
    gvar LINK_DIR, 1
    gvar LINK_ANIM_FRAME, 1
    gvar LINK_ANIM_COUNTER, 1
    gvar LINK_POS_FRAC, 1
    gvar PREV_INPUT_DIR, 1
    gvar GAME_MODE, 1
    gvar SCROLL_DIR, 1
    gvar SCROLL_FROM_X, 1
    gvar SCROLL_FROM_Y, 1
    gvar SCROLL_TO_X, 1
    gvar SCROLL_TO_Y, 1
    gvar ERASE_VALID, 1
    gvar HUD_DIRTY, 1
    gvar EXIT_REQUESTED, 1
    gvar HEART_CONTAINERS, 1
    gvar HEART_FILLED, 1
    gvar INV_RUPEES, 1
    gvar INV_KEYS, 1
    gvar INV_BOMBS, 1
    gvar OLD_SCREEN_HI, 1
    gvar OLD_SCREEN_MID, 1
    gvar OLD_SCREEN_LOW, 1
    gvar OLD_SHIFT_MODE, 1
    gvar OLD_IERB, 1
    gvar OLD_IMRB, 1

    galign
    gvar OLD_PALETTE, 32
    gvar KEY_STATES, 128

    .equ GLOBALS_BYTES, gvar_offset
