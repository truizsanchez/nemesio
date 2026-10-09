"""The one compressed format the cartridge keeps its graphics in.

Bank 0, 0x49B9 unpacks straight into VRAM, and it is written the other way round
from what one expects -- **bit 7 marks the literal copy**, not the repeat:

    0x00        end of the block
    0x01..0x7F  the next byte, N times
    0x80        the next two bytes are a new VRAM address
    0x81..0xFF  N-0x80 bytes copied as they come
"""

from game.rom.cartridge import Paging
from game.vdp import Vram

_END, _MOVE, _LITERAL = 0x00, 0x80, 0x80


def unpack(source: Paging, at: int, vram: Vram, to: int) -> int:
    """Unpack the block at `at` into `vram` from `to`; return where the block
    ended, one past its terminating zero."""
    while True:
        command = source.byte(at)
        at += 1
        if command == _END:
            return at
        if command == _MOVE:
            to = source.word(at)
            at += 2
        elif command & _LITERAL:
            for _ in range(command & 0x7F):
                vram[to] = source.byte(at)
                at += 1
                to += 1
        else:
            value = source.byte(at)
            at += 1
            for _ in range(command):
                vram[to] = value
                to += 1
