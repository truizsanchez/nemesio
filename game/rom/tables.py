"""The engine's tables, read out of the player's cartridge.

Each is where the reference listing names it; the shape each takes is
`game/engine/tables.py`'s.
"""

from game.engine.tables import (
    EndingArt, FlockArt, FortressArt, GunArt, NucleusArt, Stage5Art, Tables,
)
from game.engine.ending import CoreArt
from game.engine.words import Keyboard
from game.rom.cartridge import BANK, WINDOW, Cartridge

STAGES = 8
#: With the four bonus stages, whose cannons and prizes have scripts too.
ALL_STAGES = 12
TYPES = 32
SECTIONS, SECTIONS_A_STAGE = 0xA3A6, 16


def _bytes(cart: Cartridge, bank: int, at: int, count: int) -> tuple[int, ...]:
    return tuple(cart.block(bank, at, count))


CANNON_SCRIPTS, CANNON_END, CANNON_ROWS_MAX = 0x9262, 0xFFFF, 0x100
#: A bonus stage's prize script is read until a distance no stage reaches.
PRIZES_END = 0x400


def _script(cart: Cartridge, bank: int, table: int, stage: int) -> tuple[tuple[int, int], ...]:
    """0x9100: rows of three bytes until a distance no stage reaches."""
    at = cart.word(bank, table + 2 * stage)
    rows: list[tuple[int, int]] = []
    if not cart_window(bank, at):
        return ()
    for _ in range(CANNON_ROWS_MAX):
        distance = cart.word(bank, at)
        if distance == CANNON_END:
            break
        rows.append((distance, cart.byte(bank, at + 2)))
        at += 3
    return tuple(rows)


def cart_window(bank: int, address: int) -> bool:
    return WINDOW[bank] <= address < WINDOW[bank] + BANK


def _cannon_script(cart: Cartridge, stage: int) -> tuple[tuple[int, int], ...]:
    return _script(cart, 2, CANNON_SCRIPTS, stage)


def _ship_cards(cart: Cartridge, state: int) -> tuple[tuple[int, int, int, int], ...]:
    """0x99E3, indexed by the ship's state: six cards of four bytes."""
    if not state:
        return ()
    at = cart.word(2, 0x99E3 + 2 * state)
    cards = []
    for n in range(6):
        p1, c1, p2, c2 = cart.block(2, at + 4 * n, 4)
        cards.append((p1, c1, p2, c2))
    return tuple(cards)


def _guns(cart: Cartridge) -> GunArt:
    """Stage 3's: 0x6283 (rectangles), 0x6370 (their characters), 0x6273
    (strips, read past the table's end for the later drawings as the
    original does), 0x64D4 (the strips' rows), 0x60C1, 0x7B38, 0x7B40, 0x60E7."""
    rects, chars, strips = [], [], []
    for d in range(14):
        # C (the height) first, then B (the width): 0x490C copies B across
        # by C down.
        height, width, off = cart.block(1, 0x6283 + 3 * d, 3)
        rects.append((width, height, off & 0x7F, bool(off & 0x80)))
        chars.append(tuple(cart.block(1, cart.word(1, 0x6370 + 2 * d), max(width * height, 1))))
        dy, row = cart.block(1, 0x6273 + 2 * d, 2)
        strips.append((dy, row))

    def pairs(base: int) -> dict[int, tuple[int, int]]:
        return {k: (cart.byte(1, base + 2 * k), cart.byte(1, base + 2 * k + 1)) for k in range(3, 7)}
    return GunArt(tuple(rects), tuple(chars), tuple(strips), tuple(cart.block(1, 0x64D4, 60)),
                  pairs(0x60C1), pairs(0x7B38), pairs(0x7B40), pairs(0x60E7))


def _flocks(cart: Cartridge) -> FlockArt:
    """Bank 3, 0xBB31..0xBD7D. A place is (row, column): 0x47AE reads it as
    a word into DE, and 0x6A72 takes E as the row."""
    def words(at: int, count: int) -> tuple[tuple[int, int], ...]:
        return tuple((cart.word(3, at + 4 * n), cart.word(3, at + 4 * n + 2)) for n in range(count))

    def pairs(at: int, count: int) -> tuple[tuple[int, int], ...]:
        return tuple((cart.byte(3, at + 2 * n), cart.byte(3, at + 2 * n + 1)) for n in range(count))
    return FlockArt(
        spiral_drawings=_bytes(cart, 3, 0xBB31, 4),
        places=pairs(0xBB35, 8),
        spirals=tuple(tuple(cart.block(3, 0xBB45 + 4 * n, 4)) for n in range(10)),  # type: ignore[misc]
        spiral_speeds=words(0xBB6D, 10),
        doors=pairs(0xBBE9, 4),
        door_speeds=words(0xBC43, 4),
        big_drawings=(tuple(cart.block(3, 0xBC83, 3)), tuple(cart.block(3, 0xBC86, 3))),  # type: ignore[arg-type]
        piece_speeds=words(0xBD71, 3),
    )


def _nucleus(cart: Cartridge) -> NucleusArt:
    """Banks 1, 2 and 10; a drawing is (width, height, a byte, characters)."""
    def drawings(table: int, count: int) -> tuple[tuple[int, int, int, tuple[int, ...]], ...]:
        out = []
        for n in range(count):
            at = cart.word(10, table + 2 * n)
            width, height, extra = cart.block(10, at, 3)
            out.append((width, height, extra, tuple(cart.block(10, at + 3, width * height))))
        return tuple(out)

    def pairs(bank: int, at: int, count: int) -> tuple[tuple[int, int], ...]:
        return tuple((cart.byte(bank, at + 2 * n), cart.byte(bank, at + 2 * n + 1))
                     for n in range(count))
    return NucleusArt(
        script=_bytes(cart, 2, 0x8041, 16),
        nucleus=_bytes(cart, 2, 0x8051, 10),
        upper=_bytes(cart, 2, 0x805B, 12),
        lower=_bytes(cart, 2, 0x8067, 12),
        nuclei=drawings(0xAAA6, 5),
        arms=drawings(0xAAB0, 40),
        ramp=_bytes(cart, 2, 0x81AD, 40),
        upper_aim=_bytes(cart, 2, 0x8270, 32),
        lower_aim=_bytes(cart, 2, 0x8250, 32),
        hang=_bytes(cart, 2, 0x8377, 40),
        muzzles=pairs(2, 0x80B0, 40),
        centres=pairs(1, 0x76EF, 40),
    )


def _prizes(cart: Cartridge, stage: int) -> tuple[tuple[int, int], ...]:
    """0x5D81: a bonus stage's prizes, (distance, data) rows of three bytes
    -- the data first -- in bank 12 from the table at 0xB2D2, until a
    distance past the stage's end."""
    at = cart.word(12, 0xB2D2 + 2 * stage)
    rows: list[tuple[int, int]] = []
    for _ in range(CANNON_ROWS_MAX):
        data, distance = cart.byte(12, at), cart.word(12, at + 1)
        if distance >= PRIZES_END:
            break
        rows.append((distance, data))
        at += 3
    return tuple(rows)


def _stage5(cart: Cartridge) -> Stage5Art:
    """Bank 3, 0xB26A..0xB946."""
    script = []
    at = 0xB7BF
    while (distance := cart.word(3, at)) != 0xFFFF:
        script.append((distance, cart.byte(3, at + 2), cart.byte(3, at + 3)))
        at += 4
    big = []
    for n in range(8):
        pointer = cart.word(3, 0xB749 + 2 * n)
        height, width = cart.block(3, pointer, 2)
        big.append((height, width, tuple(cart.block(3, pointer + 2, width * height))))
    bouncers = []
    at = 0xB8B4
    while (word := cart.word(3, at)) != 0xFFFF:
        bouncers.append((word & 0x3FF, word >> 8))
        at += 2

    def pairs(at: int, count: int) -> tuple[tuple[int, int], ...]:
        return tuple((cart.byte(3, at + 2 * n), cart.byte(3, at + 2 * n + 1)) for n in range(count))
    return Stage5Art(
        script=tuple(script),
        small=tuple(_bytes(cart, 3, cart.word(3, 0xB537 + 2 * n), 25) for n in range(24)),
        big=tuple(big),
        releases=pairs(0xB368, 4),
        turret_at=pairs(0xB3C7, 4),
        turret=(_bytes(cart, 3, 0xB729, 16), _bytes(cart, 3, 0xB739, 16)),
        fan=tuple((cart.word(3, 0xB26A + 4 * n), cart.word(3, 0xB26C + 4 * n)) for n in range(16)),
        bouncers=tuple(bouncers),
        # Four: a floor of 3 reads the byte past the table's three (0xB88C).
        floors=_bytes(cart, 3, 0xB89E, 4),
        bouncer_speeds=tuple(cart.word(3, 0xB909 + 2 * n) for n in range(6)),
        bouncer_drawings=_bytes(cart, 3, 0xB93E, 8),
    )


def _fortress(cart: Cartridge) -> FortressArt:
    """Bank 2, 0x8812..0x8CE4."""
    def signed(value: int) -> int:
        return value - 0x100 if value & 0x80 else value
    drawings = []
    for n in range(14):
        at = cart.word(2, 0x8B4C + 2 * n)
        dy, dx, height, width = cart.block(2, at, 4)
        drawings.append((signed(dy), signed(dx), height, width,
                         tuple(cart.block(2, at + 4, width * height))))
    script = []
    for at in range(0x88F8, 0x890B, 3):
        if cart.byte(2, at) == 0xFF:
            break
        script.append(tuple(cart.block(2, at, 3)))
    return FortressArt(
        claws=_bytes(cart, 2, 0x8812, 0x1D),
        rising=_bytes(cart, 2, 0x884D, 5),
        rising_drawings=tuple(_bytes(cart, 2, 0x8953 + 24 * n, 24) for n in range(6)),
        script=tuple(script),  # type: ignore[arg-type]
        drawings=tuple(drawings),
        muzzles=tuple((signed(cart.byte(2, 0x8A93 + 2 * n)), signed(cart.byte(2, 0x8A94 + 2 * n)))
                      for n in range(14)),
        upper_aim=_bytes(cart, 2, 0x8B3C, 16),
        lower_aim=_bytes(cart, 2, 0x8B2C, 16),
    )


#: The words typed in pause (0x51BF, strings ended by 0x0D), and each stage's
#: name among them (0x5163, one pointer a stage from stage 1).
WORDS, NAMES, WORD_END = 0x51BF, 0x5163, 0x0D
WORD_ORDER = ("HYPER", "BAKA", "AHO", "LASER", "MISSILE", "SHIELD", "OPTION", "DOUBLE", "DOWN")


def _text(cart: Cartridge, at: int) -> str:
    out = []
    while (value := cart.byte(0, at)) != WORD_END:
        out.append(chr(value))
        at += 1
    return "".join(out)


def keyboard(cart: Cartridge) -> Keyboard:
    """The words, keyed by what each does, and the twelve names."""
    words, at = {}, WORDS
    for word in WORD_ORDER:
        words[word] = _text(cart, at)
        at += len(words[word]) + 1
    names = tuple(_text(cart, cart.word(0, NAMES + 2 * n)) for n in range(ALL_STAGES))
    return Keyboard(words, names)


def _signed(byte: int) -> int:
    return byte - 0x100 if byte & 0x80 else byte


def _ending(cart: Cartridge) -> EndingArt:
    def pairs(bank: int, at: int, count: int) -> tuple[tuple[int, int], ...]:
        data = _bytes(cart, bank, at, 2 * count)
        return tuple((data[n], data[n + 1]) for n in range(0, 2 * count, 2))
    speeds = _bytes(cart, 1, 0x718D, 32)
    return EndingArt(
        eruption_from=pairs(1, 0x7189, 2),
        eruption_speeds=tuple((speeds[n] | speeds[n + 1] << 8, speeds[n + 2] | speeds[n + 3] << 8)
                              for n in range(0, 32, 4)),
        core_shots=tuple((row, _signed(col)) for row, col in pairs(1, 0x7E03, 4)),
        head_lanes=_bytes(cart, 2, 0x8458, 4),
        head_floors=_bytes(cart, 2, 0x857B, 4),
        head_roofs=_bytes(cart, 2, 0x857F, 4),
        head_chars=(_bytes(cart, 2, 0x86F1, 16), _bytes(cart, 2, 0x8701, 16)),
        walker_chars=(_bytes(cart, 2, 0x8E5F, 12), _bytes(cart, 2, 0x8E6B, 12)),
        crystal_pieces=pairs(2, 0x8EBA, 5),
        crystal_blast=_bytes(cart, 2, 0x905C, 4),
        crystal_chars=tuple(
            _bytes(cart, 2, CRYSTAL_CHARS + 4 * (CRYSTAL_PIECES - n),
                   4 if CRYSTAL_PIECES - n == CRYSTAL_TALL else 2)
            for n in range(CRYSTAL_PIECES)),
        walker_route=_walker_route(cart),
    )


#: 0x902E: 0x905C + 4 x 0xE1B6, which counts the five pieces down from 5; the
#: third (0xE1B6 = 3) draws a second row too (0x903A).
CRYSTAL_CHARS, CRYSTAL_PIECES, CRYSTAL_TALL = 0x905C, 5, 3
#: The walkers' legs: the dispatch table after 0x8D61's `call 0x4067`, ten
#: legs before 0x8DF0 (towards the ship). Each is `ld de,dy:dx`, a call,
#: then `cp value` on the column in A, or `ld a,d` and `cp` on the row.
WALKER_LEGS, WALKER_LEG_COUNT = 0x8D64, 10
LD_DE, CALL, CP, LD_A_D = 0x11, 0xCD, 0xFE, 0x7A


def _walker_route(cart: Cartridge) -> tuple[tuple[int, int, str, int], ...]:
    route = []
    for n in range(WALKER_LEG_COUNT):
        at = cart.word(2, WALKER_LEGS + 2 * n)
        assert cart.byte(2, at) == LD_DE and cart.byte(2, at + 3) == CALL
        dx, dy = _signed(cart.byte(2, at + 1)), _signed(cart.byte(2, at + 2))
        axis, cp = ("y", at + 7) if cart.byte(2, at + 6) == LD_A_D else ("x", at + 6)
        assert cart.byte(2, cp) == CP
        route.append((dy, dx, axis, cart.byte(2, cp + 1)))
    return tuple(route)


APPEARANCES, APPEARANCES_END, APPEARANCES_MAX = 0xAF3F, 0xFFFF, 0x80


def _appearances(cart: Cartridge) -> tuple[int, ...]:
    """0xAF2C: words until 0xFFFF."""
    words = []
    for n in range(APPEARANCES_MAX):
        word = cart.word(3, APPEARANCES + 2 * n)
        if word == APPEARANCES_END:
            break
        words.append(word)
    return tuple(words)


def core_art(cart: Cartridge) -> CoreArt:
    """The core's body, eye and mouth drawings (0x7EE6, 0x7F3E, 0x7F62)."""
    return CoreArt(_bytes(cart, 1, 0x7EE6, 88), _bytes(cart, 1, 0x7F3E, 36),
                   _bytes(cart, 1, 0x7F62, 18))


def read(cart: Cartridge) -> Tables:
    records = tuple(tuple(cart.block(1, 0x6BA3 + 4 * t, 4)) for t in range(TYPES))
    sections = tuple(
        _bytes(cart, 3, cart.word(3, SECTIONS + 2 * stage), SECTIONS_A_STAGE)
        if stage else (0,) * SECTIONS_A_STAGE
        for stage in range(STAGES + 1))
    blast = _bytes(cart, 0, 0x5E5D, 8)
    return Tables(
        records=records,  # type: ignore[arg-type]
        sections=sections,
        rows_types=_bytes(cart, 3, 0xA5AF, STAGES + 1),
        trail_rows=_bytes(cart, 3, 0xA4A6, 4),
        trail_counts=_bytes(cart, 3, 0xA4AA, 16),
        left_rows=_bytes(cart, 3, 0xA640, 8),
        marks=_bytes(cart, 3, 0xA5C7, 16),
        # Twelve steps, but 0x6B88 indexes them by a difficulty that goes to
        # 0x0F from the second round: the last four are the code after them.
        shot_delays=_bytes(cart, 1, 0x6B97, 16),
        angles=_bytes(cart, 1, 0x6753, 256),
        sines=_bytes(cart, 1, 0x6853, 64),
        # Read with banks 4/5/6 paged in (0x4827): bank 5, not 2.
        character_drawings=_bytes(cart, 5, 0x91D1, 0x200),
        blast=tuple((blast[n], blast[n + 1]) for n in range(0, 8, 2)),
        cannon_script=tuple(_cannon_script(cart, stage) if stage else ()
                            for stage in range(ALL_STAGES + 1)),
        cannon_drawings=_bytes(cart, 2, 0x9205, 48),
        background_script=tuple(_script(cart, 1, 0x64FA, stage) if stage else ()
                                for stage in range(ALL_STAGES + 1)),
        prize_script=tuple(_prizes(cart, stage) if stage > STAGES else ()
                           for stage in range(ALL_STAGES + 1)),
        prize_points=tuple(cart.word(1, 0x7561 + 2 * n) for n in range(8)),
        ending=_ending(cart),
        blast_drawings=tuple(_bytes(cart, 1, cart.word(1, 0x633A + 2 * n), 16)
                             for n in range(3)),
        background_drawings=tuple(_bytes(cart, 1, cart.word(1, 0x6370 + 2 * n), 16)
                                  for n in range(16)),
        # Three steps of four, but 0x9193 indexes them by a difficulty that
        # goes to 0x0F: past them it reads on into 0x91D1's bytes.
        cannon_waits=_bytes(cart, 2, 0x91C5, 64),
        ship_cards=tuple(_ship_cards(cart, state) for state in range(4)),
        kill_sounds=_bytes(cart, 1, 0x730F, 32),
        stone_drawings=tuple((cart.byte(3, 0xAD18 + 2 * n + 1), cart.byte(3, 0xAD18 + 2 * n))
                             for n in range(3)),
        walls={2: tuple(cart.word(3, 0xAC81 + 2 * n) for n in range(6)),
               8: tuple(cart.word(3, 0xAC8D + 2 * n) for n in range(17))},
        wall_rows=_bytes(cart, 3, 0xAC7B, 6),
        rain_doors=tuple((cart.byte(3, 0xABD3 + 2 * n), cart.byte(3, 0xABD4 + 2 * n))
                         for n in range(16)),
        guns=_guns(cart),
        toward_ship=tuple(cart.word(2, 0x9657 + 2 * n) for n in range(256)),
        flocks=_flocks(cart),
        nucleus=_nucleus(cart),
        spit_speeds=tuple(cart.word(2, 0x87AF + 2 * n) for n in range(16)),
        fortress=_fortress(cart),
        stage5=_stage5(cart),
        animations={
            2: _bytes(cart, 3, 0xA933, 4),
            3: _bytes(cart, 3, 0xA84F, 8),
            5: _bytes(cart, 3, 0xAB58, 8),
            6: _bytes(cart, 3, 0xA9D0, 4),
            9: _bytes(cart, 3, 0xAD68, 6),
            0x0A: _bytes(cart, 3, 0xADB3, 6),
            0x0B: _bytes(cart, 3, 0xAE03, 4),
            0x0C: _bytes(cart, 3, 0xAED9, 6),
            0x0D: _bytes(cart, 3, 0xB03C, 6),
        },
        appearances=_appearances(cart),
        lunge_speeds=_bytes(cart, 3, 0xB000, 16),
        blast_0d=_bytes(cart, 0, 0x5EE3, 4),
    )
