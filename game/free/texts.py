"""The free assets' texts: `text.json`, read into what the band and the
screens ask of a `game.rom.band.Messages`.

    "font":   which character each letter is: "view" over the play (thirds
              0 and 1) and on the title, "band" on the band (third 2)
    "labels", "one_player_band", "two_players_band"   the band's
    "title", "one_player", "two_players"              the title's
    "player_1", "player_2"                            the turn's label
    "game_over"                                       GAME OVER's
              each a list of [row, column, text]
    "meter":  "cells", per cell [its four characters, the four chosen];
              "taken", the same for a cell already taken
"""

import json
import os
from typing import Any

from game.free.numbers import num
from game.rom.band import BAND_LABELS, BAND_ONE_PLAYER, BAND_TWO_PLAYERS

#: The band's messages are in its own font (third 2).
BAND = (BAND_LABELS, BAND_ONE_PLAYER, BAND_TWO_PLAYERS)
COLUMNS = 32


class Font:
    """Text into character numbers: the letters' of the view or the band's."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.view = {k: num(v) for k, v in spec["view"].items()}
        self.band = {k: num(v) for k, v in spec["band"].items()}

    def encode(self, text: str, on_band: bool) -> list[int]:
        table = self.band if on_band else self.view
        out = []
        for letter in text:
            if letter == " ":
                out.append(0)
            elif letter in table:
                out.append(table[letter])
            elif letter.upper() in table:
                out.append(table[letter.upper()])
            else:
                raise ValueError("%r has no character in text.json's font" % letter)
        return out


class FreeMessages:
    def __init__(self, spec: dict[str, Any]) -> None:
        font = Font(spec["font"])
        #: Per message, (cell in the name table, characters) pieces.
        self.messages: dict[str, list[tuple[int, list[int]]]] = {}
        for name, pieces in spec.items():
            if name in ("font", "meter"):
                continue
            self.messages[name] = [(num(row) * COLUMNS + num(col), font.encode(text, name in BAND))
                                   for row, col, text in pieces]
        meter = spec["meter"]
        self.cells = [tuple(bytes(num(c) for c in four) for four in cell) for cell in meter["cells"]]
        self.taken = tuple(bytes(num(c) for c in four) for four in meter["taken"])

    @classmethod
    def read(cls, folder: str) -> "FreeMessages":
        with open(os.path.join(folder, "text.json")) as handle:
            return cls(json.load(handle))

    def write(self, name: str, names: bytearray) -> None:
        for at, chars in self.messages.get(name, []):
            chars = chars[:max(len(names) - at, 0)]
            names[at:at + len(chars)] = bytes(chars)

    def meter(self, cell: int, taken: bool, chosen: bool) -> bytes:
        return (self.taken if taken else self.cells[cell - 1])[int(chosen)]
