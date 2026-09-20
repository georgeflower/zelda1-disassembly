    .equ SCREEN_STRIDE, 160
    .equ SCREEN_BYTES, 32000
    .equ SCREEN_CLEAR_LONGS, 8000
    .equ METATILE_STRIDE, 8
    .equ METATILE_HEIGHT, 16
    .equ MOVE_REPEAT_FRAMES, 5
    .equ OFF_CURRENT_ROOM, 0
    .equ OFF_PAUSED, 1
    .equ OFF_MOVE_COOLDOWN, 2
    .equ OFF_PLAYER_X, 3
    .equ OFF_PLAYER_Y, 4
    .equ OFF_PLAYER_COLOR, 5
    .equ OFF_ACTION_EVENT, 6
    .equ OFF_START_EVENT, 7
    .equ OFF_SELECT_EVENT, 8
    .equ OFF_EXIT_REQUESTED, 9
    .equ OFF_OLD_SCREEN_HI, 10
    .equ OFF_OLD_SCREEN_MID, 11
    .equ OFF_OLD_SCREEN_LOW, 12
    .equ OFF_OLD_SHIFT_MODE, 13
    .equ OFF_SCREEN_BASE_PTR, 16
    .equ OFF_OLD_PALETTE, 20
    .equ OFF_KEY_STATES, 52

    .equ VIDEO_BASE_HI, 0x00ff8201
    .equ VIDEO_BASE_MID, 0x00ff8203
    .equ VIDEO_BASE_LOW, 0x00ff820d
    .equ PALETTE_BASE, 0x00ff8240
    .equ SHIFT_MODE, 0x00ff8260
    .equ FR_CLOCK, 0x00000462
    .equ IKBD_ACIA_STATUS, 0x00fffc00
    .equ IKBD_ACIA_DATA, 0x00fffc02

    .equ SCAN_ESC, 0x01
    .equ SCAN_TAB, 0x0f
    .equ SCAN_W, 0x11
    .equ SCAN_CTRL, 0x1d
    .equ SCAN_A, 0x1e
    .equ SCAN_S, 0x1f
    .equ SCAN_D, 0x20
    .equ SCAN_RETURN, 0x1c
    .equ SCAN_LSHIFT, 0x2a
    .equ SCAN_RSHIFT, 0x36
    .equ SCAN_SPACE, 0x39
    .equ SCAN_UP, 0x48
    .equ SCAN_LEFT, 0x4b
    .equ SCAN_RIGHT, 0x4d
    .equ SCAN_DOWN, 0x50

    .section .text
    .globl _start
_start:
    lea globals(%pc), %a5
    bsr init_state
    bsr init_video

main_loop:
    bsr wait_vbl
    bsr poll_keyboard
    tst.b OFF_EXIT_REQUESTED(%a5)
    bne exit_program

    bsr update_state
    bsr draw_frame
    bra main_loop

exit_program:
    bsr restore_video
    clr.w -(%sp)
    trap #1

init_state:
    move.b #9, OFF_PLAYER_X(%a5)
    move.b #5, OFF_PLAYER_Y(%a5)
    move.b #15, OFF_PLAYER_COLOR(%a5)
    clr.b OFF_CURRENT_ROOM(%a5)
    clr.b OFF_PAUSED(%a5)
    clr.b OFF_MOVE_COOLDOWN(%a5)
    clr.b OFF_ACTION_EVENT(%a5)
    clr.b OFF_START_EVENT(%a5)
    clr.b OFF_SELECT_EVENT(%a5)
    clr.b OFF_EXIT_REQUESTED(%a5)
    lea OFF_KEY_STATES(%a5), %a0
    moveq #0, %d0
    moveq #127, %d7
clear_keys:
    move.b %d0, (%a0)+
    dbra %d7, clear_keys
    rts

init_video:
    lea OFF_OLD_PALETTE(%a5), %a0
    movea.l #PALETTE_BASE, %a1
    moveq #15, %d7
save_palette:
    move.w (%a1)+, (%a0)+
    dbra %d7, save_palette

    move.b VIDEO_BASE_HI, OFF_OLD_SCREEN_HI(%a5)
    move.b VIDEO_BASE_MID, OFF_OLD_SCREEN_MID(%a5)
    move.b VIDEO_BASE_LOW, OFF_OLD_SCREEN_LOW(%a5)
    move.b SHIFT_MODE, OFF_OLD_SHIFT_MODE(%a5)

    lea screen_buffer_raw(%pc), %a0
    move.l %a0, %d0
    add.l #255, %d0
    and.l #0xffffff00, %d0
    move.l %d0, OFF_SCREEN_BASE_PTR(%a5)
    movea.l %d0, %a0

    moveq #0, %d0
    move.w #(SCREEN_CLEAR_LONGS - 1), %d7
clear_screen:
    move.l %d0, (%a0)+
    dbra %d7, clear_screen

    movea.l OFF_SCREEN_BASE_PTR(%a5), %a0
    move.l %a0, %d0
    lsr.l #8, %d0
    move.b %d0, VIDEO_BASE_MID
    lsr.l #8, %d0
    move.b %d0, VIDEO_BASE_HI

    clr.b SHIFT_MODE
    bsr apply_room_palette
    bsr draw_frame
    rts

restore_video:
    lea OFF_OLD_PALETTE(%a5), %a0
    movea.l #PALETTE_BASE, %a1
    moveq #15, %d7
restore_palette_loop:
    move.w (%a0)+, (%a1)+
    dbra %d7, restore_palette_loop

    move.b OFF_OLD_SCREEN_MID(%a5), VIDEO_BASE_MID
    move.b OFF_OLD_SCREEN_HI(%a5), VIDEO_BASE_HI
    move.b OFF_OLD_SCREEN_LOW(%a5), VIDEO_BASE_LOW
    move.b OFF_OLD_SHIFT_MODE(%a5), SHIFT_MODE
    rts

wait_vbl:
    move.w FR_CLOCK, %d0
wait_vbl_loop:
    cmp.w FR_CLOCK, %d0
    beq wait_vbl_loop
    rts

poll_keyboard:
    clr.b OFF_ACTION_EVENT(%a5)
    clr.b OFF_START_EVENT(%a5)
    clr.b OFF_SELECT_EVENT(%a5)

poll_keyboard_loop:
    move.b IKBD_ACIA_STATUS, %d0
    btst #0, %d0
    beq poll_keyboard_done

    moveq #0, %d0
    move.b IKBD_ACIA_DATA, %d0
    cmpi.b #0x80, %d0
    bcc handle_key_release

    lea OFF_KEY_STATES(%a5), %a0
    tst.b 0(%a0, %d0.w)
    bne poll_keyboard_loop
    move.b #1, 0(%a0, %d0.w)

    cmpi.b #SCAN_ESC, %d0
    bne not_escape
    move.b #1, OFF_EXIT_REQUESTED(%a5)
not_escape:
    cmpi.b #SCAN_SPACE, %d0
    beq set_action_event
    cmpi.b #SCAN_CTRL, %d0
    beq set_action_event
    cmpi.b #SCAN_RETURN, %d0
    beq set_start_event
    cmpi.b #SCAN_RSHIFT, %d0
    beq set_select_event
    cmpi.b #SCAN_TAB, %d0
    beq set_select_event
    bra poll_keyboard_loop

set_action_event:
    move.b #1, OFF_ACTION_EVENT(%a5)
    bra poll_keyboard_loop

set_start_event:
    move.b #1, OFF_START_EVENT(%a5)
    bra poll_keyboard_loop

set_select_event:
    move.b #1, OFF_SELECT_EVENT(%a5)
    bra poll_keyboard_loop

handle_key_release:
    andi.w #0x007f, %d0
    lea OFF_KEY_STATES(%a5), %a0
    clr.b 0(%a0, %d0.w)
    bra poll_keyboard_loop

poll_keyboard_done:
    rts

update_state:
    tst.b OFF_START_EVENT(%a5)
    beq update_select
    eori.b #1, OFF_PAUSED(%a5)

update_select:
    tst.b OFF_SELECT_EVENT(%a5)
    beq update_action
    addq.b #1, OFF_CURRENT_ROOM(%a5)
    cmpi.b #DEMO_ROOM_COUNT, OFF_CURRENT_ROOM(%a5)
    bne room_ok
    clr.b OFF_CURRENT_ROOM(%a5)
room_ok:
    bsr apply_room_palette

update_action:
    tst.b OFF_ACTION_EVENT(%a5)
    beq update_movement
    cmpi.b #15, OFF_PLAYER_COLOR(%a5)
    bne set_bright_color
    move.b #12, OFF_PLAYER_COLOR(%a5)
    bra update_movement
set_bright_color:
    move.b #15, OFF_PLAYER_COLOR(%a5)

update_movement:
    tst.b OFF_PAUSED(%a5)
    bne update_done

    tst.b OFF_MOVE_COOLDOWN(%a5)
    beq check_movement_keys
    subq.b #1, OFF_MOVE_COOLDOWN(%a5)
    bra update_done

check_movement_keys:
    bsr try_move_up
    tst.b %d0
    bne movement_done
    bsr try_move_down
    tst.b %d0
    bne movement_done
    bsr try_move_left
    tst.b %d0
    bne movement_done
    bsr try_move_right
    tst.b %d0
    bne movement_done
    bra update_done

movement_done:
    move.b #MOVE_REPEAT_FRAMES, OFF_MOVE_COOLDOWN(%a5)

update_done:
    rts

try_move_up:
    lea OFF_KEY_STATES(%a5), %a0
    tst.b SCAN_UP(%a0)
    bne do_move_up
    tst.b SCAN_W(%a0)
    beq no_move_up

do_move_up:
    tst.b OFF_PLAYER_Y(%a5)
    beq no_move_up
    subq.b #1, OFF_PLAYER_Y(%a5)
    moveq #1, %d0
    rts

no_move_up:
    moveq #0, %d0
    rts

try_move_down:
    lea OFF_KEY_STATES(%a5), %a0
    tst.b SCAN_DOWN(%a0)
    bne do_move_down
    tst.b SCAN_S(%a0)
    beq no_move_down

do_move_down:
    cmpi.b #(DEMO_MAP_HEIGHT - 1), OFF_PLAYER_Y(%a5)
    beq no_move_down
    addq.b #1, OFF_PLAYER_Y(%a5)
    moveq #1, %d0
    rts

no_move_down:
    moveq #0, %d0
    rts

try_move_left:
    lea OFF_KEY_STATES(%a5), %a0
    tst.b SCAN_LEFT(%a0)
    bne do_move_left
    tst.b SCAN_A(%a0)
    beq no_move_left

do_move_left:
    tst.b OFF_PLAYER_X(%a5)
    beq no_move_left
    subq.b #1, OFF_PLAYER_X(%a5)
    moveq #1, %d0
    rts

no_move_left:
    moveq #0, %d0
    rts

try_move_right:
    lea OFF_KEY_STATES(%a5), %a0
    tst.b SCAN_RIGHT(%a0)
    bne do_move_right
    tst.b SCAN_D(%a0)
    beq no_move_right

do_move_right:
    cmpi.b #(DEMO_MAP_WIDTH - 1), OFF_PLAYER_X(%a5)
    beq no_move_right
    addq.b #1, OFF_PLAYER_X(%a5)
    moveq #1, %d0
    rts

no_move_right:
    moveq #0, %d0
    rts

apply_room_palette:
    lea room_palettes(%pc), %a0
    moveq #0, %d0
    move.b OFF_CURRENT_ROOM(%a5), %d0
    lsl.w #5, %d0
    adda.w %d0, %a0
    movea.l #PALETTE_BASE, %a1
    moveq #15, %d7
palette_copy_loop:
    move.w (%a0)+, (%a1)+
    dbra %d7, palette_copy_loop
    rts

draw_frame:
    bsr draw_room
    bsr draw_player
    rts

draw_room:
    lea room_maps(%pc), %a0
    moveq #0, %d0
    move.b OFF_CURRENT_ROOM(%a5), %d0
    mulu.w #DEMO_ROOM_BYTES, %d0
    adda.l %d0, %a0

    movea.l OFF_SCREEN_BASE_PTR(%a5), %a1
    moveq #(DEMO_MAP_HEIGHT - 1), %d7
row_loop:
    movea.l %a1, %a2
    moveq #(DEMO_MAP_WIDTH - 1), %d6
col_loop:
    moveq #0, %d0
    move.b (%a0)+, %d0
    mulu.w #DEMO_METATILE_BYTES, %d0
    lea demo_metatiles(%pc), %a3
    adda.l %d0, %a3
    movea.l %a2, %a4
    moveq #(METATILE_HEIGHT - 1), %d5
copy_metatile_row:
    move.l (%a3)+, (%a4)+
    move.l (%a3)+, (%a4)+
    adda.w #(SCREEN_STRIDE - METATILE_STRIDE), %a4
    dbra %d5, copy_metatile_row
    adda.w #METATILE_STRIDE, %a2
    dbra %d6, col_loop
    adda.l #(SCREEN_STRIDE * METATILE_HEIGHT), %a1
    dbra %d7, row_loop
    rts

draw_player:
    movea.l OFF_SCREEN_BASE_PTR(%a5), %a0
    moveq #0, %d0
    move.b OFF_PLAYER_Y(%a5), %d0
    mulu.w #(SCREEN_STRIDE * METATILE_HEIGHT), %d0
    adda.l %d0, %a0

    moveq #0, %d0
    move.b OFF_PLAYER_X(%a5), %d0
    lsl.w #3, %d0
    adda.w %d0, %a0

    moveq #0, %d0
    move.b OFF_PLAYER_COLOR(%a5), %d0
    moveq #0, %d1
    moveq #0, %d2
    moveq #0, %d3
    moveq #0, %d4
    btst #0, %d0
    beq plane1_done
    move.w #-1, %d1
plane1_done:
    btst #1, %d0
    beq plane2_done
    move.w #-1, %d2
plane2_done:
    btst #2, %d0
    beq plane3_done
    move.w #-1, %d3
plane3_done:
    btst #3, %d0
    beq plane4_done
    move.w #-1, %d4
plane4_done:

    moveq #(METATILE_HEIGHT - 1), %d7
player_row_loop:
    move.w %d1, (%a0)
    move.w %d2, 2(%a0)
    move.w %d3, 4(%a0)
    move.w %d4, 6(%a0)
    adda.w #SCREEN_STRIDE, %a0
    dbra %d7, player_row_loop
    rts

    .section .rodata
    .include "demo_assets.inc"
    .align 2
demo_metatiles:
    .incbin "demo_metatiles.bin"

    .section .data
globals:
    .space 180
    .align 8
screen_buffer_raw:
    .space 32256
