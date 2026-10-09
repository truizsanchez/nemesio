"""The game's ending, once the ship has left stage 8: a screen of its own.

Bank 0, 0x4AC0 ("dispatch the ship's end"), steps 1 to 9 of 0xE1D1 --
step 0, the ship flying off to the right, is the engine's. None of it is
play: it is the cartridge drawing into VRAM, so it lives here, next to the
title's screens, and hands its VRAM to whoever draws.

1. once the sound has stopped: the letters, and bank 10's pictures of the
   end; a 4x4 drawing in the middle of the screen, and the sound 0x38;
2. shrapnel out of the middle, one piece every three game frames, 0xC0 of
   them, each in one of sixteen directions the R register picks (0x4CC9);
3. the drawing turns into three others, 0x10 game frames each, and goes;
4. the power-up meter's six cells light one by one, faster and faster;
5. the border flickers, colour 3 and 9;
6-8. the screen clears and, a letter every six game frames, GOOD, NICE,
   FINE or GREAT by the round -- CONGRATULATIONS the fifth -- then
   BONUS 50000 POINTS, and the 500 (in BCD hundreds) are paid;
9. once the sound has stopped, it is over.
"""

from __future__ import annotations

import random

from game.rom.band import write_stream
from game.rom.cartridge import Cartridge, Paging
from game.rom import rle
from game.rom.screens import load_font
from game.vdp import COLOURS, NAMES, PATTERNS, SPRITE_PATTERNS, THIRD, Vram

#: Bank 10's pictures of the end: patterns and colours from character 0x83
#: on in all three thirds, and the sprite patterns (0x4B11..0x4B29).
BANKS = {0x6000: 1, 0x8000: 2, 0xA000: 10}
PICTURES = ((0xA0DB, PATTERNS + 0x418), (0xA3F4, COLOURS + 0x418))
SPRITE_PICTURES = 0xA683
#: The 4x4 drawing and its wiping (0x4FB2, 0x4FCE); its three changes, in
#: bank 1 at 0x6340, go to row 5, column 14 (0x38AE).
DRAWING, WIPE, CHANGES, CHANGE_AT = 0x4FB2, 0x4FCE, 0x6340, 0x38AE
#: The meter's six drawings (0x4EDA), and how long each stays (0x4C10).
METER, METER_TIMES = 0x4EDA, (0x28, 0x28, 0x10, 0x0C, 0x08, 0x04)
#: The words by round (0x4FEA), CONGRATULATIONS (0x502E) and the bonus (0x5040).
WORDS, CONGRATULATIONS, BONUS_WORDS, ROUNDS = 0x4FEA, 0x502E, 0x5040, 5
BONUS = 500
#: The shrapnel: 32 pieces of 16 bytes, from (0x38, 0x80); 0xC0 of them, one
#: every three game frames; pattern 0x2C in colour 7, turning into 0x30,
#: 0x34, 0x38 (the first kind, at 0x0C, 0x18, 0x24 game frames) or 0x30
#: (the other, halved in speed, at 0x60). Off past row 0xC0 or column 0xF8.
PIECES, PIECES_OUT, PIECE_EVERY = 32, 0xC0, 3
PIECE_ROW, PIECE_COL, PIECE_PATTERN, PIECE_COLOUR = 0x38, 0x80, 0x2C, 7
DIRECTIONS = 0x4D3E
GONE_ROW, GONE_COL = 0xC0, 0xF8
#: The sounds the steps end on (0x4B4E, 0x4B7A, 0x4BD0, 0x4C5A), and the
#: letters' pace.
SOUNDS = {1: 0x38, 2: 0x3B, 3: 0x44, 6: 0xA9}
LETTER_EVERY = 6
#: The border's two colours in step 5 (0x4E8E).
BORDER = (9, 3)
#: With 0xE1D1 up a game frame is cut short (0x4545), so it takes one
#: interrupt, not the usual two -- except the one that loads bank 10's
#: pictures (8) and the one that clears for the words (2). Measured on the
#: 60 Hz machine; the sounds the steps wait for run on interrupts.
INTERRUPTS, LOAD_INTERRUPTS, WORDS_INTERRUPTS = 1, 8, 2


class Finale:
    def __init__(self, cart: Cartridge, rng: random.Random, round_: int, vram: Vram,
                 japanese: bool = False) -> None:
        """`vram` is the play's as the fade left it: what bank 10 does not
        load over stays."""
        self.cart = cart
        self.rng = rng
        #: 0xE070: which round's word.
        self.round = round_ % ROUNDS
        self.japanese = japanese
        self.vram = vram
        self.names = bytearray(768)
        #: 0xE1D1, 0xE1D2, 0xE1D5, 0xE1D7, 0xE1D9.
        self.step = 1
        self.clock = 0
        self.pieces_left = 0
        self.piece_clock = 0
        self.at = 0
        #: The shrapnel: [kind, frames, row (8.8), col (8.8), vy, vx].
        self.pieces: list[list[int] | None] = [None] * PIECES
        self.border = 0
        self.sprites_on = False
        #: The slow words: where they go and what is left of them.
        self.letters: tuple[int, int] | None = None
        self.letter_clock = 0
        self.loaded = False
        self.sounds: list[int] = []
        self.music_fade = False
        self.bonus = 0
        self.done = False
        #: How many interrupts this game frame took.
        self.interrupts = INTERRUPTS

    # -- a game frame ------------------------------------------------------------------

    def update(self, busy: bool) -> None:
        self.sounds = []
        self.music_fade = False
        self.bonus = 0
        self.loaded = False
        self.interrupts = INTERRUPTS
        step = self.step
        if step == 1:
            if busy:
                return
            self._load()
            self.interrupts = LOAD_INTERRUPTS
            write_stream(self.cart, DRAWING, self.names)
            self.clock, self.pieces_left, self.piece_clock = 0, PIECES_OUT, PIECE_EVERY
            self.sprites_on = True
            self._next()
        elif step == 2:
            self._release()
            self._move()
            if not self.pieces_left:
                self.clock, self.at = 0x10, 0
                self._next()
        elif step == 3:
            self._move()
            self.clock -= 1
            if not self.clock:
                self.clock = 0x10
                self.at += 1
                if self.at == 3:
                    write_stream(self.cart, WIPE, self.names)
                    self.at, self.clock = 0, 0x40
                    self._next()
                    return
            self._change()
        elif step == 4:
            self._move()
            self.clock -= 1
            if not self.clock:
                self.at += 1
                if self.at == len(METER_TIMES):
                    self.sprites_on = False
                    self.clock = 0x20
                    self._next()
                    return
                self.clock = METER_TIMES[self.at]
            write_stream(self.cart, self.cart.word(0, METER + 2 * self.at), self.names)
        elif step == 5:
            self.border = BORDER[self.clock >> 1 & 1]
            self.clock -= 1
            if not self.clock:
                self.border = 0
                self.clock = 0x28
                self._next()
        elif step == 6:
            self.names[:] = bytes(768)
            load_font(self.cart, self.vram)
            self.loaded = True
            self.interrupts = WORDS_INTERRUPTS
            if self.round == ROUNDS - 1 and not self.japanese:
                words = CONGRATULATIONS
            else:
                words = self.cart.word(0, WORDS + 2 * self.round)
            self._slowly(words)
            self._next()
        elif step == 7:
            if self._letter():
                return
            self.music_fade = True
            self._slowly(BONUS_WORDS)
            self._next()
        elif step == 8:
            if self._letter():
                return
            self.bonus = BONUS
            self._next()
        elif not busy:
            self.names[:] = bytes(768)
            self.done = True

    def _next(self) -> None:
        """0x4AFA, with the sound the step ends on."""
        sound = SOUNDS.get(self.step)
        if sound is not None:
            self.sounds.append(sound)
        self.step += 1

    def _load(self) -> None:
        """0x4B04."""
        self.names[:] = bytes(768)
        load_font(self.cart, self.vram)
        source = Paging(self.cart, BANKS)
        for block, to in PICTURES:
            for third in range(3):
                rle.unpack(source, block, self.vram, to + third * THIRD)
        rle.unpack(source, SPRITE_PICTURES, self.vram, SPRITE_PATTERNS)
        self.loaded = True

    def _change(self) -> None:
        """0x4B9C: drawing `at` of the three, 4x4, at row 5, column 14."""
        at = CHANGE_AT - NAMES
        drawing = CHANGES + self.at * 16
        for row in range(4):
            for col in range(4):
                self.names[at + row * 32 + col] = self.cart.byte(1, drawing + row * 4 + col)

    # -- the shrapnel (0x4CC9..0x4E39) --------------------------------------------------

    def _release(self) -> None:
        self.piece_clock -= 1
        if self.piece_clock:
            return
        self.piece_clock = PIECE_EVERY
        if not self.pieces_left:
            return
        self.pieces_left -= 1
        # R's bit 0 (0x4CDC): set, the other kind.
        kind = 2 if self.rng.randrange(2) else 1
        free = next((n for n, p in enumerate(self.pieces) if p is None), None)
        if free is None:
            return
        at = DIRECTIONS + 4 * self.rng.randrange(16)
        vy, vx = self.cart.word(0, at), self.cart.word(0, at + 2)
        if kind == 2:
            vy, vx = _half(vy), _half(vx)
        # Two more reads of R, seven bits each, onto the low bytes (0x4D20).
        vy = (vy + self.rng.randrange(128)) & 0xFFFF
        vx = (vx + self.rng.randrange(128)) & 0xFFFF
        self.pieces[free] = [kind, 0, PIECE_ROW << 8, PIECE_COL << 8, vy, vx]

    def _move(self) -> None:
        for n, piece in enumerate(self.pieces):
            if piece is None:
                continue
            row = piece[2] + piece[4]
            if (row >> 8) & 0xFF >= GONE_ROW:
                self.pieces[n] = None
                continue
            piece[2] = row & 0xFFFF
            piece[3] = (piece[3] + piece[5]) & 0xFFFF
            if piece[3] >> 8 >= GONE_COL:
                self.pieces[n] = None
                continue
            piece[1] = (piece[1] + 1) & 0xFF

    @staticmethod
    def pattern(piece: list[int]) -> int:
        """0x4E13 and 0x4E2E."""
        frames = piece[1]
        if piece[0] == 1:
            return PIECE_PATTERN + 4 * sum(frames >= t for t in (0x0C, 0x18, 0x24))
        return PIECE_PATTERN + (4 if frames >= 0x60 else 0)

    def sprites(self) -> list[tuple[int, int, int, int]]:
        """(row, column, pattern, colour), the first in front."""
        if not self.sprites_on:
            return []
        return [(p[2] >> 8, p[3] >> 8, self.pattern(p), PIECE_COLOUR)
                for p in self.pieces if p is not None]

    # -- the words, a letter at a time (0x4E9C, 0x4EAD) ---------------------------------

    def _slowly(self, at: int) -> None:
        self.letters = (self.cart.word(0, at), at + 2)
        self.letter_clock = 1

    def _letter(self) -> bool:
        """True while there are letters to come."""
        self.letter_clock -= 1
        if self.letter_clock:
            return True
        self.letter_clock = LETTER_EVERY
        assert self.letters is not None
        to, at = self.letters
        value = self.cart.byte(0, at)
        if value == 0xFF:
            return False
        if value == 0xFE:
            to = self.cart.word(0, at + 1)
            at += 3
            value = self.cart.byte(0, at)
        self.names[to - NAMES] = value
        self.letters = (to + 1, at + 1)
        return True


def _half(value: int) -> int:
    """`sra d / rr e`: a signed word halved."""
    return (value >> 1 | value & 0x8000) & 0xFFFF
