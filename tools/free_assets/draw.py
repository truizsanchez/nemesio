"""Drawing the free assets: the TMS9918's colours, a 5x7 font, a canvas of
cells, and the sheets a stage's pictures are drawn on (its characters, its
sprites) with who has which number."""

import math
from typing import Any, Callable, Sequence

#: Something that draws on a canvas (a lambda with defaults, often).
Painter = Callable[..., Any]

from game.engine.original import SCENERY
from game.free import graphics
from game.free.png import PALETTE, Picture

# -- colours (the TMS9918's) ----------------------------------------------------------
CLEAR, BLACK, GREEN, LIGHT_GREEN, DARK_BLUE, LIGHT_BLUE, DARK_RED, CYAN = range(8)
RED, LIGHT_RED, DARK_YELLOW, LIGHT_YELLOW, DARK_GREEN, MAGENTA, GREY, WHITE = range(8, 16)

# -- a 5x7 font, drawn here -------------------------------------------------------------
GLYPHS = {
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    "A": ("..#..", ".#.#.", "#...#", "#...#", "#####", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("###..", "#..#.", "#...#", "#...#", "#...#", "#..#.", "###.."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
}


def glyph(letter: str) -> tuple[str, ...]:
    return GLYPHS[letter]


# -- drawing ------------------------------------------------------------------------------

class Canvas:
    """A picture drawn in cells: a character's or a sprite's."""

    def __init__(self, picture: Picture, x0: int, y0: int, w: int, h: int) -> None:
        self.p, self.x0, self.y0, self.w, self.h = picture, x0, y0, w, h

    def set(self, x: int, y: int, colour: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[self.x0 + x, self.y0 + y] = colour

    def fill(self, colour: int) -> None:
        for y in range(self.h):
            for x in range(self.w):
                self.set(x, y, colour)

    def rect(self, x: int, y: int, w: int, h: int, colour: int) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, colour)

    def polygon(self, points: Sequence[tuple[float, float]], colour: int) -> None:
        for y in range(self.h):
            for x in range(self.w):
                if inside(points, x + 0.5, y + 0.5):
                    self.set(x, y, colour)

    def circle(self, cx: float, cy: float, r: float, colour: int, ring: float = 0) -> None:
        for y in range(self.h):
            for x in range(self.w):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                if d <= r and (not ring or d >= r - ring):
                    self.set(x, y, colour)

    def line(self, x0: float, y0: float, x1: float, y1: float, colour: int, width: float = 1) -> None:
        steps = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        for n in range(steps + 1):
            t = n / steps
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            for dy in range(-int(width // 2), int(width // 2) + 1):
                for dx in range(-int(width // 2), int(width // 2) + 1):
                    self.set(int(x + dx), int(y + dy), colour)

    def facets(self, faces: Sequence[tuple[Sequence[tuple[float, float]], int]]) -> None:
        """Polygons, each in its own colour, one after another."""
        for points, colour in faces:
            self.polygon(points, colour)

    def lit(self, faces: Sequence[Sequence[tuple[float, float]]], ramp: Sequence[int],
            centre: tuple[float, float] | None = None) -> None:
        """Faces shaded by where they lie from `centre` (their middle, if
        not given): towards the light (above, to the left) the ramp's
        lightest, away from it its darkest."""
        self.facets([(face, shade(face, ramp, centre or middle(faces))) for face in faces])

    def mesh(self, faces: Sequence[Sequence[tuple[float, float]]], colour: int, seam: int = CLEAR) -> None:
        """A sprite's facets: the faces in one colour, and the edges two of
        them share drawn in `seam` (the cut between them)."""
        for face in faces:
            self.polygon(face, colour)
        for (x0, y0), (x1, y1) in shared_edges(faces):
            # Short of both ends by a pixel, so the outline holds the faces together.
            length = math.hypot(x1 - x0, y1 - y0)
            if length > 2:
                dx, dy = (x1 - x0) / length, (y1 - y0) / length
                self.line(x0 + dx, y0 + dy, x1 - dx, y1 - dy, seam)

    def quadrants(self, ramp: Sequence[int]) -> None:
        """What is drawn shaded by the 8x8 cell it falls in, lit from above
        on the left: a cell's row keeps one colour, as over the sky it must."""
        for y in range(self.h):
            for x in range(self.w):
                if self.p[self.x0 + x, self.y0 + y] != CLEAR:
                    cells = (x * 2 // self.w) + (y * 2 // self.h)
                    self.set(x, y, ramp[len(ramp) - 1 - min(cells, len(ramp) - 1)])

    def gem(self, cx: float, cy: float, w: float, h: float, ramp: Sequence[int]) -> None:
        """A cut stone seen from the side: its crown (lit), its girdle and its
        pavilion (in shadow), in bands a row keeps one colour of."""
        dark, mid, light = ramp[0], ramp[len(ramp) // 2], ramp[-1]
        top, girdle, low = cy - h / 2, cy - h / 8, cy + h / 8
        self.polygon([(cx - w / 4, top), (cx + w / 4, top), (cx + w / 2, girdle), (cx - w / 2, girdle)], light)
        self.polygon([(cx - w / 2, girdle), (cx + w / 2, girdle), (cx + w / 2, low), (cx - w / 2, low)], mid)
        self.polygon([(cx - w / 2, low), (cx + w / 2, low), (cx, cy + h / 2)], dark)

    def text(self, x: int, y: int, letter: str, colour: int) -> None:
        for r, row in enumerate(glyph(letter)):
            for c, bit in enumerate(row):
                if bit == "#":
                    self.set(x + c, y + r, colour)


#: The light the facets are shaded by: from above, a little to the left.
LIGHT = (-0.45, -0.9)


def middle(faces: Sequence[Sequence[tuple[float, float]]]) -> tuple[float, float]:
    points = [p for face in faces for p in face]
    return (sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points))


def shade(face: Sequence[tuple[float, float]], ramp: Sequence[int], centre: tuple[float, float]) -> int:
    """The ramp's colour for a face: by how much the way from `centre` to the
    face's middle looks towards the light."""
    mx, my = middle([face])
    dx, dy = mx - centre[0], my - centre[1]
    length = math.hypot(dx, dy)
    if length < 0.5:
        return ramp[len(ramp) // 2]
    towards = (dx * LIGHT[0] + dy * LIGHT[1]) / length / math.hypot(*LIGHT)
    return ramp[min(int((towards + 1) / 2 * len(ramp)), len(ramp) - 1)]


def fan(centre: tuple[float, float], rim: Sequence[tuple[float, float]]) -> list[list[tuple[float, float]]]:
    """A convex shape cut into triangles from a point inside it: a gem."""
    return [[centre, rim[n], rim[(n + 1) % len(rim)]] for n in range(len(rim))]


def ngon(cx: float, cy: float, r: float, sides: int, turn: float = 0,
         squash: float = 1) -> list[tuple[float, float]]:
    """A regular polygon's corners (squashed upright by `squash`)."""
    return [(cx + r * math.cos(turn + 2 * math.pi * n / sides),
             cy + r * squash * math.sin(turn + 2 * math.pi * n / sides)) for n in range(sides)]


def cube(cx: float, cy: float, r: float) -> list[list[tuple[float, float]]]:
    """A hexagon as three faces meeting in its middle: a cube seen corner on."""
    rim = ngon(cx, cy, r, 6, math.pi / 6)
    centre = (cx, cy)
    return [[centre, rim[n], rim[(n + 1) % 6], rim[(n + 2) % 6]] for n in (3, 5, 1)]


def shared_edges(faces: Sequence[Sequence[tuple[float, float]]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """The edges two faces have in common (the cuts inside a shape)."""
    seen: dict[tuple[tuple[float, float], ...], int] = {}
    for face in faces:
        for n in range(len(face)):
            a, b = face[n], face[(n + 1) % len(face)]
            key = tuple(sorted(((round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2)))))
            seen[key] = seen.get(key, 0) + 1
    return [(a, b) for (a, b), count in seen.items() if count > 1]


def _distance(a: int, b: int) -> int:
    ra, rb = PALETTE[a], PALETTE[b]
    return sum(((ra >> s & 0xFF) - (rb >> s & 0xFF)) ** 2 for s in (0, 8, 16))


def two_a_row(canvas: "Canvas") -> None:
    """Every row of eight pixels in its two commonest colours, as the
    TMS9918 shows it: a third colour becomes the nearer of the two."""
    for y in range(canvas.h):
        for x0 in range(0, canvas.w, 8):
            row = [canvas.p[canvas.x0 + x0 + x, canvas.y0 + y] for x in range(8)]
            counts: dict[int, int] = {}
            for colour in row:
                counts[colour] = counts.get(colour, 0) + 1
            if len(counts) <= 2:
                continue
            two = sorted(counts, key=lambda c: (-counts[c], c))[:2]
            for x, colour in enumerate(row):
                if colour not in two:
                    canvas.set(x0 + x, y, min(two, key=lambda c: (_distance(colour, c), c)))


def inside(points: Sequence[tuple[float, float]], x: float, y: float) -> bool:
    result = False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]
        xj, yj = points[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            result = not result
        j = i
    return result


class Chars:
    """`chars.png`, and who has which character."""

    def __init__(self) -> None:
        self.picture = Picture(graphics.CHARS_WIDTH, graphics.CHARS_HEIGHT)
        self.names: dict[int, str] = {}
        self.free = list(range(SCENERY, 0x100))
        #: Scenery cells already drawn, by their pixels: a drawing that
        #: repeats one takes the same character.
        self.drawn: dict[tuple[int, ...], int] = {}

    def shared(self, big: Picture, x: int, y: int, name: str) -> int:
        """The scenery character for the 8x8 cell of `big` at (x, y): one
        already drawn like it, or the next free."""
        key = tuple(big[x + i, y + j] for j in range(8) for i in range(8))
        if key not in self.drawn:
            char = self.scenery(1)[0]
            self.block([char], name, big, x, y, 1)
            self.drawn[key] = char
        return self.drawn[key]

    def canvas(self, char: int, third: int) -> Canvas:
        x, y = graphics.cell(third, char)
        return Canvas(self.picture, x, y, 8, 8)

    def draw(self, char: int, name: str, painter: Painter, thirds: tuple[int, ...] = (0, 1, 2)) -> int:
        self.names[char] = name
        for third in thirds:
            canvas = self.canvas(char, third)
            painter(canvas)
            two_a_row(canvas)
        return char

    def scenery(self, count: int, together: bool = False) -> list[int]:
        """The next `count` scenery characters; `together`, one after
        another (the shot's four, a pair)."""
        taken, self.free = self.free[:count], self.free[count:]
        if len(taken) < count:
            raise SystemExit("out of scenery characters")
        if together and taken != list(range(taken[0], taken[0] + count)):
            raise SystemExit("no %d scenery characters in a row" % count)
        return taken

    def block(self, chars: list[int], name: str, big: Picture, bx: int, by: int, w: int) -> None:
        """A drawing of w x h characters cut out of `big`, into `chars`."""
        for n, char in enumerate(chars):
            cx, cy = n % w * 8, n // w * 8
            self.names[char] = "%s (%d)" % (name, n)
            for third in range(3):
                canvas = self.canvas(char, third)
                for y in range(8):
                    for x in range(8):
                        canvas.set(x, y, big[bx + cx + x, by + cy + y])
                two_a_row(canvas)




class Sprites:
    def __init__(self) -> None:
        self.picture = Picture(graphics.SPRITES_WIDTH, graphics.SPRITES_HEIGHT)
        self.names: dict[int, str] = {}

    def draw(self, pattern: int, name: str, painter: Painter) -> None:
        n = pattern // 4
        self.names[pattern] = name
        painter(Canvas(self.picture, n % 16 * 16, n // 16 * 16, 16, 16))


#: What every stage has lays its numbers out from the first; a stage's own
#: from these on: solid characters, sprite patterns, drawings of four.
STAGE_SOLID, STAGE_PATTERNS, STAGE_DRAWINGS = 0x58, 0xAC, 24


class Sheet:
    """A stage's pictures and its numbers: the characters (and the scenery
    ones shared by their pixels), the sprite patterns, the drawings."""

    def __init__(self) -> None:
        self.chars = Chars()
        self.sprites = Sprites()
        self._solid = iter(range(STAGE_SOLID, SCENERY))
        self._patterns = iter(range(STAGE_PATTERNS, 0x100, 4))
        self._drawings = iter(range(STAGE_DRAWINGS, 128))
        #: The stage's drawings of four characters, by number.
        self.drawings: dict[int, list[int]] = {}
        #: Patterns the layout names that the stage draws itself.
        self.kept: set[int] = set()

    def solid(self, count: int) -> tuple[int, ...]:
        try:
            return tuple(next(self._solid) for _ in range(count))
        except StopIteration:
            raise SystemExit("a stage is out of solid characters")

    def patterns(self, count: int) -> tuple[int, ...]:
        """The next `count` patterns, past any the stage has kept."""
        out: list[int] = []
        try:
            while len(out) < count:
                pattern = next(self._patterns)
                if pattern not in self.kept:
                    out.append(pattern)
        except StopIteration:
            raise SystemExit("a stage is out of sprite patterns")
        return tuple(out)

    def drawing(self, painter: Painter, name: str,
                number: int | None = None) -> int:
        """A drawing of 2x2 scenery characters out of a 16x16 painter; its
        number (the next free, or `number`)."""
        big = Picture(16, 16)
        painter(Canvas(big, 0, 0, 16, 16))
        if number is None:
            number = next(self._drawings)
        self.drawings[number] = [self.chars.shared(big, x, y, name) for y in (0, 8) for x in (0, 8)]
        return number

    def block(self, painter: Painter, width: int, height: int, name: str,
              chars: Sequence[int] | None = None) -> list[int]:
        """A drawing of width x height characters: into `chars` (solid, say)
        or scenery shared by their pixels; a blank cell is character 0 unless
        `chars` are given."""
        big = Picture(width * 8, height * 8)
        painter(Canvas(big, 0, 0, width * 8, height * 8))
        if chars is not None:
            self.chars.block(list(chars), name, big, 0, 0, width)
            return list(chars)
        out = []
        for n in range(width * height):
            x, y = n % width * 8, n // width * 8
            if any(big[x + i, y + j] for i in range(8) for j in range(8)):
                out.append(self.chars.shared(big, x, y, name))
            else:
                out.append(0)
        return out
