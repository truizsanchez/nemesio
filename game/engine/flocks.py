"""Stage 5's end: two flocks, and the three types they are made of.

Bank 1, 0x6EA8 ("end of stage 5") runs them, counted in 0xE065: when the
scroll stops, the long flock (0xB946); when its clock runs out, the flock of
the big ones (0xBB95); when that one's runs out, the scroll on to 0x1FF and
then the core. Each flock is a clock of (difficulty + 0x14) * 0x1E game
frames and a cadence; it lets one out each time the cadence comes round.

- Type 0x1D, the long flock's (0xB9C1): it appears where its place says,
  blinking and harmless for 0x32 game frames, then spirals -- a seventh of a
  radian a step round a centre, with no sine: the difference to the centre
  over eight, added to the other coordinate (0xBA9D) -- and flies off. One in
  eight comes in by the ship when the ship hugs the top or the bottom.
- Type 0x1E, the big one's (0xBBF1), is the only object that takes THREE
  slots: two copies of it ride under it in a triangle. It chases the ship's
  row, bounces off the sides, cannot be shot, and after 0x5A game frames (or
  when the ship touches it) breaks into three type 0x1F that fly apart and,
  while the flock lasts, curve after the ship (0x95EB).

With options, these fire only when the player fires (0xE008 bit 4): the
original's way of making the options' extra shots cost something.
"""

from __future__ import annotations

from game.engine.objects import Objects, Slot
from game.engine.tables import FlockArt

SPIRAL, BIG, PIECE = 0x1D, 0x1E, 0x1F
#: A flock's clock: (difficulty + 0x14) * 0x1E game frames (0xB94B, 0xBB9A).
CLOCK_BASE, CLOCK_TIMES = 0x14, 0x1E
#: Game frames between two: 0x1F less the difficulty (0xB959), 0x28 less
#: twice it (0xBBA8).
LONG_EVERY, BIG_EVERY = 0x1F, 0x28
#: One in eight of the long flock comes by the ship when it is above row 8
#: or below 0x90: at row 0x0C or 0x8E, its variant 8 or 9 (0xB99E).
EDGE_TOP, EDGE_BOTTOM = 0x08, 0x90
EDGE_ROWS, EDGE_VARIANTS = (0x0C, 0x8E), (8, 9)
#: From variant 8 on, the spiral's centre is four columns left of it (0xB9D3).
EDGE_FIRST, EDGE_CENTRE_DX = 8, 4
#: Type 0x1D: 0x32 game frames appearing, blinking colour 8 from 0x1E left
#: and 9 from 0x0A; then 0x3C a step of its radius (0xB9F4, 0xBA24).
APPEAR, BLINK_FROM, BLINK_LATE, BLINK, BLINK_LAST = 0x32, 0x1E, 0x0A, 8, 9
RADIUS_EVERY, RADIUS = 0x3C, 0xFF
#: Its four drawings, every four game frames (every two while appearing).
SPIRAL_DRAWINGS, SPIRAL_MASK, APPEARING_MASK = 4, 3, 1
#: It fires every 0x40 game frames with one option, 0x20 with two (0xBA6B).
ONE_OPTION_MASK, TWO_OPTIONS_MASK = 0x3F, 0x1F
#: Type 0x1E: door 0 comes in at row 0x18 with the ship below 0x50, 0x78 if
#: not (0xBBF7); it lives 0x5A game frames, blinking colour 7 or 5 by bit 2
#: of what it has left for the last 0x1E (0xBC89).
DOOR_ROW_SPLIT, DOOR_ROW_HIGH, DOOR_ROW_LOW = 0x50, 0x18, 0x78
BIG_LIFE, BIG_BLINK_FROM, BIG_COLOURS = 0x5A, 0x1E, (7, 5)
#: Its two copies: 0x10 lower, eight to the left and eight to the right.
UNDER, ASIDE = 0x10, 8
#: It changes drawings every 0x0F or 5 game frames, at the R register's whim.
BIG_BLINKS = (5, 0x0F)
#: A third of a pixel a game frame towards the ship's row, between rows 0x10
#: and 0x70; turned back past column 0xE0 or before 0x10 (0xBCFB).
BIG_CHASE, BIG_TOP, BIG_BOTTOM = 0x0020, 0x10, 0x70
BIG_SIDE, BIG_SIDES = 0x10, 0xD0
#: Type 0x1F: the layout's flock piece (0xE8), one hit; its drawing's bit 2 flips every 10 or
#: 3 game frames (0xBDB8); without the flock it leaves at two pixels a game
#: frame away from row 0x58 (0xBD95).
PIECE_BLINKS, PIECE_BIT, PIECE_FIRST_BLINK = (3, 0x0A), 4, 3
PIECE_ROW, PIECE_AWAY = 0x58, 0x0200
#: Going down, it looks for the map 0x10 lower (0xBDA5).
PIECE_BELOW = 0x10
#: Touching the big one pays 10 (0x749D), in BCD like every score.
BIG_TOUCH_POINTS = 10
#: 0x9657 is read by (one distance's high nibble, the other's).
NIBBLE = 0xF0


def _sra3(value: int) -> int:
    """Three `sra a` of a byte: its signed eighth, rounded down."""
    return (((value & 0xFF) ^ 0x80) - 0x80) >> 3


class Flocks:
    """0xE988..0xE997, and the movers of types 0x1D, 0x1E and 0x1F."""

    def __init__(self, objects: Objects, art: FlockArt) -> None:
        self.objects = objects
        self.art = art
        #: 0xE988: the long flock is on; 0xE989 its clock; 0xE98B/0xE98C its
        #: cadence and what is left of it; 0xE98D how many; 0xE98E the
        #: variant of the one being made.
        self.long_on = False
        self.long_clock = 0
        self.long_every = self.long_wait = 0
        self.long_count = 0
        self.variant = 0
        #: 0xE990..0xE996: the same for the big ones, and the door.
        self.big_on = False
        self.big_clock = 0
        self.big_every = self.big_wait = 0
        self.door_count = 0
        self.door = 0
        #: 0xE150: a flock's clock ran out (0x7D64).
        self.done = False
        objects.builders.update({SPIRAL: self._build_spiral, BIG: self._build_big})
        objects.movers.update({SPIRAL: self._move_spiral, BIG: self._move_big,
                               PIECE: self._move_piece})

    # -- the two flocks ----------------------------------------------------------

    def start_long(self, difficulty: int) -> None:
        """0xB946."""
        self.long_on = True
        self.long_clock = (difficulty + CLOCK_BASE) * CLOCK_TIMES
        self.long_every = self.long_wait = (LONG_EVERY - difficulty) & 0xFF

    def start_big(self, difficulty: int) -> None:
        """0xBB95."""
        self.big_on = True
        self.big_clock = (difficulty + CLOCK_BASE) * CLOCK_TIMES
        self.big_every = self.big_wait = (BIG_EVERY - 2 * difficulty) & 0xFF

    def release(self) -> None:
        """0xB966 and 0xBBB6, a game frame."""
        if self.long_on:
            self._release_long()
        if self.big_on:
            self._release_big()

    def _release_long(self) -> None:
        self.long_clock = (self.long_clock - 1) & 0xFFFF
        if not self.long_clock:
            self.done = True
            return
        self.long_wait = (self.long_wait - 1) & 0xFF
        if self.long_wait:
            return
        self.long_wait = self.long_every
        variant = self.long_count & 7
        self.long_count = (self.long_count + 1) & 0xFF
        place: tuple[int, int] | None = None
        if not variant:
            place = self._by_the_ship()
            if place is not None:
                variant = EDGE_VARIANTS[place[0] == EDGE_ROWS[1]]
        self.variant = variant
        if place is None:
            place = self.art.places[variant]
        self.objects.make(SPIRAL, *place)

    def _by_the_ship(self) -> tuple[int, int] | None:
        """0xB99E: at the ship's column, by the edge the ship hugs."""
        w = self.objects.world
        if w.ship_row < EDGE_TOP:
            return EDGE_ROWS[0], w.ship_col
        if w.ship_row >= EDGE_BOTTOM:
            return EDGE_ROWS[1], w.ship_col
        return None

    def _release_big(self) -> None:
        self.big_clock = (self.big_clock - 1) & 0xFFFF
        if not self.big_clock:
            self.done = True
            return
        self.big_wait = (self.big_wait - 1) & 0xFF
        if self.big_wait:
            return
        self.big_wait = self.big_every
        self.door_count = (self.door_count + 1) & 0xFF
        self.door = self.door_count & 3
        self.objects.make(BIG, *self.art.doors[self.door])

    # -- type 0x1D ------------------------------------------------------------------

    def _build_spiral(self, s: Slot) -> None:
        """0xB9C1."""
        variant = self.variant
        s[19] = variant
        row, col, count, turn = self.art.spirals[variant]
        if variant >= EDGE_FIRST:
            col = s[6] - EDGE_CENTRE_DX
        s[21], s[22] = row, col
        s[28], s[30] = count, turn
        s[20] = RADIUS
        s[2] = APPEAR
        s[27] = 0
        s.vx(0)
        s.vy(0)

    def _move_spiral(self, s: Slot) -> None:
        """0xB9FF."""
        o = self.objects
        o._animate(s, SPIRAL_MASK if s[1] else APPEARING_MASK, SPIRAL_DRAWINGS,
                   self.art.spiral_drawings)
        if o._solid_pair(s.row, s.col, walls=True):
            o.kill(s, pays=False)
            return
        if s[1] == 1:
            self._spiral_on(s)
            return
        if s[1]:
            return
        s[2] = s[2] - 1
        if not s[2]:
            s[2], s[27] = RADIUS_EVERY, 3
            s[1] = 1
            return
        if s[2] >= BLINK_FROM:
            return
        s[13] = BLINK if s[2] >= BLINK_LATE else BLINK_LAST

    def _spiral_on(self, s: Slot) -> None:
        """0xBA46: round its centre while the count lasts, then away at its
        variant's speeds."""
        self._fire_spiral(s)
        s[28] = s[28] - 1
        if s[28]:
            self._turn(s)
            return
        s[1] = 2
        vy, vx = self.art.spiral_speeds[s[19]]
        s.vy(vy)
        s.vx(vx)

    @staticmethod
    def _turn(s: Slot) -> None:
        """0xBA9D and 0xBAEA: each coordinate takes an eighth of the other's
        difference to the centre, and both are scaled by the radius -- which
        is not about the centre but about the screen's corner."""
        sign = 1 if s[30] & 1 else -1
        down = _sra3(s[4] - s[21])
        across = _sra3(s[6] - s[22])
        col = (s[6] + sign * down) & 0xFF
        row = (s[4] - sign * across) & 0xFF
        s[4] = row * s[20] >> 8
        s[6] = col * s[20] >> 8
        s[2] = s[2] - 1
        if not s[2]:
            s[2] = RADIUS_EVERY
            s[20] = s[20] - 1

    def _fire_spiral(self, s: Slot) -> None:
        """0xBA6B: with options, when the player fires; without, as any
        enemy does -- from the second round, or with the shield or the laser."""
        w = self.objects.world
        if w.options:
            mask = ONE_OPTION_MASK if w.options == 1 else TWO_OPTIONS_MASK
            if not w.frames & mask and w.fire_pressed:
                self.objects.fire_now(s)
            return
        if w.round or w.shield_on or w.laser:
            self.objects._fire_unaimed(s)

    # -- type 0x1E ------------------------------------------------------------------

    def _three(self, s: Slot) -> list[Slot]:
        at = self.objects.slots.index(s)
        return self.objects.slots[at:at + 3]

    def _build_big(self, s: Slot) -> None:
        """0xBBF1: the two copies, in a triangle, and its door's speeds."""
        if not self.door:
            row = DOOR_ROW_HIGH if self.objects.world.ship_row >= DOOR_ROW_SPLIT else DOOR_ROW_LOW
            s[4] = row
        s.vx(0)
        s.vy(0)
        s[29] = 0
        three = self._three(s)
        for n, other in enumerate(three[1:], 1):
            other.data[:] = s.data
            other[19] = n
        self._triangle(three)
        self._drawings(three, 0)
        s[20] = 1
        s[2] = BIG_LIFE
        s[19] = 0
        vy, vx = self.art.door_speeds[self.door]
        s.vy(vy)
        s.vx(vx)

    @staticmethod
    def _triangle(three: list[Slot]) -> None:
        """0xBCAD."""
        first = three[0]
        row = (first[4] + UNDER) & 0xFF
        left = (first[6] - ASIDE) & 0xFF
        three[1][4], three[1][6] = row, left
        three[2][4], three[2][6] = row, left + 2 * ASIDE

    def _drawings(self, three: list[Slot], which: int) -> None:
        """0xBC6C."""
        for other, pattern in zip(three, self.art.big_drawings[which]):
            other[12] = pattern

    def _move_big(self, s: Slot) -> None:
        """0xBCE3: only the first of the three moves."""
        if s[19]:
            return
        s[2] = s[2] - 1
        if not s[2]:
            self.split(s)
            return
        three = self._three(s)
        if s[2] < BIG_BLINK_FROM:
            colour = BIG_COLOURS[bool(s[2] & 4)]
            for other in three:
                other[13] = colour
        s[20] = s[20] - 1
        if not s[20]:
            s[20] = BIG_BLINKS[self.objects.rng.randrange(2)]
            s[29] = s[29] ^ 1
            self._drawings(three, s[29])
        self._fire_big(s)
        w = self.objects.world
        s.vy(BIG_CHASE if w.ship_row >= s.row else -BIG_CHASE & 0xFFFF)
        s.add_speed()
        if s[4] > BIG_BOTTOM:
            s[4] = BIG_BOTTOM
        elif s[4] <= BIG_TOP:
            s[4] = BIG_TOP
        self._triangle(three)
        if (s[6] - BIG_SIDE) & 0xFF >= BIG_SIDES:
            s.vx(-s.word(9) & 0xFFFF)

    def _fire_big(self, s: Slot) -> None:
        """0xBCC9: from the second round, with two options, when the player
        fires, every 0x20 game frames."""
        w = self.objects.world
        if w.round and w.options >= 2 and not w.frames & TWO_OPTIONS_MASK and w.fire_pressed:
            self.objects.fire_now(s)

    def split(self, s: Slot) -> None:
        """0xBD33, from the first of the three: three type 0x1F, apart."""
        for other, (vy, vx) in zip(self._three(self.first(s)), self.art.piece_speeds):
            other[0], other[12] = PIECE, self.objects.layout.flock_piece
            other[2], other[29] = 0, 0
            other[15] = 1
            other[27], other[20] = 3, PIECE_FIRST_BLINK
            other.vy(vy)
            other.vx(vx)

    def first(self, s: Slot) -> Slot:
        """0x748A: byte 19 says which of the three it is."""
        return self.objects.slots[self.objects.slots.index(s) - s[19]]

    def touched(self, s: Slot) -> None:
        """0x7488: the ship touched a big one: it breaks, and pays 10."""
        self.split(s)
        self.objects.world.score += BIG_TOUCH_POINTS

    # -- type 0x1F ------------------------------------------------------------------

    def _move_piece(self, s: Slot) -> None:
        """0xBD7D."""
        o = self.objects
        row = s.row if s[8] & 0x80 else s.row + PIECE_BELOW
        if o._solid_pair(row, s.col, walls=True):
            o.kill(s, pays=False)
            return
        s[20] = s[20] - 1
        if not s[20]:
            s[20] = PIECE_BLINKS[o.rng.randrange(2)]
            s[12] = s[12] ^ PIECE_BIT
        if self.big_on:
            self._toward_ship(s)
            s.vy(s.word(7) + s.word(23))
            s.vx(s.word(9) + s.word(25))
        else:
            s.vy(PIECE_AWAY if s.row >= PIECE_ROW else -PIECE_AWAY & 0xFFFF)

    def _toward_ship(self, s: Slot) -> None:
        """0x95EB: the two accelerations, looked up."""
        w = self.objects.world
        dx = s.col - w.ship_col
        dy = s.row - w.ship_row
        across, down = abs(dx) & 0xFF, abs(dy) & 0xFF
        table = self.objects.tables.toward_ship
        ax = table[(across & NIBBLE) | down >> 4]
        ay = table[(down & NIBBLE) | across >> 4]
        if dx >= 0:
            ax = -ax & 0xFFFF
        if dy >= 0:
            ay = -ay & 0xFFFF
        s.set_word(25, ax)
        s.set_word(23, ay)
