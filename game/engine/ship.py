"""The ship: its position, its speed, the pad, the box it stays in, the map.

Bank 2, 0x9955 ("place the ship"), 0x98DA ("the ship crashes") and 0x9B7B
("kill the ship"). Position is 8.8 fixed point, row and column, as the card at
0xE200 keeps it: 0xE203/0xE204 and 0xE205/0xE206.
"""

from game.engine.original import (
    DOWN,
    EXPLOSION,
    LEFT,
    RIGHT,
    SHIP_PROBE_HALF,
    SHIP_PROBE_Y,
    SHIP_SPEED_BASE,
    SHIP_SPEED_MAX,
    SHIP_START_X,
    SHIP_START_Y,
    SHIP_UNIT,
    SHIP_X_MAX,
    SHIP_X_MIN,
    SHIP_Y_BIAS,
    SHIP_Y_MAX,
    SHIP_Y_MIN,
    SHIP_Y_MIN_OPEN,
    SHIP_Y_OPEN_FROM,
    SHIP_Y_OPEN_STAGES,
    UP,
)
from game.engine.layout import Layout
from game.engine.stages import Stages
from game.engine.original import CELL, MAP_COLUMNS, MAP_ROWS
from game.engine.terrain import Map, is_terrain

Sprite = tuple[int, int]


def _axis(pad: int, minus: int, plus: int) -> int:
    """0x9B0D: one axis of the pad as -0x80, 0 or +0x80; both held is none."""
    held = pad & (minus | plus)
    if held == minus:
        return -SHIP_UNIT
    if held == plus:
        return SHIP_UNIT
    return 0


class Ship:
    def __init__(self, stage: int, layout: Layout | None = None,
                 stages: Stages | None = None) -> None:
        self.stage = stage
        #: Which sprites it is drawn with, and which characters are walls.
        self.layout = layout or Layout()
        self.stages = stages or Stages()
        self.y = SHIP_START_Y << 8
        self.x = SHIP_START_X << 8
        #: SPEED UPs taken (0xE202).
        self.speed = 0
        #: None while flying; the explosion's state (0-3) once hit.
        self.exploding: int | None = None
        self.explosion_left = 0
        #: The life is over: the explosion has run out.
        self.gone = False
        self.sprites: tuple[Sprite, Sprite] = self.layout.ship[0]

    def place(self, row: int, col: int) -> None:
        """Row and column written, their fractions left as they are."""
        self.y = row << 8 | self.y & 0xFF
        self.x = col << 8 | self.x & 0xFF

    @property
    def row(self) -> int:
        return self.y >> 8

    @property
    def col(self) -> int:
        return self.x >> 8

    def step(self, pad: int, pushed: int | None = None) -> None:
        """0x9955: a game frame of the ship, flying or exploding; in the
        game's ending, pushed right at 0xE1D3 with no walls (0x9962)."""
        if self.exploding is not None:
            self._explode()
            return
        if pushed is not None:
            self.x = (self.x + pushed) & 0xFFFF
            self.sprites = self.layout.ship[0]
            return
        times = min(self.speed, SHIP_SPEED_MAX) + SHIP_SPEED_BASE + 1
        dy = _axis(pad, UP, DOWN) * times
        dx = _axis(pad, LEFT, RIGHT) * times
        self.y = self._clamp_y((self.y + dy) & 0xFFFF)
        self.x = self._clamp_x((self.x + dx) & 0xFFFF)
        # 0x99B7: up and down pick the drawing; both is neither.
        vertical = pad & (UP | DOWN)
        self.sprites = self.layout.ship[0 if vertical == UP | DOWN else vertical]

    def _clamp_y(self, y: int) -> int:
        """0x9ABB: the high byte, tested with 0x10 added (in eight bits)."""
        top = (SHIP_Y_MIN_OPEN if self.stage in SHIP_Y_OPEN_STAGES
               or self.stage >= SHIP_Y_OPEN_FROM else SHIP_Y_MIN)
        high = ((y >> 8) + SHIP_Y_BIAS) & 0xFF
        high = min(max(high, top), SHIP_Y_MAX)
        return ((high - SHIP_Y_BIAS) & 0xFF) << 8 | y & 0xFF

    @staticmethod
    def _clamp_x(x: int) -> int:
        """0x9AAB."""
        high = min(max(x >> 8, SHIP_X_MIN), SHIP_X_MAX)
        return high << 8 | x & 0xFF

    def hits(self, terrain: Map) -> bool:
        """0x98DA: the cell at the ship's row plus eight and its column, and
        the one to its right; with the column's low bits past half a cell,
        only the one to the right."""
        row = ((self.row + SHIP_PROBE_Y) & 0xFF) // CELL
        at = row * MAP_COLUMNS + self.col // CELL
        probes = (at, at + 1) if self.col % CELL < SHIP_PROBE_HALF else (at + 1,)
        return any(self._solid(terrain, a) for a in probes)

    def _solid(self, terrain: Map, at: int) -> bool:
        if not 0 <= at < MAP_ROWS * MAP_COLUMNS:
            return False
        character = terrain.cells[at]
        if is_terrain(character):
            return True
        return character in self.stages.ship_walls.get(self.stage, ())

    def die(self) -> None:
        """0x9B7B: the speed goes, and the explosion starts."""
        if self.exploding is not None:
            return
        self.speed = 0
        self._explosion_state(0)

    def _explosion_state(self, state: int) -> None:
        self.exploding = state
        self.explosion_left = EXPLOSION[state][0]
        self.sprites = self.layout.explosion[state]
        self.parts = tuple((self.row, (self.col + dx) & 0xFF, pattern, colour)
                           for dx, pattern, colour in self.layout.explosion_parts[state])

    #: 0xE220 and 0xE240 while it explodes: (row, column, pattern, colour).
    parts: tuple[tuple[int, int, int, int], ...] = ()

    def _explode(self) -> None:
        """0x9B91."""
        assert self.exploding is not None
        self.explosion_left -= 1
        if self.explosion_left:
            return
        if self.exploding + 1 >= len(EXPLOSION):
            self.gone = True
            return
        self._explosion_state(self.exploding + 1)
