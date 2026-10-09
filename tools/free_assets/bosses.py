"""What more than one stage has at its end: the core (stages 1-4) and the
crystal (stages 1 and 4), drawn into a stage's own solid characters."""

from game.engine.ending import BODY_H, BODY_W
from tools.free_assets.draw import (
    BLACK, CYAN, DARK_BLUE, DARK_RED, LIGHT_BLUE, LIGHT_YELLOW, RED, Canvas,
    Sheet, ngon,
)


def paint_crystal(sheet: Sheet) -> dict[str, object]:
    """Five launchers anchored to the rock the map has behind them (two
    halves: a missile's nose and its tube's mount; the middle one a pair of
    them, four characters), and their blast: the ending's crystal_chars and
    crystal_blast."""
    left, right = sheet.solid(2)
    blues = (DARK_BLUE, LIGHT_BLUE, CYAN)

    def nose(c: Canvas) -> None:
        # The missile's cone, lit from the top left, pointing where it flies.
        c.lit([[(0, 4), (8, 1), (8, 4)], [(0, 4), (8, 4), (8, 7)]], blues)

    def mount(c: Canvas) -> None:
        # The tube going into the rock, with a collar where it leaves it.
        c.rect(0, 1, 8, 6, LIGHT_BLUE)
        c.rect(0, 1, 8, 2, CYAN)
        c.rect(0, 5, 8, 2, DARK_BLUE)
        c.rect(5, 0, 3, 8, DARK_RED)
        c.rect(5, 0, 1, 8, RED)
    sheet.chars.draw(left, "launcher, missile", nose)
    sheet.chars.draw(right, "launcher, mount", mount)

    def middle(c: Canvas) -> None:
        # Two missiles on one wide mount.
        for y in (1, 9):
            c.lit([[(0, y + 3), (8, y), (8, y + 3)], [(0, y + 3), (8, y + 3), (8, y + 6)]], blues)
            c.rect(8, y, 8, 6, LIGHT_BLUE)
            c.rect(8, y, 8, 2, CYAN)
            c.rect(8, y + 4, 8, 2, DARK_BLUE)
        c.rect(12, 0, 4, 16, DARK_RED)
        c.rect(12, 0, 1, 16, RED)
    four = sheet.block(middle, 2, 2, "launcher, double", sheet.solid(4))
    blast = sheet.solid(2)
    sheet.chars.draw(blast[0], "launcher blown up 1", lambda c: c.polygon(
        [(4, 0), (5, 3), (8, 4), (5, 5), (4, 8), (3, 5), (0, 4), (3, 3)], LIGHT_YELLOW))
    sheet.chars.draw(blast[1], "launcher blown up 2", lambda c: c.polygon(ngon(4, 4, 3.5, 4), RED))
    two = [hex(left), hex(right)]
    return {"crystal_chars": [two, two, [hex(c) for c in four], two, two],
            "crystal_blast": [hex(blast[0]), hex(blast[1]), hex(blast[0]), hex(blast[1])]}


def paint_core(sheet: Sheet, hurt: tuple[int, int] | None = None) -> dict[str, list[str]]:
    """The core: an 11x8 body of edges and fill, a 3x2 eye (six drawings,
    worst to whole) and a 3x2 mouth (open, shut, broken); `hurt`, two
    characters the hurt eye and the broken mouth show (a blast's, say), or
    two of its own."""
    fill_, top, bottom, left, right, tl, tr, bl, br = sheet.solid(9)
    chars = sheet.chars
    # Armour plates: low pyramids in two blues, bevelled edges lit on top.
    chars.draw(fill_, "core", lambda c: c.facets([
        ([(0, 0), (8, 0), (4, 4)], LIGHT_BLUE), ([(0, 0), (4, 4), (0, 8)], LIGHT_BLUE),
        ([(8, 0), (8, 8), (4, 4)], DARK_BLUE), ([(0, 8), (4, 4), (8, 8)], DARK_BLUE)]))
    for char, side, lit in ((top, [(0, 0), (8, 0), (8, 3), (0, 3)], CYAN),
                            (bottom, [(0, 5), (8, 5), (8, 8), (0, 8)], DARK_BLUE),
                            (left, [(0, 0), (3, 0), (3, 8), (0, 8)], CYAN),
                            (right, [(5, 0), (8, 0), (8, 8), (5, 8)], DARK_BLUE)):
        chars.draw(char, "core's edge", lambda c, side=side, lit=lit: (
            c.fill(LIGHT_BLUE), c.polygon(side, lit)))
    for char, pts, lit in ((tl, [(8, 0), (8, 8), (0, 8)], CYAN), (tr, [(0, 0), (8, 8), (0, 8)], CYAN),
                           (bl, [(0, 0), (8, 0), (8, 8)], LIGHT_BLUE), (br, [(0, 0), (8, 0), (0, 8)], DARK_BLUE)):
        chars.draw(char, "core's corner", lambda c, pts=pts, lit=lit: c.polygon(pts, lit))

    def eye_(c: Canvas) -> None:
        # A cut lens: its upper faces lit, its lower in shadow, a dark pupil.
        c.fill(DARK_BLUE)
        c.polygon(ngon(12, 8, 10, 6, 0, 0.8), LIGHT_BLUE)
        c.polygon([(2, 8), (7, 1.1), (17, 1.1), (22, 8)], CYAN)
        c.polygon(ngon(12, 8, 4.5, 6, 0), DARK_BLUE)
    eye = sheet.block(eye_, 3, 2, "core's eye", sheet.solid(6))
    mouth = sheet.block(lambda c: (c.fill(DARK_BLUE),
                                   c.polygon([(2, 3), (22, 3), (19, 13), (5, 13)], BLACK),
                                   c.polygon([(2, 3), (22, 3), (21, 5), (3, 5)], LIGHT_BLUE)), 3, 2,
                        "core's mouth, open", sheet.solid(6))
    if hurt is None:
        h1, h2 = sheet.solid(2)
        chars.draw(h1, "core hurt", lambda c: c.circle(4, 4, 4, LIGHT_YELLOW, 1.5))
        chars.draw(h2, "core hurt", lambda c: c.circle(4, 4, 3, RED))
    else:
        h1, h2 = hurt
    f = fill_
    rows = [
        [0, 0, tl, top, top, top, top, top, top, tr, 0],
        [0, tl, f, f, f, f, f, f, f, f, tr],
        [left] + [f] * 9 + [right],
        [left] + [f] * 9 + [right],
        [left] + [f] * 9 + [right],
        [left] + [f] * 9 + [right],
        [0, bl, f, f, f, f, f, f, f, f, br],
        [0, 0, bl, bottom, bottom, bottom, bottom, bottom, bottom, br, 0],
    ]
    assert len(rows) == BODY_H and all(len(r) == BODY_W for r in rows)
    hurt_eye = [eye[0], h1, eye[2], eye[3], h2, eye[5]]
    worst = [h2, h1, h2, h1, h2, h1]
    eyes = worst + hurt_eye + hurt_eye + eye * 3
    shut = [f, top, f, f, bottom, f]
    broken = [h2, f, h2, f, h2, f]
    return {"body": [hex(c) for row in rows for c in row], "eyes": [hex(c) for c in eyes],
            "mouths": [hex(c) for c in mouth + shut + broken]}

