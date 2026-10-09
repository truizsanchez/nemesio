"""The ship's weapons: the normal shot, the double, the laser, the missile --
fired by the ship and by each of its options.

Bank 2: firing (0x9CC5), each weapon (0x9D05..0x9DEF), moving them (0x9E14),
and meeting the map (0x9F81..0xA021). The original keeps nine slots of
sixteen bytes at 0xE260, and each shooter -- the ship, the first option, the
second -- has its own: the normal shot and the laser at 0xE260 + 0x20n, the
double at 0xE270 + 0x20n, and a missile at 0xE2C0 + 0x10n. Kept here the same.

**The normal shot and the laser are characters written into the map**, not
sprites (0xA27F); the double and the missile are sprites (0xA17F).
"""

from dataclasses import dataclass

from game.engine.original import (
    AUTOFIRE,
    BREAKABLE_FROM,
    CELL,
    FIRE,
    MAP_COLUMNS,
    SCENERY,
    SHOT_DX,
    SHOT_DY,
    SHOT_SPEED,
)
from game.engine.layout import Layout
from game.engine.stages import Characters, Stages
from game.engine.terrain import Map

NORMAL, DOUBLE, LASER, MISSILE = 1, 2, 3, 4
SHOOTERS = 3
#: The double: from the shooter's own row and column plus 8, six pixels up
#: and twelve along a frame (0x9D7E, 0x9E52); its pattern is the layout's.
DOUBLE_DX, DOUBLE_RISE = 8, 6
#: The laser: the normal shot's place, growing four cells a frame to its
#: length (0x9DCD: 8, or 15 with a second LASER), then running 0x20 a frame,
#: and shrinking by four once cut (0x9E66).
LASER_GROWTH, LASER_RUN, LASER_SHRINK = 4, 0x20, 5
LASER_LENGTHS = (0, 0x08, 0x0F)
#: The missile: from row and column plus 8 (0x9DE0, 0x9EE0).
MISSILE_D = 8
MISSILE_BOTTOM = 0xA0


@dataclass
class Shot:
    kind: int
    #: Row and column, 8.8 (0xE262-0xE265).
    y: int
    x: int
    #: The character (normal, laser) or pattern (double, missile), and colour.
    character: int = 0
    colour: int = 0
    #: The laser's step (byte 1), its length in cells (12), what is left to
    #: grow (13), and whose it is (8-9).
    step: int = 0
    length: int = 0
    grow: int = 0
    owner: int = 0

    @property
    def row(self) -> int:
        return self.y >> 8

    @property
    def col(self) -> int:
        return self.x >> 8

    @property
    def cell(self) -> tuple[int, int]:
        return self.row // CELL, self.col // CELL


@dataclass
class Card:
    """What the weapons read of a shooter: where it is (0xE204, 0xE206)."""

    row: int
    col: int
    alive: bool = True


class Shots:
    def __init__(self, stage: int, layout: Layout | None = None,
                 stages: Stages | None = None) -> None:
        #: Which characters and sprites the shots are drawn with, and which
        #: are walls and breakable.
        self.layout = layout or Layout()
        self.stages = stages or Stages()
        self.stage = stage
        #: slots[shooter] = [the normal shot or laser, the double].
        self.slots: list[list[Shot | None]] = [[None, None] for _ in range(SHOOTERS)]
        self.missiles: list[Shot | None] = [None] * SHOOTERS
        #: 0xE180: game frames the button has been held.
        self.held = 0
        #: 0xE184: no room for the double this time.
        self.no_double = False
        #: The card's weapons: 0xE20C (normal: 2 alone, 1 with the double),
        #: 0xE20D (the double), 0xE20E (the laser), 0xE20F (the missile).
        self.normal = 2
        self.double = 0
        self.laser = 0
        self.missile = 0
        self.fired = False
        self.sounds: list[int] = []
        #: A boss is on screen (0xE151): nothing breaks on stage 2 or 9+.
        self.boss = False

    def all(self) -> list[Shot]:
        out = [s for pair in self.slots for s in pair if s is not None]
        return out + [m for m in self.missiles if m is not None]

    # -- firing (0x9CC5) ---------------------------------------------------------

    def trigger(self, pad: int, pressed: int, shooters: list[Card]) -> None:
        self.fired = False
        if not pressed & FIRE:
            if not pad & FIRE:
                self.held = 0
                return
            self.held += 1
            if self.held < AUTOFIRE:
                return
        self.held = 0
        for n, card in enumerate(shooters):
            if card.alive:
                self._fire(n, card)

    def _fire(self, n: int, card: Card) -> None:
        """0x9D05: every weapon the card carries."""
        if self.normal:
            self._fire_normal(n, card)
        if self.double:
            self._fire_double(n, card)
        if self.laser:
            self._fire_laser(n, card)
        if self.missile:
            self._fire_missile(n, card)

    def _fire_normal(self, n: int, card: Card) -> None:
        pair = self.slots[n]
        if self.normal == 1:
            # 0x9D44: with the double, both slots must be free, the first
            # taken.
            if pair[0] is not None or pair[1] is not None:
                self.no_double = True
                return
            self.no_double = False
            at = 0
        else:
            # 0x9D29: alone, whichever of the two is free.
            free = [i for i in (0, 1) if pair[i] is None]
            if not free:
                return
            at = free[0]
        pair[at] = Shot(NORMAL, ((card.row + SHOT_DY) & 0xFF) << 8,
                        ((card.col + SHOT_DX) & 0xFF & ~(CELL - 1)) << 8,
                        self.layout.shot_character + (card.row >> 1 & 3))
        self.fired = True
        self.sounds.append(1)

    def _fire_double(self, n: int, card: Card) -> None:
        """0x9D6F."""
        if self.no_double or self.slots[n][1] is not None:
            return
        self.slots[n][1] = Shot(DOUBLE, card.row << 8, ((card.col + DOUBLE_DX) & 0xFF) << 8,
                                *self.layout.double)
        self.sounds.append(2)

    def _fire_laser(self, n: int, card: Card) -> None:
        """0x9D8F."""
        if self.slots[n][0] is not None:
            return
        self.slots[n][0] = Shot(
            LASER, ((card.row + SHOT_DY) & 0xFF) << 8,
            ((card.col + SHOT_DX) & 0xFF & ~(CELL - 1)) << 8,
            self.layout.laser_character + (card.row >> 1 & 3),
            grow=LASER_LENGTHS[min(self.laser, 2)], owner=n)
        self.sounds.append(3)

    def _fire_missile(self, n: int, card: Card) -> None:
        """0x9DD0."""
        if self.missiles[n] is not None:
            return
        self.missiles[n] = Shot(MISSILE, ((card.row + MISSILE_D) & 0xFF) << 8,
                                ((card.col + MISSILE_D) & 0xFF) << 8,
                                self.layout.missile[1], self.layout.missile[2])

    # -- moving (0x9E14) -----------------------------------------------------------

    def move(self, shooters: list[Card], terrain: Map, frames: int) -> None:
        for n, pair in enumerate(self.slots):
            for i, shot in enumerate(pair):
                if shot is not None and not self._move(shot, shooters):
                    pair[i] = None
        for n, missile in enumerate(self.missiles):
            if missile is not None and not self._move_missile(missile, terrain, frames):
                self.missiles[n] = None

    def _move(self, shot: Shot, shooters: list[Card]) -> bool:
        if shot.kind == NORMAL:
            shot.x += SHOT_SPEED << 8
            return shot.x <= 0xFFFF
        if shot.kind == DOUBLE:
            shot.y -= DOUBLE_RISE << 8
            if shot.y < 0:
                return False
            shot.x += SHOT_SPEED << 8
            return shot.x <= 0xFFFF
        return self._move_laser(shot, shooters)

    def _move_laser(self, shot: Shot, shooters: list[Card]) -> bool:
        """0x9E66: grows stuck to its shooter, then runs, then shrinks."""
        if shot.step == 0:
            card = shooters[shot.owner]
            shot.y = ((card.row + SHOT_DY) & 0xFF) << 8
            shot.x = ((card.col + SHOT_DX) & 0xFF & ~(CELL - 1)) << 8
            shot.character = self.layout.laser_character + (card.row >> 1 & 3)
            for _ in range(LASER_GROWTH):
                shot.length += 1
                shot.grow -= 1
                if not shot.grow:
                    shot.step = 1
                    break
            self._clip(shot)
            return True
        shot.x = (shot.x & 0xFF) | ((shot.col + LASER_RUN) & 0xFF) << 8
        if shot.col < LASER_RUN:
            return False
        if shot.step == 1:
            self._clip(shot)
            return shot.length > 0
        if shot.length < LASER_SHRINK:
            return False
        shot.length -= LASER_SHRINK - 1
        return True

    @staticmethod
    def _clip(shot: Shot) -> None:
        """0x9EC4: no longer than the screen has room for."""
        room = (0x100 - shot.col) // CELL
        if shot.length > room:
            shot.length = room

    def _move_missile(self, shot: Shot, terrain: Map, frames: int) -> bool:
        """0x9EE0: hugs the ground -- falls with nothing below, climbs a step,
        crashes into a wall."""
        shot.colour = self.layout.missile[2] + (1 if frames & 2 else 0)
        row, col = shot.row, shot.col
        fast = self.missile >= 2
        if not self._solid(terrain, row + 8, col):
            fall = 0x180 if fast else 0x100
            shot.x += fall
            if shot.x > 0xFFFF:
                return False
            return self._drop(shot, fast)
        if not self._solid(terrain, row + 8, col + 8):
            if not self._drop(shot, fast):
                return False
        elif self._solid(terrain, row, col + 8):
            return False
        shot.character = self.layout.missile[0]
        shot.x += 0x600 if fast else 0x400
        return shot.x <= 0xFFFF

    def _drop(self, shot: Shot, fast: bool) -> bool:
        """0x9F24: the falling drawing, and down it goes."""
        shot.character = self.layout.missile[1]
        shot.y += 0x600 if fast else 0x400
        return shot.row < MISSILE_BOTTOM

    # -- meeting the map (0x9F81) ---------------------------------------------------

    def meet_lasers(self, terrain: Map) -> None:
        """0x9FE6, in the drawing pass (0x9F81)."""
        for pair in self.slots:
            for i, shot in enumerate(pair):
                if shot is not None and shot.kind == LASER and not self._laser_meets(shot, terrain):
                    pair[i] = None

    def meet(self, terrain: Map) -> bool:
        """0x9FAD for the normal shot and the double, in the clearing pass
        (0x9F85). True if a shot ended on the map (sound 6)."""
        hit = False
        for pair in self.slots:
            for i, shot in enumerate(pair):
                if shot is None or shot.kind == LASER:
                    continue
                row, col = shot.cell
                cols = (col, col + 1) if col + 1 < MAP_COLUMNS else (col,)
                for c in cols:
                    if not self._solid_cell(terrain, row, c):
                        continue
                    pair[i] = None
                    if not self._breaks(terrain, row, c):
                        hit = True
                    break
        return hit

    def _breakable(self) -> tuple[Characters, int] | None:
        breakable = self.stages.breakable
        if self.stage in breakable:
            found, sound = breakable[self.stage]
            if self.stage != 2 or not self.boss:
                return found, sound
        if self.stage >= BREAKABLE_FROM and not self.boss:
            return self.stages.breakable_late
        return None

    def _breaks(self, terrain: Map, row: int, col: int) -> bool:
        """0x9FC3: a breakable cell goes, with its group's sound."""
        breakable = self._breakable()
        if breakable is None or terrain[row, col] not in breakable[0]:
            return False
        terrain[row, col] = 0
        self.sounds.append(breakable[1])
        return True

    def _laser_meets(self, shot: Shot, terrain: Map) -> bool:
        """0x9FE6: along the laser, a breakable cell goes and the laser runs
        on; the first other solid cell cuts it there."""
        row, col = shot.cell
        for n in range(shot.length):
            if not self._solid_cell(terrain, row, col + n):
                continue
            if self._breaks(terrain, row, col + n):
                continue
            shot.step = 2
            shot.length = n
            return n > 0
        return True

    def _solid(self, terrain: Map, y: int, x: int) -> bool:
        return self._solid_cell(terrain, (y & 0xFF) // CELL, (x & 0xFF) // CELL)

    def _solid_cell(self, terrain: Map, row: int, col: int) -> bool:
        if not terrain.inside(row, col):
            return False
        character = terrain[row, col]
        if 0 < character < SCENERY:
            return True
        return character in self.stages.shot_walls.get(self.stage, ())
