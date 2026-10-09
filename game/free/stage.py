"""A free stage's terrain: a text map and its legend.

`stageN.txt` is the map as it scrolls in: 22 lines, one a row of the map,
and one character a column; column c is the one at distance `start` + c.
`stageN.json` says which of the original's stages it plays like ("rules",
N if left out), what each character of the text is (its legend, a map
character number) and where the scroll starts, stops and restarts:

    {"rules": 1, "start": 128, "limit": 415, "checkpoint": 248,
     "legend": {"#": 67, "^": 68, "*": 246, ...},
     "star_rows": [0, 5, 0, 17, ...]}

and the stage's own tables (read by `game/free/tables.py`).

A space is empty. Outside the text the columns are sky, with a star on the
row `star_rows` gives for the distance's five low bits (1-22, 0 none), as
the cartridge's sky columns.
"""

import json
import os

from game.engine.ending import CoreArt
from game.engine.original import MAP_ROWS
from game.engine.tables import Tables
from game.free.numbers import num

EMPTY = " "
#: The original's stages whose rules a free one can play by.
LAST_RULES = 8


def files(folder: str) -> list[int]:
    """The stages there are: stage1, stage2... up to the first missing."""
    out: list[int] = []
    while os.path.isfile(os.path.join(folder, "stage%d.txt" % (len(out) + 1))):
        out.append(len(out) + 1)
    return out


class FreeStage:
    """What `game.engine.terrain.Terrain` asks of a stage."""

    def __init__(self, folder: str, number: int) -> None:
        #: Which stage of the free assets it is (stageN), and the original's
        #: stage whose rules it plays by: the engine's number for it.
        self.file = number
        #: Its own tables and core, which the engine plays it with: set by
        #: FreeContent (tables.py reads them).
        self.tables: Tables | None = None
        self.core_art: CoreArt | None = None
        with open(os.path.join(folder, "stage%d.json" % number)) as handle:
            spec = json.load(handle)
        self.number = num(spec.get("rules", number))
        if not 1 <= self.number <= LAST_RULES:
            raise ValueError("stage%d.json's rules are stage %d's, and the original's are 1-%d"
                             % (number, self.number, LAST_RULES))
        with open(os.path.join(folder, "stage%d.txt" % number)) as handle:
            lines = handle.read().split("\n")
        rows = [line.rstrip("\r") for line in lines[:MAP_ROWS]]
        if len(rows) < MAP_ROWS:
            raise ValueError("stage%d.txt has %d rows, and a map has %d"
                             % (number, len(rows), MAP_ROWS))
        width = max(len(row) for row in rows)
        legend = {EMPTY: 0}
        for key, value in spec["legend"].items():
            legend[key] = num(value)
        self.columns: list[list[int]] = []
        for c in range(width):
            column = []
            for r, row in enumerate(rows):
                key = row[c] if c < len(row) else EMPTY
                if key not in legend:
                    raise ValueError("stage%d.txt, row %d, column %d: %r is not in the legend"
                                     % (number, r + 1, c + 1, key))
                column.append(legend[key])
            self.columns.append(column)
        self.start = num(spec["start"])
        self.end = self.start + width
        self.limit = num(spec["limit"])
        self.checkpoint = num(spec["checkpoint"])
        self.star_rows = [num(n) for n in spec.get("star_rows", [])] or [0]

    def column(self, distance: int) -> list[int] | None:
        if not self.start <= distance < self.end:
            return None
        return list(self.columns[distance - self.start])

    def star_row(self, distance: int) -> int | None:
        row = self.star_rows[distance % len(self.star_rows)]
        return row - 1 if 1 <= row <= MAP_ROWS else None
