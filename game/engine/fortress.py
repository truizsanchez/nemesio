"""Stage 8's boss: the fortress's claws, its gate and the brain's anchors.

Boss 4 (bank 2, 0x87F3), from distance 0x16E, in six steps counted in 0xE190:

0. two claws come in from the right wall, one low (row 0x78) and one high
   (0x20), drawn with characters (0x8805);
1. at distance 0x178, a gate starts to rise (0xE9A0, 0x884D) and 0x1E0 game
   frames are counted;
2. when they are out, or the ship passes column 0xC8, or a claw is shot
   down, the scroll may run on to 0x19F and the gate closes, a drawing every
   0x20 game frames (0x8852);
3. another 0x1E0 (0x887E);
4. on the way, six anchors (type 0x11) come in on a script (0x88D3); once
   the scroll has stopped, when they are all shot or the count is out
   (0x888D),
5. the screen goes dark (0xA6C0), the objects are cleared, and the game's
   ending takes over.

A claw rides the scroll left, turns a drawing every six game frames towards
where the ship is from its anchor 0x38 to the right -- each in its own
quarter of the turn -- and fires from its tip every 0x10.

The claws keep the original's bytes: 0 type (7), 1 which (bit 0: the upper),
3 row, 5 column, 7 turn clock, 8 shot clock, 9 life, 10 drawing, 11 the one
it wants, 12 burst (1 shot down, 2 off the left).
"""

from __future__ import annotations

from game.engine.fade import Fade
from game.engine.objects import ANCHOR, Objects
from game.engine.tables import FortressArt
from game.engine.terrain import Map

CLAW, CLAWS, SIZE = 7, 2, 16
#: Distances (0x8835) and the scroll's last limit (0x8876).
GATE_AT, LAST_LIMIT = 0x178, 0x19F
#: 0x1E0 game frames, twice (0x883A, 0x8882); or the ship past 0xC8 (0x8860).
WAIT, SHIP_PAST = 0x1E0, 0xC8
#: The claws aim from 0x38 to the right of them (0x8AE2); each reaches a
#: quarter of the turn from 0x40 (the upper) or 0x80 (the lower), resting at
#: drawing 8 or 1 outside it (0x8AF1, 0x8B15).
ANCHOR_DX, UPPER_FROM, LOWER_FROM, QUARTER = 0x38, 0x40, 0x80, 0x40
UPPER_REST, LOWER_REST = 8, 1
#: A claw turns every six game frames and fires every 0x10 (0x8AB3, 0x8A79).
TURN_EVERY, FIRE_EVERY = 6, 0x10
#: Met in 8 by 8 about the centre 0x8A93 gives it, six lower (0x76D9).
BOX, CENTRE_DY, SHOT_ROWS, SHOT_COLS = 0x08, 6, 0x02, 0x10
SHOT_TAKES, LASER_TAKES = 4, 1
#: Shot down: 10 points, sound 0x0E, a blast (0x7797); a second blast 0x10
#: above or below and 0x10 right as it is wiped (0x8A0A).
POINTS, BURST_SOUND, HIT_SOUND, BLAST_DY, BLAST_DX = 10, 0x0E, 0x06, 0x10, 0x10
SHOT_DOWN, OFF_LEFT = 1, 2
#: The gate: 4 by 6 characters, a drawing every 0x20 game frames, six (0x8927).
GATE_W, GATE_H, GATE_EVERY, GATE_DRAWINGS = 4, 6, 0x20, 6
ANCHOR_COL = 0xF8


class Fortress:
    def __init__(self, objects: Objects, art: FortressArt) -> None:
        self.objects = objects
        self.art = art
        #: 0xE780 and 0xE790.
        self.claws = [bytearray(SIZE) for _ in range(CLAWS)]
        #: 0xE190, 0xE153.
        self.step = 0
        self.clock = 0
        #: 0xE9A0..0xE9A4: the gate's step, row, column, clock, drawing.
        self.gate = [0, 0, 0, 0, 0]
        #: 0xE10A: a claw was shot down.
        self.claw_down = False
        self.limit: int | None = None
        self.fade = Fade()
        self.done = False

    # -- a game frame (0x87F3) -------------------------------------------------------

    #: The boss's first game frame is only counted (0x7C4F).
    starting = True

    def update(self, distance: int, moved: bool, stopped: bool, busy: bool) -> None:
        if self.starting:
            self.starting = False
            return
        if self.step == 0:
            cards = self.art.claws
            self.claws[0][:SIZE] = bytes(cards[:SIZE])
            self.claws[1][:len(cards) - SIZE] = bytes(cards[SIZE:])
            self.step = 1
        elif self.step == 1:
            self._claws(moved)
            if distance >= GATE_AT:
                self.clock = WAIT
                self.gate = list(self.art.rising)
                self.step = 2
        elif self.step == 2:
            self._claws(moved)
            self.clock -= 1
            if (self.clock and self.objects.world.ship_col < SHIP_PAST
                    and not self.claw_down):
                return
            self.gate[0] = max(self.gate[0], 2)
            self.limit = LAST_LIMIT
            self.step = 3
        elif self.step == 3:
            self.objects.next_drawing = 0
            self.clock = WAIT
            self.step = 4
        elif self.step == 4:
            self._claws(moved)
            if moved:
                self._script(distance)
            if not stopped:
                return
            if self.objects.alive:
                self.clock -= 1
                if self.clock:
                    return
            self.fade = Fade()
            self.step = 5
        elif self.step == 5:
            self.fade.update(busy, False, self.objects.world.sounds)
            if self.fade.done:
                for s in self.objects.slots:
                    s.data[:] = bytes(len(s.data))
                self.objects.alive = 0
                self.done = True

    def _script(self, distance: int) -> None:
        """0x88D3: the anchors whose distance's low byte this is."""
        low = distance & 0xFF
        for at, row, drawing in self.art.script:
            if low < at:
                return
            if low == at:
                self.objects.next_drawing = drawing
                self.objects.make(ANCHOR, row, ANCHOR_COL)

    def _claws(self, moved: bool) -> None:
        """0x8A5C."""
        for claw in self.claws:
            if not claw[0]:
                continue
            if moved:
                claw[5] = (claw[5] - 8) & 0xFF
                if not claw[5]:
                    claw[12] = OFF_LEFT
            claw[11] = self._want(claw)
            claw[7] = (claw[7] - 1) & 0xFF
            if not claw[7]:
                claw[7] = TURN_EVERY
                if claw[10] != claw[11]:
                    claw[10] = (claw[10] + (1 if claw[10] < claw[11] else -1)) & 0xFF
            claw[8] = (claw[8] - 1) & 0xFF
            if claw[8]:
                continue
            claw[8] = FIRE_EVERY
            dy, dx = self.art.muzzles[claw[10]]
            self.objects.fire_at_ship((claw[3] + dy) & 0xFF, (claw[5] + dx) & 0xFF)

    def _want(self, claw: bytearray) -> int:
        """0x8ADC."""
        angle = self.objects._angle(claw[3], (claw[5] + ANCHOR_DX) & 0xFF)
        if claw[1] & 1:
            drawing, turn, table = UPPER_REST, (angle - UPPER_FROM) & 0xFF, self.art.upper_aim
        else:
            drawing, turn, table = LOWER_REST, (angle - LOWER_FROM) & 0xFF, self.art.lower_aim
        if turn < QUARTER:
            drawing = table[turn >> 2 & 0x0F]
        tremble = self.objects.rng.randrange(4) - 1
        return (drawing + (0 if tremble == 2 else tremble)) & 0xFF

    # -- the gate (0x890B, 0x8935), run and drawn early in every game frame ----------

    def rise(self, terrain: Map, moved: bool) -> None:
        gate = self.gate
        if not gate[0]:
            return
        if moved:
            under = gate[2] < 8
            gate[2] = (gate[2] - 8) & 0xFF
            if under:
                gate[0] = 3
                return
        if gate[0] == 2:
            gate[3] = (gate[3] - 1) & 0xFF
            if not gate[3]:
                gate[3] = GATE_EVERY
                gate[4] += 1
                if gate[4] >= GATE_DRAWINGS:
                    gate[0] = 3
        if gate[0] != 2:
            return
        chars = self.art.rising_drawings[gate[4]]
        top, left = gate[1] >> 3, gate[2] >> 3
        for r in range(GATE_H):
            for c in range(GATE_W):
                if left + c < 32 and terrain.inside(top + r, left + c):
                    terrain[top + r, left + c] = chars[r * GATE_W + c]

    # -- the claws drawn into the map (0x8A21), and wiped (0x89E3) ----------------------

    def cells(self) -> list[tuple[int, int, int]]:
        out = []
        for claw in self.claws:
            if claw[0]:
                out += self._drawing(claw)
        return out

    def _drawing(self, claw: bytearray) -> list[tuple[int, int, int]]:
        dy, dx, height, width, chars = self.art.drawings[claw[10]]
        row, col = (claw[3] + dy) & 0xFF, claw[5] + dx
        if col > 0xFF:
            return []
        top, left = row >> 3, col >> 3
        return [(top + r, left + c, chars[r * width + c])
                for r in range(height) for c in range(width) if left + c < 32]

    def wipe(self, terrain: Map) -> None:
        """0x89E3: a claw burst goes, blowing up once more; one gone off the
        left leaves its drawing in the map."""
        for claw in self.claws:
            if not claw[0]:
                continue
            burst = claw[12]
            cells = self._drawing(claw)
            if burst:
                claw[0] = 0
                if burst != SHOT_DOWN:
                    continue
                dy = BLAST_DY if claw[1] & 1 else -BLAST_DY
                self.objects.blast_at(claw[3] + dy, claw[5] + BLAST_DX)
            for r, c, _ in cells:
                if terrain.inside(r, c):
                    terrain[r, c] = 0

    # -- being shot (0x760E) ----------------------------------------------------------

    def meets(self, row: int, col: int, laser_cols: int = 0) -> int | None:
        for n, claw in enumerate(self.claws):
            # Still a claw until it is wiped: a second shot in the same game
            # frame hits it again, and pays again (0x7688).
            if claw[0] != CLAW:
                continue
            dy, dx = self.art.muzzles[claw[10]]
            y, x = (claw[3] + dy + CENTRE_DY) & 0xFF, (claw[5] + dx) & 0xFF
            a = (y - row) & 0xFF
            if not (a < SHOT_ROWS or a + BOX > 0xFF):
                continue
            a = (x - col) & 0xFF
            if a < (laser_cols or SHOT_COLS) or a + BOX > 0xFF:
                return n
        return None

    def hit(self, n: int, laser: bool) -> None:
        """0x7797."""
        claw = self.claws[n]
        claw[9] = (claw[9] - (LASER_TAKES if laser else SHOT_TAKES)) & 0xFF
        if not (claw[9] - 1) & 0x80:
            self.objects.world.sounds.append(HIT_SOUND)
            return
        claw[12] = SHOT_DOWN
        self.claw_down = True
        self.objects.world.sounds.append(BURST_SOUND)
        self.objects.world.score += POINTS
        self.objects.blast_at(claw[3], claw[5])
