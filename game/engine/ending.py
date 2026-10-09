"""How a stage ends: stage 1's eruption and its boss, the core.

Bank 1, 0x6CEF ("end of stage 1"), in four steps counted in 0xE065:

0. when the scroll stops at the stage's limit, the volcanoes erupt: 0x1C2
   rocks (type 0x0F), one every other game frame (0x70D6);
1. once the last is out, the scroll runs on to 0x1C0;
2. when it stops again, the boss comes (0xE151);
3. once the boss is done (0xE150), the next stage.

The boss is the core (0x7C8D): it waits for the screen to empty, loads its
characters over the stage's (0x4A6D), slides in, rides up and down towards
the ship firing four shots at each turn, opens its mouth for a while -- the
only time its eye can be hit -- and leaves or blows up.

At distance 0x165 comes the red crystal (0x8E77): five pieces drawn with
characters, ten hits each, firing to the left, riding the scroll off.
"""

from dataclasses import dataclass

from game.engine.flocks import Flocks
from game.engine.eye import Eye
from game.engine.fade import Fade
from game.engine.fortress import Fortress
from game.engine.nuclei import Nuclei
from game.engine.target import AFTER_BONUS, BONUS
from game.engine.objects import BLAST, Objects
from game.engine.tables import EndingArt
from game.engine.terrain import Map


def art(objects: Objects) -> EndingArt:
    """Stages 1-4's tables, out of the cartridge."""
    assert objects.tables.ending is not None
    return objects.tables.ending

#: The eruption: 0x1C2 rocks, from its two mouths in turn (0x7189), at one
#: of eight speeds (0x718D) upwards, halved for the first 30 (0x7156), every
#: other one mirrored.
ERUPTION_ROCKS, ERUPTION_HALF_UNTIL = 0x1C2, 0x1A4
ERUPTION_SOUND_AT, ERUPTION_SOUND = 0x1C1, 0x32
ROCK = 0x0F

#: The core's first card (0x7ED9): row 0x40, column 0xF8, its mouth shut,
#: 0x16 hits, its step clock at 1.
CORE_ROW, CORE_COL, CORE_LIFE = 0x40, 0xF8, 0x16
#: It slides in eight a step every eight game frames to column 0x98, then
#: stays 0x2D0 game frames: the mouth opens at 0x258 left and shuts at 0x78.
CORE_STOP, CORE_STAY, CORE_OPEN, CORE_SHUT = 0x98, 0x2D0, 0x258, 0x78
CORE_LEAVE, CORE_GONE = 0x28, 0x78
#: Its turns: ten or so steps of eight rows, every five, four or three game
#: frames by difficulty, turning back at rows 0x10 and 0x78 (0x7E0B).
CORE_STEPS, CORE_TOP, CORE_BOTTOM = 0x0B, 0x10, 0x78
#: Its four shots: from these offsets of its row and column, drawn with two
#: characters, 0xFA00 less 0x20 a difficulty step to the left (0x7DA8).
#: Its eye can be hit only by a normal shot or a laser, in the band 0x1D-0x24
#: below its row (0x7827), and pays 5 every fourth hit, 0x100 when it dies.
EYE_TOP, EYE_BAND = 0x1C, 8
#: Points are added in BCD (0x55B4): 0x0100 is a hundred.
CORE_POINTS, EYE_POINTS = 100, 5
#: The body is 11 x 8 characters; the eye and the mouth 3 x 2 each, at (0x18,
#: 8) and (0x18, 0x20) from its corner (0x7E70).
BODY_W, BODY_H, PART_W, PART_H = 11, 8, 3, 2
EYE_AT, MOUTH_AT = (0x18, 0x08), (0x18, 0x20)
#: The box a shot is looked for in, around the core (0x76A0, 0x7636).
BOX_ROWS, BOX_COLS, BOX_SHOT_ROWS, BOX_SHOT_COLS = 0x40, 0x58, 0x02, 0x10
BOSS_SOUND, EYE_SOUND, BOUNCE_SOUND = 0x3B, 0x0D, 0x06
#: From the second round, each time the player fires with none left to go,
#: six more shots, one a game frame, aimed from 0x1C below and 8 right of
#: its corner at speed 0x60, into the six slots past its four (0x7D6A).
CORE_BURST, CORE_BURST_SPEED, CORE_BURST_AT, CORE_BURST_SLOTS = 6, 0x60, (0x1C, 8), 4


@dataclass
class CoreArt:
    """The core's drawings, out of the cartridge: 88 body characters, the
    eye's seven and the mouth's three drawings of six."""

    body: tuple[int, ...]
    eyes: tuple[int, ...]
    mouths: tuple[int, ...]


class Core:
    def __init__(self, objects: Objects) -> None:
        self.objects = objects
        self.step = 0
        self.clock = 0x1E
        self.row, self.col = CORE_ROW, CORE_COL
        self.alive = False
        self.dead = False
        self.face = 1
        self.life = CORE_LIFE
        self.moving = False
        self.going_down = False
        self.steps = 0
        self.step_clock = 1
        #: The characters are loaded (0x4A6D) once the screen is empty.
        self.needs_art = False
        self.done = False
        #: The boss's first game frame is only counted (0x7C4F).
        self.starting = True

    def update(self, ship_row: int, frames: int, difficulty: int) -> None:
        """0x7C8D, a game frame."""
        if self.starting:
            self.starting = False
            return
        if self.step == 0:
            self._wait_for_empty()
        elif self.step == 1:
            if frames & 7:
                return
            self.col -= 8
            if self.col == CORE_STOP:
                self.clock, self.face = CORE_STAY, 1
                self.step = 2
        elif self.step == 2:
            self._stay(ship_row, difficulty)
        elif self.step == 3:
            self.clock -= 1
            if self.clock:
                return
            self.alive = False
            self.objects.world.sounds.append(BOSS_SOUND)
            if self.dead:
                self.objects.world.score += CORE_POINTS
            # 0x7D3E: a background blast.
            self.objects.blast_at(self.row + 0x08, self.col + 0x18)
            self.clock = CORE_GONE
            self.step = 4
        elif self.step == 4:
            self.clock -= 1
            if not self.clock:
                self.done = True

    def _wait_for_empty(self) -> None:
        self.clock -= 1
        if self.clock:
            return
        if any(s.type for s in self.objects.slots + self.objects.shots):
            self.clock = 1
            return
        self.needs_art = True
        for s in self.objects.slots + self.objects.shots:
            s.data[:] = bytes(len(s.data))
        self.objects.alive = 0
        self.alive = True
        self.clock = 0x3C
        self.step = 1

    def _stay(self, ship_row: int, difficulty: int) -> None:
        """0x7CFC."""
        if self.dead:
            self._leave()
            return
        self._move(ship_row, difficulty)
        self._burst()
        self.clock -= 1
        if self.clock == CORE_OPEN:
            self.face = 0
        elif self.clock == CORE_SHUT:
            self.face = 1
        elif not self.clock:
            self._leave()

    #: 0xE78C: the burst's shots left.
    burst = 0

    def _burst(self) -> None:
        """0x7D6A."""
        world = self.objects.world
        if not world.round:
            return
        if not self.burst:
            if world.fire_pressed:
                self.burst = CORE_BURST
            return
        self.burst -= 1
        row = (self.row + CORE_BURST_AT[0]) & 0xFF
        col = (self.col + CORE_BURST_AT[1]) & 0xFF
        vy, vx, _ = self.objects._aim(row, col, CORE_BURST_SPEED)
        free = next((s for s in self.objects.shots[CORE_BURST_SLOTS:] if not s[0]), None)
        if free is not None:
            self.objects.mount_shot(free, row, col, vy, vx)

    def _leave(self) -> None:
        self.face = 2
        self.clock = CORE_LEAVE
        self.step = 3

    def _move(self, ship_row: int, difficulty: int) -> None:
        """0x7E0B."""
        if not self.moving:
            self.moving = True
            self.steps = self.objects.rng.randrange(4)
            self.going_down = ship_row >= (self.row + 0x18) & 0xFF
            self._fire(difficulty)
            return
        self.step_clock -= 1
        if self.step_clock:
            return
        self.step_clock = 5 if difficulty < 4 else 4 if difficulty < 0x0A else 3
        self.steps += 1
        if self.steps == CORE_STEPS:
            self.moving = False
            return
        self.row = (self.row + (8 if self.going_down else -8)) & 0xFF
        if self.row < CORE_TOP:
            self.going_down = True
        elif self.row >= CORE_BOTTOM:
            self.going_down = False

    def _fire(self, difficulty: int) -> None:
        """0x7DA8: the first four of the ten enemy-shot slots, whatever was
        in them."""
        speed = (0xFA00 - (difficulty + 1) * 0x20) & 0xFFFF
        shots = art(self.objects).core_shots
        for n, (dy, dx) in enumerate(shots):
            s = self.objects.shots[n]
            s.data[:] = bytes(len(s.data))
            s[0] = 1
            s[4] = self.row + dy
            s[6] = self.col + dx
            s.set_word(9, speed)
            s[11] = 2 + ((len(shots) - n) & 1)
            s[27] = 1

    def _blast(self, row: int, col: int) -> None:
        s = self.objects.slots[0]
        s[0], s[2], s[27] = BLAST, 0, 0
        s[4], s[6] = row & 0xFF, col & 0xFF
        s[11], s[14], s[17] = 0, 0, 0

    # -- being shot (0x760E) -------------------------------------------------------

    def box(self, shot_row: int, shot_col: int, laser_cols: int = 0) -> bool:
        """0x75FD with the core's box (0x40 rows by 0x58 columns) and a
        shot's (2 by 0x10, or across a laser's length: 0x767B)."""
        if not self.alive or self.dead:
            return False
        a = (self.row - shot_row) & 0xFF
        if not (a < BOX_SHOT_ROWS or a + BOX_ROWS > 0xFF):
            return False
        a = (self.col - shot_col) & 0xFF
        return a < (laser_cols or BOX_SHOT_COLS) or a + BOX_COLS > 0xFF

    def hit(self, kind: int, shot_row: int) -> bool:
        """0x7827: whether the shot is spent (never a laser's)."""
        if not kind & 1:
            return False
        if (self.face or self.dead
                or ((self.row + EYE_TOP - shot_row) & 0xFF) + EYE_BAND <= 0xFF):
            # 0x788C: off the eye, only the laser sounds.
            if kind == 3:
                self.objects.world.sounds.append(BOUNCE_SOUND)
            return False
        self._blast(self.row + 0x18, self.col + 0x0C)
        self.life -= 1
        if not self.life:
            self.dead = True
        elif self.life & 3 == 3:
            self.objects.world.score += EYE_POINTS
        self.objects.world.sounds.append(EYE_SOUND)
        return kind != 3

    # -- drawn into the map (0x7E70) ---------------------------------------------

    def cells(self, art: CoreArt) -> list[tuple[int, int, int]]:
        """(row, column, character) for the body, the eye and the mouth, in
        cells; what falls off the screen is not drawn. The rectangles are
        copied whole (0x490C), their empty characters too: the stars under
        the core are wiped, and 0x7EC8 clears the body's rectangle after."""
        out: list[tuple[int, int, int]] = []
        if not self.alive:
            return out

        def rect(dy: int, dx: int, w: int, h: int, chars: tuple[int, ...]) -> None:
            y, x = (self.row + dy) & 0xFF, (self.col + dx) & 0xFF
            if (self.col + dx) > 0xFF:
                return
            for r in range(h):
                for c in range(w):
                    col = x // 8 + c
                    if col < 32:
                        out.append((y // 8 + r, col, chars[r * w + c]))

        rect(0, 0, BODY_W, BODY_H, art.body)
        eye = ((self.life >> 1) & 0x0E) * 3
        rect(*EYE_AT, PART_W, PART_H, art.eyes[eye:eye + 6])
        mouth = self.face * 6
        rect(*MOUTH_AT, PART_W, PART_H, art.mouths[mouth:mouth + 6])
        return out


#: The crystal (0x8E77): at its distance (the stages' `crystal`), five pieces
#: at their rows and columns (0x8EBA), each drawn as two characters -- the
#: middle one as two rows of two (0x9060..) -- ten hits each (0x8EA8).
CRYSTAL_HITS = 10
#: A piece blown up shows 0x68 and 0x69 in turn, four game frames each
#: (0x8F08, reading 0x8FE4 + 0x78..0x7B).
#: They fire every 0x5C less four a difficulty step game frames: from 0x18
#: to a piece's left, four to the left a frame, drawn with characters 0x58
#: (or 0x60 for the last two) (0x8F5D).
CRYSTAL_EVERY, CRYSTAL_FIRE_DX, CRYSTAL_FIRES_FROM = 0x5C, 0x18, 0x30


@dataclass
class Piece:
    n: int
    row: int
    col: int
    hits: int = CRYSTAL_HITS
    #: None while whole; the blast's step once hit to pieces.
    blast: int | None = None
    clock: int = 0


class Crystal:
    """0xEB00, and 0xE1B0-0xE1B6."""

    def __init__(self, objects: Objects, difficulty: int) -> None:
        self.objects = objects
        self.pieces: list[Piece | None] = [
            Piece(n, r, c) for n, (r, c) in enumerate(art(objects).crystal_pieces)]
        self.group_col = 0xF8
        self.every = (CRYSTAL_EVERY - 4 * difficulty) & 0xFF
        self.clock = self.every
        self.gone = False
        self.saved: list[tuple[int, int, int]] = []

    def update(self, moved: bool) -> None:
        """0x8EC4."""
        if moved:
            self.group_col -= 8
            if self.group_col < 0:
                self.gone = True
                return
        for n, piece in enumerate(self.pieces):
            if piece is None:
                continue
            if moved:
                piece.col -= 8
                if piece.col < 0:
                    self.pieces[n] = None
                    continue
            if piece.blast is not None:
                piece.clock += 1
                if piece.clock >= 4:
                    piece.clock = 0
                    piece.blast += 1
                    if piece.blast >= len(art(self.objects).crystal_blast):
                        self.pieces[n] = None
        self.clock -= 1
        if self.clock:
            return
        self.clock = self.every
        for piece in self.pieces:
            if piece is not None and piece.blast is None and piece.col >= CRYSTAL_FIRES_FROM:
                self._fire(piece)

    def _fire(self, piece: Piece) -> None:
        free = next((s for s in self.objects.shots if not s.type), None)
        if free is None:
            return
        free.data[:] = bytes(len(free.data))
        free[0] = 1
        free[4], free[6] = piece.row, (piece.col - CRYSTAL_FIRE_DX) & 0xFF
        free.set_word(9, 0xFC00)
        free[11] = 4 if piece.n < 3 else 5
        free[27] = 1

    def hit(self, piece: Piece) -> None:
        """0x7208 with the enemies' rules: a point and a blast at ten hits."""
        piece.hits -= 1
        if piece.hits:
            return
        self.objects.world.score += 1
        self.objects.world.sounds.append(self.objects.tables.kill_sounds[1])
        piece.blast, piece.clock = 0, 0

    def cells(self) -> list[tuple[int, int, int]]:
        out = []
        for piece in self.pieces:
            if piece is None:
                continue
            row, col = piece.row // 8, piece.col // 8
            if piece.blast is not None:
                out.append((row, col, art(self.objects).crystal_blast[piece.blast]))
                continue
            chars = art(self.objects).crystal_chars[piece.n]
            out += [(row, col, chars[0]), (row, col + 1, chars[1])]
            if len(chars) > 2:
                out += [(row + 1, col, chars[2]), (row + 1, col + 1, chars[3])]
        return [(r, c, ch) for r, c, ch in out if 0 <= c < 32]

    def draw(self, terrain: Map) -> list[tuple[int, int, int]]:
        """0x8FFE: into the map, what was there kept to be put back."""
        cells = [(r, c, ch) for r, c, ch in self.cells() if terrain.inside(r, c)]
        self.saved = [(r, c, terrain[r, c]) for r, c, _ in cells]
        for r, c, ch in cells:
            terrain[r, c] = ch
        return cells

    def restore(self, terrain: Map) -> None:
        for r, c, ch in reversed(self.saved):
            terrain[r, c] = ch
        self.saved = []


#: Stage 2's end (0x6D66): a rain of stones for 0x384 game frames, one every
#: 0x14 less the difficulty, through one of sixteen doors at random (0xAB86),
#: then the scroll on to the stage's boss limit and the core.
RAIN_FRAMES, RAIN_EVERY, STONE = 0x384, 0x14, 8


#: Stage 3's boss (0x839F): heads of 4x4 characters (0x86F1, mouth open
#: 0x8701), one every 0x3C less two a difficulty step game frames for
#: (0x14 + difficulty) x 0x1E of them, in four lanes (0x8458) of at most two,
#: each chasing the ship inside its lane (0x857B, 0x857F) and firing threes
#: (type 0x0B) after a warning, ten hits apiece at four a normal shot.
HEAD_LIFE, HEAD_STAY, HEAD_SLOTS, HEAD_POINTS = 0x28, 0x1E, 8, 30
HEAD_THREE = 0x0B
#: The other boss (0x83A5, boss 6 of 0x7C41): from the second round, at
#: distance 0x60 exactly (0x6DCD), one head alone. Its byte 14 is 4 (the
#: lane counted is 0xE15F, none of the four), which runs it on the fast
#: motor: it stays 0xF0 game frames and takes 0x3C hits (0x83BE, 0x83C2);
#: every other game frame four towards the ship's row, between rows 0x00
#: and 0x90 (0x85C6), and, on the others, four towards a column 0x40 ahead
#: of it, up to 0xF0 (0x85FB); done, it leaves four a game frame (0x8629).
OTHER_BOSS_AT, FAST_LANE, FAST_STAY, FAST_LIFE = 0x60, 4, 0xF0, 0x3C
FAST_STEP, FAST_FLOOR, FAST_AHEAD, FAST_RIGHT = 0x400, 0x90, 0x40, 0xF0


@dataclass
class Head:
    lane: int
    row: int
    col: int = 0xF8 << 8
    step: int = 0
    drawing: int = 0
    shot_step: int = 0
    shot_clock: int = 1
    warn: int = 0
    life: int = HEAD_LIFE
    stay: int = HEAD_STAY
    fast: bool = False

    @property
    def x(self) -> int:
        return self.col >> 8

    @property
    def y(self) -> int:
        return self.row >> 8


class Heads:
    """0x83D1 ("the boss's step") and 0x84C0 ("run the eight pieces")."""

    #: 0xE152 while these are on.
    boss = 1
    waits_for_blasts = True

    def __init__(self, objects: Objects, difficulty: int) -> None:
        self.objects = objects
        self.heads: list[Head | None] = [None] * HEAD_SLOTS
        self.clock = (difficulty + 0x14) * 0x1E
        self.every = (0x3C - 2 * difficulty) & 0xFF
        self.next = self.every
        self.previous = 0
        #: 0xE15B..0xE15F: the heads in each lane, and the fast one's.
        self.in_lane = [0, 0, 0, 0, 0]
        #: The boss's first game frame is only counted (0x7C4F), and its
        #: step 0 only sets the clocks (0x83DA): two game frames of nothing.
        self.starting = 2
        self.releasing = True
        self.done = False

    def update(self, ship_row: int, ship_col: int, difficulty: int) -> None:
        if self.starting:
            self.starting -= 1
            return
        if self.releasing:
            self.clock -= 1
            if not self.clock:
                self.releasing = False
            else:
                self.next -= 1
                if not self.next:
                    self.next = self.every
                    self._release()
        elif not any(self.heads) and not (self.waits_for_blasts and self.objects.blasts.any()):
            # 0x845C: no piece left and no background blast (0x84AC).
            self.done = True
        for n, head in enumerate(self.heads):
            if head is not None and self._run(head, ship_row, ship_col, difficulty):
                self.in_lane[head.lane] -= 1
                self.heads[n] = None

    def _release(self) -> None:
        """0x841A: a free slot, a lane by R other than the last and not full."""
        if None not in self.heads:
            return
        lane = self.objects.rng.randrange(4)
        for _ in range(4):
            if lane != self.previous and self.in_lane[lane] < 2:
                break
            lane = (lane + 1) & 3
        else:
            return
        self.in_lane[lane] += 1
        self.previous = lane
        self.heads[self.heads.index(None)] = Head(lane, art(self.objects).head_lanes[lane] << 8)

    def _run(self, head: Head, ship_row: int, ship_col: int, difficulty: int) -> bool:
        """0x84D9. True once it has gone."""
        if head.step == 0:
            head.col -= 0x100
            if head.x < 0xE1:
                head.step = 1
            return False
        if head.step == 1:
            head.stay -= 1
            if not head.stay:
                head.drawing = 0
                head.step = 2
                return False
            self._fire(head, difficulty)
            if head.fast:
                self._chase_row_fast(head, ship_row)
                return self._chase_col_fast(head, ship_col)
            self._chase_row(head, ship_row)
            return self._chase_col(head, ship_col, difficulty)
        if head.fast:
            return self._leave_fast(head)
        head.col -= 0x100
        return head.col < 0

    def _chase_row_fast(self, head: Head, ship_row: int) -> None:
        """0x85C6: on even stays, four towards the ship's row."""
        if head.stay & 1:
            return
        if ((ship_row - head.y + 8) & 0xFF) < 0x11:
            return
        if ship_row >= head.y:
            head.row += FAST_STEP
            if head.y > FAST_FLOOR:
                head.row = FAST_FLOOR << 8 | head.row & 0xFF
        else:
            # 0x85EC: the roof is row 0, and a row past it wraps and stays.
            head.row = (head.row - FAST_STEP) & 0xFFFF

    def _chase_col_fast(self, head: Head, ship_col: int) -> bool:
        """0x85FB: on odd stays, four towards a column 0x40 ahead of it."""
        if not head.stay & 1:
            return False
        c = abs(head.x - FAST_AHEAD)
        if ((ship_col - c + 8) & 0xFF) < 0x11:
            return False
        if ship_col >= c:
            head.col += FAST_STEP
            if head.x >= FAST_RIGHT:
                head.col = FAST_RIGHT << 8 | head.col & 0xFF
            return False
        return self._leave_fast(head)

    def _leave_fast(self, head: Head) -> bool:
        """0x8629: four to the left; past the edge, gone."""
        head.col -= FAST_STEP
        return head.col < 0

    def _fire(self, head: Head, difficulty: int) -> None:
        """0x8654."""
        if head.shot_step == 0:
            head.shot_clock -= 1
            if head.shot_clock:
                return
            if self.objects.alive >= 0x0A:
                head.shot_clock = (0x22 - 2 * difficulty) & 0xFF
                return
            head.warn, head.drawing, head.shot_step = 0x0A, 1, 1
        elif head.shot_step == 1:
            head.warn -= 1
            if head.warn:
                return
            head.warn = 0x0A
            for n in (3, 2, 1):
                self.objects.three = n
                if head.x >= 8:
                    self.objects.make(HEAD_THREE, (head.y + 8) & 0xFF, head.x - 8)
            head.shot_step = 2
        else:
            head.warn -= 1
            if head.warn:
                return
            head.drawing = head.shot_step = 0
            head.shot_clock = (0x22 - 2 * difficulty) & 0xFF

    def _chase_row(self, head: Head, ship_row: int) -> None:
        """0x852F: every eight frames of its stay, two towards the ship's row."""
        if head.stay & 7:
            return
        gap = (ship_row - head.y) & 0xFF
        if (gap + 8) & 0xFF < 0x11:
            return
        if ship_row >= head.y:
            floor = art(self.objects).head_floors[head.lane]
            head.row = min(head.row + 0x200, floor << 8 | head.row & 0xFF)
        else:
            roof = art(self.objects).head_roofs[head.lane]
            head.row = max(head.row - 0x200, roof << 8 | head.row & 0xFF)

    def _chase_col(self, head: Head, ship_col: int, difficulty: int) -> bool:
        """0x8583: every four frames, two towards a column ahead of the
        ship; leaving by the left edge, gone."""
        if (head.stay & 3) != 1:
            return False
        margin = (0x60 - 4 * difficulty) & 0xFF
        c = abs(head.x - margin)
        target = ship_col - c
        if abs(target) < 9:
            return False
        if target >= 0:
            head.col = min(head.col + 0x200, 0xF0 << 8)
            return False
        head.col -= 0x200
        return head.col < 0

    def meets(self, row: int, col: int, laser_cols: int = 0) -> Head | None:
        """0x76A4 with 0x75FD: a box by its step."""
        for head in self.heads:
            if head is None:
                continue
            # 0x76D5: a piece of type 2 is met in a box of 0x20 by 0x20.
            rows, cols = 0x20, 0x20
            a = (head.y - row) & 0xFF
            if not (a < 2 or a + rows > 0xFF):
                continue
            a = (head.x - col) & 0xFF
            if a < (laser_cols or 0x10) or a + cols > 0xFF:
                return head
        return None

    def hit(self, head: Head, laser: bool) -> None:
        """0x774B / 0x777F."""
        head.life -= 1 if laser else 4
        if head.life - 1 >= 0:
            self.objects.world.sounds.append(BOUNCE_SOUND)
            return
        self.objects.world.score += HEAD_POINTS
        self.objects.world.sounds.append(0x0E)
        self.objects.blast_at(head.y, head.x)
        self.in_lane[head.lane] -= 1
        self.heads[self.heads.index(head)] = None

    def cells(self) -> list[tuple[int, int, int]]:
        out = []
        for head in self.heads:
            if head is None:
                continue
            chars = art(self.objects).head_chars[head.drawing]
            for r in range(4):
                for c in range(4):
                    col = head.x // 8 + c
                    if col < 32:
                        out.append((head.y // 8 + r, col, chars[r * 4 + c]))
        return out


class LoneHead(Heads):
    """0x83AB ("start or end the boss") and 0x84BB ("run a piece"): the
    other boss, one fast head in the first slot; done once it is empty."""

    boss = 6
    #: 0x83C8 looks at its slot only.
    waits_for_blasts = False

    def __init__(self, objects: Objects) -> None:
        super().__init__(objects, 0)
        self.releasing = False
        self.starting = 0
        #: 0xE151 at 1, then 0xE190's step 0, then running.
        self.step = 0

    def update(self, ship_row: int, ship_col: int, difficulty: int) -> None:
        if self.step == 0:
            # 0x7C4F: the boss's first game frame only counts it in.
            self.step = 1
            return
        if self.step == 1:
            # 0x8426 puts it in the lane 0xE159 says, which the last run of
            # the slots left at 0.
            self.step = 2
            self.in_lane[FAST_LANE] += 1
            self.heads[0] = Head(FAST_LANE, art(self.objects).head_lanes[0] << 8, stay=FAST_STAY,
                                 life=FAST_LIFE, fast=True)
        super().update(ship_row, ship_col, difficulty)


#: Stage 4's boss (0x8CE4): for 0x258 game frames, one every 0x48 less two a
#: difficulty step, pieces of 4x3 blinking characters (0x8E5F, 0x8E6B) that
#: fly a fixed route (0x8D7C..0x8E14), ten hits apiece.
WALKER_LIFE, WALKER_POINTS, WALKER_TIME = 0x28, 10, 0x258
#: The game's ending: the ship leaves at 0x300, 0x40 faster a game frame,
#: to the sound 0x41, and is gone past column 0xF0 (0x6F78, 0x4AE1, 0x4AF1).
LEAVING_SPEED, LEAVING_MORE, LEAVING_SOUND, GONE_PAST = 0x0300, 0x0040, 0x41, 0xF0
#: Stage 8's boss comes at distance 0x16E (0x6F50).
STAGE_8_BOSS_AT = 0x16E
#: Stage 6's boss comes at distance 0xA0 (0x6EFD).
STAGE_6_BOSS_AT = 0xA0
#: Stage 4's rush: 0xB4 rocks from the roof, at column 0xD0 riding the
#: scroll (0x6E15); where it starts is the stages' `rush`.
STAGE_4_RUSH, STAGE_4_RUSH_COL = 0xB4, 0xD0


@dataclass
class Walker:
    row: int = 0x18
    col: int = 0xF8
    step: int = 0
    life: int = WALKER_LIFE


class Walkers:
    def __init__(self, objects: Objects, difficulty: int) -> None:
        self.objects = objects
        self.walkers: list[Walker | None] = [None] * HEAD_SLOTS
        self.clock = WALKER_TIME
        self.every = self.next = (0x48 - 2 * difficulty) & 0xFF
        #: The boss's first game frame is only counted (0x7C4F), and its
        #: step 0 only sets the clocks (0x8CF3): two game frames of nothing.
        self.starting = 2
        self.releasing = True
        self.done = False

    def update(self, ship_row: int, frames: int) -> None:
        if self.starting:
            self.starting -= 1
            return
        if self.releasing:
            self.clock -= 1
            if not self.clock:
                self.releasing = False
            else:
                self.next -= 1
                if not self.next:
                    self.next = self.every
                    if None in self.walkers:
                        self.walkers[self.walkers.index(None)] = Walker()
        elif not any(self.walkers) and not self.objects.blasts.any():
            # 0x8D39: no piece left and no background blast (0x84AC).
            self.done = True
        for n, w in enumerate(self.walkers):
            if w is not None and self._leg(w, ship_row):
                self.walkers[n] = None

    def _leg(self, w: Walker, ship_row: int) -> bool:
        """0x8D59. True once gone."""
        route = art(self.objects).walker_route
        if w.step < len(route):
            dy, dx, axis, value = route[w.step]
            w.row, w.col = (w.row + dy) & 0xFF, (w.col + dx) & 0xFF
            if (w.col if axis == "x" else w.row) == value:
                w.step += 1
            return False
        if w.step == len(route):
            # 0x8DF0: towards the ship's row until level, or out of 0x30-0x88.
            gap = (ship_row - w.row) & 0xFF
            if (gap + 8) & 0xFF < 0x11:
                w.step += 1
                return False
            w.row = (w.row + (-2 if ship_row < w.row else 2)) & 0xFF
            if (w.row - 0x30) & 0xFF >= 0x58:
                w.step += 1
            return False
        w.col = (w.col - 2) & 0xFF
        return w.col >= 0xF0

    def meets(self, row: int, col: int, laser_cols: int = 0) -> Walker | None:
        """0x76EB: 0x18 rows by 0x20 columns."""
        for w in self.walkers:
            if w is None:
                continue
            a = (w.row - row) & 0xFF
            if not (a < 2 or a + 0x18 > 0xFF):
                continue
            a = (w.col - col) & 0xFF
            if a < (laser_cols or 0x10) or a + 0x20 > 0xFF:
                return w
        return None

    def hit(self, w: Walker, laser: bool) -> None:
        """0x7773."""
        w.life -= 1 if laser else 4
        if w.life - 1 >= 0:
            self.objects.world.sounds.append(BOUNCE_SOUND)
            return
        self.objects.world.score += WALKER_POINTS
        self.objects.world.sounds.append(0x0E)
        self.objects.blast_at(w.row, w.col)
        self.walkers[self.walkers.index(w)] = None

    def cells(self, frames: int) -> list[tuple[int, int, int]]:
        out = []
        chars = art(self.objects).walker_chars[1 if frames & 4 else 0]
        for w in self.walkers:
            if w is None:
                continue
            for r in range(3):
                for c in range(4):
                    col = w.col // 8 + c
                    if col < 32:
                        out.append((w.row // 8 + r, col, chars[r * 4 + c]))
        return out


class Ending:
    """0x6CEF for stage 1, 0x6D66 for stage 2, 0x6DA7 for stage 3, 0x6E15
    for stage 4."""

    def __init__(self, objects: Objects, stage: int) -> None:
        self.objects = objects
        self.stage = stage
        #: Where the ends' crystal comes and their scroll stops.
        self.distances = objects.tables.stages
        self.step = 0
        #: 0xE140 and 0xE148: the eruption on, and the rocks left.
        self.erupting = False
        self.rocks = 0
        self.core: Core | None = None
        #: 0xE1B0: the crystal.
        self.crystal: Crystal | None = None
        self.crystal_done = False
        #: The scroll's limit, when this moves it.
        self.limit: int | None = None
        self.next_stage = False
        if stage == 5 and objects.tables.flocks is not None:
            self.flocks = Flocks(objects, objects.tables.flocks)

    #: 0x6FB9: the stage the game jumps to, when it does.
    jump_to: int | None = None
    raining = 0
    rain_every = 0
    rain_clock = 0

    def update(self, stopped: bool, frames: int, distance: int = 0,
               difficulty: int = 0, alive: bool = True, target: bool = False) -> None:
        if self.stage in AFTER_BONUS:
            # 0x6F97..0x6FB2: at the end of a bonus stage, back.
            if stopped:
                self.jump_to = AFTER_BONUS[self.stage]
            return
        if target and self.stage in BONUS:
            # 0x6D66, 0x6DA7, 0x6E15, 0x6F19: the target taken, the stage
            # runs to its limit and the bonus stage follows.
            if stopped:
                self.jump_to = BONUS[self.stage]
            return
        if self.stage == 2:
            self._stage_2(stopped, difficulty)
            return
        if self.stage == 3:
            self._stage_3(stopped, difficulty, distance)
            return
        if self.stage == 4:
            self._stage_4(stopped, distance, difficulty)
            return
        if self.stage == 7 and self.objects.tables.spit_speeds:
            self._stage_7(stopped)
            return
        if self.stage == 8 and self.objects.tables.fortress is not None:
            self._stage_8(distance, alive)
            return
        if self.stage == 6 and self.objects.tables.nucleus is not None:
            self._stage_6(distance)
            return
        if self.stage == 5 and self.flocks is not None:
            self._stage_5(stopped, difficulty)
            return
        if self.stage != 1:
            # Stages 5-8 on tables without their bosses' (a test's): no end.
            return
        if self.step == 0:
            if self.crystal is not None:
                # 0x6D20: once the crystal has ridden off, it is over.
                if self.crystal.gone:
                    self.crystal = None
                return
            if distance == self.distances.crystal.get(1) and not self.crystal_done:
                self.crystal_done = True
                self.crystal = Crystal(self.objects, difficulty)
                return
            if stopped:
                self.erupting, self.rocks = True, ERUPTION_ROCKS
                self.step = 1
        elif self.step == 1:
            if not self.erupting:
                self.limit = self.distances.boss[1]
                self.step = 2
        elif self.step == 2:
            if stopped:
                self.core = Core(self.objects)
                self.step = 3
        elif self.step == 3 and self.core is not None and self.core.done:
            self.core = None
            self.next_stage = True

    def _rush_over(self) -> None:
        self.erupting = False
        self.rocks_done = True

    def _stage_2(self, stopped: bool, difficulty: int) -> None:
        if self.step == 0:
            if stopped:
                self.raining = RAIN_FRAMES
                self.rain_every = self.rain_clock = (RAIN_EVERY - difficulty) & 0xFF
                self.step = 1
        elif self.step == 1:
            if not self.raining:
                self.limit = self.distances.boss[2]
                self.step = 2
        elif self.step == 2:
            if stopped:
                self.core = Core(self.objects)
                self.step = 3
        elif self.step == 3 and self.core is not None and self.core.done:
            self.core = None
            self.next_stage = True

    heads: "Heads | None" = None

    def _stage_3(self, stopped: bool, difficulty: int, distance: int) -> None:
        if self.step == 0:
            if self.heads is not None:
                # 0x6DED: the other boss up, until it is done.
                if self.heads.done:
                    self.heads = None
                return
            if distance == OTHER_BOSS_AT:
                # 0x6DE1: from the second round, the other boss.
                if self.objects.world.round:
                    self.heads = LoneHead(self.objects)
                return
            if stopped:
                self.heads = Heads(self.objects, difficulty)
                self.step = 1
        elif self.step == 1:
            if self.heads is not None and self.heads.done:
                self.heads = None
                self.limit = self.distances.boss[3]
                self.step = 2
        elif self.step == 2:
            if stopped:
                self.core = Core(self.objects)
                self.step = 3
        elif self.step == 3 and self.core is not None and self.core.done:
            self.core = None
            self.next_stage = True

    walkers: "Walkers | None" = None
    #: 0xE140: which rush (1, stage 1's volcanoes; 2, one that rides the
    #: scroll from 0xE141).
    rush_kind = 1
    rush_col = 0

    def _stage_4(self, stopped: bool, distance: int, difficulty: int) -> None:
        if self.step == 0:
            if self.erupting:
                return
            if self.rocks_done:
                self.step = 1
                return
            if distance == self.distances.rush.get(4):
                self.erupting, self.rocks = True, STAGE_4_RUSH
                self.rush_kind, self.rush_col = 2, STAGE_4_RUSH_COL
        elif self.step == 1:
            if self.crystal is not None:
                if self.crystal.gone:
                    self.crystal = None
                return
            if distance == self.distances.crystal.get(4) and not self.crystal_done:
                self.crystal_done = True
                self.crystal = Crystal(self.objects, difficulty)
                return
            if stopped:
                self.walkers = Walkers(self.objects, difficulty)
                self.step = 2
        elif self.step == 2:
            if self.walkers is not None and self.walkers.done:
                self.walkers = None
                self.limit = self.distances.boss[4]
                self.step = 3
        elif self.step == 3:
            if stopped:
                self.core = Core(self.objects)
                self.step = 4
        elif self.step == 4 and self.core is not None and self.core.done:
            self.core = None
            self.next_stage = True

    rocks_done = False
    flocks: Flocks | None = None

    def _stage_5(self, stopped: bool, difficulty: int) -> None:
        """0x6EA8: the long flock, the big ones', then on to 0x1FF and the
        core."""
        flocks = self.flocks
        assert flocks is not None
        if self.step == 0:
            if stopped:
                flocks.start_long(difficulty)
                self.step = 1
        elif self.step == 1:
            if flocks.done:
                flocks.done, flocks.long_on = False, False
                flocks.start_big(difficulty)
                self.step = 2
        elif self.step == 2:
            if flocks.done:
                flocks.done, flocks.big_on = False, False
                self.limit = self.distances.boss[5]
                self.step = 3
        elif self.step == 3:
            if stopped:
                self.core = Core(self.objects)
                self.step = 4
        elif self.step == 4 and self.core is not None and self.core.done:
            self.core = None
            self.next_stage = True

    nuclei: Nuclei | None = None

    def _stage_6(self, distance: int) -> None:
        """0x6EF0: past distance 0xA0 the nuclei; once they are done the
        scroll stops where it is, and the core."""
        if self.step == 0:
            if distance >= STAGE_6_BOSS_AT:
                assert self.objects.tables.nucleus is not None
                self.nuclei = Nuclei(self.objects, self.objects.tables.nucleus)
                self.step = 1
        elif self.step == 1:
            if self.nuclei is not None and self.nuclei.done:
                self.nuclei = None
                self.limit = distance
                self.core = Core(self.objects)
                self.step = 2
        elif self.step == 2 and self.core is not None and self.core.done:
            self.core = None
            self.next_stage = True

    eye: Eye | None = None
    fortress: Fortress | None = None

    def _stage_7(self, stopped: bool) -> None:
        """0x6F19: the eye once the scroll has stopped."""
        if self.step == 0:
            if stopped:
                self.eye = Eye(self.objects, self.objects.tables.spit_speeds)
                self.step = 1
        elif self.step == 1 and self.eye is not None and self.eye.done:
            self.eye = None
            self.next_stage = True

    #: 0xE1D0/0xE1D3: the game's ending is on, and the ship's speed as it
    #: leaves; 0xE1D1 up: the ship is gone and the host's finale plays
    #: (game/finale.py) until it says it is over (0xE150).
    leaving: int | None = None
    finale = False
    finale_done = False

    def _stage_8(self, distance: int, alive: bool) -> None:
        """0x6F43: the fortress at distance 0x16E exactly; then, with the
        ship alive, the game's ending."""
        if self.step == 0:
            if distance == STAGE_8_BOSS_AT:
                assert self.objects.tables.fortress is not None
                self.fortress = Fortress(self.objects, self.objects.tables.fortress)
                self.step = 1
        elif self.step == 1 and self.fortress is not None:
            if self.fortress.limit is not None:
                self.limit = self.fortress.limit
            if self.fortress.done:
                self.fortress = None
                if not alive:
                    return
                # 0x6F72.
                self.leaving = LEAVING_SPEED
                self.objects.world.sounds.append(LEAVING_SOUND)
                self.step = 2
        elif self.step == 2 and self.finale_done:
            self.leaving = None
            self.next_stage = True

    def leave(self) -> None:
        """0x4ADE: faster every game frame."""
        assert self.leaving is not None
        self.leaving = (self.leaving + LEAVING_MORE) & 0xFFFF

    @property
    def music_frozen(self) -> bool:
        """0xE114: from the core, the eye, or the fortress's last count, the
        stage's music is left as it is (0x700D)."""
        return (self.core is not None or self.eye is not None or self.leaving is not None
                or (self.fortress is not None and self.fortress.step >= 5))

    @property
    def fade(self) -> "Fade | None":
        """The screen going dark, while it is."""
        if self.eye is not None and self.eye.step == 3:
            return self.eye.fade
        if self.fortress is not None and self.fortress.step == 5:
            return self.fortress.fade
        return None

    @property
    def boss(self) -> int | None:
        """0xE152 while 0xE151 is up: which boss of 0x7C41's table is on."""
        if self.core is not None:
            return 0
        if self.heads is not None:
            return self.heads.boss
        if self.nuclei is not None:
            return 2
        if self.eye is not None:
            return 3
        if self.fortress is not None:
            return 4
        if self.walkers is not None:
            return 5
        return None

    def rain(self) -> None:
        """0xABA3: a stone through one of the sixteen doors."""
        if not self.raining:
            return
        self.raining -= 1
        if not self.raining:
            return
        self.rain_clock -= 1
        if self.rain_clock:
            return
        self.rain_clock = self.rain_every
        doors = self.objects.tables.rain_doors
        row, col = doors[self.objects.rng.randrange(len(doors))]
        self.objects.make(STONE, row, col)

    def erupt(self, frames: int, moved: bool = False) -> None:
        """0x70D6: a rock every other game frame."""
        if not self.erupting:
            return
        if self.rush_kind == 2 and moved:
            self.rush_col -= 8
            if self.rush_col < 0:
                self._rush_over()
                return
        if frames & 1:
            return
        self.rocks -= 1
        if not self.rocks:
            self._rush_over()
            return
        if self.rush_kind == 1:
            if self.rocks == ERUPTION_SOUND_AT:
                self.objects.world.sounds.append(ERUPTION_SOUND)
            row, col = art(self.objects).eruption_from[self.rocks & 1]
        else:
            if self.rocks == 0xB3:
                self.objects.world.sounds.append(0x13)
            row, col = 0x20, self.rush_col
        vy, vx = art(self.objects).eruption_speeds[self.objects.rng.randrange(8)]
        if self.stage == 1:
            vy = -vy & 0xFFFF
        if self.rocks >= (ERUPTION_HALF_UNTIL if self.rush_kind == 1 else 0xA5):
            vy = (vy >> 1) | (vy & 0x8000)
            vx >>= 1
        if self.rocks & (2 if self.rush_kind == 1 else 1):
            vx = -vx & 0xFFFF
        self.objects.rock_speed = (vy, vx)
        self.objects.make(ROCK, row, col)
