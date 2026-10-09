"""The hidden target that opens the bonus stages (bank 3, 0xB042).

Five stages hide one: at a distance of their own a spot comes in at column
0xF0 on a row of its own and rides the scroll left. Nothing draws it -- it is
three bytes, 0xE1C1..0xE1C3, kind, row and column. Fly within 0x10 of it
and, on stages 2, 3 and 7, the screen stops (0xE1C0): everything on it blows
up, the sound 0xCD, and 0x40 game frames later the scroll runs a column every
game frame (0xE1C0 at 2, the sound 0x41) up to a limit of the stage's, where
its ending sends the game to bonus stage 9, 10 or 12 instead (0x6D66,
0x6DA7, 0x6F19). Stages 1 and 4 count instead: the kinds of the last targets
taken (0xE06C, 0xE06D), and the third in a row that differs stops stage 4
the same way, to bonus stage 11.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Per stage, (distance, row, kind) (0xB086..0xB0BD); in at column 0xF0.
TARGETS = {1: ((0xFC, 0x88, 2),), 2: ((0x190, 0x88, 1),), 3: ((0x12A, 0x30, 1),),
           4: ((0xC0, 0x10, 3), (0x104, 0x10, 4)), 7: ((0x177, 0x38, 1),)}
COLUMN = 0xF0
#: Where the scroll then stops (0xB119..0xB123; the listing's "stage 6" is
#: stage 7), or 0x1C0 on the third kind counted (0xB114).
LIMITS = {2: 0x1CF, 3: 0x19F, 7: 0x1A0}
COUNTED, COUNTED_LIMIT = 3, 0x1C0
#: Within 0x10 either way: the row from eight above, the column from the spot.
NEAR, ROW_FROM = 0x10, 8
#: Stopped 0x40 game frames, then fast; the two sounds.
STOPPED_FRAMES, STOPPED, FAST = 0x40, 1, 2
STOP_SOUND, FAST_SOUND = 0xCD, 0x41
#: Where each stage's target leads (0x6D6C..0x6F24), and each bonus stage
#: back to (0x418F).
BONUS = {2: 9, 3: 10, 4: 11, 7: 12}
AFTER_BONUS = {9: 3, 10: 4, 11: 5, 12: 8}


@dataclass
class Target:
    """0xE1C0..0xE1C5."""

    kind: int = 0
    row: int = 0
    col: int = 0
    #: 0xE1C0: 0, the screen goes; 1, stopped; 2, the scroll runs fast.
    mode: int = 0
    clock: int = 0

    def update(self, stage: int, distance: int, moved: bool, ship_row: int, ship_col: int,
               counted: list[int], sounds: list[int]) -> int | None:
        """A game frame (0xB042, the ship alive); the limit the scroll
        stops at when the target is taken and closes the stretch."""
        if self.mode:
            self.clock -= 1
            if not self.clock:
                self.mode = FAST
                sounds.append(FAST_SOUND)
            return None
        if moved:
            for at, row, kind in TARGETS.get(stage, ()):
                if distance == at:
                    self.kind, self.row, self.col = kind, row, COLUMN
        if not self.kind:
            return None
        limit = self._touched(stage, ship_row, ship_col, counted)
        if limit is not None:
            self.mode, self.clock, self.kind = STOPPED, STOPPED_FRAMES, 0
            sounds.append(STOP_SOUND)
            return limit
        if moved:
            self.col -= 8
            if self.col < 0:
                self.kind = 0
        return None

    def _touched(self, stage: int, ship_row: int, ship_col: int,
                 counted: list[int]) -> int | None:
        """0xB0DD."""
        if (ship_row - self.row + ROW_FROM) & 0xFF >= NEAR:
            return None
        if (ship_col - self.col) & 0xFF >= NEAR:
            return None
        if stage in LIMITS:
            return LIMITS[stage]
        if self.kind == counted[0]:
            return None
        counted[0], self.kind = self.kind, 0
        counted[1] += 1
        if counted[1] != COUNTED:
            return None
        counted[1] = 0
        return COUNTED_LIMIT
