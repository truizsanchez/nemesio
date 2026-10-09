"""The scroll: the distance, the map one column to the left, a column in.

Bank 0, 0x466A, once a game frame. The distance (0xE063) is how many columns
have come in; the column on the right of the map is always the one at the
distance. With the scroll in its usual mode a rotating bit (0xE062) lets one
game frame in eight through, so the screen moves eight pixels every sixteen
video frames: the MSX1 has no scroll register, and the original moves by
whole characters.
"""

import random
from typing import Callable

from game.engine.original import (
    FIRST_FILL,
    MAP_COLUMNS,
    SCROLL_BIT_START,
    SCROLL_EVERY_STEP,
    SCROLL_STOPPED,
    STARS,
)
from game.engine.terrain import Map, Terrain


class Scroll:
    def __init__(self, terrain: Terrain, rng: random.Random,
                 stars: tuple[int, int] = STARS) -> None:
        self.terrain = terrain
        self.rng = rng
        #: The two star characters a sky column's star is one of.
        self.stars = stars
        self.map = Map()
        self.distance = 0
        #: 0xE1C0: 0 the rotating bit, 1 stopped, 2 every step.
        self.mode = 0
        self.bit = SCROLL_BIT_START
        #: Whether this game frame brought a column in (0xE100), and whether
        #: the distance is at the limit (0xE107).
        self.moved = False
        self.at_limit = False
        #: 0xE105: where the scroll stops; the ending can move it.
        self.limit = terrain.limit

    def start(self, distance: int,
              each: Callable[[int, int], None] | None = None) -> None:
        """0x45F5: set the distance back by a screen and bring a screen in, so
        the column on the right is `distance - 1`'s and the next step brings
        `distance`'s. `each` is called with every column's distance and
        pixel column, as 0x460C calls the spawners on each step."""
        self.distance = distance - FIRST_FILL
        for col in range(MAP_COLUMNS):
            self._bring_in(col)
            if each is not None:
                each(self.distance, col * 8)
            self.distance += 1
        self.distance -= 1
        self.bit = SCROLL_BIT_START

    def step(self) -> None:
        """0x466A."""
        self.moved = False
        self.at_limit = self.distance >= self.limit
        if self.at_limit or self.mode == SCROLL_STOPPED:
            return
        if self.mode != SCROLL_EVERY_STEP:
            self.bit = (self.bit << 1 | self.bit >> 7) & 0xFF
            if not self.bit & 1:
                return
        self.distance += 1
        self.moved = True
        self.map.shift_left()
        self._bring_in(MAP_COLUMNS - 1)

    def _bring_in(self, col: int) -> None:
        """0x46AE: the column at the distance, into `col`."""
        cells = self.terrain.column(self.distance)
        if cells is None:
            cells = [0] * len(self.map.cells[::MAP_COLUMNS])
            star = self.terrain.star_row(self.distance)
            if star is not None:
                cells[star] = self.rng.choice(self.stars)
        self.map.put_column(col, cells)
