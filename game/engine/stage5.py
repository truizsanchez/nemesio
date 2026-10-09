"""Stage 5's own background engine (bank 3, 0xB2AA..0xB537).

The other stages move their background objects with bank 1's engine;
stage 5 has its own, on the same eight slots of eight bytes at 0xE700, with
pieces drawn as rectangles of characters into the map (0xB3D2):

- small ones (kinds 1-4, 5x5, painted and left in the map): they open through four drawings, wait for
  the ship to come within range -- 0x20 past them for kinds 1 and 3, 0x30
  short of them for 2 and 4 -- and while it stays, let a type 0x1C out every
  eight game frames, aimed at it. Shots meet them only while open (0x7982).
- big ones (kinds 5-8, walls): drawn and never wiped; after 0x30 game frames
  each puts a turret in one of the four slots of 0xE880; broken (0x0C of
  life), it becomes kind 9-12, the broken drawing.
- turrets (0xB145): they slide out of their wall row by row, move eight
  pixels at a time as far as the script said, then peek out and in, and
  when out fire a fan of three at the ship (0xB1FC). Only out can they be
  shot: 0x30 of life, five a shot and three a laser (0x7B91).

A slot: 0 kind, 1 step, 2 row, 3 column, 4 clock, 5 life (a turret: rows
out, then life), 6 drawing (a turret: out), 7 steps left.
"""

from __future__ import annotations

from game.engine.objects import Objects
from game.engine.tables import Stage5Art
from game.engine.terrain import Map

SLOTS, TURRETS, SIZE = 8, 4, 8
SMALL_FROM, BIG_FROM, BROKEN_FROM = 1, 5, 9
#: The script's pieces come in at column 0xF8, the small ones only there and
#: always at column 0xC0, with the sound 0x0C (0xB4AF, 0xB501).
ENTER, SMALL_COLUMN, SMALL_SOUND = 0xF8, 0xC0, 0x0C
#: A small one: eight game frames a drawing, four to open, 0x0F of life; a
#: big one: 0x30 game frames to its turret, 0x0C of life (0xB504, 0xB525).
SMALL_EVERY, SMALL_OPENING, SMALL_LIFE = 8, 4, 0x0F
BIG_WAIT, BIG_LIFE = 0x30, 0x0C
#: The ship in range: 0x20 behind (kinds 1, 3) or 0x30 ahead (2, 4) (0xB32C).
BEHIND, AHEAD = 0x20, 0x30
#: What a small one lets out, and a turret's slide and wait (0xB18F..0xB1F8).
RELEASE = 0x1C
TURRET_EVERY, TURRET_ROWS, TURRET_REST, TURRET_OUT, TURRET_LIFE = 5, 3, 0x18, 0x20, 0x30
#: Its fan, from 0x10 in, the middle and one either side (0xB1FC).
FAN_FROM = 0x10
#: Shots: five, three for a laser; hits pay 10; the sounds (0x7A4F, 0x7C01).
SHOT_TAKES, LASER_TAKES, POINTS, HIT_SOUND = 5, 3, 10, 6
BURST_SOUND, SMALL_BURST_SOUND, TURRET_BURST_SOUND = 0x0E, 0x0F, 0x0F


class Stage5:
    def __init__(self, objects: Objects, art: Stage5Art) -> None:
        self.objects = objects
        self.art = art
        self.slots = [bytearray(SIZE) for _ in range(SLOTS)]
        self.turrets = [bytearray(SIZE) for _ in range(TURRETS)]
        #: 0xE109: the script's next row.
        self.row = 0
        self.drawn: list[tuple[int, int]] = []

    # -- the script (0xB49E, 0xB4AA) ------------------------------------------------------

    def fill(self, distance: int, col: int) -> None:
        """The screen being filled at a stage's start: past rows skipped,
        those at this column's distance placed there."""
        while self.row < len(self.art.script) and self.art.script[self.row][0] < distance:
            self.row += 1
        self._place(distance, col)

    def spawn(self, distance: int, moved: bool) -> None:
        if moved:
            self._place(distance, ENTER)

    def _place(self, distance: int, col: int) -> None:
        script = self.art.script
        while self.row < len(script) and script[self.row][0] == distance:
            _, row, data = script[self.row]
            self.row += 1
            free = next((s for s in self.slots if not s[0]), None)
            if free is None:
                # 0xB4E6: the row is spent all the same.
                continue
            kind = (data + 1) & 0x0F
            if kind < BIG_FROM:
                if col != ENTER:
                    continue
                free[:] = bytes([kind, 0, row, SMALL_COLUMN, SMALL_EVERY, SMALL_LIFE,
                                 (data * 6) & 0xFF, 0])
                self.objects.world.sounds.append(SMALL_SOUND)
            else:
                free[:] = bytes([kind, 0, row, col, BIG_WAIT, BIG_LIFE, col, data >> 4])

    # -- a game frame (0xB2AA, 0xB145) -------------------------------------------------------

    def step(self, moved: bool, ship_row: int, ship_col: int, difficulty: int) -> None:
        for piece in self.slots:
            if not piece[0]:
                continue
            if piece[0] >= BIG_FROM:
                self._raise_turret(piece)
            else:
                self._small(piece, ship_col)
            if moved:
                if piece[3] < 8:
                    piece[0] = 0
                else:
                    piece[3] -= 8
        for turret in self.turrets:
            if turret[0]:
                self._turret(turret, moved, difficulty)

    def _small(self, piece: bytearray, ship_col: int) -> None:
        step = piece[1]
        if step == 0:
            piece[4] = (piece[4] - 1) & 0xFF
            if piece[4]:
                return
            piece[4] = SMALL_EVERY
            piece[6] += 1
            piece[7] += 1
            if piece[7] >= SMALL_OPENING:
                piece[1] = 1
        elif step == 1:
            if self._in_range(piece, ship_col):
                piece[6] += 1
                piece[4] = SMALL_EVERY
                piece[1] = 2
        elif not self._in_range(piece, ship_col):
            piece[6] -= 1
            piece[1] = 1
        else:
            piece[4] = (piece[4] - 1) & 0xFF
            if piece[4]:
                return
            piece[4] = SMALL_EVERY
            dy, dx = self.art.releases[piece[0] - 1]
            self.objects.make(RELEASE, (piece[2] + dy) & 0xFF, (piece[3] + dx) & 0xFF)

    @staticmethod
    def _in_range(piece: bytearray, ship_col: int) -> bool:
        """0xB32C."""
        if piece[0] in (1, 3):
            return piece[3] >= BEHIND and piece[3] - BEHIND >= ship_col
        return piece[3] + AHEAD <= 0xFF and piece[3] + AHEAD < ship_col

    def _raise_turret(self, piece: bytearray) -> None:
        """0xB370."""
        if piece[0] >= BROKEN_FROM or not piece[4]:
            return
        piece[4] -= 1
        if piece[4]:
            return
        free = next((t for t in self.turrets if not t[0]), None)
        if free is None:
            piece[4] = 1
            return
        dy, dx = self.art.turret_at[piece[0] - BIG_FROM]
        free[:] = bytes([1 if piece[0] & 1 else 2, 0, (piece[2] + dy) & 0xFF,
                         (piece[3] + dx) & 0xFF, TURRET_EVERY, 0, 0, piece[7]])

    def _turret(self, turret: bytearray, moved: bool, difficulty: int) -> None:
        """0xB15C."""
        if moved:
            if turret[3] < 8:
                turret[0] = 0
                return
            turret[3] -= 8
        step = turret[1]
        if step == 0:
            turret[4] -= 1
            if turret[4]:
                return
            if turret[0] & 1:
                turret[2] = (turret[2] - 8) & 0xFF
            turret[4] = TURRET_EVERY
            turret[5] += 1
            if turret[5] >= TURRET_ROWS:
                turret[1] = 1
        elif step == 1:
            turret[4] -= 1
            if turret[4]:
                return
            turret[4] = TURRET_EVERY
            turret[7] = (turret[7] - 1) & 0xFF
            if turret[7]:
                turret[2] = (turret[2] + (-8 if turret[0] & 1 else 8)) & 0xFF
                return
            turret[1], turret[4], turret[5] = 2, TURRET_REST, TURRET_LIFE
        elif step == 2:
            turret[6] = 0
            turret[4] = (turret[4] - 1) & 0xFF
            if turret[4]:
                return
            turret[1], turret[4] = 3, TURRET_OUT
        else:
            turret[6] = 1
            turret[4] = (turret[4] - 1) & 0xFF
            if turret[4]:
                return
            self._fan(turret)
            turret[1] = 2
            turret[4] = (TURRET_REST - (difficulty >> 1)) & 0xFF

    def _fan(self, turret: bytearray) -> None:
        """0xB1FC: three shots, the angle's sixteenth and either side."""
        row, col = (turret[2] + FAN_FROM) & 0xFF, (turret[3] + FAN_FROM) & 0xFF
        angle = self.objects._angle(row, col) >> 4
        for side in (0, 1, -1):
            free = next((s for s in self.objects.shots if not s.type), None)
            if free is None:
                return
            vy, vx = self.art.fan[(angle + side) & 0x0F]
            # 0xB234: the fractions (bytes 3 and 5) are left as the slot's
            # last shot left them.
            free[0], free[4], free[6] = 1, row, col
            free.set_word(7, vy)
            free.set_word(9, vx)
            free[11], free[27] = 0, 1
            free[12], free[13] = self.objects.layout.enemy_shot

    # -- drawn into the map (0xB3D2, 0xB431), wiped after (0xB410, 0xB42E) -----------

    def _rects(self) -> list[tuple[int, int, int, int, tuple[int, ...], bool]]:
        """(row, col, height, width, characters, wiped after) of everything."""
        out = []
        for piece in self.slots:
            if not piece[0]:
                continue
            if piece[0] < BIG_FROM:
                # Painted every game frame and never wiped: 0x61A3 returns
                # for stage 5, so they stay in the map (0x45CD, 0x698F).
                out.append((piece[2], piece[3], 5, 5, self.art.small[piece[6] % len(self.art.small)],
                            False))
            else:
                height, width, chars = self.art.big[piece[0] - BIG_FROM]
                out.append((piece[2], piece[3], height, width, chars, False))
        for turret in self.turrets:
            if not turret[0]:
                continue
            drawing = self.art.turret[1 if turret[6] else 0]
            if turret[1]:
                out.append((turret[2], turret[3], 4, 4, drawing, True))
            else:
                rows = turret[5] + 1
                first = 0 if turret[0] == 1 else (3 - turret[5]) * 4
                out.append((turret[2], turret[3], rows, 4, self.art.turret[0][first:], True))
        return out

    def draw(self, terrain: Map) -> None:
        self.drawn = []
        for row, col, height, width, chars, wiped in self._rects():
            top, left = row >> 3, col >> 3
            for r in range(height):
                for c in range(width):
                    if left + c < 32 and terrain.inside(top + r, left + c):
                        terrain[top + r, left + c] = chars[r * width + c]
                        if wiped:
                            self.drawn.append((top + r, left + c))

    def erase(self, terrain: Map) -> None:
        for r, c in self.drawn:
            terrain[r, c] = 0

    # -- being shot (0x7970, 0x7B91) --------------------------------------------------

    def meets(self, row: int, col: int, laser_length: int = 0) -> bytearray | None:
        reach = laser_length * 8 if laser_length else 8
        for piece in self.slots:
            kind = piece[0]
            if not kind or kind >= BROKEN_FROM:
                continue
            if kind < BIG_FROM:
                if piece[1] != 2:
                    continue
                if (piece[2] + 0x10 - row) & 0xFF < 0xF0:
                    continue
                a = ((0xF8 if kind & 1 else 0x20) + piece[3] - col) & 0xFF
                if a < reach or a + 0x10 > 0xFF:
                    return piece
                continue
            if kind == 6:
                if ((row - piece[2] - 0x12) & 0xFF) >= 8:
                    continue
            elif ((row - piece[2] + 8) & 0xFF) >= 0x10:
                continue
            if piece[3] >= (0xE8 if kind >= 7 else 0xC8):
                continue
            a = (piece[3] - col) & 0xFF
            if a < reach or a + 0x20 > 0xFF:
                return piece
        for turret in self.turrets:
            if not turret[0] or not turret[6]:
                continue
            if ((row - turret[2] + 2) & 0xFF) >= 0x22:
                continue
            a = (turret[3] - col) & 0xFF
            if a < reach or a + 0x20 > 0xFF:
                return turret
        return None

    def hit(self, piece: bytearray, laser: bool) -> None:
        world = self.objects.world
        is_turret = any(piece is t for t in self.turrets)
        if is_turret:
            piece[6] = (piece[0] * 2 - 1) & 0xFF
        piece[5] = (piece[5] - (LASER_TAKES if laser else SHOT_TAKES)) & 0xFF
        if not (piece[5] - 1) & 0x80:
            world.sounds.append(HIT_SOUND)
            return
        world.score += POINTS
        row = piece[2]
        if is_turret:
            world.sounds.append(TURRET_BURST_SOUND)
            piece[0] = 0
        elif piece[0] < BIG_FROM:
            world.sounds.append(SMALL_BURST_SOUND)
            piece[0] = 0
        else:
            # 0x7A78: a wall broken turns into its broken drawing.
            world.sounds.append(BURST_SOUND)
            piece[0] += 4
            if piece[0] == 0x0B:
                row = (row - 0x18) & 0xFF
        self.objects.blast_at(row, piece[3])
