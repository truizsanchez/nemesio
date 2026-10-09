"""What every stage has, at the same numbers in every stage's pictures: the
font and the band, the terrain, the hatches, the bricks, the shots and the
stars, the cannons, fliers, bugs and capsules, the blasts, the ship and its
explosion, the options, the walkers; the layout the rules draw with, and
the tables the stages share."""

import math

from game.engine.objects import BOMB, CAPSULE
from game.free.png import Picture
from tools.free_assets.draw import (
    cube, ngon, BLACK, CLEAR, CYAN, DARK_BLUE, DARK_RED, DARK_YELLOW, GREEN, GREY, LIGHT_BLUE,
    LIGHT_GREEN, LIGHT_RED, LIGHT_YELLOW, MAGENTA, RED, WHITE, DARK_GREEN, Canvas, Chars, Sheet,
    Painter, Sprites, STAGE_DRAWINGS, STAGE_PATTERNS, STAGE_SOLID,
)

def paint_font(chars: Chars) -> dict[str, dict[str, str]]:
    """The letters over the view (thirds 0 and 1) and the band's (third 2)."""
    view: dict[str, str] = {}

    def letter(char: int, text: str, colour: int = WHITE, back: int = CLEAR,
               thirds: tuple[int, ...] = (0, 1)) -> None:
        def paint(c: Canvas) -> None:
            c.fill(back)
            c.text(1, 0, text, colour)
        chars.draw(char, "letter %s" % text, paint, thirds)

    for n in range(10):
        letter(0x10 + n, str(n))
        view[str(n)] = hex(0x10 + n)
    letter(0x1A, "-")
    view["-"] = "0x1a"
    # The title's cursor: a ship across two characters.
    ship = Picture(16, 8)
    Canvas(ship, 0, 0, 16, 8).polygon([(1, 1), (14, 4), (1, 7)], WHITE)
    Canvas(ship, 0, 0, 16, 8).rect(0, 3, 4, 2, LIGHT_RED)
    for n, char in enumerate((0x1B, 0x1C)):
        def paint(c: Canvas, n: int = n) -> None:
            for y in range(8):
                for x in range(8):
                    c.set(x, y, ship[n * 8 + x, y])
        chars.draw(char, "cursor", paint, (0, 1))
    letter(0x1D, ".")
    view["."] = "0x1d"
    letter(0x1E, "!")
    view["!"] = "0x1e"
    letter(0x1F, ":")
    view[":"] = "0x1f"
    for n, text in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        letter(0x21 + n, text)
        view[text] = hex(0x21 + n)

    band: dict[str, str] = {}
    for n in range(10):
        letter(1 + n, str(n), WHITE, BLACK, (2,))
        band[str(n)] = hex(1 + n)

    def lives(c: Canvas) -> None:
        c.fill(BLACK)
        c.polygon([(0, 1), (8, 4), (0, 7)], LIGHT_BLUE)
    chars.draw(0x0B, "band: ship", lives, (2,))
    band["@"] = "0x0b"
    for n, text in enumerate("HIP"):
        letter(0x0C + n, text, LIGHT_YELLOW, BLACK, (2,))
        band[text] = hex(0x0C + n)
    return {"view": view, "band": band}


METER_WORDS = ("SPD ", "MSL ", "DBL ", "LSR ", "OPT ", "SHD ")


def paint_meter(chars: Chars) -> dict[str, object]:
    """The power meter's letters in third 2: plain on dark blue, chosen
    dark on yellow; a taken cell is dashes."""
    letters = sorted(set("".join(METER_WORDS)) | {"-"})
    plain = {text: 0x10 + n for n, text in enumerate(letters)}
    chosen = {text: 0x10 + len(letters) + n for n, text in enumerate(letters)}
    if max(chosen.values()) > 0x42:
        raise SystemExit("the meter's letters do not fit")
    for table, fore, back in ((plain, LIGHT_BLUE, DARK_BLUE), (chosen, DARK_BLUE, LIGHT_YELLOW)):
        for text, char in table.items():
            def paint(c: Canvas, text: str = text, fore: int = fore, back: int = back) -> None:
                c.fill(back)
                if text != " ":
                    c.text(1, 0, text, fore)
            chars.draw(char, "meter %s" % text, paint, (2,))
    cells = [[[hex(plain[t]) for t in word], [hex(chosen[t]) for t in word]]
             for word in METER_WORDS]
    return {"cells": cells, "taken": [[hex(plain["-"])] * 4, [hex(chosen["-"])] * 4]}



# -- solid characters every stage has ------------------------------------------

_SOLID = iter(range(0x43, STAGE_SOLID))


def _solid(count: int) -> tuple[int, ...]:
    return tuple(next(_SOLID) for _ in range(count))


ROCK, TOP, BOTTOM, RISE, FALL, ROOF_DOWN, ROOF_UP = _solid(7)
HATCH_L, HATCH_R, HATCH_CL, HATCH_CR, HATCH_BODY, DOOR, DOOR_C, HATCH_HIT = _solid(8)
#: A block a shot breaks (stage 2's rules and 7's), and the one next to it.
BRICK, BRICK_B = _solid(2)
#: The crystal's shots, drawn with two characters (the layout's pairs 4 and
#: the other): solid, as the ship meets them.
CRYSTAL_SHOT, CRYSTAL_SHOT_OTHER = _solid(2), _solid(2)
assert next(_SOLID, None) is None, "the common solid characters and STAGE_SOLID disagree"

# -- drawings of four characters every stage has ---------------------------------

_DRAWINGS = iter(range(STAGE_DRAWINGS))


def _drawings(count: int) -> tuple[int, ...]:
    return tuple(next(_DRAWINGS) for _ in range(count))


#: The fliers (type 2): four drawings, two of them; the bugs (type 7): eight
#: there and back, three of them; the cannons: six turns each, on the floor
#: and on the roof, three drawn; the capsules and the ship a box gives.
FLIER = _drawings(4)
BUG = _drawings(5)
FLOOR_CANNON, ROOF_CANNON = _drawings(6)[0], _drawings(6)[0]
CAPSULE_D, BOMB_D, SHIP_D = _drawings(3)
_drawings(STAGE_DRAWINGS - 24)

# -- sprite patterns every stage has ------------------------------------------------

_PATTERNS = iter(range(0, STAGE_PATTERNS, 4))


def _patterns(count: int) -> tuple[int, ...]:
    return tuple(next(_PATTERNS) for _ in range(count))


SHIP = _patterns(6)
DOUBLE, MISSILE_ROLL, MISSILE_FALL = _patterns(3)
SHIELDS = _patterns(6)
BLINK = _patterns(1)[0]
OPTION_BIG, OPTION_SMALL = _patterns(2)
BOOM = _patterns(8)
BLAST = _patterns(4)
ENEMY_SHOT = _patterns(1)[0]
#: The walkers (type 5): on the floor and on the roof, walking right (two
#: steps), walking left (two), and standing facing right, then left. A stage
#: with no walkers may draw its own in their place.
WALKERS = {floor: dict(zip(("right", "left", "face"), (_patterns(2), _patterns(2), _patterns(2))))
           for floor in (True, False)}
assert next(_PATTERNS, None) is None, "the common patterns and STAGE_PATTERNS disagree"
#: The layout names these too, for stage 7 only (another stage may draw its
#: own there): the eye's six characters (solid, the last ones) and a type
#: 0x0D leaving (the last pattern). Stage 7 lays out its own short of them.
EYE_CHARS = tuple(range(0x71, 0x77))
LEAVING_0D = 0xFC
#: And for stage 5: a big one's piece, which blinks by bit 2 of its pattern
#: (so this one and the next).
FLOCK_PIECE = 0xF0

ROCK_A, ROCK_B = DARK_GREEN, GREEN
ON = WHITE


# -- painting what every stage has ----------------------------------------------------

def paint_terrain(chars: Chars, fill: int = ROCK_A, speck: int = ROCK_B, edge: int = LIGHT_GREEN) -> None:
    """The ground and the roof, in a stage's colours, as facets: the rock a
    low pyramid (its faces to the light in `speck`, the others in `fill`),
    the ground's top and the slopes towards the sky lit (`edge`), the roof's
    underside in shadow."""
    def rock(c: Canvas) -> None:
        c.facets([([(0, 0), (8, 0), (5, 3)], speck), ([(0, 0), (5, 3), (0, 8)], speck),
                  ([(8, 0), (8, 8), (5, 3)], fill), ([(0, 8), (5, 3), (8, 8)], fill)])

    def top(c: Canvas) -> None:
        c.facets([([(0, 3), (8, 2), (8, 8)], speck), ([(0, 3), (8, 8), (0, 8)], fill),
                  ([(0, 0), (8, 0), (8, 2), (0, 3)], edge)])

    def bottom(c: Canvas) -> None:
        c.facets([([(0, 0), (8, 0), (0, 5)], speck), ([(8, 0), (8, 6), (0, 5)], fill),
                  ([(0, 5), (8, 6), (8, 8), (0, 8)], speck)])

    def slope(c: Canvas, points: list[tuple[float, float]], lit: bool) -> None:
        c.polygon(points, speck)
        if lit:
            c.rect(0, 0, 8, 3, CLEAR)
            c.polygon(points, speck)
            for y in range(3):
                for x in range(8):
                    if c.p[c.x0 + x, c.y0 + y] != CLEAR:
                        c.set(x, y, edge)
        else:
            for y in range(4):
                for x in range(8):
                    if c.p[c.x0 + x, c.y0 + y] != CLEAR:
                        c.set(x, y, fill)
    chars.draw(ROCK, "rock", rock)
    chars.draw(TOP, "ground's top", top)
    chars.draw(BOTTOM, "roof's edge", bottom)
    chars.draw(RISE, "slope up", lambda c: slope(c, [(8, 0), (8, 8), (0, 8)], True))
    chars.draw(FALL, "slope down", lambda c: slope(c, [(0, 0), (8, 8), (0, 8)], True))
    chars.draw(ROOF_DOWN, "roof coming down", lambda c: slope(c, [(0, 0), (8, 0), (8, 8)], False))
    chars.draw(ROOF_UP, "roof going up", lambda c: slope(c, [(0, 0), (8, 0), (0, 8)], False))

    def brick(c: Canvas, shift: int) -> None:
        # Bevelled blocks: a lit top row, a body, dark joints.
        c.fill(DARK_YELLOW)
        for y in (0, 4):
            c.rect(0, y, 8, 1, LIGHT_YELLOW)
        for y in (3, 7):
            c.rect(0, y, 8, 1, BLACK)
        for y0, x in ((0, 3 + shift), (4, (7 + shift) % 8)):
            c.rect(x, y0, 1, 3, BLACK)
    chars.draw(BRICK, "brick (breaks)", lambda c: brick(c, 0))
    chars.draw(BRICK_B, "brick (breaks)", lambda c: brick(c, 4))


def paint_hatches(chars: Chars) -> None:
    """The hatches: an octagon's half for a dome, lit on its upper rows."""
    def dome(c: Canvas, left: bool, up: bool) -> None:
        cx, cy = (8 if left else 0), (8 if up else 0)
        c.polygon(ngon(cx, cy, 8.5, 8, math.pi / 8), GREY)
        for y in range(8):
            lit = (y < 4) if up else (y < 2)
            if lit:
                for x in range(8):
                    if c.p[c.x0 + x, c.y0 + y] == GREY:
                        c.set(x, y, WHITE)
    chars.draw(HATCH_L, "hatch, dome left", lambda c: dome(c, True, True))
    chars.draw(HATCH_R, "hatch, dome right", lambda c: dome(c, False, True))
    chars.draw(HATCH_CL, "roof hatch, dome left", lambda c: dome(c, True, False))
    chars.draw(HATCH_CR, "roof hatch, dome right", lambda c: dome(c, False, False))
    chars.draw(HATCH_BODY, "hatch's body", lambda c: (c.fill(GREY), c.rect(0, 0, 8, 1, WHITE),
                                                      c.rect(0, 3, 8, 2, DARK_BLUE)))
    chars.draw(DOOR, "hatch's door", lambda c: (c.fill(GREY), c.polygon([(1, 8), (1, 4), (4, 2), (7, 4), (7, 8)], BLACK)))
    chars.draw(DOOR_C, "roof hatch's door", lambda c: (c.fill(GREY), c.polygon([(1, 0), (1, 4), (4, 6), (7, 4), (7, 0)], BLACK)))
    chars.draw(HATCH_HIT, "hatch, shot", lambda c: (c.fill(GREY), c.polygon([(0, 0), (3, 4), (0, 8)], DARK_RED),
                                                   c.polygon([(8, 0), (5, 4), (8, 8)], DARK_RED),
                                                   c.polygon([(1, 0), (7, 0), (4, 3)], RED),
                                                   c.polygon([(1, 8), (7, 8), (4, 5)], RED)))


def hatch_drawings() -> list[list[int]]:
    """The hatches' 4x4 drawings: on the floor, shot; on the roof, shot;
    sixteen of them, as stage 2's rules read them twelve further on."""
    floor = [0, HATCH_L, HATCH_R, 0,
             HATCH_L, DOOR, DOOR, HATCH_R,
             HATCH_BODY, HATCH_BODY, HATCH_BODY, HATCH_BODY,
             ROCK, ROCK, ROCK, ROCK]
    floor_hit = [HATCH_HIT if ch == DOOR else ch for ch in floor]
    roof = [ROCK, ROCK, ROCK, ROCK,
            HATCH_BODY, HATCH_BODY, HATCH_BODY, HATCH_BODY,
            HATCH_CL, DOOR_C, DOOR_C, HATCH_CR,
            0, HATCH_CL, HATCH_CR, 0]
    roof_hit = [HATCH_HIT if ch == DOOR_C else ch for ch in roof]
    return ([floor, floor_hit, roof, roof_hit] * 4)[:16]


def paint_crystal_shots(chars: Chars) -> None:
    """The launchers' missiles in flight: the nose (cyan, as on the
    launcher) and the tube with its flame, yellow or red."""
    def nose(c: Canvas) -> None:
        c.polygon([(0, 4), (8, 2), (8, 6)], CYAN)
        c.rect(4, 4, 4, 2, LIGHT_BLUE)

    def tube(c: Canvas, flame: int) -> None:
        c.rect(0, 2, 5, 2, CYAN)
        c.rect(0, 4, 5, 2, LIGHT_BLUE)
        c.polygon([(5, 2), (8, 4), (5, 6)], flame)
    for first, flame in ((CRYSTAL_SHOT[0], LIGHT_YELLOW), (CRYSTAL_SHOT_OTHER[0], LIGHT_RED)):
        chars.draw(first, "crystal's shot, left", nose)
        chars.draw(first + 1, "crystal's shot, right", lambda c, flame=flame: tube(c, flame))


def paint_sky(chars: Chars) -> dict[str, object]:
    """The characters the rules name, and so the layout's: the stars, the
    shot's four and the laser's (a row of two pixels, where in the cell the
    shooter's row falls), the enemy shots drawn as pairs."""
    stars = chars.scenery(2)
    for star in stars:
        chars.draw(star, "star", lambda c: c.set(3, 0, WHITE))
    shot, laser = chars.scenery(4, together=True), chars.scenery(4, together=True)
    for n in range(4):
        chars.draw(shot[n], "shot", lambda c, n=n: c.rect(0, 2 * n, 8, 2, LIGHT_YELLOW))
        chars.draw(laser[n], "laser", lambda c, n=n: c.rect(0, 2 * n, 8, 2, CYAN))
    pairs = {}
    for kind, colour in ((2, LIGHT_YELLOW), (3, CYAN)):
        first, second = chars.scenery(2, together=True)
        chars.draw(first, "enemy shot, drawn", lambda c, colour=colour: c.rect(2, 3, 6, 2, colour))
        chars.draw(second, "enemy shot, drawn", lambda c, colour=colour: c.rect(0, 3, 8, 2, colour))
        pairs[kind] = first
    pairs[4] = CRYSTAL_SHOT[0]
    return {"stars": stars, "shot_character": shot[0], "laser_character": laser[0],
            "pairs": pairs, "pair_other": CRYSTAL_SHOT_OTHER[0]}


def paint_decor(chars: Chars, kind: str, colours: tuple[int, int, int]) -> dict[str, int]:
    """The scenery a stage's plan grows (tools/free_assets/maps.py, DECOR),
    in its colours (dark, mid, light): on the ground "Y" and "y", under the
    roof "U" and "u" (the same, upside down), or in the sky "h" and "H".
    Named for the map. Over the sky a row keeps one colour: facets in bands."""
    dark, mid, light = colours

    def flip(painter: Painter) -> Painter:
        def upside_down(c: Canvas) -> None:
            painter(c)
            rows = [[c.p[c.x0 + x, c.y0 + y] for x in range(8)] for y in range(8)]
            for y in range(8):
                for x in range(8):
                    c.set(x, y, rows[7 - y][x])
        return upside_down

    def pine(tall: bool) -> Painter:
        def draw(c: Canvas) -> None:
            # Tiers of a fir, the upper lit; a stub of trunk.
            top = 0 if tall else 2
            c.polygon([(4, top), (8.5, 7), (-0.5, 7)], mid)
            c.polygon([(4, top), (6.5, top + 3.5), (1.5, top + 3.5)], light)
            c.rect(3, 7, 2, 1, dark)
        return draw

    def shard(tall: bool) -> Painter:
        def draw(c: Canvas) -> None:
            # Two crystals leaning, their tips lit.
            h = 0 if tall else 3
            c.polygon([(1, 8), (3, h), (5, 8)], mid)
            c.polygon([(4, 8), (7, h + 3), (8, 8)], mid)
            for y in range(8):
                if y < h + 3:
                    for x in range(8):
                        if c.p[c.x0 + x, c.y0 + y] == mid:
                            c.set(x, y, light)
        return draw

    def tendril(tall: bool) -> Painter:
        def draw(c: Canvas) -> None:
            # A hooked spine of three segments, bending.
            if tall:
                c.polygon([(2, 8), (4, 8), (4, 4), (7, 1), (5, 1), (2, 4)], light)
            else:
                c.polygon([(3, 8), (5, 8), (6, 5), (3, 3), (4, 5)], mid)
        return draw

    painters: dict[str, tuple[Painter, Painter]] = {
        "groves": (pine(True), pine(False)), "shards": (shard(True), shard(False)),
        "tendrils": (tendril(True), tendril(False)),
    }
    names = {"groves": "tree", "shards": "crystal", "tendrils": "tendril"}
    if kind in painters:
        tall, short = painters[kind]
        out = {}
        for letter, painter, name in (("Y", tall, "%s"), ("y", short, "%s, small"),
                                      ("U", flip(tall), "%s, hanging"),
                                      ("u", flip(short), "%s, small, hanging")):
            out[letter] = chars.scenery(1)[0]
            chars.draw(out[letter], name % names[kind], painter)
        return out
    one, other = chars.scenery(2)
    if kind == "lattice":
        # A net of diamonds, far behind.
        chars.draw(one, "lattice", lambda c: (c.line(0, 4, 4, 0, dark), c.line(4, 0, 7, 3, dark),
                                              c.line(7, 4, 4, 7, dark), c.line(3, 7, 0, 4, dark)))
        chars.draw(other, "lattice", lambda c: c.polygon(ngon(4, 4, 2, 4), dark))
    elif kind == "bubbles":
        chars.draw(one, "bubble", lambda c: (c.polygon(ngon(4, 4, 4, 6), dark),
                                             c.polygon(ngon(4, 4, 2.6, 6), CLEAR),
                                             c.polygon([(2, 1), (4, 1), (2, 3)], mid)))
        chars.draw(other, "bubble, small", lambda c: (c.polygon(ngon(3, 5, 2.5, 6), dark),
                                                      c.polygon(ngon(3, 5, 1.2, 6), CLEAR)))
    else:
        # Lights far off: pairs of dots, and a warning one.
        chars.draw(one, "lights", lambda c: (c.rect(0, 3, 2, 1, mid), c.rect(5, 3, 2, 1, mid)))
        chars.draw(other, "light", lambda c: (c.rect(3, 2, 2, 1, light), c.rect(3, 5, 2, 1, light)))
    return {"h": one, "H": other}


BLUES, REDS, MAGENTAS = ((DARK_BLUE, LIGHT_BLUE, CYAN), (DARK_RED, RED, LIGHT_RED),
                         (DARK_RED, MAGENTA, LIGHT_RED))


def paint_objects(sheet: Sheet) -> None:
    """The objects drawn with characters every stage has, as the numbers
    above: few different cells, so the stages keep characters of their own.
    Lit facets; a row of a cell keeps one colour over the sky."""
    for n in range(4):
        angle = (n % 2) * math.pi / 4

        def flier(c: Canvas, angle: float = angle) -> None:
            for k in range(4):
                a = angle + k * math.pi / 2
                c.polygon([(8, 8), (8 + 7.5 * math.cos(a - 0.45), 8 + 7.5 * math.sin(a - 0.45)),
                           (8 + 7.5 * math.cos(a), 8 + 7.5 * math.sin(a)),
                           (8 + 4.5 * math.cos(a + 0.35), 8 + 4.5 * math.sin(a + 0.35))], CYAN)
            c.polygon(ngon(8, 8, 1.8, 4), CLEAR)
            c.quadrants(BLUES)
        sheet.drawing(flier, "flier", FLIER[n])
    for k, n in enumerate(BUG):
        turn = min(k, 2) / 2

        def bug(c: Canvas, turn: float = turn) -> None:
            c.polygon(ngon(8, 8, 7, 8, math.pi / 8), MAGENTA)
            c.quadrants(MAGENTAS)
            w = 6 * (1 - turn) + 1
            c.polygon([(8 - w / 2, 3), (8 + w / 2, 3), (8 + w / 4, 13), (8 - w / 4, 13)], CLEAR)
        sheet.drawing(bug, "bug", n)
    # Six turns from the left (0) round to the right (5), two to a drawing.
    for base, roof in ((FLOOR_CANNON, False), (ROOF_CANNON, True)):
        for turn in range(6):
            a = math.pi - (turn // 2 * 2 + 1) * math.pi / 6

            def cannon(c: Canvas, a: float = a, roof: bool = roof) -> None:
                if roof:
                    c.facets([([(1, 0), (15, 0), (12, 4)], GREY), ([(1, 0), (12, 4), (4, 4)], GREY),
                              ([(4, 4), (12, 4), (10, 7), (6, 7)], DARK_BLUE)])
                    c.line(8, 8, 8 + 6 * math.cos(a), 8 + 6 * math.sin(a), LIGHT_RED, 2)
                else:
                    c.facets([([(6, 9), (10, 9), (12, 12), (4, 12)], WHITE),
                              ([(4, 12), (12, 12), (15, 16), (1, 16)], GREY)])
                    c.line(8, 7, 8 + 6 * math.cos(a), 7 - 6 * math.sin(a), LIGHT_RED, 2)
            sheet.drawing(cannon, "cannon", base + turn)
    for number, ramp in ((CAPSULE_D, REDS), (BOMB_D, BLUES)):
        def capsule(c: Canvas, ramp: tuple[int, ...] = ramp) -> None:
            c.gem(8, 8, 15, 11, ramp)
        sheet.drawing(capsule, "capsule", number)
    sheet.drawing(lambda c: (c.polygon([(1, 3), (15, 8), (1, 13), (5, 8)], CYAN), c.quadrants(BLUES)),
                  "a ship more", SHIP_D)


def paint_blasts(sheet: Sheet) -> list[list[int]]:
    """The background blasts: three 4x4 drawings, small to big, of few
    different cells: a spark, a ring of shards, a burst of them."""
    def small(c: Canvas) -> None:
        c.polygon([(16, 8), (18, 14), (24, 16), (18, 18), (16, 24), (14, 18), (8, 16), (14, 14)], LIGHT_YELLOW)

    def ring(c: Canvas) -> None:
        for k in range(8):
            a = k * math.pi / 4
            c.polygon([(16 + 13 * math.cos(a), 16 + 13 * math.sin(a)),
                       (16 + 8 * math.cos(a - 0.3), 16 + 8 * math.sin(a - 0.3)),
                       (16 + 8 * math.cos(a + 0.3), 16 + 8 * math.sin(a + 0.3))], LIGHT_YELLOW)

    def burst(c: Canvas) -> None:
        for k in range(8):
            a = k * math.pi / 4 + math.pi / 8
            c.polygon([(16 + 15 * math.cos(a), 16 + 15 * math.sin(a)),
                       (16 + 4 * math.cos(a - 0.5), 16 + 4 * math.sin(a - 0.5)),
                       (16 + 4 * math.cos(a + 0.5), 16 + 4 * math.sin(a + 0.5))], DARK_YELLOW)
        c.polygon(ngon(16, 16, 5, 4, math.pi / 4), LIGHT_YELLOW)
    return [sheet.block(p, 4, 4, "blast") for p in (small, ring, burst)]


def paint_sprites(s: Sheet) -> dict[str, object]:
    """The patterns every stage has; returns the layout's sprites."""
    sprites = s.sprites
    tilt = (0, -3, 3)
    bodies, tops = SHIP[0::2], SHIP[1::2]
    for n in range(3):
        t = tilt[n]

        def body(c: Canvas, t: float = t) -> None:
            # A paper dart: swept wings under a body cut along its keel.
            def y(v: float, k: float) -> float:
                return v + t * k
            c.polygon([(0, y(1, -.5)), (10, y(6, .2)), (3, y(7, .1))], ON)
            c.polygon([(0, y(15, .5)), (10, y(10, .2)), (3, y(9, .1))], ON)
            c.mesh([[(1, y(6, 0)), (8, y(5, .1)), (15, y(8, .3)), (1, y(8, .15))],
                    [(1, y(8, .15)), (15, y(8, .3)), (8, y(11, .1)), (1, y(10, 0))]], ON)
        sprites.draw(bodies[n], "ship", body)
        sprites.draw(tops[n], "ship's cockpit and flame", lambda c, t=t: (
            c.polygon([(6, 7 + t / 4), (9, 5.5 + t / 4), (12, 7.5 + t / 3), (9, 9 + t / 4)], ON),
            c.polygon([(0, 6.5 + t / 6), (4, 8 + t / 6), (0, 10 + t / 6)], ON)))
    sprites.draw(DOUBLE, "double", lambda c: c.polygon([(1, 14), (12, 2), (14, 4), (3, 15)], ON))
    sprites.draw(MISSILE_ROLL, "missile, rolling",
                 lambda c: c.mesh([[(2, 6), (11, 6), (11, 10), (2, 10)], [(11, 6), (15, 8), (11, 10)]], ON))
    sprites.draw(MISSILE_FALL, "missile, falling",
                 lambda c: c.mesh([[(3, 3), (7, 1), (12, 9), (8, 11)], [(8, 11), (12, 9), (13, 14)]], ON))
    for k, pattern in enumerate(SHIELDS):
        t, thick = tilt[k % 3], 2 if k < 3 else 1

        def shield(c: Canvas, t: float = t, thick: float = thick) -> None:
            outer = ngon(0, 8 + t / 2, 12.5, 12, math.pi / 12)
            inner = ngon(0, 8 + t / 2, 12.5 - thick - 0.5, 12, math.pi / 12)
            c.polygon(outer, ON)
            c.polygon(inner, CLEAR)
            for x, y in outer[:3] + outer[-3:]:
                c.line(x * 0.8, 8 + t / 2 + (y - 8 - t / 2) * 0.8, x, y, CLEAR)
        sprites.draw(pattern, "shield", shield)
    sprites.draw(BLINK, "ship blinking", lambda c: c.polygon([(0, 6.5), (4, 8), (0, 10)], ON))
    for pattern, r in ((OPTION_BIG, 6.5), (OPTION_SMALL, 5)):
        sprites.draw(pattern, "option", lambda c, r=r: c.mesh(cube(8, 8, r), ON))
    for k, pattern in enumerate(BOOM):
        r = 3 + k % 5

        def boom(c: Canvas, r: float = r, k: int = k) -> None:
            # Shards flying out: triangles pointing away from the middle.
            for j in range(6):
                a = k * 0.5 + j * math.pi / 3
                tip = (8 + (r + 2) * math.cos(a), 8 + (r + 2) * math.sin(a))
                side = (8 + r * 0.5 * math.cos(a - 0.5), 8 + r * 0.5 * math.sin(a - 0.5))
                other = (8 + r * 0.5 * math.cos(a + 0.5), 8 + r * 0.5 * math.sin(a + 0.5))
                c.polygon([side, tip, other], ON)
        sprites.draw(pattern, "ship blowing up", boom)
    for k, pattern in enumerate(BLAST):
        def blast(c: Canvas, k: int = k) -> None:
            r = 3 + 1.5 * k
            c.polygon(ngon(8, 8, r + 1, 8, k * 0.3), ON)
            c.polygon(ngon(8, 8, max(r - 1.5, 0), 4, k * 0.3 + math.pi / 4), CLEAR)
            if k < 2:
                c.polygon(ngon(8, 8, max(2.5 - k, 1), 4, math.pi / 4), ON)
        sprites.draw(pattern, "blast", blast)
    sprites.draw(ENEMY_SHOT, "enemy shot", lambda c: c.polygon(ngon(8, 8, 2.6, 4), ON))
    faces = {floor: list(kinds["face"]) for floor, kinds in WALKERS.items()}
    return {
        "ship": [[[bodies[n], WHITE], [tops[n], LIGHT_RED]] for n in range(3)],
        "explosion": [[[BOOM[0], LIGHT_YELLOW], [BOOM[1], RED]],
                      [[BOOM[2], LIGHT_YELLOW], [BOOM[3], DARK_RED]],
                      [[BOOM[4], GREY], [BOOM[5], DARK_RED]],
                      [[BOOM[0], LIGHT_YELLOW], [BOOM[1], RED]]],
        "explosion_parts": [[[0, BOOM[6], WHITE], [0, BOOM[6], WHITE]],
                            [[0xF8, BOOM[7], RED], [0x08, BOOM[7], RED]],
                            [[0xF4, BOOM[7], DARK_RED], [0x0C, BOOM[7], DARK_RED]],
                            [[0, BOOM[6], WHITE], [0, BOOM[6], WHITE]]],
        "double": [DOUBLE, WHITE],
        "missile": [MISSILE_ROLL, MISSILE_FALL, DARK_YELLOW],
        "options": [[OPTION_BIG, LIGHT_RED], [OPTION_BIG, RED], [OPTION_SMALL, DARK_RED],
                    [OPTION_SMALL, RED]],
        "enemy_shot": [ENEMY_SHOT, LIGHT_RED],
        "walker_start": {"floor": WALKERS[True]["right"][0], "roof": WALKERS[False]["right"][0]},
        "walker_facing": {"floor": faces[True], "roof": faces[False]},
        "blast_pattern": BLAST[0],
        # Stage 7's blasts and the bonus stages' prizes: the plain blast.
        "blast_0d_pattern": BLAST[0],
        "float_pattern": BLAST[0],
        "leaving_0d": LEAVING_0D,
        "flock_piece": FLOCK_PIECE,
        "eye_open": list(EYE_CHARS[0:2]), "eye_shut": list(EYE_CHARS[2:4]),
        "eye_dead": list(EYE_CHARS[4:6]),
        "bug_drawings": list(BUG) + list(BUG[3:0:-1]),
        "ship_drawing": SHIP_D,
        "capsule_drawing": CAPSULE_D,
        "capsule_drawings": {hex(CAPSULE): CAPSULE_D, hex(BOMB): BOMB_D},
    }


def paint_walkers(sprites: Sprites) -> None:
    """The walkers, for a stage that has them."""
    for floor, kinds in WALKERS.items():
        for kind, (first, second) in kinds.items():
            for pattern, right, step in ((first, kind != "left", 0 if kind != "face" else 2),
                                         (second, kind == "right", 1 if kind != "face" else 2)):
                def walker(c: Canvas, floor: bool = floor, right: bool = right, step: int = step) -> None:
                    # A faceted pod on two angled legs, its visor to the way it faces.
                    top, bottom = (3, 11) if floor else (5, 13)

                    def x_(x: float) -> float:
                        return x if right else 15 - x
                    c.polygon([(x_(1), bottom - 1), (x_(3), top + 1), (x_(8), top), (x_(15), top + 4),
                               (x_(13), bottom)], ON)
                    c.polygon([(x_(9), top + 2), (x_(14), top + 4), (x_(9), top + 4)], CLEAR)
                    legs = (3, 11) if step == 0 else (5, 9) if step == 1 else (4, 10)
                    for x in legs:
                        if floor:
                            c.polygon([(x, 11), (x + 2, 11), (x + 3, 16), (x - 1, 16)], ON)
                        else:
                            c.polygon([(x - 1, 0), (x + 3, 0), (x + 2, 5), (x, 5)], ON)
                sprites.draw(pattern, "walker, %s" % ("floor" if floor else "roof"), walker)


def walker_animation() -> list[int]:
    """Walking, two drawings each (0xAB58's order): on the roof right, left,
    then on the floor right, left."""
    return [p for floor in (False, True) for kind in ("right", "left") for p in WALKERS[floor][kind]]


class Common:
    """What painting the common part of a sheet gave: the font, the meter,
    the layout, the blasts and the map's scenery legend."""

    def __init__(self, sheet: Sheet, terrain: tuple[int, int, int] = (ROCK_A, ROCK_B, LIGHT_GREEN),
                 decor: str = "groves", decor_colours: tuple[int, int, int] = (DARK_YELLOW, GREEN, LIGHT_GREEN)) -> None:
        chars = sheet.chars
        self.layout = paint_sky(chars)
        self.font = paint_font(chars)
        self.meter = paint_meter(chars)
        paint_terrain(chars, *terrain)
        paint_hatches(chars)
        paint_crystal_shots(chars)
        paint_objects(sheet)
        self.blasts = paint_blasts(sheet)
        # After what the shared tables name, which must be at the same
        # numbers in every stage: the decor takes more or fewer characters.
        self.scenery = paint_decor(chars, decor, decor_colours)
        self.layout.update(paint_sprites(sheet))
        stars = self.layout["stars"]
        assert isinstance(stars, list)
        self.scenery.update({"*": stars[0], "+": stars[1]})
        self.legend = {"#": ROCK, "^": TOP, "v": BOTTOM, "/": RISE, "\\": FALL, "q": ROOF_DOWN,
                       "p": ROOF_UP, "b": BRICK, "B": BRICK_B}
