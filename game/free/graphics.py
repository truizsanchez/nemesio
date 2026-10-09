"""The free assets' pictures into the VDP's memory, and back.

`chars.png` is the play's characters laid out as `game/render/vdp_draw.py`
lays out image 0: 256x192, character c of third t in the 8x8 cell (c % 32,
8t + c // 32). The TMS9918 gives a row of eight pixels two colours, so each
row is read as its one or two colours -- a row with more keeps its two
commonest, and `problems` says where.

`sprites.png` is the 64 sprite patterns as image 1 lays them out: 256x64,
pattern n (of 16x16) at (n % 16, n // 16). A sprite has one colour, given by
the tables, so any pixel brighter than black is on.
"""

from collections import Counter

from game.free.png import Picture
from game.vdp import COLOURS, NAMES, PATTERNS, SPRITE_PATTERNS, THIRD, Vram

CHARS_WIDTH, CHARS_HEIGHT = 256, 192
SPRITES_WIDTH, SPRITES_HEIGHT = 256, 64
_CHARS_A_ROW, _SPRITES_A_ROW, _SPRITE = 32, 16, 16
#: A sprite pixel is on from colour 2: 0 is transparent and 1 black.
_SPRITE_ON = 2


def cell(third: int, char: int) -> tuple[int, int]:
    """Where a character's top left pixel is in `chars.png`."""
    return char % _CHARS_A_ROW * 8, (third * 8 + char // _CHARS_A_ROW) * 8


def encode_row(pixels: list[int]) -> tuple[int, int]:
    """Eight pixels as (pattern, colour): the brighter index is the
    foreground, drawn where the pattern's bits are set."""
    counts = Counter(pixels)
    two = sorted(c for c, _ in counts.most_common(2))
    if len(two) == 1:
        return 0, two[0]
    back, fore = two
    bits = 0
    for x, colour in enumerate(pixels):
        if colour == fore or (colour != back and abs(colour - fore) < abs(colour - back)):
            bits |= 0x80 >> x
    return bits, fore << 4 | back


def load_chars(picture: Picture, vram: Vram) -> list[str]:
    """Every character of the three thirds into the pattern and colour
    tables. Returns the rows that had more than two colours."""
    problems = []
    for third in range(3):
        for char in range(256):
            x0, y0 = cell(third, char)
            for y in range(8):
                pixels = [picture[x0 + x, y0 + y] for x in range(8)]
                if len(set(pixels)) > 2:
                    problems.append("chars.png: third %d, character 0x%02X, row %d has more "
                                    "than two colours" % (third, char, y))
                bits, colour = encode_row(pixels)
                at = third * THIRD + char * 8 + y
                vram[PATTERNS + at] = bits
                vram[COLOURS + at] = colour
    return problems


def chars_picture(vram: Vram) -> Picture:
    picture = Picture(CHARS_WIDTH, CHARS_HEIGHT)
    for third in range(3):
        for char in range(256):
            x0, y0 = cell(third, char)
            for y in range(8):
                at = third * THIRD + char * 8 + y
                bits, colour = vram[PATTERNS + at], vram[COLOURS + at]
                for x in range(8):
                    picture[x0 + x, y0 + y] = colour >> 4 if bits & 0x80 >> x else colour & 0x0F
    return picture


def load_sprites(picture: Picture, vram: Vram) -> None:
    for n in range(SPRITES_WIDTH // _SPRITE * (SPRITES_HEIGHT // _SPRITE)):
        x0, y0 = n % _SPRITES_A_ROW * _SPRITE, n // _SPRITES_A_ROW * _SPRITE
        for half in range(2):
            for y in range(_SPRITE):
                bits = 0
                for x in range(8):
                    if picture[x0 + half * 8 + x, y0 + y] >= _SPRITE_ON:
                        bits |= 0x80 >> x
                vram[SPRITE_PATTERNS + n * 32 + half * 16 + y] = bits


def sprites_picture(vram: Vram, colour: int = 15) -> Picture:
    picture = Picture(SPRITES_WIDTH, SPRITES_HEIGHT)
    for n in range(64):
        x0, y0 = n % _SPRITES_A_ROW * _SPRITE, n // _SPRITES_A_ROW * _SPRITE
        for half in range(2):
            for y in range(_SPRITE):
                bits = vram[SPRITE_PATTERNS + n * 32 + half * 16 + y]
                for x in range(8):
                    if bits & 0x80 >> x:
                        picture[x0 + half * 8 + x, y0 + y] = colour
    return picture


def screen(picture: Picture, vram: Vram, keep: range, reserved: set[int]) -> list[str]:
    """A whole screen's picture (256x192) as characters and names: each
    third's distinct 8x8 cells become its characters, from the first not in
    `reserved` (the font's, already in `vram`) and not 0; a blank black cell
    is character 0. Returns the problems (a third out of characters, rows of
    more than two colours)."""
    problems = []
    names = bytearray(768)
    for third in range(3):
        free = (c for c in keep if c not in reserved)
        seen: dict[tuple[tuple[int, int], ...], int] = {}
        for row in range(8):
            for col in range(32):
                rows = []
                for y in range(8):
                    pixels = [picture[col * 8 + x, (third * 8 + row) * 8 + y] for x in range(8)]
                    if len(set(pixels)) > 2:
                        problems.append("title.png: a row of the cell at row %d, column %d has "
                                        "more than two colours" % (third * 8 + row, col))
                    rows.append(encode_row(pixels))
                key = tuple(rows)
                if all(bits == 0 and colour & 0x0F <= 1 for bits, colour in rows):
                    continue
                if key not in seen:
                    char = next(free, None)
                    if char is None:
                        problems.append("title.png: third %d has more different cells than "
                                        "characters" % third)
                        continue
                    seen[key] = char
                    for y, (bits, colour) in enumerate(rows):
                        at = third * THIRD + char * 8 + y
                        vram[PATTERNS + at] = bits
                        vram[COLOURS + at] = colour
                names[(third * 8 + row) * 32 + col] = seen[key]
    vram.data[NAMES:NAMES + 768] = names
    return problems
