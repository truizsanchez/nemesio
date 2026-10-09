"""The screen going dark at the end of stages 7 and 8 (bank 3, 0xA6C0).

No palette to fade on a TMS9918: the cartridge eats the tables instead. In
one game frame every background colour goes (colour table AND 0xF0); then,
a third of the screen's rows at a time, the patterns lose a bit -- with the
mask turned three bits for every byte, so the dark comes in crumbs -- until
the mask is empty; then the map buffer is cleared, and once the sound it
started (0x3E) has stopped, it is done (0xE1A3).

The engine keeps no VRAM, so what a game frame does to it comes out as
`writes`: (address, length, mask, turning) for whoever holds the VRAM. The
bottom third's first 0x44 characters and its last are spared: the band's
letters live there.
"""

from __future__ import annotations

#: The colour and pattern tables (0x575A's layout), and a third of either.
COLOURS, PATTERNS, THIRD = 0x0000, 0x2000, 0x0800
#: A pass takes 0x40 characters of each third at a time, 0x200 bytes; the
#: bottom third starts at 0x44 and ends short at 0xC0 (0xA768).
CHUNK, CHARS, BAND_FROM, SHORT_FROM, SHORT, FROM_BAND = 0x200, 0x40, 0x44, 0xC0, 0x1B0, 0x1E0
#: The masks: 0xF0 for the colours, then 0xFE shifted left each pass.
COLOUR_MASK, FIRST_PATTERN_MASK = 0xF0, 0xFE
SOUND = 0x3E
MAP_BYTES = 0x2C0
#: What a game frame of this costs, in interrupts, measured on the 60 Hz
#: machine (0xE003's writes against the interrupts): the colour pass 14 (13
#: for stage 7's eye, with less else to do), a pattern pass 5, 6, 6 and 5 by
#: the row it starts at. The sound it plays runs on interrupts, so the dark
#: comes at its own pace.
COLOUR_PASS_INTERRUPTS = 14
PASS_INTERRUPTS = {0x00: 5, 0x40: 6, 0x80: 6, 0xC0: 5}

Write = tuple[int, int, int, bool]


class Fade:
    def __init__(self, colour_pass: int = COLOUR_PASS_INTERRUPTS) -> None:
        """`colour_pass`: the interrupts the colour pass takes here."""
        self.colour_pass = colour_pass
        #: 0xE1A0, 0xE1A1, 0xE1A2, 0xE1A3.
        self.step = 0
        self.row = 0
        self.mask = 0
        self.done = False
        self.writes: list[Write] = []
        self.clear_map = False
        #: How many interrupts this game frame takes; None for the usual.
        self.interrupts: int | None = None

    def update(self, busy: bool, ending: bool, sounds: list[int]) -> None:
        """A game frame. `busy`: the first channel still sounds (0xE012);
        `ending`: the game's ending is on (0xE1D0), which has its own sound."""
        self.writes = []
        self.clear_map = False
        self.interrupts = None
        if self.step == 0:
            if not ending:
                sounds.append(SOUND)
            self.done = False
            self.row, self.mask = 0, COLOUR_MASK
            for row in range(0, 0x100, CHARS):
                self._pass(COLOURS, row, turning=False)
            self.step, self.mask = 1, FIRST_PATTERN_MASK
            self.interrupts = self.colour_pass
        elif self.step == 1:
            self._pass(PATTERNS, self.row, turning=True)
            self.interrupts = PASS_INTERRUPTS[self.row]
            self.row = (self.row + CHARS) & 0xFF
            if self.row:
                return
            if self.mask:
                self.mask = self.mask << 1 & 0xFF
            else:
                self.step = 2
        elif self.step == 2:
            self.clear_map = True
            self.step = 3
        elif not busy:
            self.done = True

    def _pass(self, table: int, row: int, turning: bool) -> None:
        """0xA6E0/0xA70F: the bottom third (from row 0x40 on), then the
        middle and the top."""
        if row >= CHARS:
            self._chunk(table + 2 * THIRD, BAND_FROM if row < 0x80 else row, turning)
        self._chunk(table + THIRD, row, turning)
        self._chunk(table, row, turning)

    def _chunk(self, base: int, row: int, turning: bool) -> None:
        """0xA765."""
        length = FROM_BAND if row == BAND_FROM else SHORT if row == SHORT_FROM else CHUNK
        self.writes.append((base + row * 8, length, self.mask, turning))


def apply(vram: bytearray, writes: list[Write]) -> None:
    """0xA799: the writes onto a VRAM -- for the host that holds one."""
    for at, length, mask, turning in writes:
        for n in range(at, at + length):
            vram[n] &= mask
            if turning:
                mask = (mask >> 3 | mask << 5) & 0xFF
