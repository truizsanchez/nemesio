"""A stage's characters and sprite patterns, loaded as the cartridge loads them.

What bank 0, 0x422A does when a stage is set up, in its order:

1. the font of the band under the view (0x58BA): digits and a few loose
   characters into the third third;
2. with banks 4, 5 and 6 paged in, the **records** (0x42FC): six bytes each --
   which thirds, where the pattern stream is, the first character, where the
   colour stream is -- the ones every stage loads (0x932D) and then the
   stage's own list (table 0x92E3);
3. two lists of **mirrors** (0x433F): characters made by flipping characters
   already loaded, by bits (left to right) and then by bytes (upside down), so
   half the terrain is stored once;
4. the sprite patterns (0x86BB into 0x1800), and two blocks more per stage
   (table 0x42AD), and one for stage 5 (0x8FCB into 0x1D00).
"""

from game.rom import rle
from game.rom.cartridge import Cartridge, Paging
from game.vdp import COLOURS, PATTERNS, SPRITE_PATTERNS, THIRD, Vram

#: How the cartridge pages the banks for the graphics job (0x422F).
GRAPHICS_BANKS = {0x6000: 4, 0x8000: 5, 0xA000: 6}

#: Records every stage loads, then the per-stage list's table.
COMMON_RECORDS = 0x932D
STAGE_RECORDS = 0x92E3
#: The two mirror lists, per stage: flipped by bits, then flipped by bytes.
MIRRORS_BY_BITS = 0x92FB
MIRRORS_BY_BYTES = 0x9313
#: The sprite patterns every stage has, and the two blocks a stage adds: three
#: bytes each -- the source, and the pattern (in 8-byte units) it starts at.
#: The table's base is one stage early: there is no stage 0.
SPRITES = 0x86BB
STAGE_SPRITES = 0x42AD
#: Stage 5's extra block.
STAGE5_SPRITES, STAGE5_SPRITES_AT = 0x8FCB, 0x1D00

#: The band's font (0x58BA): colour cells blanked to white on black, the ten
#: digits copied raw, and nine loose characters out of a raw table.
FONT_BLANK = ((0x1008, 0x50), (0x1068, 0x40))
FONT_BLANK_COLOUR = 0xF0
DIGITS, DIGITS_AT, DIGITS_SIZE = 0x5906, 0x3008, 0x50
LOOSE_LIST, LOOSE_AT, LOOSE_SOURCE = 0x58FD, 0x3068, 0x596E
#: The letters of the messages over the view (0x5874): the same two raw
#: tables as the font, into the first two thirds, white on transparent.
LETTERS = ((0x5906, 0x0080, 0x68), (0x596E, 0x0100, 0xD8))
LETTERS_COLOUR, LETTERS_COLOUR_AT, LETTERS_COLOUR_SIZE = 0xF0, 0x0080, 0x158

# A record's first byte: which thirds it fills (bit 0 the third, bit 1 the
# middle, bit 2 the first). A mirror's third byte: the source's third in bits
# 0-2 (the same order), the destinations' in bits 3-5.
_RECORD_THIRDS = ((0x01, 2), (0x02, 1), (0x04, 0))
_MIRROR_TO = ((0x08, 2), (0x10, 1), (0x20, 0))
_RECORD, _MIRROR = 6, 4


def load_font(cart: Cartridge, vram: Vram) -> None:
    """0x58BA."""
    for at, size in FONT_BLANK:
        for n in range(size):
            vram[at + n] = FONT_BLANK_COLOUR
    for n, value in enumerate(cart.block(0, DIGITS, DIGITS_SIZE)):
        vram[DIGITS_AT + n] = value
    at, to = LOOSE_LIST, LOOSE_AT
    while char := cart.byte(0, at):
        for n, value in enumerate(cart.block(0, LOOSE_SOURCE + char * 8, 8)):
            vram[to + n] = value
        at += 1
        to += 8


def load_letters(cart: Cartridge, vram: Vram) -> None:
    """0x5874: the font for the messages over the view, in thirds 0 and 1."""
    for third in (0, 1):
        for source, at, size in LETTERS:
            for n, value in enumerate(cart.block(0, source, size)):
                vram[PATTERNS + third * THIRD + at + n] = value
        for n in range(LETTERS_COLOUR_SIZE):
            vram[COLOURS + third * THIRD + LETTERS_COLOUR_AT + n] = LETTERS_COLOUR


def load_records(source: Paging, at: int, vram: Vram) -> None:
    """0x4371: records of six bytes until a zero."""
    while thirds := source.byte(at):
        patterns, char, colours = source.word(at + 1), source.byte(at + 3), source.word(at + 4)
        for bit, third in _RECORD_THIRDS:
            if thirds & bit:
                to = third * THIRD + char * 8
                rle.unpack(source, patterns, vram, PATTERNS + to)
                rle.unpack(source, colours, vram, COLOURS + to)
        at += _RECORD


def _flip_bits(value: int) -> int:
    return int("{:08b}".format(value)[::-1], 2)


def load_mirrors(source: Paging, at: int, vram: Vram, by_bytes: bool) -> None:
    """0x4348: four bytes a mirror -- source character, destination character,
    thirds, count -- until a zero. The source is read back out of VRAM, so a
    mirror can only be of something already loaded."""
    while first := source.byte(at):
        to_char, thirds, count = source.byte(at + 1), source.byte(at + 2), source.byte(at + 3)
        from_third = 0 if thirds & 0x04 else 1 if thirds & 0x02 else 2
        size = count * 8
        start = from_third * THIRD + first * 8
        tables = []
        for table in (PATTERNS, COLOURS):
            data = [vram[table + start + n] for n in range(size)]
            if by_bytes:
                data = [value for c in range(count)
                        for value in reversed(data[c * 8:c * 8 + 8])]
            elif table == PATTERNS:
                # 0x43F2 flips only the pattern buffer (0xE300): a row's two
                # colours are the same whichever way round it is drawn.
                data = [_flip_bits(value) for value in data]
            tables.append((table, data))
        for bit, third in _MIRROR_TO:
            if thirds & bit:
                for table, data in tables:
                    for n, value in enumerate(data):
                        vram[table + third * THIRD + to_char * 8 + n] = value
        at += _MIRROR


def load_stage(cart: Cartridge, stage: int, vram: Vram) -> None:
    """Everything 0x422A loads for `stage` (1-12)."""
    load_font(cart, vram)
    source = Paging(cart, GRAPHICS_BANKS)
    load_records(source, COMMON_RECORDS, vram)
    load_records(source, source.word(STAGE_RECORDS + 2 * stage), vram)
    load_mirrors(source, source.word(MIRRORS_BY_BITS + 2 * stage), vram, by_bytes=False)
    load_mirrors(source, source.word(MIRRORS_BY_BYTES + 2 * stage), vram, by_bytes=True)
    rle.unpack(source, SPRITES, vram, SPRITE_PATTERNS)
    at = STAGE_SPRITES + 6 * stage
    for _ in range(2):
        block, first = source.word(at), source.byte(at + 2)
        rle.unpack(source, block, vram, SPRITE_PATTERNS + first * 8)
        at += 3
    if stage == 5:
        rle.unpack(source, STAGE5_SPRITES, vram, STAGE5_SPRITES_AT)


def load_play(cart: Cartridge, stage: int, vram: Vram) -> None:
    """What VRAM holds when a life starts on `stage`: the letters (state 4,
    0x544F), then the stage's graphics again over them (state 5 sets the stage
    up with 0x422A), so a stage's own characters win."""
    load_stage(cart, stage, vram)
    load_letters(cart, vram)
    load_stage(cart, stage, vram)


#: The boss's characters (0x4A6D): records at 0x98A3 and a list of mirrors,
#: by bytes, at 0x98B0.
BOSS_RECORDS, BOSS_MIRRORS = 0x98A3, 0x98B0


def load_boss(cart: Cartridge, vram: Vram) -> None:
    source = Paging(cart, GRAPHICS_BANKS)
    load_records(source, BOSS_RECORDS, vram)
    load_mirrors(source, BOSS_MIRRORS, vram, by_bytes=True)
