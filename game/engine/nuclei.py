"""Stage 6's boss: nuclei with two arms each, for most of the stage.

Bank 1, 0x7F74 (boss 2 of the table at 0x7C41), with bank 2's 0x8001..0x8377
and drawings in bank 10. From distance 0xA0 the stage has no waves of its own:
every 0xC0 game frames a script of sixteen (0x8041) says which arms the next
nucleus comes with, the upper, the lower or both. Two nuclei at most, in the
slots of 0xE790 and 0xE7C0, each followed by its two arms' slots.

A nucleus drifts left eight pixels every ten game frames, and eight up or down
towards the ship's row. Its arms hang from it, one above and one below, and
turn a drawing at a time towards the ship -- one arm aims while the other
rests, taking turns every 0x40 game frames -- and fire from their tips. They
are characters drawn into the map, so the ship dies on them as on the
terrain. Shots take four from a piece (a laser one): an arm lasts 0x10, a
nucleus 0x7F and shrinks twice on the way; when a nucleus bursts its arms go
with it. Past distance 0x1A0 no more come, and once the last is gone, the
core.

The slots keep the original's sixteen bytes: 0 type (3 a nucleus, 4 an arm),
1 how hurt a nucleus is, 3 row, 5 column, 6 drawing, 7 shot clock, 8 step
clock, 9 life, 10 the drawing an arm is at (a nucleus's clock), 11 the one
it wants.
"""

from __future__ import annotations

from game.engine.objects import Objects
from game.engine.tables import NucleusArt

NUCLEUS, ARM = 3, 4
PIECES, SIZE = 6, 16
#: The two nuclei's slots; each one's arms are the next two.
FIRST, SECOND = 0, 3
#: Where the script ends (0x7FE1), how often it moves on (0x7FF2), and how
#: long the stage waits once the screen is clear (0x7F8B); after distance
#: 0xFF (a life lost past the checkpoint) the script starts at its third.
SCRIPT_UNTIL, SCRIPT_EVERY, FIRST_WAIT = 0x1A0, 0xC0, 0x40
CHECKPOINT, CHECKPOINT_SCRIPT = 0xFF, 2
SCRIPT_STEPS = 0x0F
#: A nucleus moves every ten game frames, eight pixels (0x8162); off the left
#: past column 0x10 it is gone with its arms.
NUCLEUS_EVERY, NUCLEUS_STEP, NUCLEUS_GONE = 0x0A, 8, 0x10
#: How far down it goes: 0x90, or 0x4E with a lower arm; up: to 0x38 with an
#: upper arm (0x8182, 0x8197). It goes down while the ship is 0x10 below it.
DOWN_TO, DOWN_TO_ARMED, UP_TO_ARMED, BELOW = 0x90, 0x4E, 0x38, 0x10
#: Hurt, it shows two drawings and then one (0x8153).
BLINK_BIT, STILL_FROM = 0x10, 2
#: An arm turns a drawing every five to eight game frames (0x811F).
ARM_EVERY = 5
#: The arms take turns: bit 6 of the nucleus's clock (0x81F6); the resting
#: arm holds drawing 0x0A (upper) or 0x1D (lower), and so does one that would
#: aim out of its reach while the nucleus is left of column 0x40 (0x822B).
TURNS, UPPER_REST, LOWER_REST = 0x40, 0x0A, 0x1D
REACH_COLUMN, REACH_FROM, REACH = 0x40, 0x0A, 0x14
#: Game frames between an arm's shots: 0x1B less the difficulty, halved (0x808F).
ARM_SHOTS = 0x1B
#: A shot takes four, a laser one (0x7749). A nucleus is met in a box of 0x20
#: by 0x20, 0x10 by 0x10, then 0x10 rows by 8 columns as it is hurt; an arm in
#: 8 rows by 0x10 columns about the centre 0x76EF gives it, six lower (0x7688).
SHOT_TAKES, LASER_TAKES = 4, 1
NUCLEUS_BOXES = ((0x20, 0x20), (0x10, 0x10), (0x10, 0x08))
ARM_BOX, ARM_CENTRE_DY = (0x08, 0x10), 6
SHOT_ROWS, SHOT_COLS = 0x02, 0x10
#: Hurt below 0x20 and below 0x10 (0x77F7).
HURT, HURTER = 0x20, 0x10
#: A nucleus pays 50, an arm 10 (0x780E, 0x77EE); 0x0D a hit, 0x0E a burst.
NUCLEUS_POINTS, ARM_POINTS, HIT_SOUND, BURST_SOUND = 50, 10, 0x0D, 0x0E


class Nuclei:
    def __init__(self, objects: Objects, art: NucleusArt) -> None:
        self.objects = objects
        self.art = art
        #: 0xE790..0xE7EF.
        self.pieces = [bytearray(SIZE) for _ in range(PIECES)]
        #: 0xE190, with -1 the game frame 0x7C4F takes to start it.
        self.step = -1
        #: 0xE153 and 0xE116: the script's clock and where it is.
        self.clock = 0
        self.script_at = 0
        #: 0xE117: the script is over; 0xE150: the boss is done.
        self.over = False
        self.done = False

    # -- a game frame (0x7F74) -------------------------------------------------------

    def update(self, distance: int, difficulty: int) -> None:
        if self.step == -1:
            self.step = 0
        elif self.step == 0:
            if any(s.type for s in self.objects.slots):
                return
            self.clock = FIRST_WAIT
            self.script_at = CHECKPOINT_SCRIPT if distance >= CHECKPOINT else 0
            self.step = 1
        elif self.step == 1:
            self._script(distance)
            self._aim()
            for n in range(PIECES):
                self._move(n)
            self._fire(difficulty)
            if self.over and not self.pieces[FIRST][0] and not self.pieces[SECOND][0]:
                self.step = 2
        else:
            self.done = True

    def _script(self, distance: int) -> None:
        """0x7FDE, then 0x8001."""
        if distance >= SCRIPT_UNTIL:
            self.over = True
            return
        self.clock = (self.clock - 1) & 0xFF
        if self.clock:
            return
        self.clock = SCRIPT_EVERY
        arms = self.art.script[self.script_at & SCRIPT_STEPS]
        self.script_at = (self.script_at + 1) & 0xFF
        if not self.pieces[FIRST][0]:
            at = FIRST
        elif not self.pieces[SECOND][0]:
            at = SECOND
        else:
            return
        self.pieces[at][:len(self.art.nucleus)] = bytes(self.art.nucleus)
        if arms & 1:
            self.pieces[at + 1][:len(self.art.upper)] = bytes(self.art.upper)
        if arms & 2:
            self.pieces[at + 2][:len(self.art.lower)] = bytes(self.art.lower)

    def _aim(self) -> None:
        """0x81D5: the angle to the ship picks the drawing an arm wants."""
        for at in (FIRST, SECOND):
            nucleus = self.pieces[at]
            if not nucleus[0]:
                continue
            angle = self.objects._angle(nucleus[3], nucleus[5]) >> 3
            upper, lower = self.pieces[at + 1], self.pieces[at + 2]
            resting = bool(nucleus[10] & TURNS)
            if upper[0]:
                upper[11] = UPPER_REST if resting else self._want(
                    nucleus, self.art.upper_aim[angle], UPPER_REST)
            if lower[0]:
                lower[11] = LOWER_REST if not resting else self._want(
                    nucleus, self.art.lower_aim[angle], LOWER_REST)

    def _want(self, nucleus: bytearray, drawing: int, rest: int) -> int:
        """0x8238's tremble of one either way, and 0x822B's reach."""
        tremble = self.objects.rng.randrange(4) - 1
        drawing = (drawing + (0 if tremble == 2 else tremble)) & 0xFF
        if nucleus[5] < REACH_COLUMN and (drawing - REACH_FROM) & 0xFF >= REACH:
            return rest
        return drawing

    def _move(self, n: int) -> None:
        """0x8113."""
        piece = self.pieces[n]
        if piece[0] == NUCLEUS:
            self._drift(n)
            return
        if piece[0] != ARM:
            return
        piece[8] = (piece[8] - 1) & 0xFF
        if piece[8]:
            return
        piece[8] = ARM_EVERY + self.objects.rng.randrange(4)
        if piece[10] == piece[11]:
            return
        piece[10] = (piece[10] + (1 if piece[10] < piece[11] else -1)) & 0xFF
        piece[6] = self.art.ramp[piece[10]]

    def _drift(self, n: int) -> None:
        """0x8144."""
        nucleus = self.pieces[n]
        nucleus[10] = (nucleus[10] - 1) & 0xFF
        blink = 1 if nucleus[10] & BLINK_BIT and nucleus[1] < STILL_FROM else 0
        nucleus[6] = nucleus[1] * 2 + blink
        nucleus[8] = (nucleus[8] - 1) & 0xFF
        if nucleus[8]:
            return
        nucleus[8] = NUCLEUS_EVERY
        col = (nucleus[5] - NUCLEUS_STEP) & 0xFF
        if col < NUCLEUS_GONE:
            for piece in self.pieces[n:n + 3]:
                piece[0] = 0
            return
        nucleus[5] = col
        row = nucleus[3]
        upper, lower = self.pieces[n + 1], self.pieces[n + 2]
        if (row + BELOW) & 0xFF < self.objects.world.ship_row:
            to = DOWN_TO_ARMED if lower[0] else DOWN_TO
            if (row + NUCLEUS_STEP) & 0xFF < to:
                nucleus[3] = row + NUCLEUS_STEP
        else:
            # Without an upper arm the limit is B as the loop left it: the
            # slots still to go, counting this one (0x8104).
            to = UP_TO_ARMED if upper[0] else PIECES - n
            if (row - NUCLEUS_STEP) & 0xFF >= to:
                nucleus[3] = (row - NUCLEUS_STEP) & 0xFF

    def _fire(self, difficulty: int) -> None:
        """0x8073: the five slots after the first, arms only."""
        for piece in self.pieces[1:]:
            if piece[0] != ARM:
                continue
            piece[7] = (piece[7] - 1) & 0xFF
            if piece[7]:
                continue
            piece[7] = (((ARM_SHOTS - difficulty) & 0xFF ^ 0x80) - 0x80) >> 1 & 0xFF
            dy, dx = self.art.muzzles[piece[6]]
            self.objects.fire_at_ship((piece[3] + dy) & 0xFF, (piece[5] + dx) & 0xFF)

    # -- drawn into the map (0x8293, 0x8290) -----------------------------------------

    def _hang(self) -> None:
        """0x8308: where the arms hang this game frame."""
        for at in (FIRST, SECOND):
            nucleus = self.pieces[at]
            if not nucleus[0]:
                continue
            _, height, across, _ = self.art.nuclei[nucleus[6]]
            upper, lower = self.pieces[at + 1], self.pieces[at + 2]
            if upper[0]:
                upper[3] = (nucleus[3] - self.art.arms[upper[6]][1] * 8) & 0xFF
                upper[5] = (self.art.hang[upper[6]] + nucleus[5] + across) & 0xFF
            if lower[0]:
                lower[5] = (self.art.hang[lower[6]] + nucleus[5] + across) & 0xFF
                lower[3] = (nucleus[3] + height * 8) & 0xFF

    def cells(self) -> list[tuple[int, int, int]]:
        """(row, column, character) for the six pieces, cut at the right edge
        as 0x492E cuts them."""
        self._hang()
        out = []
        for piece in self.pieces:
            if piece[0] == NUCLEUS:
                width, height, _, chars = self.art.nuclei[piece[6]]
            elif piece[0] == ARM:
                width, height, _, chars = self.art.arms[piece[6]]
            else:
                continue
            top, left = piece[3] >> 3, piece[5] >> 3
            for r in range(height):
                for c in range(width):
                    if left + c < 32:
                        out.append((top + r, left + c, chars[r * width + c]))
        return out

    # -- being shot (0x760E) ------------------------------------------------------------

    def meets(self, row: int, col: int, laser_cols: int = 0) -> int | None:
        """0x7688 with 0x75FD: the first piece whose box the shot is in."""
        for n, piece in enumerate(self.pieces):
            if piece[0] == NUCLEUS:
                rows, cols = NUCLEUS_BOXES[min(piece[1], 2)]
                y, x = piece[3], piece[5]
            elif piece[0] == ARM:
                rows, cols = ARM_BOX
                dy, dx = self.art.centres[piece[6]]
                y, x = (piece[3] + dy + ARM_CENTRE_DY) & 0xFF, (piece[5] + dx) & 0xFF
            else:
                continue
            a = (y - row) & 0xFF
            if not (a < SHOT_ROWS or a + rows > 0xFF):
                continue
            a = (x - col) & 0xFF
            if a < (laser_cols or SHOT_COLS) or a + cols > 0xFF:
                return n
        return None

    def hit(self, n: int, laser: bool) -> None:
        """0x773F: the piece loses four or one, and may burst."""
        piece = self.pieces[n]
        sounds = self.objects.world.sounds
        piece[9] = (piece[9] - (LASER_TAKES if laser else SHOT_TAKES)) & 0xFF
        left = (piece[9] - 1) & 0xFF
        if piece[0] == NUCLEUS:
            if left & 0x80:
                sounds.append(BURST_SOUND)
                self._burst(n, NUCLEUS_POINTS)
                self._burst(n + 1, ARM_POINTS)
                self._burst(n + 2, ARM_POINTS)
                return
            piece[1] = 2 if left < HURTER else 1 if left < HURT else 0
            sounds.append(HIT_SOUND)
        elif piece[0] == ARM:
            if not left & 0x80:
                sounds.append(HIT_SOUND)
                return
            sounds.append(BURST_SOUND)
            self._burst(n, ARM_POINTS)

    def _burst(self, n: int, points: int) -> None:
        """0x77E6 and 0x77C8."""
        piece = self.pieces[n]
        if not piece[0]:
            return
        self.objects.world.score += points
        piece[0] = 0
        self.objects.blast_at(piece[3], piece[5])
