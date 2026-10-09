"""Stage 7's boss: the eye at the end of the brain (boss 3, bank 2, 0x8719).

The brain is terrain; its eye is two characters the boss writes into the map
(0x87CF), one above the other, and a piece of type 5 in the boss's slot at
0xE780 that shots meet. For 0x258 game frames, every other one, the eye
spits a type 0x10 to the left at one of sixteen speeds -- the R register
picks it -- down from row 0x40 or, with bit 1 of the frame counter, up from
0x6F. Shot out (0x40, four a shot, one a laser) it pays 100 and shuts;
outlasted it just closes. 0x5A game frames later the screen goes dark
(0xA6C0) and the stage is over.
"""

from __future__ import annotations

from game.engine.fade import Fade
from game.engine.objects import SPIT, Objects
from game.engine.original import EYE_AT
from game.engine.terrain import Map

#: The piece (0x8748): type 5, 0x40 of life, at row 0x50 and column 0xB7
#: with the eye's cells at (10, 27) (the stages' `eye`): that far from
#: them.
PIECE, LIFE, PIECE_DY, PIECE_DX = 5, 0x40, 0x00, -0x21
#: It is met in a box of 0x10 by 0x10 (0x76B4), as the core's shots are.
BOX, SHOT_ROWS, SHOT_COLS = 0x10, 0x02, 0x10
#: It spits 0x258 game frames, then waits 0x5A (0x872C, 0x87A4).
SPITTING, AFTER = 0x258, 0x5A
#: The fade's colour pass, in interrupts: one fewer than stage 8's, with
#: less else running in the game frame (measured, 60 Hz).
FADE_COLOUR_PASS = 13
#: From (0x40, 0xA4), or (0x6F, 0xA4) upwards -- that far from the piece --
#: seven pixels a frame left.
SPIT_DY, SPIT_BELOW_DY, SPIT_DX, SPIT_ACROSS = -0x10, 0x1F, -0x13, 0xF900
POINTS, BURST_SOUND = 100, 0x0E
SHOT_TAKES, LASER_TAKES = 4, 1


class Eye:
    def __init__(self, objects: Objects, speeds: tuple[int, ...]) -> None:
        self.objects = objects
        #: The eye's upper cell, and its two characters open, shut, dead.
        self.at = objects.tables.stages.eye.get(7, EYE_AT[7])
        layout = objects.layout
        self.open, self.shut, self.dead = layout.eye_open, layout.eye_shut, layout.eye_dead
        self.row = (self.at[0] * 8 + PIECE_DY) & 0xFF
        self.col = (self.at[1] * 8 + PIECE_DX) & 0xFF
        #: 0x87AF: the sixteen speeds the spit comes out at.
        self.speeds = speeds
        #: 0xE190, with -1 the game frame 0x7C4F takes to start it.
        self.step = -1
        self.clock = 0
        #: 0xE780's type and life.
        self.piece = 0
        self.life = 0
        self.fade = Fade()
        self.done = False

    def update(self, terrain: Map, frames: int, busy: bool) -> None:
        """0x8719, a game frame."""
        if self.step == -1:
            self.step = 0
        elif self.step == 0:
            self.clock = SPITTING
            self.piece, self.life = PIECE, LIFE
            self._eye(terrain, self.open)
            self.step = 1
        elif self.step == 1:
            self._spit(terrain, frames)
        elif self.step == 2:
            self.clock = (self.clock - 1) & 0xFF
            if not self.clock:
                self.fade = Fade(FADE_COLOUR_PASS)
                self.step = 3
        else:
            self.fade.update(busy, False, self.objects.world.sounds)
            if self.fade.done:
                self.done = True

    def _spit(self, terrain: Map, frames: int) -> None:
        """0x8752."""
        if not self.life:
            self.objects.world.score += POINTS
            self._close(terrain, self.dead)
            return
        self.clock -= 1
        if not self.clock:
            self._close(terrain, self.shut)
            return
        if frames & 1:
            return
        speed = self.speeds[self.objects.rng.randrange(16)]
        row = (self.row + SPIT_DY) & 0xFF
        if frames & 2:
            row, speed = (self.row + SPIT_BELOW_DY) & 0xFF, -speed & 0xFFFF
        self.objects.next_speed = (speed, SPIT_ACROSS)
        self.objects.make(SPIT, row, (self.col + SPIT_DX) & 0xFF)

    def _close(self, terrain: Map, eye: tuple[int, int]) -> None:
        self._eye(terrain, eye)
        self.clock = AFTER
        self.step = 2

    def _eye(self, terrain: Map, eye: tuple[int, int]) -> None:
        """0x87CF."""
        row, col = self.at
        terrain[row, col], terrain[row + 1, col] = eye

    # -- being shot (0x760E) ------------------------------------------------------

    def meets(self, row: int, col: int, laser_cols: int = 0) -> int | None:
        if not self.piece:
            return None
        a = (self.row - row) & 0xFF
        if not (a < SHOT_ROWS or a + BOX > 0xFF):
            return None
        a = (self.col - col) & 0xFF
        return 0 if a < (laser_cols or SHOT_COLS) or a + BOX > 0xFF else None

    def hit(self, _: int, laser: bool) -> None:
        """0x77BA: no sound until it bursts, and no points here."""
        self.life = (self.life - (LASER_TAKES if laser else SHOT_TAKES)) & 0xFF
        if not (self.life - 1) & 0x80:
            return
        self.piece = 0
        self.objects.world.sounds.append(BURST_SOUND)

    def cells(self) -> list[tuple[int, int, int]]:
        return []
