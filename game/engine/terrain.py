"""The map as the engine holds it, and what a stage answers about its terrain.

The original keeps the screen's 22x32 characters in RAM at 0xED00 and
everything that meets the terrain reads that buffer: the ship, the shots,
the objects. So does this engine. What goes into it -- a stage's columns --
comes from `Terrain`, which the cartridge reader (`game/rom/stage.py`)
answers, or anything else shaped like it.
"""

from typing import Protocol

from game.engine.original import CELL, MAP_COLUMNS, MAP_ROWS, SCENERY


class Terrain(Protocol):
    """A stage's columns, by distance."""

    number: int
    start: int
    end: int
    limit: int
    checkpoint: int

    def column(self, distance: int) -> list[int] | None:
        """The column's 22 characters, top down; None is sky."""

    def star_row(self, distance: int) -> int | None:
        """A sky column's star row (0-21), or None."""


class Map:
    """0xED00: the 22x32 characters on screen, row by row."""

    def __init__(self) -> None:
        self.cells = bytearray(MAP_ROWS * MAP_COLUMNS)

    def __getitem__(self, at: tuple[int, int]) -> int:
        row, col = at
        return self.cells[row * MAP_COLUMNS + col]

    def __setitem__(self, at: tuple[int, int], value: int) -> None:
        row, col = at
        self.cells[row * MAP_COLUMNS + col] = value

    def shift_left(self) -> None:
        """0x4695: every row one cell to the left. The rightmost column keeps
        what it had until the new column is written over it."""
        for row in range(MAP_ROWS):
            at = row * MAP_COLUMNS
            self.cells[at:at + MAP_COLUMNS - 1] = self.cells[at + 1:at + MAP_COLUMNS]

    def clear(self) -> None:
        """0xA744: the 0x2C0 bytes to zero."""
        self.cells[:] = bytes(len(self.cells))

    def put_column(self, col: int, cells: list[int]) -> None:
        for row, value in enumerate(cells):
            self[row, col] = value

    @staticmethod
    def cell_of(y: int, x: int) -> tuple[int, int]:
        """0x571B: the cell a screen point is in. Rows past the map's are not
        clipped here -- the original reads past 0xEFBF into whatever follows --
        and a caller that can be below the map clips for itself."""
        return y // CELL, x // CELL

    def keep(self, at: int, width: int, height: int) -> bytes:
        """0x6964: a rectangle from cell `at` on, row by row, with no
        clipping: a row past the right edge goes on into the next."""
        out = bytearray()
        for r in range(height):
            for c in range(width):
                n = at + r * MAP_COLUMNS + c
                out.append(self.cells[n] if 0 <= n < len(self.cells) else 0)
        return bytes(out)

    def put_back(self, at: int, width: int, kept: bytes) -> None:
        """0x6A5B: what `keep` kept, written back the same way."""
        for k, value in enumerate(kept):
            n = at + k // width * MAP_COLUMNS + k % width
            if 0 <= n < len(self.cells):
                self.cells[n] = value

    def inside(self, row: int, col: int) -> bool:
        return 0 <= row < MAP_ROWS and 0 <= col < MAP_COLUMNS


def is_terrain(character: int) -> bool:
    """Solid for anything that meets the map, on every stage (bank 2, 0x98FF):
    not empty and under SCENERY."""
    return 0 < character < SCENERY
