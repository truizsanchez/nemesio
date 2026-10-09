"""The screens between plays, built in VRAM as the cartridge builds them.

The title (bank 0, 0x5B77): the font in all three thirds (0x5851), the title's
patterns and colours out of banks 9 and 10 (0x5B50), the 28x5 panel with the
name (0x5B9B; NEMESIS, or GRADIUS on a Japanese machine), and the messages
(0x57EB, 0x5812). GAME OVER is its message (0x5836) on a cleared screen.
"""

from game.rom import rle
from game.rom.band import (
    GAME_OVER_TEXT, ONE_PLAYER_LINE, TITLE, TWO_PLAYERS_LINE, Messages, RomMessages,
)
from game.rom.cartridge import Cartridge, Paging
from game.vdp import COLOURS, NAMES, PATTERNS, THIRD, Vram

TITLE_BANKS = {0x8000: 9, 0xA000: 10}
#: 0x5851: the font's two raw tables, into all three thirds, white on clear.
FONT = ((0x5906, 0x0080, 0x68), (0x596E, 0x0100, 0xD8))
FONT_COLOUR, FONT_COLOUR_AT, FONT_COLOUR_SIZE = 0xF0, 0x0080, 0x158
#: The title's two compressed blocks, into each third at 0x468.
TITLE_PATTERNS, TITLE_COLOURS, TITLE_AT = 0x9C57, 0x9EAB, 0x468
#: The panel: five rows of 28 characters at row 4, column 2 (0x5B9B).
PANEL_WESTERN, PANEL_JAPANESE, PANEL_AT, PANEL_ROWS, PANEL_COLUMNS = 0x9B3F, 0x9BCB, 0x3882, 5, 28
#: The title's messages, and the one that blinks when chosen (0x5808, 0x5812),
#: by name (their streams' addresses are game/rom/band.py's).
ONE_PLAYER, TWO_PLAYERS = ONE_PLAYER_LINE, TWO_PLAYERS_LINE


def load_font(cart: Cartridge, vram: Vram) -> None:
    for third in range(3):
        for source, at, size in FONT:
            for n, value in enumerate(cart.block(0, source, size)):
                vram[PATTERNS + third * THIRD + at + n] = value
        for n in range(FONT_COLOUR_SIZE):
            vram[COLOURS + third * THIRD + FONT_COLOUR_AT + n] = FONT_COLOUR


def title(cart: Cartridge, japanese: bool = False) -> Vram:
    vram = Vram()
    load_font(cart, vram)
    source = Paging(cart, TITLE_BANKS)
    for block, table in ((TITLE_PATTERNS, PATTERNS), (TITLE_COLOURS, COLOURS)):
        for third in range(3):
            rle.unpack(source, block, vram, table + third * THIRD + TITLE_AT)
    panel = PANEL_JAPANESE if japanese else PANEL_WESTERN
    for row in range(PANEL_ROWS):
        for col in range(PANEL_COLUMNS):
            vram[PANEL_AT + row * 32 + col] = cart.byte(9, panel + row * PANEL_COLUMNS + col)
    write_messages(RomMessages(cart), vram)
    return vram


def write_messages(messages: Messages, vram: Vram) -> None:
    """The title's lines and the second choice over its picture (0x5B77)."""
    names = bytearray(vram.data[NAMES:NAMES + 768])
    messages.write(TITLE, names)
    messages.write(TWO_PLAYERS_LINE, names)
    vram.data[NAMES:NAMES + 768] = names


def game_over(messages: Messages) -> bytearray:
    """The names of the GAME OVER screen, over the play's characters."""
    names = bytearray(768)
    messages.write(GAME_OVER_TEXT, names)
    return names


def blank_message(messages: Messages, name: str, names: bytearray) -> None:
    """0x4998 with C=0 ("clear characters"): the message's cells cleared."""
    probe = bytearray(768)
    messages.write(name, probe)
    for n, value in enumerate(probe):
        if value:
            names[n] = 0
