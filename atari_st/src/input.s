| IKBD keyboard polling.
|
| TOS' own handler is masked off in init_video, so scan codes are read straight
| from the ACIA and tracked in a key-state table the game logic samples.

    .equ SCAN_ESC, 0x01
    .equ SCAN_W, 0x11
    .equ SCAN_A, 0x1e
    .equ SCAN_S, 0x1f
    .equ SCAN_D, 0x20
    .equ SCAN_UP, 0x48
    .equ SCAN_LEFT, 0x4b
    .equ SCAN_RIGHT, 0x4d
    .equ SCAN_DOWN, 0x50
    .equ SCAN_RELEASE_BIT, 0x80

poll_keyboard:
    movem.l %d0/%a0, -(%sp)
1:  movea.l #IKBD_ACIA_STATUS, %a0
    move.b (%a0), %d0
    btst #0, %d0
    beq 9f

    moveq #0, %d0
    movea.l #IKBD_ACIA_DATA, %a0
    move.b (%a0), %d0
    cmpi.b #SCAN_RELEASE_BIT, %d0
    bcc 3f

    lea OFF_KEY_STATES(%a5), %a0
    move.b #1, 0(%a0, %d0.w)
    cmpi.b #SCAN_ESC, %d0
    bne 1b
    move.b #1, OFF_EXIT_REQUESTED(%a5)
    bra 1b

3:  andi.w #0x007f, %d0
    lea OFF_KEY_STATES(%a5), %a0
    clr.b 0(%a0, %d0.w)
    bra 1b

9:  movem.l (%sp)+, %d0/%a0
    rts
