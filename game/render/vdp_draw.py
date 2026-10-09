"""The VDP's memory drawn with Pyxel: characters through a tilemap, sprites
through a bank of patterns.

Image 0 holds every character of the three thirds, 32 to a row: third t's
character c is tile (c % 32, 8t + c // 32), so a whole screen is one `bltm`.
Image 1 holds the 64 sprite patterns of 16x16 as a mask in colour 1, which
`pal` turns into the sprite's colour when it is drawn.
"""

import pyxel

from game.vdp import COLOURS, PATTERNS, SPRITE_PATTERNS, THIRD, Vram

CHARACTERS, SPRITES, SCREEN = 0, 1, 0
_HEX = "0123456789abcdef"
SPRITE_SIZE = 16
SPRITES_A_ROW = 16


def tile(third: int, character: int) -> tuple[int, int]:
    return character % 32, third * 8 + character // 32


def load(vram: Vram) -> None:
    """Characters and sprite patterns into images 0 and 1."""
    rows: list[str] = []
    for third in range(3):
        for char_row in range(8):
            for y in range(8):
                line = []
                for char in range(char_row * 32, char_row * 32 + 32):
                    at = third * THIRD + char * 8 + y
                    bits, colour = vram[PATTERNS + at], vram[COLOURS + at]
                    for x in range(8):
                        line.append(_HEX[colour >> 4 if bits & 0x80 >> x else colour & 0x0F])
                rows.append("".join(line))
    pyxel.images[CHARACTERS].set(0, 0, rows)
    sprite_rows = ["0" * 256 for _ in range(64)]
    grid = [list(row) for row in sprite_rows]
    for n in range(64):
        base = SPRITE_PATTERNS + n * 32
        ox, oy = n % SPRITES_A_ROW * SPRITE_SIZE, n // SPRITES_A_ROW * SPRITE_SIZE
        for half in range(2):
            for y in range(16):
                bits = vram[base + half * 16 + y]
                for x in range(8):
                    if bits & 0x80 >> x:
                        grid[oy + y][ox + half * 8 + x] = "1"
    pyxel.images[SPRITES].set(0, 0, ["".join(row) for row in grid])


def put_names(names: bytes | bytearray, first_row: int = 0) -> None:
    """Characters by row into the tilemap, from `first_row`."""
    tilemap = pyxel.tilemaps[SCREEN]
    for n, char in enumerate(names):
        row, col = divmod(first_row * 32 + n, 32)
        tilemap.pset(col, row, tile(row // 8, char))


def draw_screen(backdrop: bool = False) -> None:
    """The name table; with `backdrop`, colour 0 lets what is behind show
    (the backdrop, register 7), which only the game's ending changes."""
    pyxel.bltm(0, 0, SCREEN, 0, 0, 256, 192, 0 if backdrop else None)


def draw_sprite(y: int, x: int, pattern: int, colour: int) -> None:
    """A 16x16 sprite at its attribute's Y and X: the VDP draws it a line
    lower than the Y it is given."""
    if not colour:
        return
    n = pattern // 4
    pyxel.pal(1, colour)
    pyxel.blt(x, y + 1, SPRITES, n % SPRITES_A_ROW * SPRITE_SIZE,
              n // SPRITES_A_ROW * SPRITE_SIZE, SPRITE_SIZE, SPRITE_SIZE, 0)
    pyxel.pal()


#: The VDP draws four sprites a line, the first in its table (0x3B00);
#: a Y past the screen's lines draws nothing but a 0xD0 ends the table.
SPRITES_A_LINE, LINES, END_OF_TABLE = 4, 192, 0xD0


def draw_sprite_table(table: list[tuple[int, int, int, int] | None]) -> None:
    """The attribute table as the VDP draws it: per line, only the first
    four sprites that cross it, the earlier in front. None is a sprite put
    off the screen (0xE0, 0xA225), which crosses no line."""
    shown: list[list[bool]] = []
    count = [0] * LINES
    for entry in table:
        rows = [False] * SPRITE_SIZE
        shown.append(rows)
        if entry is None:
            continue
        y = entry[0]
        if y == END_OF_TABLE:
            break
        top = (y + 1) if y < 0xE1 else y + 1 - 0x100
        for r in range(SPRITE_SIZE):
            line = top + r
            if 0 <= line < LINES and count[line] < SPRITES_A_LINE:
                count[line] += 1
                rows[r] = True
    for entry, rows in reversed(list(zip(table, shown))):
        if entry is None or not any(rows):
            continue
        y, x, pattern, colour = entry
        if not colour:
            continue
        top = (y + 1) if y < 0xE1 else y + 1 - 0x100
        n = pattern // 4
        u, v = n % SPRITES_A_ROW * SPRITE_SIZE, n // SPRITES_A_ROW * SPRITE_SIZE
        pyxel.pal(1, colour)
        r = 0
        while r < SPRITE_SIZE:
            if not rows[r]:
                r += 1
                continue
            start = r
            while r < SPRITE_SIZE and rows[r]:
                r += 1
            pyxel.blt(x, top + start, SPRITES, u, v + start, SPRITE_SIZE, r - start, 0)
        pyxel.pal()


def set_pattern_row(vram: Vram, character: int, row: int, bits: int) -> None:
    """One pixel row of a character in all three thirds, as the cartridge
    rewrites the stars': in `vram` and in image 0."""
    image = pyxel.images[CHARACTERS]
    for third in range(3):
        at = third * THIRD + character * 8 + row
        vram[PATTERNS + at] = bits
        colour = vram[COLOURS + at]
        u, v = tile(third, character)
        for x in range(8):
            image.pset(u * 8 + x, v * 8 + row, colour >> 4 if bits & 0x80 >> x else colour & 0x0F)
