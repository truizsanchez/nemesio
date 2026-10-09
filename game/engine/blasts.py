"""The background blasts: where something drawn into the map blows up.

Bank 1, 0x7B4E ("set up the background blast"): four slots of eight bytes at
0xE800, apart from the twelve objects' --

    0 type (0x20)   1 clock   2 row   3 column   6 drawing

-- each a 4x4 of characters (0x633A, three drawings, the last first) that
rides the scroll (0x6014) and changes every four game frames (0x6182). It is
drawn into the map after the ship has met it (0x47B7) and taken out again
before the next game frame (0x699B): it is only seen, never touched.

Taken out means zeroed, but for three of the bosses (0xE152 at 1, 5 or 6):
then 0x690C keeps the 4x4 cells under each one in 0xEA80 before anything is
drawn (0x45C1), and 0x6A03 writes them back instead. A blast made after that
(a piece shot down) writes back whatever its slot kept last; 0xEA80 is only
zeroed as a stage is built (0x4116).
"""

from dataclasses import dataclass

from game.engine.original import MAP_COLUMNS
from game.engine.terrain import Map

SLOTS, SIZE = 4, 4
#: 0x7B63: type 0x20, a clock of four, drawing 2 first; it rides the scroll
#: eight a column (0x601C).
BLAST_TYPE, EVERY, FIRST_DRAWING, CELL = 0x20, 4, 2, 8


@dataclass
class Blast:
    row: int
    col: int
    clock: int = EVERY
    drawing: int = FIRST_DRAWING


class Blasts:
    def __init__(self, drawings: tuple[tuple[int, ...], ...]) -> None:
        self.drawings = drawings
        self.slots: list[Blast | None] = [None] * SLOTS
        self.drawn: list[tuple[int, int]] = []
        #: 0xEA80: sixteen bytes a slot, what 0x690C kept under it.
        self.kept = [bytes(SIZE * SIZE)] * SLOTS

    def make(self, row: int, col: int) -> None:
        """0x7B4E: the first free slot; none, no blast."""
        if None in self.slots:
            self.slots[self.slots.index(None)] = Blast(row & 0xFF, col & 0xFF)

    def any(self) -> bool:
        """0x84AC: whether one is still on."""
        return any(self.slots)

    def step(self, moved: bool) -> None:
        """0x616A, each slot through 0x6182."""
        for n, blast in enumerate(self.slots):
            if blast is None:
                continue
            if moved:
                if blast.col < CELL:
                    self.slots[n] = None
                    continue
                blast.col -= CELL
            blast.clock -= 1
            if blast.clock:
                continue
            blast.clock = EVERY
            blast.drawing -= 1
            if blast.drawing < 0:
                self.slots[n] = None

    def draw(self, terrain: Map) -> None:
        """0x6199: into the map, as the background objects are (0x620D)."""
        self.drawn = []
        if not self.drawings:
            return
        for blast in self.slots:
            if blast is None:
                continue
            chars = self.drawings[blast.drawing]
            top, left = blast.row // 8, blast.col // 8
            for r in range(SIZE):
                for c in range(SIZE):
                    if left + c >= 32 or not terrain.inside(top + r, left + c):
                        continue
                    terrain[top + r, left + c] = chars[r * SIZE + c]
                    self.drawn.append((top + r, left + c))

    @staticmethod
    def _at(blast: Blast) -> int:
        return (blast.row >> 3) * MAP_COLUMNS + (blast.col >> 3)

    def keep(self, terrain: Map) -> None:
        """0x6928: what each one will cover, kept in its slot of 0xEA80."""
        for n, blast in enumerate(self.slots):
            if blast is not None:
                self.kept[n] = terrain.keep(self._at(blast), SIZE, SIZE)

    def erase(self, terrain: Map, put_back: bool = False) -> None:
        """0x6196: the rectangles back to nothing; or, `put_back`, 0x6A1F:
        each slot's kept cells where it is."""
        if put_back:
            for n, blast in enumerate(self.slots):
                if blast is not None:
                    terrain.put_back(self._at(blast), SIZE, self.kept[n])
        else:
            for row, col in self.drawn:
                terrain[row, col] = 0
        self.drawn = []
