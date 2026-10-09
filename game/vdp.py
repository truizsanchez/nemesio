"""The TMS9918's memory as the cartridge lays it out, with no chip behind it.

The original draws by writing VRAM: characters into the pattern and colour
tables, the map into the name table, the sprites into the attribute table.
This game keeps the same 16 KB so that what the cartridge loads is loaded
byte for byte, and `game/render/` turns it into pictures.

**The layout is not the BIOS's.** The eight bytes at bank 0, 0x575A, program
the VDP so that patterns live at 0x2000, colours at 0x0000, names at 0x3800,
sprite attributes at 0x3B00 and sprite patterns at 0x1800. Every address in
the reference listing assumes this.
"""

PATTERNS = 0x2000
COLOURS = 0x0000
NAMES = 0x3800
ATTRIBUTES = 0x3B00
SPRITE_PATTERNS = 0x1800

#: A third of the screen: eight rows of characters, each third with its own
#: 256 patterns and colours (Graphics II).
THIRD = 0x800
SIZE = 0x4000

COLUMNS, ROWS = 32, 24
#: The screen, in pixels.
WIDTH, HEIGHT = 256, 192


class Vram:
    """16 KB, and the one mutation the loaders need."""

    def __init__(self) -> None:
        self.data = bytearray(SIZE)

    def __getitem__(self, address: int) -> int:
        return self.data[address & 0x3FFF]

    def __setitem__(self, address: int, value: int) -> None:
        self.data[address & 0x3FFF] = value

    def character(self, third: int, char: int) -> tuple[bytes, bytes]:
        """A character's eight pattern bytes and eight colour bytes."""
        at = third * THIRD + char * 8
        return (bytes(self.data[PATTERNS + at:PATTERNS + at + 8]),
                bytes(self.data[COLOURS + at:COLOURS + at + 8]))

    def sprite_pattern(self, number: int) -> bytes:
        """A 16x16 sprite's 32 bytes: the left half's sixteen rows, then the
        right half's."""
        at = SPRITE_PATTERNS + (number & 0xFC) * 8
        return bytes(self.data[at:at + 32])
