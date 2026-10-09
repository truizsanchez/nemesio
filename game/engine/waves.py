"""Where the enemies come from on stages 1-8: the waves.

Bank 3, 0xA310 ("release the stretch's enemies"), once a game frame. The stage is
cut in sections of 0x20 of distance, and each has a byte whose bits say which
of six generators run there (0xA3A6): a pair (type 3), a trail (4), eight from
the left (5), four from below (6), a flock (9), eight mixed (5 and 6). Before
all of them runs the six-in-a-row wave (0xA4BA), and after them five
generators that run everywhere -- not yet here.
"""

from typing import TYPE_CHECKING

from game.engine.objects import Objects

if TYPE_CHECKING:
    from game.engine.flocks import Flocks

#: The bouncers come in at column 0xF8, at row 8 or a floor (0xB864).
BOUNCER, BOUNCER_TOP, BOUNCER_COLUMN = 0x1B, 8, 0xF8
#: Bosses 5 and 6 of 0x7C41's table let the waves run (0xA337).
BOSSES_WITH_WAVES = 5
#: The first wave waits 0x40 game frames (0x420E).
FIRST_WAIT = 0x40
#: No waves from distance 0x200 on (0xE064, the distance's high byte).
LAST_DISTANCE_HIGH = 2
#: The six-in-a-row waves come only before distance 0x80 (0x40 on stage 8),
#: one every eight columns (0xA513).
ROWS_BEFORE, ROWS_BEFORE_8, ROWS_EVERY = 0x80, 0x40, 8
ROWS_OF = 6
#: With this many alive a new generator waits for room (0xA351), and a wave
#: in a row waits with more than seven alive (0xA509); the pair waits with
#: eleven (0xA444).
ROOM, ROWS_ROOM, PAIR_ROOM = 0x0B, 7, 0x0B
#: Only stage 7 has the type 0x0D's script (0xAEE2), and nothing comes out
#: of it with the column left of 0x80 (0xAF19).
APPEARANCES_STAGE, APPEARANCE_TYPE, APPEARANCE_FROM = 7, 0x0D, 0x80


class Waves:
    def __init__(self, objects: Objects, stage: int) -> None:
        self.objects = objects
        self.stage = stage
        self.wait = FIRST_WAIT
        #: 0xE160-0xE165: the wave in a row: its step, its delay, how many are
        #: left, its type, (0xE164), the row it comes in on.
        self.rows_step = 0
        self.rows_delay = 0
        self.rows_left = 0
        self.rows_type = 0
        self.rows_row = 0
        #: 0xE125: enemies asked for, which marks every fourth.
        self.asked = 0
        #: Each generator's (left, delay): 0xE96C, 0xE960, 0xE966, 0xE96A,
        #: 0xE962.
        self.pair_delay = 0
        self.trail = [0, 0]
        self.left = [0, 0]
        self.below = [0, 0]
        self.flock = [0, 0]
        self.appearances = Appearances(objects, stage)

    #: Stage 5's flocks, let out last of all (0xA387, 0xA38A).
    flocks: "Flocks | None" = None
    #: Stage 5's bouncers' script, (distance, packed), and its next row
    #: (0xB8B4, 0xE97D).
    bouncers: tuple[tuple[int, int], ...] = ()
    bouncer_row = 0

    def _bouncers(self, distance: int, moved: bool) -> None:
        """0xB859: a type 0x1B for each row at this distance. The packed
        byte's five high bits (0xE97E) say its floor and speed; with bit 0 of
        them clear it comes in at row 8, set at one of the three floors."""
        if not moved:
            return
        while (self.bouncer_row < len(self.bouncers)
               and self.bouncers[self.bouncer_row][0] == distance):
            packed = self.bouncers[self.bouncer_row][1] >> 2 & 0x1F
            self.bouncer_row += 1
            self.objects.bouncer = packed
            art = self.objects.tables.stage5
            row = art.floors[packed >> 3 & 3] if packed & 1 and art else BOUNCER_TOP
            self.objects.make(BOUNCER, row, BOUNCER_COLUMN)

    def step(self, distance: int, moved: bool, boss: int | None = None) -> None:
        """0xA310. With a boss on, only bosses 5 and 6 let the waves be; the
        others let a wave in a row already coming finish (0xA32F)."""
        if self.wait:
            self.wait -= 1
            return
        if self.stage >= 9:
            return
        if distance >> 8 >= LAST_DISTANCE_HIGH:
            return
        if boss is not None and (boss - BOSSES_WITH_WAVES) & 0xFF >= 2:
            if self.rows_step:
                self._rows(distance, moved)
            return
        self._rows(distance, moved)
        if self.objects.made:
            room = (ROOM - self.objects.alive) & 0xFF
            if room < self.rows_left:
                return
        bits = self.objects.tables.sections[self.stage][distance >> 5 & 0x0F]
        if bits & 0x01:
            self._pair()
        if bits & 0x02:
            self._trail()
        if bits & 0x04:
            self._from_the_left()
        if bits & 0x08:
            self._four_from_below()
        if bits & 0x10:
            self._flock()
        if bits & 0x20:
            self._eight_mixed()
        self._walls(distance, moved)
        self.appearances.step(distance, moved)
        self._bouncers(distance, moved)
        if self.flocks is not None:
            self.flocks.release()

    # -- the wave in a row (0xA4BA) ------------------------------------------

    def _rows(self, distance: int, moved: bool) -> None:
        if self.rows_step == 0:
            self._start_rows(distance, moved)
            return
        if self.rows_step == 1:
            if self.objects.alive < ROWS_ROOM:
                self.rows_step = 2
            return
        self.rows_delay -= 1
        if self.rows_delay:
            return
        if self.rows_type == 2:
            self.rows_delay = 4
        elif self.rows_type == 0x0C:
            self.rows_delay = 0x10
        else:
            self.rows_delay = 4 if self.rows_left & 1 else 1
        self.rows_left -= 1
        if not self.rows_left:
            self.rows_step = 0
        self.objects.rows_left = self.rows_left
        self.objects.make(self.rows_type, self.rows_row, 0xF0)
        if not self.objects.made:
            self.rows_left += 1
            self.rows_step = 1

    def _start_rows(self, distance: int, moved: bool) -> None:
        """0xA50E."""
        if not moved:
            return
        before = ROWS_BEFORE_8 if self.stage == 8 else ROWS_BEFORE
        if distance >= before or distance % ROWS_EVERY:
            return
        self.rows_step, self.rows_delay = 1, 1
        both = self.objects.tables.rows_types[self.stage]
        number = (self.objects.wave_number + 1) & 0xFF or 1
        self.objects.wave_number = number
        kind = (both >> 4 if number & 1 else both) & 0x0F
        self.rows_type = kind
        self.rows_row = self._rows_row(kind, both, number)
        self.rows_left = ROWS_OF
        if not self.objects.open_group(number, ROWS_OF):
            self.rows_step = 0

    @staticmethod
    def _rows_row(kind: int, both: int, number: int) -> int:
        """0xA57E: the top or the bottom, and types 0x0A and 0x0C their own."""
        if kind == 0x0A:
            return 0x80 if number & 2 else 0x40
        if kind == 0x0C:
            return 0x98 if number & 2 else 0x06
        bit = number if both & 0x0F == both >> 4 else number >> 1
        return 0x98 if bit & 1 else 0x08

    # -- the walls of stones (0xABF3) ----------------------------------------------

    wall_left = 0
    wall_every_other = False
    wall_col = 0

    def _walls(self, distance: int, moved: bool) -> None:
        """Stages 2 and 8: at each distance on their list, a wall of stones
        (type 8) down one side, one a frame."""
        if self.wall_left:
            self._wall_stone()
            return
        if not moved:
            return
        walls = self.objects.tables.walls.get(self.stage)
        if not walls:
            return
        for wall in walls:
            if wall & 0x7FFF == distance:
                self.wall_col = 0x40 if wall & 0x8000 else 0xC0
                self.wall_every_other = self.stage == 8
                self.wall_left = 3 if self.wall_every_other else 5
                return

    def _wall_stone(self) -> None:
        """0xAC5B: rows from 0xAC7B (0xAC7C for stage 8's), counting down."""
        rows = self.objects.tables.wall_rows
        row = rows[self.wall_left + (1 if self.wall_every_other else 0)]
        self.objects.make(8, row, self.wall_col)
        self.wall_left -= 1

    # -- the six generators ------------------------------------------------------

    def _next_mark(self) -> int:
        mark = self.objects.mark(self.asked)
        self.asked += 1
        return mark

    def _difficulty_wait(self, base: int, times: int) -> int:
        return (base - times * self.objects.world.difficulty) & 0xFF

    def _pair(self) -> None:
        """0xA438: two of type 3, rows 0x30 and 0x60."""
        if self.pair_delay:
            self.pair_delay -= 1
            if self.pair_delay:
                return
        if self.objects.alive >= PAIR_ROOM:
            return
        self.pair_delay = self._difficulty_wait(0x70, 2)
        mark = self._next_mark()
        first = second = mark
        if mark == 2:
            first = self.objects.rng.randrange(2) + 1
            second = first ^ 3
        self.objects.make(3, 0x30, 0xF0, first)
        self.objects.make(3, 0x60, 0xF0, second)

    def _trail(self) -> None:
        """0xA46F: type 4, one every eight frames, on four rows in turn."""
        left, delay = self.trail
        if not left:
            counts = self.objects.tables.trail_counts
            self.trail = [counts[self.objects.world.difficulty], self._difficulty_wait(0x70, 2)]
            return
        delay -= 1
        if delay:
            self.trail[1] = delay
            return
        left -= 1
        self.trail = [left, 8]
        row = self.objects.tables.trail_rows[left & 3]
        self.objects.make(4, row, 0xF0)

    def _from_the_left(self) -> None:
        """0xA60D: eight of type 5 from the left edge."""
        left, delay = self.left
        if not left:
            self.left = [8, 1]
            return
        delay -= 1
        if delay:
            self.left[1] = delay
            return
        left -= 1
        self.left = [left, self._difficulty_wait(0x70, 4)]
        row = self.objects.tables.left_rows[left & 7]
        self.objects.make(5, row, 0x00, self._next_mark())

    def _four_from_below(self) -> None:
        """0xA648: four of type 6 at row 0x8F, the last from the left."""
        left, delay = self.below
        if not left:
            self.below = [4, 1]
            return
        delay -= 1
        if delay:
            self.below[1] = delay
            return
        left -= 1
        self.below = [left, self._difficulty_wait(0x60, 4)]
        col = 0xF0 if left & 3 else 0x00
        self.objects.make(6, 0x8F, col, self._next_mark())

    def _eight_mixed(self) -> None:
        """0xA679: four of type 5 on the ship's far side, then four of type 6.
        It shares its count with the four from below (0xE96A)."""
        left, delay = self.below
        if not left:
            self.below = [8, 1]
            return
        delay -= 1
        if delay:
            self.below[1] = delay
            return
        left -= 1
        self.below = [left, self._difficulty_wait(0x50, 4)]
        if left >= 4:
            row = 0x90 if self.objects.world.ship_row < 0x58 else 0x08
            self.objects.make(5, row, 0x00)
            return
        self.objects.make(6, 0x90, 0xF0 if left & 1 else 0x00)

    def _flock(self) -> None:
        """0xA5D7: eight of type 9, one every seven frames, four low, four
        high, then 0x3C frames to the next flock."""
        left, delay = self.flock
        if not left:
            if delay:
                delay -= 1
                if delay:
                    self.flock[1] = delay
                    return
            self.flock = [8, delay + 1]
            return
        delay -= 1
        if delay:
            self.flock[1] = delay
            return
        left -= 1
        self.flock = [left, 7 if left else 0x3C]
        row = 0x88 if left >= 4 else 0x18
        self.objects.make(9, row, 0xF0)


class Appearances:
    """0xAEDF/0xAEF3: stage 7's script of type 0x0D, one word an appearance
    (0xAF3F), its next word at 0xE968."""

    def __init__(self, objects: Objects, stage: int) -> None:
        self.objects = objects
        self.words = objects.tables.appearances if stage == APPEARANCES_STAGE else ()
        self.next = 0

    def fill(self, distance: int, col: int) -> None:
        """0xAEDF, while the screen fills: words passed are skipped."""
        while self.next < len(self.words):
            word = self.words[self.next]
            if distance < word & 0x1FF:
                return
            self.next += 1
            if distance == word & 0x1FF:
                self._make(word, col)

    def step(self, distance: int, moved: bool) -> None:
        """0xAEF3: in a game frame that brought a column in, the words at
        this distance, at column 0xF8."""
        if not moved:
            return
        while self.next < len(self.words) and self.words[self.next] & 0x1FF == distance:
            self._make(self.words[self.next], 0xF8)
            self.next += 1

    def _make(self, word: int, col: int) -> None:
        if col < APPEARANCE_FROM:
            return
        self.objects.make(APPEARANCE_TYPE, word >> 8 & 0xF8, col, word >> 9 & 3)


class Cannons:
    """0x90B5/0x90C1: the cannons' script, one row per cannon (0xE108)."""

    def __init__(self, objects: Objects, stage: int) -> None:
        self.objects = objects
        self.script = objects.tables.cannon_script[stage] if stage < len(
            objects.tables.cannon_script) else ()
        self.next = 0

    def fill(self, distance: int, col: int) -> None:
        """0x90B5, while the screen fills: rows passed are skipped."""
        while self.next < len(self.script):
            at, data = self.script[self.next]
            if distance < at:
                return
            self.next += 1
            if distance == at:
                self._make(data, col)

    def step(self, distance: int, moved: bool) -> None:
        """0x90C1: in a game frame that brought a column in, the rows at this
        distance, at column 0xF8."""
        if not moved:
            return
        while self.next < len(self.script) and self.script[self.next][0] == distance:
            self._make(self.script[self.next][1], 0xF8)
            self.next += 1

    def _make(self, data: int, col: int) -> None:
        self.objects.cannon_data = data
        mark = 0 if not data & 0x40 else 2 if data & 0x80 else 1
        self.objects.make(1, (data & 0x1F) * 8, col, mark)


#: A bonus stage's prizes come in at column 0xF8 (0x5D4C); bit 2 of the data
#: says a prize (0x16 on) rather than a box (0x19), its two low bits which,
#: and its mark is those plus three (0x5D67).
PRIZE_COLUMN, PRIZE_FROM, BOX_KIND, MARK_FROM = 0xF8, 0x16, 0x19, 3


class Prizes:
    """0x5D41 ("release what is due"): on bonus stages, when a column comes in,
    every row of the script at the distance, in order."""

    def __init__(self, objects: Objects, script: tuple[tuple[int, int], ...]) -> None:
        self.objects = objects
        self.script = script
        #: 0xE127: the script's next row.
        self.row = 0

    def step(self, distance: int, moved: bool) -> None:
        if not moved:
            return
        while self.row < len(self.script) and self.script[self.row][0] == distance:
            data = self.script[self.row][1]
            self.row += 1
            which = data & 3
            kind = PRIZE_FROM + which if data & 4 else BOX_KIND
            self.objects.make(kind, data & 0xF8, PRIZE_COLUMN, mark=which + MARK_FROM)
