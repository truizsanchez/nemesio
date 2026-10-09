"""The texts, the sound effects and the title picture."""

import random

from game.free.png import Picture
from tools.free_assets.draw import (
    CYAN, DARK_BLUE, GREY, LIGHT_BLUE, LIGHT_RED, WHITE, Canvas, glyph,
)


# -- the texts and the sounds ---------------------------------------------------------------------

def text(font: dict[str, dict[str, str]], meter: dict[str, object]) -> dict[str, object]:
    return {
        "font": font,
        "labels": [[23, 2, "@"], [23, 16, "00"], [23, 19, "HI"], [23, 28, "00"]],
        "one_player_band": [[23, 7, "1P"]],
        "two_players_band": [[23, 7, "2P"]],
        "title": [[14, 11, "PLAY SELECT"], [17, 13, "1 PLAYER"]],
        "one_player": [[17, 13, "1 PLAYER"]],
        "two_players": [[19, 13, "2 PLAYERS"]],
        "player_1": [[8, 12, "PLAYER 1"]],
        "player_2": [[8, 12, "PLAYER 2"]],
        "game_over": [[10, 11, "GAME OVER"]],
        "ending": [[10, 11, "WELL DONE!"]],
        "ending_bonus": [[13, 7, "BONUS 50000 POINTS"]],
        "meter": meter,
    }


def sweep(kind: str, frames: int, volumes: list[int], periods: list[int], noise: int = 0) -> list:
    return [[kind, frames, v, p, noise] for v, p in zip(volumes, periods)]


def decay(top: int, steps: int) -> list[int]:
    return [max(top - k * top // steps, 3) for k in range(steps)]


def sounds() -> dict[str, object]:
    def one(steps: list) -> list:
        return [steps]

    def noise(frames: int, top: int, steps: int, first: int, last: int) -> list:
        return [["noise", frames, v, 0, first + (last - first) * k // max(steps - 1, 1)]
                for k, v in enumerate(decay(top, steps))]
    boom = noise(2, 15, 10, 8, 30)
    return {
        "pause_periods": [0x30, 0x40, 0x50, 0x60],
        "sounds": {
            "0x01": one(sweep("tone", 1, [12, 11, 9, 7], [0x050, 0x070, 0x090, 0x0B0])),
            "0x02": one(sweep("tone", 1, [11, 9, 7], [0x060, 0x080, 0x0A0])),
            "0x03": one(sweep("tone", 1, [13, 12, 11, 10, 8, 6], [0x120, 0x0E0, 0x0B0, 0x090, 0x070, 0x050])),
            "0x05": one(noise(1, 13, 4, 2, 8)),
            "0x06": one(noise(1, 12, 3, 4, 10)),
            "0x08": one(noise(2, 13, 6, 10, 20)),
            "0x09": one(noise(2, 12, 6, 16, 26)),
            "0x0a": one(sweep("both", 2, decay(14, 6), [0x300, 0x340, 0x380, 0x3C0, 0x400, 0x440], 12)),
            "0x0d": one(sweep("tone", 1, [14, 12, 14, 10], [0x040, 0x030, 0x040, 0x030])),
            "0x0e": one(boom),
            "0x0f": one(noise(2, 14, 8, 12, 26)),
            "0x10": one(sweep("tone", 2, [12, 12, 12, 10], [0x0D6, 0x0AA, 0x08F, 0x06B])),
            "0x11": one(sweep("tone", 3, [13, 13, 13, 13, 10], [0x11D, 0x0E2, 0x0BE, 0x08F, 0x08F])),
            "0x12": one(sweep("tone", 2, [12, 12, 10], [0x0BE, 0x08F, 0x06B])),
            "0x13": one(noise(4, 13, 8, 20, 31)),
            "0x14": one(sweep("tone", 2, [13, 13, 13, 11, 8], [0x1AC, 0x153, 0x11D, 0x0D6, 0x0D6])),
            "0x15": one(sweep("tone", 4, [13, 13, 13, 13, 13, 9], [0x1AC, 0x11D, 0x0D6, 0x11D, 0x0D6, 0x0D6])),
            "0x32": [noise(6, 14, 12, 20, 31), sweep("tone", 6, decay(12, 12), [0x800 + 0x40 * k for k in range(12)]),
                     noise(6, 13, 12, 24, 31)],
            "0x3b": [noise(4, 15, 16, 10, 31), sweep("tone", 4, decay(13, 16), [0x400 + 0x80 * k for k in range(16)]),
                     noise(4, 15, 16, 16, 31)],
            "0x41": [sweep("tone", 2, [10] * 6, [0x200 - 0x40 * k for k in range(6)]),
                     sweep("tone", 2, [8] * 6, [0x210 - 0x40 * k for k in range(6)]),
                     noise(2, 9, 6, 4, 10)],
            "0x47": [sweep("tone", 3, decay(14, 12), [0x080 + 0x40 * k for k in range(12)]),
                     noise(3, 15, 12, 8, 31),
                     sweep("tone", 3, decay(12, 12), [0x0C0 + 0x60 * k for k in range(12)])],
        },
    }


# -- the title ------------------------------------------------------------------------------------

def title(rng: random.Random) -> Picture:
    picture = Picture(256, 192)
    c = Canvas(picture, 0, 0, 256, 192)
    for _ in range(60):
        x, y = rng.randrange(256), rng.randrange(192)
        if y < 16 or 168 <= y < 176 or y >= 184:
            c.set(x, y, (WHITE, GREY, LIGHT_BLUE)[(x // 8 + y // 8) % 3])
    word = "NEMESIO"
    scale = 4
    x0 = (256 - len(word) * 6 * scale) // 2 + scale
    for n, letter in enumerate(word):
        rows = glyph(letter)

        def on(r: int, col: int) -> bool:
            return 0 <= r < len(rows) and 0 <= col < len(rows[r]) and rows[r][col] == "#"
        for r, row in enumerate(rows):
            for col, bit in enumerate(row):
                if bit != "#":
                    continue
                # A block with its corners cut where nothing is next to them nor
                # across the corner:
                # the letters as facets. Lit on top, in shadow below.
                colour = CYAN if r == 0 else LIGHT_BLUE if r < 3 else DARK_BLUE
                x, y = x0 + (n * 6 + col) * scale, 24 + r * scale
                cut = scale / 2
                tl = not (on(r - 1, col) or on(r, col - 1) or on(r - 1, col - 1))
                tr = not (on(r - 1, col) or on(r, col + 1) or on(r - 1, col + 1))
                bl = not (on(r + 1, col) or on(r, col - 1) or on(r + 1, col - 1))
                br = not (on(r + 1, col) or on(r, col + 1) or on(r + 1, col + 1))
                c.polygon([(x + (cut if tl else 0), y), (x + scale - (cut if tr else 0), y),
                           (x + scale, y + (cut if tr else 0)), (x + scale, y + scale - (cut if br else 0)),
                           (x + scale - (cut if br else 0), y + scale), (x + (cut if bl else 0), y + scale),
                           (x, y + scale - (cut if bl else 0)), (x, y + (cut if tl else 0))], colour)
    # The ship: its upper face lit, its lower in shadow, a flame behind.
    c.polygon([(40, 78), (72, 88), (48, 88)], WHITE)
    c.polygon([(48, 88), (72, 88), (40, 98)], GREY)
    c.polygon([(32, 86), (40, 88), (32, 90)], LIGHT_RED)
    return picture


