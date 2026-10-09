"""The band under the view: rows 22 and 23 of the name table, as the cartridge
writes them.

Bank 0, 0x5632 ("write the labels"): the labels out of two streams in the
format of 0x4998 -- a VRAM address, characters, 0xFE for another address,
0xFF to end -- then the lives, the power meter and the two scores.

The labels and the messages are asked of a `Messages` by name: the
cartridge's (`RomMessages`, its streams where the listing has them) or the
free assets' (`game/free/texts.py`).
"""

from typing import Protocol

from game.rom.cartridge import Cartridge
from game.vdp import NAMES

#: The labels (0x57CE), and the one-player line (0x57E1; 0x57E6 is 2P's).
LABELS, ONE_PLAYER, TWO_PLAYER = 0x57CE, 0x57E1, 0x57E6
#: With two players, whose turn it is (0x5545): PLAYER 1 or PLAYER 2.
TURNS = (0x5820, 0x582B)
#: The title's messages, and the choices that blink when chosen (0x57EB,
#: 0x5808, 0x5812); GAME OVER's (0x5836). Written by game/rom/screens.py.
TITLE_MESSAGES, TITLE_ONE_PLAYER, TITLE_TWO_PLAYERS = 0x57EB, 0x5808, 0x5812
GAME_OVER = 0x5836
#: Where the lives go: row 23, column 3 (0x5668). Two digits, the tens blank
#: under ten.
LIVES_AT = 0x3AE3
#: The meter: six cells of four characters from row 22, column 4 (0x569D).
#: Cell c's four are at 0x56D1 + 8c; the next four are the chosen cell's;
#: a cell already taken is the four at 0x5709 instead (0x56C1).
METER_AT, METER, METER_TAKEN, METER_CELL = 0x3AC4, 0x56D1, 0x5709, 4
#: The scores, six digits each: the record at row 23, column 22, and the
#: player's at column 10 (0x5650, 0x5659).
RECORD_AT, SCORE_AT, DIGITS = 0x3AF6, 0x3AEA, 6
#: A digit's character is its value plus one (0x5690).
DIGIT_ZERO = 1
_NEW_ADDRESS, _END = 0xFE, 0xFF


def write_stream(cart: Cartridge, at: int, names: bytearray) -> None:
    """0x4998, into `names` (the 768 bytes of the name table)."""
    while True:
        address = cart.word(0, at)
        at += 2
        while (value := cart.byte(0, at)) not in (_NEW_ADDRESS, _END):
            names[address - NAMES] = value
            address += 1
            at += 1
        at += 1
        if value == _END:
            return


def _digits(names: bytearray, address: int, value: int, count: int) -> None:
    text = "%0*d" % (count, value % 10 ** count)
    for n, digit in enumerate(text):
        names[address - NAMES + n] = int(digit) + DIGIT_ZERO


#: The messages, by name. The band's: its labels and whose line (1P or 2P).
BAND_LABELS, BAND_ONE_PLAYER, BAND_TWO_PLAYERS = "labels", "one_player_band", "two_players_band"
#: The title's (its lines, and the two choices that blink), the turn's
#: label, GAME OVER.
TITLE, ONE_PLAYER_LINE, TWO_PLAYERS_LINE = "title", "one_player", "two_players"
TURN_LABELS = ("player_1", "player_2")
GAME_OVER_TEXT = "game_over"


class Messages(Protocol):
    def write(self, name: str, names: bytearray) -> None:
        """The message into `names` (the name table's 768 bytes)."""

    def meter(self, cell: int, taken: bool, chosen: bool) -> bytes:
        """A power meter cell's four characters (cell 1-6)."""


class RomMessages:
    """The cartridge's: its 0x4998 streams, and the meter's characters."""

    STREAMS = {
        BAND_LABELS: LABELS, BAND_ONE_PLAYER: ONE_PLAYER, BAND_TWO_PLAYERS: TWO_PLAYER,
        TITLE: TITLE_MESSAGES, ONE_PLAYER_LINE: TITLE_ONE_PLAYER,
        TWO_PLAYERS_LINE: TITLE_TWO_PLAYERS,
        TURN_LABELS[0]: TURNS[0], TURN_LABELS[1]: TURNS[1], GAME_OVER_TEXT: GAME_OVER,
    }

    def __init__(self, cart: Cartridge) -> None:
        self.cart = cart

    def write(self, name: str, names: bytearray) -> None:
        write_stream(self.cart, self.STREAMS[name], names)

    def meter(self, cell: int, taken: bool, chosen: bool) -> bytes:
        source = METER_TAKEN if taken else METER + 8 * cell
        if chosen:
            source += METER_CELL
        return self.cart.block(0, source, METER_CELL)


def write_band(messages: Messages, names: bytearray, lives: int, taken: list[bool],
               chosen: int, score: int, record: int, turn: int = 0) -> None:
    """Everything 0x5632 writes. `taken` is the six meter cells already taken;
    `chosen` is the cell the capsules have lit (1-6), 0 for none; `turn`,
    whose score it is (0x5638)."""
    messages.write(BAND_LABELS, names)
    messages.write(BAND_TWO_PLAYERS if turn else BAND_ONE_PLAYER, names)
    if lives < 10:
        names[LIVES_AT - NAMES] = 0
        names[LIVES_AT - NAMES + 1] = lives + DIGIT_ZERO
    else:
        _digits(names, LIVES_AT, lives, 2)
    at = METER_AT - NAMES
    for cell in range(1, len(taken) + 1):
        four = messages.meter(cell, taken[cell - 1], chosen == cell)
        names[at:at + METER_CELL] = four
        at += METER_CELL
    _digits(names, RECORD_AT, record, DIGITS)
    _digits(names, SCORE_AT, score, DIGITS)
