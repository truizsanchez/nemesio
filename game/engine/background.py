"""The background objects: the hatches that let out bugs.

Bank 1: their script (0x62AD, table 0x64FA -- rows of distance and a byte, as
the cannons'), their step (0x6008), their drawing into the map (0x61E8) and
the shots against them (0x7898). Two slots of eight bytes at 0xE700 (stage 3
has eight and its own kinds, not here yet):

    0 kind (1 or 2, by bit 7 of the script's byte)   1 step
    2 row   3 column   4 clock   5 hits it takes   6 drawing   7 bugs left

A hatch lets out six bugs (type 7), one every eight game frames, upwards for
kind 1 and downwards for kind 2. It is a 4x4 of characters written into the
map, where the ship meets it as terrain, and it can be shot to pieces.
"""

from dataclasses import dataclass

from game.engine.objects import Objects
from game.engine.tables import GunArt
from game.engine.terrain import Map

SLOTS = 2
BUGS, BUG_EVERY, BUG = 6, 8, 7
#: A hatch placed while the screen fills waits longer before its first bug.
FIRST_WAIT, FIRST_WAIT_FILLING = 0x18, 0xFF
HITS = 0x0F
#: A normal shot takes five, a laser three and goes on (0x7AB0).
SHOT_DAMAGE, LASER_DAMAGE = 5, 3
POINTS, SOUND_HIT, SOUND_GONE = 10, 0x06, 0x0E
#: The box a shot meets it in (0x78E0): 0x22 rows from 2 above, and 8 columns
#: before it (a laser: its length) to 0x20 after.
BOX_ROWS, BOX_ABOVE, BOX_AFTER, BOX_LAST_COLUMN = 0x22, 2, 0x20, 0xE8
#: On stage 2, drawings from 2 on are twelve further along (0x61FD).
STAGE_2_SKIP = 12
SIZE = 4


@dataclass
class Hatch:
    kind: int
    row: int
    col: int
    clock: int
    hits: int = HITS
    drawing: int = 0
    bugs: int = BUGS


class Background:
    def __init__(self, objects: Objects, script: tuple[tuple[int, int], ...],
                 drawings: tuple[tuple[int, ...], ...], stage: int) -> None:
        self.objects = objects
        self.script = script
        self.drawings = drawings
        self.stage = stage
        self.hatches: list[Hatch | None] = [None] * SLOTS
        #: 0xE109: the script's next row.
        self.next = 0
        self.drawn: list[tuple[int, int]] = []

    # -- the script (0x62AD, 0x62C1) -------------------------------------------------

    def fill(self, distance: int, col: int) -> None:
        while self.next < len(self.script):
            at, data = self.script[self.next]
            if distance < at:
                return
            self.next += 1
            if distance == at:
                self._make(data, col)

    def spawn(self, distance: int, moved: bool) -> None:
        if not moved:
            return
        while self.next < len(self.script) and self.script[self.next][0] == distance:
            self._make(self.script[self.next][1], 0xF8)
            self.next += 1

    def _make(self, data: int, col: int) -> None:
        """0x62F8: the first free slot; none free, none made."""
        for n, hatch in enumerate(self.hatches):
            if hatch is None:
                kind = 2 if data & 0x80 else 1
                self.hatches[n] = Hatch(
                    kind, (data & 0x1F) * 8, col,
                    FIRST_WAIT if col == 0xF8 else FIRST_WAIT_FILLING,
                    drawing=(kind - 1) * 2)
                return

    # -- a game frame (0x5FE4) ---------------------------------------------------------

    def step(self, moved: bool) -> None:
        for n, hatch in enumerate(self.hatches):
            if hatch is None:
                continue
            self._release(hatch)
            if moved:
                if hatch.col < 8:
                    self.hatches[n] = None
                else:
                    hatch.col -= 8

    def _release(self, hatch: Hatch) -> None:
        """0x6038: a bug every eight game frames while it has any."""
        if not hatch.bugs:
            return
        hatch.clock = (hatch.clock - 1) & 0xFF
        if hatch.clock:
            return
        hatch.clock = BUG_EVERY
        hatch.bugs -= 1
        row = (hatch.row + (-8 if hatch.kind & 1 else 0x18)) & 0xFF
        self.objects.spawner_kind = hatch.kind
        self.objects.make(BUG, row, hatch.col)

    # -- in the map (0x61E8) -------------------------------------------------------------

    def draw(self, terrain: Map) -> None:
        self.drawn = []
        for hatch in self.hatches:
            if hatch is None:
                continue
            drawing = hatch.drawing
            if self.stage == 2 and drawing >= 2:
                drawing += STAGE_2_SKIP
            chars = self.drawings[drawing]
            top, left = hatch.row // 8, hatch.col // 8
            for r in range(SIZE):
                for c in range(SIZE):
                    if left + c >= 32 or not terrain.inside(top + r, left + c):
                        continue
                    terrain[top + r, left + c] = chars[r * SIZE + c]
                    self.drawn.append((top + r, left + c))

    def erase(self, terrain: Map) -> None:
        """0x61DA: the rectangles back to nothing."""
        for row, col in self.drawn:
            terrain[row, col] = 0

    # -- shot (0x7898) -----------------------------------------------------------------

    def meets(self, row: int, col: int, laser_length: int = 0) -> Hatch | None:
        reach = laser_length * 8 if laser_length else 8
        for hatch in self.hatches:
            if hatch is None:
                continue
            if (row - hatch.row + BOX_ABOVE) & 0xFF >= BOX_ROWS:
                continue
            if hatch.col >= BOX_LAST_COLUMN:
                continue
            a = (hatch.col - col) & 0xFF
            if a < reach or a + BOX_AFTER > 0xFF:
                return hatch
        return None

    def hit(self, hatch: Hatch, laser: bool) -> None:
        """0x7AB0."""
        hatch.drawing = hatch.kind * 2 - 1
        hatch.hits -= LASER_DAMAGE if laser else SHOT_DAMAGE
        if hatch.hits - 1 >= 0:
            self.objects.world.sounds.append(SOUND_HIT)
            return
        self.objects.world.sounds.append(SOUND_GONE)
        self.objects.world.score += POINTS
        at = self.hatches.index(hatch)
        self.hatches[at] = None


#: Stage 3's eight background objects (kinds 3-6): gun emplacements that wake
#: when the ship comes near (0x610E..0x6168), fire bursts of sixteen aimed
#: shots (type 0x0E) every four game frames (0x6086), and rest 0x40 less two a
#: difficulty step between bursts. Shot to pieces only while awake.
STAGE_3, STAGE_3_SLOTS, STAGE_3_BURST, STAGE_3_EVERY = 3, 8, 0x10, 4
AIMED = 0x0E
EXPLODING_FRAMES = 0x0D


@dataclass
class Gun:
    kind: int
    row: int
    col: int
    clock: int
    step: int = 0
    hits: int = HITS
    drawing: int = 0
    shots: int = 0


class Guns:
    def __init__(self, objects: Objects, script: tuple[tuple[int, int], ...], art: GunArt) -> None:
        self.objects = objects
        self.script = script
        self.art = art
        self.guns: list[Gun | None] = [None] * STAGE_3_SLOTS
        self.next = 0
        self.drawn: list[tuple[int, int]] = []
        #: The map they are drawn into, where a kill wipes one.
        self.terrain = Map()

    def fill(self, distance: int, col: int) -> None:
        while self.next < len(self.script):
            at, data = self.script[self.next]
            if distance < at:
                return
            self.next += 1
            if distance == at:
                self._make(data, col)

    def spawn(self, distance: int, moved: bool) -> None:
        if not moved:
            return
        while self.next < len(self.script) and self.script[self.next][0] == distance:
            self._make(self.script[self.next][1], 0xF8)
            self.next += 1

    def _make(self, data: int, col: int) -> None:
        """0x6332: the kind out of bits 6-7."""
        for n, gun in enumerate(self.guns):
            if gun is None:
                kind = (data >> 6 & 3) + 3
                self.guns[n] = Gun(kind, (data & 0x1F) * 8, col,
                                   FIRST_WAIT if col == 0xF8 else FIRST_WAIT_FILLING,
                                   drawing=(kind - 1) * 2)
                return

    def step(self, moved: bool, ship_row: int, ship_col: int, difficulty: int) -> None:
        for n, gun in enumerate(self.guns):
            if gun is None:
                continue
            if self._run(gun, ship_row, ship_col, difficulty):
                self.guns[n] = None
                continue
            if moved:
                if gun.col < 8:
                    self.guns[n] = None
                else:
                    gun.col -= 8

    def _run(self, gun: Gun, ship_row: int, ship_col: int, difficulty: int) -> bool:
        """0x6061. True once it is gone."""
        if gun.step == 1:
            self._burst(gun, difficulty)
        elif gun.step == 2:
            dy, drawing = self.art.wrecks[gun.kind]
            gun.row = (gun.row + dy) & 0xFF
            gun.drawing, gun.clock, gun.step = drawing, EXPLODING_FRAMES, 3
        elif gun.step == 3:
            gun.clock -= 1
            return not gun.clock
        else:
            self._watch(gun, ship_row, ship_col)
        return False

    def _watch(self, gun: Gun, ship_row: int, ship_col: int) -> None:
        """0x610E-0x6168: each kind wakes on its own test, once its clock
        has run down."""
        gun.clock = (gun.clock - 1) & 0xFF
        if gun.clock:
            return
        gun.clock = 1
        if gun.kind == 3:
            if (gun.row + 0x40) & 0xFF < ship_row or (gun.col + 0x14) & 0xFF < ship_col:
                return
        elif gun.kind == 4:
            if (gun.row + 0x40) & 0xFF < ship_row:
                return
            if gun.col < 0x34 or gun.col - 0x34 >= ship_col:
                return
        elif gun.kind == 5:
            if (gun.row + 0x18) & 0xFF >= ship_row:
                return
        elif gun.row < ship_row:
            return
        gun.clock, gun.shots, gun.step = STAGE_3_BURST, STAGE_3_BURST, 1
        gun.drawing = (gun.kind - 1) * 2 + 1

    def _burst(self, gun: Gun, difficulty: int) -> None:
        """0x6086."""
        closed = (gun.kind - 1) * 2
        if gun.col < 0x18:
            gun.drawing = closed
            return
        gun.clock -= 1
        if gun.clock:
            gun.drawing = closed + 1
            return
        gun.clock = STAGE_3_EVERY
        gun.shots -= 1
        if not gun.shots:
            gun.step = 0
            gun.clock = (0x40 - 2 * difficulty) & 0xFF
            gun.drawing = closed
            return
        dy, dx = self.art.muzzles[gun.kind]
        col = gun.col + dx
        if col > 0xFF:
            return
        self.objects.make(AIMED, (gun.row + dy) & 0xFF, col)

    # -- in the map (0x6229, 0x6256) ----------------------------------------------------

    def _rect(self, gun: Gun, terrain: Map) -> list[tuple[int, int, int]]:
        """0x6229: the drawing's rectangle, (row, column, character)."""
        width, height, dx, lower = self.art.rects[gun.drawing]
        chars = self.art.chars[gun.drawing]
        row = (gun.row + (8 if lower else 0)) // 8
        col = gun.col + dx
        if col > 0xFF:
            return []
        return [(row + r, col // 8 + c, chars[r * width + c])
                for r in range(height) for c in range(width)
                if col // 8 + c < 32 and terrain.inside(row + r, col // 8 + c)]

    def draw(self, terrain: Map) -> None:
        """0x61AF, every game frame. Stage 3's are never wiped after (0x61A3
        leaves stages 3 and 5 alone): they stay in the map, wrecks and all,
        and the objects meet them."""
        self.terrain = terrain
        self.drawn = []
        for gun in self.guns:
            if gun is None:
                continue
            for r, c, character in self._rect(gun, terrain):
                terrain[r, c] = character
                self.drawn.append((r, c))
            dy, strip = self.art.strips[gun.drawing]
            srow = ((gun.row + dy) & 0xFF) // 8
            for c in range(10):
                cc = gun.col // 8 + c
                if cc < 32 and terrain.inside(srow, cc):
                    # 0x6278: the strip is never cleared; it stays in the map.
                    terrain[srow, cc] = self.art.strip_rows[strip * 10 + c]

    # -- shot (0x7902) ----------------------------------------------------------------

    def meets(self, row: int, col: int, laser_length: int = 0) -> Gun | None:
        reach = laser_length * 8 if laser_length else 8
        for gun in self.guns:
            if gun is None or gun.step != 1:
                continue
            cy, cx = self.art.centres[gun.kind]
            if ((cy + gun.row - row) & 0xFF) + 0x10 <= 0xFF:
                continue
            x = gun.col + cx
            if x > 0xFF or x >= 0xF0:
                continue
            a = (x - col) & 0xFF
            if a < reach or a + 0x10 > 0xFF:
                return gun
        return None

    def hit(self, gun: Gun, laser: bool) -> None:
        """0x7AF0."""
        gun.hits -= LASER_DAMAGE if laser else SHOT_DAMAGE
        if gun.hits - 1 >= 0:
            self.objects.world.sounds.append(SOUND_HIT)
            return
        # 0x7B13: shot to pieces, its rectangle is wiped (the strip stays).
        for r, c, _ in self._rect(gun, self.terrain):
            self.terrain[r, c] = 0
        self.objects.world.score += POINTS
        self.objects.world.sounds.append(0x0F)
        by, bx = self.art.blasts[gun.kind]
        self.objects.blast_at(gun.row + by, gun.col + bx)
        gun.step = 2
