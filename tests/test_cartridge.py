"""The cartridge reader: identification, banks, and the RLE.

Each rule is a case a reader can see, on bytes this file writes.
"""

import pytest

from game.rom import rle
from game.rom.cartridge import SIZE, NotTheCartridge, Paging, identify
from game.vdp import Vram
from tests.cartridge_shape import Blank


def test_a_file_of_the_wrong_size_is_refused_with_its_size():
    with pytest.raises(NotTheCartridge, match="this file is 100"):
        identify(b"AB" + bytes(98))


def test_a_file_that_is_not_a_cartridge_is_refused():
    with pytest.raises(NotTheCartridge, match="not an MSX cartridge"):
        identify(bytes(SIZE))


def test_another_dump_is_refused_by_its_hash():
    with pytest.raises(NotTheCartridge, match="SHA-1"):
        identify(b"AB" + bytes(SIZE - 2))


def test_an_address_is_read_in_the_window_its_bank_runs_at():
    blank = Blank()
    blank.put(11, 0x8123, [0x42])
    blank.put(3, 0xA000, [0x07])
    cart = blank.cartridge()
    assert cart.byte(11, 0x8123) == 0x42
    assert cart.byte(3, 0xA000) == 0x07


def test_an_address_outside_a_banks_window_is_an_error_not_a_wrong_byte():
    """Bank 11 only ever runs at 0x8000; asking it for 0xA000 is a bug in the
    caller, and returning some byte would hide it."""
    with pytest.raises(ValueError):
        Blank().cartridge().byte(11, 0xA000)


def test_paging_resolves_a_pointer_to_the_bank_in_its_window():
    blank = Blank()
    blank.put(0, 0x4100, [1])
    blank.put(5, 0x8100, [2])
    blank.put(6, 0xA100, [3])
    paging = Paging(blank.cartridge(), {0x6000: 4, 0x8000: 5, 0xA000: 6})
    assert [paging.byte(a) for a in (0x4100, 0x8100, 0xA100)] == [1, 2, 3]


def _unpack(stream: list[int], to: int = 0x100) -> tuple[Vram, int]:
    blank = Blank()
    blank.put(5, 0x8000, stream)
    vram = Vram()
    end = rle.unpack(Paging(blank.cartridge(), {0x8000: 5}), 0x8000, vram, to)
    return vram, end


def test_rle_a_command_under_0x80_repeats_the_next_byte():
    vram, end = _unpack([3, 0xAA, 0])
    assert vram.data[0x100:0x104] == bytes([0xAA, 0xAA, 0xAA, 0])
    assert end == 0x8003


def test_rle_bit_7_is_the_literal_copy():
    """The original's format is the other way round from the usual one."""
    vram, _ = _unpack([0x82, 1, 2, 0])
    assert vram.data[0x100:0x103] == bytes([1, 2, 0])


def test_rle_0x80_moves_the_vram_address():
    vram, _ = _unpack([0x80, 0x00, 0x20, 1, 9, 0])
    assert vram.data[0x2000] == 9 and vram.data[0x100] == 0


def test_the_walkers_route_is_read_out_of_its_code():
    from game.rom.tables import WALKER_LEG_COUNT, WALKER_LEGS, _walker_route
    blank = Blank()
    at = 0x8D7C
    for n in range(WALKER_LEG_COUNT):
        blank.word(2, WALKER_LEGS + 2 * n, at)
        if n % 2:
            # ld de,0x02FE / call / ld a,d / cp 0x30: down and left, to row 0x30.
            code = [0x11, 0xFE, 0x02, 0xCD, 0x00, 0x90, 0x7A, 0xFE, 0x30]
        else:
            # ld de,0x00FE / call / cp 0xE6: left, to column 0xE6.
            code = [0x11, 0xFE, 0x00, 0xCD, 0x00, 0x90, 0xFE, 0xE6]
        blank.put(2, at, code)
        at += len(code) + 2
    route = _walker_route(blank.cartridge())
    assert route[0] == (0, -2, "x", 0xE6) and route[1] == (2, -2, "y", 0x30)
