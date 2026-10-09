"""A stage's terrain, as the cartridge's script and pieces give it.

Bank 0, 0x46AE: every scroll step brings in one column on the right of the map.
Inside the stage's **script range** the column comes from the script: every
four columns the script gives a row of six piece numbers, each piece is four by
four characters, and five pieces make twenty rows and the sixth the last two.
Outside the range the column is sky -- nothing but one star, on the row the
table at 0x478E gives for the distance.

Stages 3 and 6 have no script (their range is 0xFFFF): sky end to end.
"""

from game.rom.cartridge import Cartridge, Paging

#: How the cartridge pages banks for the map job (0x460E).
MAP_BANKS = {0x8000: 11, 0xA000: 12}

#: Per stage, six bytes (base one stage early): where the script starts, where
#: it ends, and where the scroll stops -- copied to 0xE101 by 0x41C3.
RANGES = 0x4499
#: Per stage, the checkpoint: a life lost past it restarts there (0x41DB).
#: The table's base is one stage early, and stage 12 reads past its end into
#: code (0x422A) -- 0xBACD, a distance no stage reaches, which is the
#: original's and kept.
CHECKPOINTS = 0x4212
#: Per stage, a pointer to its script (0x97DE, bank 11).
SCRIPTS = 0x97DE
#: The two sets of 4x4 pieces; stages 5, 9, 10 and 12 use the second.
PIECES, OTHER_PIECES = 0x8000, 0x8FF0
OTHER_PIECE_STAGES = (5, 9, 10, 12)
#: Which row a sky column's star is on, by the distance's five low bits;
#: 1-based, and anything outside 1..22 is no star.
STAR_ROWS = 0x478E

ROWS = 22
NO_SCRIPT = 0xFFFF
_PIECES_A_ROW, _PIECE, _PIECE_SIDE = 6, 16, 4


class Stage:
    """One stage's script range and its columns."""

    def __init__(self, cart: Cartridge, number: int) -> None:
        self.cart = cart
        self.number = number
        self.source = Paging(cart, MAP_BANKS)
        at = RANGES + 6 * number
        self.start = cart.word(0, at)
        self.end = cart.word(0, at + 2)
        #: The scroll does not go past this distance (0xE105).
        self.limit = cart.word(0, at + 4)
        self.checkpoint = cart.word(0, CHECKPOINTS + 2 * number)
        self.script = self.source.word(SCRIPTS + 2 * number)
        self.pieces = OTHER_PIECES if number in OTHER_PIECE_STAGES else PIECES

    def scripted(self, distance: int) -> bool:
        """0x46AE: the script applies from its start up to, not including, its end."""
        return self.start <= distance < self.end

    def column(self, distance: int) -> list[int] | None:
        """The 22 characters of the column at `distance`, top down, or None
        for a sky column."""
        if not self.scripted(distance):
            return None
        at = self.script + ((distance - self.start) >> 2) * _PIECES_A_ROW
        across = distance & 3
        cells: list[int] = []
        for n in range(_PIECES_A_ROW):
            piece = self.pieces + self.source.byte(at + n) * _PIECE + across
            for row in range(_PIECE_SIDE if n < _PIECES_A_ROW - 1 else 2):
                cells.append(self.source.byte(piece + row * _PIECE_SIDE))
        return cells

    def star_row(self, distance: int) -> int | None:
        """0x4738: the row (0-21) of a sky column's star, or None."""
        row = self.cart.byte(0, STAR_ROWS + (distance & 0x1F))
        return row - 1 if 1 <= row <= ROWS else None
