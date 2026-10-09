"""What the cartridge shows when nobody plays: the Konami logo, and the
picture that plays the title tune. The demo between them is a play fed a
recorded pad (`demo_pad`), run by the host.

Bank 0's states 0 and 2 (0x52D7, 0x5312), a video frame at a time:

- the logo (0x5A46): on the blue backdrop, three strips of characters rise a
  row every other frame from row 21 to row 7 -- the letters of Konami and
  SOFTWARE -- then the mark comes (0x57BD) and it stays 256 frames;
- the picture (0x5BF8): the screen is wiped a column a frame (0x558A), then
  bank 9's picture and the sound 0xA6; while it plays, three characters
  twinkle through six colours (0xBDD2), seven stars blink (0xBE2B), and
  three emitters throw comets of four sprites (bank 10, 0xA88D).
"""

from __future__ import annotations

import random

from game.rom import rle
from game.rom.cartridge import Cartridge, Paging
from game.rom.screens import load_font
from game.vdp import COLOURS, NAMES, PATTERNS, SPRITE_PATTERNS, THIRD, Vram

BANKS = {0x6000: 1, 0x8000: 9, 0xA000: 10}
#: 0x575A's register 7: white on blue; the play's backdrop is black.
BACKDROP = 4

# -- the logo ------------------------------------------------------------------------

#: The letters (0x5A9A) in every third from character 0x40, white (0x5A54).
LOGO, LOGO_CHAR, LOGO_COLOUR, LOGO_COLOURS = 0x5A9A, 0x40, 0xF0, 0xD8
#: Fourteen rows up from row 21, column 10; strips of 3, 11 and 12 (0x5A46).
LOGO_STEPS, LOGO_FROM, LOGO_STRIPS = 14, 0x3AAA, (3, 11, 12)
#: Then the mark (0x57BD, its destination in its first two bytes), and 256
#: frames (0x52E8).
MARK, LOGO_STAYS = 0x57BD, 0x100


class Logo:
    def __init__(self, cart: Cartridge) -> None:
        self.cart = cart
        self.vram = Vram()
        load_font(cart, self.vram)
        source = Paging(cart, BANKS)
        for third in range(3):
            rle.unpack(source, LOGO, self.vram, PATTERNS + third * THIRD + LOGO_CHAR * 8)
            for n in range(LOGO_COLOURS):
                self.vram[COLOURS + third * THIRD + LOGO_CHAR * 8 + n] = LOGO_COLOUR
        self.steps = LOGO_STEPS
        self.cursor = LOGO_FROM
        self.frames = 0
        self.stay = 0
        self.done = False

    @property
    def names(self) -> bytes:
        return bytes(self.vram.data[NAMES:NAMES + 768])

    def update(self) -> None:
        """A video frame: 0x52D9 rises on odd frames of 0xE003."""
        self.frames += 1
        if self.steps:
            if not self.frames & 1:
                return
            self.cursor -= 0x20
            at, char = self.cursor, LOGO_CHAR
            for count in LOGO_STRIPS:
                for n in range(count):
                    self.vram[at + n] = char + n
                char += count
                at += 0x20
            for n in range(LOGO_STRIPS[-1]):
                self.vram[at + n] = 0
            self.steps -= 1
            if not self.steps:
                source = Paging(self.cart, BANKS)
                rle.unpack(source, MARK + 2, self.vram, self.cart.word(0, MARK))
                self.stay = LOGO_STAYS
            return
        self.stay -= 1
        if not self.stay:
            self.done = True


# -- the picture ---------------------------------------------------------------------

#: Bank 9's three thirds of patterns and colours from character 1 (0x5C0F),
#: bank 10's frame characters from 0xF0 in every third and the sprites, and
#: the 768 names, not compressed, at bank 9's 0x8000.
PICTURE = ((0x8300, PATTERNS + 8), (0x87FA, PATTERNS + THIRD + 8),
           (0x8CB2, PATTERNS + 2 * THIRD + 8), (0x917E, COLOURS + 8),
           (0x9515, COLOURS + THIRD + 8), (0x989F, COLOURS + 2 * THIRD + 8))
FRAME = ((0xA758, PATTERNS + 0x780), (0xA783, COLOURS + 0x780))
PICTURE_SPRITES, PICTURE_NAMES = 0xA7A4, 0x8000
TUNE = 0xA6
#: The wipe: a column a frame, 0x21 frames (0x558A).
WIPE = 0x20
#: The three twinkling characters, their six colours each (bank 3, 0xBE19)
#: and their first clocks (0xA82E); 8 to 0x17 frames a colour, by R.
TWINKLES, TWINKLE_COLOURS, TWINKLE_CLOCKS = (0xF6, 0xF7, 0xF8), 0xBE19, (0x10, 0x18, 0x20)
#: The seven stars: (clock, its reload, step, name address) (0xA849), their
#: four characters (0xBE62), each over the next below.
STARS, STAR_CHARS = 0xA849, 0xBE62
#: Three emitters (0xA881: kind, clock, row, column); a comet of their four
#: kinds every eight frames, a rest of 0x60 every four (0xA927); its kind's
#: start (0xA995), steps (0xA8F3) and sprites' offsets (0xAA46); colour by
#: emitter (0xA9B9).
EMITTERS, KINDS, STARTS, STEPS, OFFSETS, COMET_COLOURS = (0xA881, 0xA989, 0xA995, 0xA8F3,
                                                         0xAA46, 0xA9B9)
COMETS, COMET_EVERY, COMET_REST = 8, 8, 0x60


class Picture:
    def __init__(self, cart: Cartridge, rng: random.Random, names: bytes) -> None:
        """`names`: the screen it wipes."""
        self.cart = cart
        self.rng = rng
        self.vram = Vram()
        self.vram.data[NAMES:NAMES + 768] = names
        self.wipe = WIPE
        self.shown = False
        self.sounds: list[int] = []
        self.loaded = False
        self.done = False
        self.twinkles = [[0, clock] for clock in TWINKLE_CLOCKS]
        self.stars = [list(cart.block(10, STARS + 8 * n, 5)) for n in range(7)]
        self.emitters = [[*cart.block(10, EMITTERS + 4 * n, 4), 0] for n in range(3)]
        #: [kind, grown, clock, row, col, sprites, pattern, colour].
        self.comets: list[list[int] | None] = [None] * COMETS

    @property
    def names(self) -> bytes:
        return bytes(self.vram.data[NAMES:NAMES + 768])

    def update(self, busy: bool) -> None:
        self.sounds, self.loaded = [], False
        if not self.shown:
            if self.wipe >= 0:
                col = self.wipe ^ 0x1F
                for row in range(24):
                    self.vram[NAMES + row * 32 + col] = 0
                self.wipe -= 1
                return
            self._load()
            return
        self._comets()
        self._twinkle()
        if not busy:
            self.done = True

    def _load(self) -> None:
        """0x5BF8."""
        load_font(self.cart, self.vram)
        source = Paging(self.cart, BANKS)
        for block, to in PICTURE:
            rle.unpack(source, block, self.vram, to)
        for block, to in FRAME:
            for third in range(3):
                rle.unpack(source, block, self.vram, to + third * THIRD)
        rle.unpack(source, PICTURE_SPRITES, self.vram, SPRITE_PATTERNS)
        self.vram.data[NAMES:NAMES + 768] = self.cart.block(9, PICTURE_NAMES, 768)
        self.shown = self.loaded = True
        self.sounds.append(TUNE)

    # -- 0xBDD2 ---------------------------------------------------------------------------

    def _twinkle(self) -> None:
        for star in self.stars:
            star[0] = (star[0] - 1) & 0xFF
            if star[0]:
                continue
            star[0] = star[1]
            star[2] = (star[2] + 1) & 3
            char = self.cart.byte(3, STAR_CHARS + star[2])
            at = star[3] | star[4] << 8
            self.vram[at] = char
            self.vram[at + 0x20] = char + 1
        for n, twinkle in enumerate(self.twinkles):
            twinkle[1] -= 1
            if twinkle[1]:
                continue
            twinkle[1] = 8 + self.rng.randrange(16)
            twinkle[0] = (twinkle[0] + 1) % 6
            colour = self.cart.byte(3, TWINKLE_COLOURS + 6 * n + twinkle[0])
            for row in range(8):
                self.vram[COLOURS + TWINKLES[n] * 8 + row] = colour
            self.loaded = True

    # -- bank 10, 0xA88D ------------------------------------------------------------------

    def _comets(self) -> None:
        cart = self.cart
        for n, comet in enumerate(self.comets):
            if comet is None:
                continue
            if not comet[1]:
                comet[2] -= 1
                if not comet[2]:
                    comet[2] = 2
                    comet[5] += 1
                    if comet[5] >= 4:
                        comet[1] = 1
                continue
            dy, dx = cart.byte(10, STEPS + 2 * comet[0]), cart.byte(10, STEPS + 2 * comet[0] + 1)
            comet[3] = (comet[3] + dy) & 0xFF
            if comet[3] >= 0xC0:
                self.comets[n] = None
            comet[4] = (comet[4] + dx) & 0xFF
            if comet[4] >= 0xF0:
                self.comets[n] = None
        for emitter in self.emitters:
            emitter[1] = (emitter[1] - 1) & 0xFF
            if emitter[1]:
                continue
            emitter[1] = COMET_EVERY
            self._throw(emitter)

    def _throw(self, emitter: list[int]) -> None:
        cart = self.cart
        which = emitter[4] & 3
        if which == 3:
            emitter[1] = COMET_REST
        emitter[4] += 1
        kind = cart.byte(10, KINDS + emitter[0] * 4 + which)
        free = next((n for n, c in enumerate(self.comets) if c is None), None)
        if free is None:
            return
        start = STARTS + kind * 3
        self.comets[free] = [kind, 0, 2, (cart.byte(10, start) + emitter[2]) & 0xFF,
                             (cart.byte(10, start + 1) + emitter[3]) & 0xFF, 1,
                             cart.byte(10, start + 2), cart.byte(10, COMET_COLOURS + emitter[0])]

    def sprites(self) -> list[tuple[int, int, int, int]]:
        """(row, column, pattern, colour), the first in front (0xA9C2)."""
        out = []
        for comet in self.comets:
            if comet is None:
                continue
            kind, row, col = comet[0], comet[3], comet[4]
            for n in range(comet[5]):
                at = OFFSETS + kind * 8 + 2 * n
                y = (self.cart.byte(10, at) + row) & 0xFF
                x = (self.cart.byte(10, at + 1) + col) & 0xFF
                if y >= 0xC0:
                    continue
                if (x ^ col) & 0x80 and ((col - 0x40) & 0xFF) >= 0x80:
                    continue
                out.append((y, x, comet[6], comet[7]))
        return out


# -- the demo -----------------------------------------------------------------------

#: Per stage, the recording (bank 0's 0x5D1D, into banks 11 and 12): pairs of
#: (game frames, pad); the fire is always held (0x5CD2). The demo ends at
#: distance 0x100 (0x5CBE) and the next shows the next stage (0xE006).
DEMO, DEMO_BANKS, DEMO_FIRE, DEMO_UNTIL = 0x5D1D, {0x8000: 11, 0xA000: 12}, 0x10, 0x100


def demo_pad(cart: Cartridge, stage: int, frames: int = 0x800) -> list[int]:
    """The pad of each game frame of `stage`'s demo, as long as asked."""
    source = Paging(cart, DEMO_BANKS)
    at = cart.word(0, DEMO + 2 * stage)
    out: list[int] = []
    while len(out) < frames:
        count, pad = source.byte(at), source.byte(at + 1)
        out += [pad | DEMO_FIRE] * (count or 0x100)
        at += 2
    return out[:frames]
