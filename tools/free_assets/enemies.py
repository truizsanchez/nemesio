"""Enemies more than one stage has, drawn into a stage's own sprite
patterns: each paints its drawings and returns their patterns."""

import math

from tools.free_assets.common import ON
from tools.free_assets.draw import CLEAR, Canvas, Sheet, cube, fan, ngon


def spinner(sheet: Sheet) -> tuple[int, ...]:
    """A pyramid turning (seen from above: four faces), five drawings (type 3)."""
    out = sheet.patterns(5)
    for k, pattern in enumerate(out):
        a = k * math.pi / 10
        sheet.sprites.draw(pattern, "spinner", lambda c, a=a: c.mesh(
            fan((8, 8), ngon(8, 8, 7.5, 4, a)), ON))
    return out


def dart(sheet: Sheet) -> tuple[int, ...]:
    """An arrowhead, cut along its spine, three drawings (type 4)."""
    out = sheet.patterns(3)
    for k, pattern in enumerate(out):
        sheet.sprites.draw(pattern, "dart", lambda c, k=k: c.mesh(
            [[(1, 8), (14, 2 + k), (10, 8)], [(1, 8), (10, 8), (14, 14 - k)]], ON))
    return out


def jumper(sheet: Sheet) -> tuple[int, ...]:
    """A faceted ball on legs, squashing, four drawings (type 6)."""
    out = sheet.patterns(4)
    for k, pattern in enumerate(out):
        q = (0, 1.5, 3, 1.5)[k]
        sheet.sprites.draw(pattern, "jumper", lambda c, q=q: (
            c.mesh([[(x, 7 + q / 2 + (y - 7) * (1 - q / 8)) for x, y in face] for face in cube(8, 7, 6.5)], ON),
            c.polygon([(3, 12), (5, 12), (4, 16), (1, 16)], ON),
            c.polygon([(11, 12), (13, 12), (15, 16), (12, 16)], ON)))
    return out


def drone(sheet: Sheet) -> tuple[int, ...]:
    """A cube with flapping triangle wings, four drawings (types 9, 0x0A...)."""
    out = sheet.patterns(4)
    for k, pattern in enumerate(out):
        def draw(c: Canvas, k: int = k) -> None:
            c.mesh(cube(8, 8, 5.5), ON)
            lift = (3, 0, -3, 0)[k]
            for x0, x1 in ((3, 0), (13, 16)):
                c.polygon([(x0, 7), (x1, 7 - lift - 3), (x1, 9 - lift)], ON)
        sheet.sprites.draw(pattern, "drone", draw)
    return out


def rock(sheet: Sheet) -> int:
    """A lump of facets (type 0x0F, the eruption's)."""
    pattern = sheet.patterns(1)[0]
    sheet.sprites.draw(pattern, "rock", lambda c: c.mesh(
        [[(3, 2), (10, 1), (15, 6), (8, 8)], [(15, 6), (13, 13), (6, 15), (8, 8)],
         [(6, 15), (1, 10), (3, 2), (8, 8)]], ON))
    return pattern


def stone(sheet: Sheet) -> tuple[int, ...]:
    """A hexagon growing, a cube as it grows, three drawings (type 8)."""
    out = sheet.patterns(3)
    for k, pattern in enumerate(out):
        r = 3 + 2 * k
        sheet.sprites.draw(pattern, "stone, growing", lambda c, r=r: c.mesh(cube(8, 8, r), ON)
                           if r > 4 else c.polygon(ngon(8, 8, r, 6, math.pi / 6), ON))
    return out


def ring(sheet: Sheet, count: int = 4) -> tuple[int, ...]:
    """A ring of shards pulsing (count drawings)."""
    out = sheet.patterns(count)
    for k, pattern in enumerate(out):
        def draw(c: Canvas, k: int = k) -> None:
            r = 4.5 + k % 3
            c.polygon(ngon(8, 8, r + 1, 8, k * 0.2), ON)
            c.polygon(ngon(8, 8, r - 1.2, 8, k * 0.2), CLEAR)
            for x, y in ngon(8, 8, r + 1.5, 4, k * 0.2 + math.pi / 8):
                c.line(8 + (x - 8) * 0.6, 8 + (y - 8) * 0.6, x, y, CLEAR)
        sheet.sprites.draw(pattern, "ring", draw)
    return out


def spark(sheet: Sheet, count: int = 4) -> tuple[int, ...]:
    """A star of thin triangles turning (count drawings)."""
    out = sheet.patterns(count)
    for k, pattern in enumerate(out):
        def draw(c: Canvas, k: int = k) -> None:
            for j in range(4):
                a = k * math.pi / (2 * count) + j * math.pi / 2
                c.polygon([(8 + 7.5 * math.cos(a), 8 + 7.5 * math.sin(a)),
                           (8 + 1.6 * math.cos(a + 1.2), 8 + 1.6 * math.sin(a + 1.2)),
                           (8 + 1.6 * math.cos(a - 1.2), 8 + 1.6 * math.sin(a - 1.2))], ON)
        sheet.sprites.draw(pattern, "spark", draw)
    return out


def back_and_forth(frames: tuple[int, ...], length: int) -> list[int]:
    """An animation of `length` steps: the frames there and back."""
    cycle = list(frames) + list(frames[-2:0:-1])
    return [cycle[n % len(cycle)] for n in range(length)]
