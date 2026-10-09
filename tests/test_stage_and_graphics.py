"""A stage's terrain and characters, on cartridge-shaped bytes.

Whether these give the original's own, cell for cell, is `tools/check_rom.py`'s
job against the cartridge running in openMSX.
"""

from game.rom import graphics
from game.rom.cartridge import Paging
from game.rom.stage import OTHER_PIECES, PIECES, RANGES, SCRIPTS, STAR_ROWS, Stage
from game.vdp import COLOURS, PATTERNS, THIRD, Vram
from tests.cartridge_shape import Blank

SCRIPT = 0x9000


def _stage(number: int = 1, start: int = 0x20, end: int = 0x28) -> Blank:
    blank = Blank()
    blank.word(0, RANGES + 6 * number, start)
    blank.word(0, RANGES + 6 * number + 2, end)
    blank.word(0, RANGES + 6 * number + 4, end - 1)
    blank.word(11, SCRIPTS + 2 * number, SCRIPT)
    return blank


def test_a_column_is_six_pieces_the_last_giving_only_two_rows():
    blank = _stage()
    blank.put(11, SCRIPT, [1, 2, 3, 4, 5, 6])
    for piece in range(1, 7):
        # Every cell of piece p says p, and which of its rows it is.
        blank.put(11, PIECES + piece * 16, [piece << 4 | row for row in range(4) for _ in range(4)])
    column = Stage(blank.cartridge(), 1).column(0x20)
    assert column is not None and len(column) == 22
    assert column[:4] == [0x10, 0x11, 0x12, 0x13]
    assert column[20:] == [0x60, 0x61]


def test_the_distances_two_low_bits_pick_the_pieces_column():
    """Not the distance into the script: the absolute one (0x470D)."""
    blank = _stage(start=0x21, end=0x30)
    blank.put(11, SCRIPT, [1, 0, 0, 0, 0, 0])
    blank.put(11, PIECES + 16, [0xA0, 0xA1, 0xA2, 0xA3])
    column = Stage(blank.cartridge(), 1).column(0x22)
    assert column is not None and column[0] == 0xA2


def test_every_four_columns_the_script_moves_on_a_row():
    blank = _stage()
    blank.put(11, SCRIPT, [1, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0])
    blank.put(11, PIECES + 16, [0x11] * 16)
    blank.put(11, PIECES + 32, [0x22] * 16)
    stage = Stage(blank.cartridge(), 1)
    assert [stage.column(d)[0] for d in (0x23, 0x24)] == [0x11, 0x22]  # type: ignore[index]


def test_outside_the_range_a_column_is_sky_with_the_tables_star():
    blank = _stage()
    blank.put(0, STAR_ROWS + 5, [3])
    blank.put(0, STAR_ROWS + 6, [0])
    stage = Stage(blank.cartridge(), 1)
    assert stage.column(0x28) is None, "the end of the range is not in it"
    assert stage.star_row(5) == 2 and stage.star_row(6) is None


def test_stages_5_9_10_12_use_the_other_pieces():
    assert Stage(_stage(5).cartridge(), 5).pieces == OTHER_PIECES
    assert Stage(_stage(4).cartridge(), 4).pieces == PIECES


def test_a_mirror_by_bits_flips_each_row_left_to_right_into_the_named_thirds():
    blank = Blank()
    # Source character 0x10 in the first third (bit 2), to 0x20 in the second
    # third (bit 4), one character.
    blank.put(5, 0x8000, [0x10, 0x20, 0x04 | 0x10, 1, 0])
    vram = Vram()
    for n in range(8):
        vram[PATTERNS + 0x10 * 8 + n] = 0x80 >> n
        vram[COLOURS + 0x10 * 8 + n] = 0xF1
    graphics.load_mirrors(Paging(blank.cartridge(), graphics.GRAPHICS_BANKS),
                          0x8000, vram, by_bytes=False)
    assert [vram[PATTERNS + THIRD + 0x20 * 8 + n] for n in range(8)] == [1 << n for n in range(8)]
    assert vram[COLOURS + THIRD + 0x20 * 8] == 0xF1
    assert vram[PATTERNS + 0x20 * 8] == 0, "the first third was not named"


def test_a_mirror_by_bytes_turns_each_character_upside_down():
    blank = Blank()
    blank.put(5, 0x8000, [0x10, 0x20, 0x04 | 0x20, 2, 0])
    vram = Vram()
    for n in range(16):
        vram[PATTERNS + 0x10 * 8 + n] = n
    graphics.load_mirrors(Paging(blank.cartridge(), graphics.GRAPHICS_BANKS),
                          0x8000, vram, by_bytes=True)
    assert [vram[PATTERNS + 0x20 * 8 + n] for n in range(16)] == \
        list(range(7, -1, -1)) + list(range(15, 7, -1))
