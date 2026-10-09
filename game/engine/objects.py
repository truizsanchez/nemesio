"""The objects: enemies, their shots, what they leave behind.

Twelve slots of 32 bytes at 0xE300 and ten more at 0xE500 for enemy shots, as
the original keeps them. A slot is kept here as the same 32 bytes, read and
written at the same offsets, because every routine that moves an object is a
little machine over those bytes (bank 3, 0xA7B9..0xB537, and bank 2's
helpers) and a port that renamed them would have to be checked against the
listing through a translation. The offsets:

    0 type (0 free)       1 step            2 counter
    3-4 row (8.8)         5-6 column (8.8)  7-8 row speed   9-10 column speed
    11 drawn with characters                12 pattern      13 colour
    14 mark (0, 1 red, 2)                   15 hits left    16 shot delay
    17 in a group         18 the group      23-24, 25-26 accelerations
    27 flags: bit 0 touches the ship, bit 1 can be shot
    28 rope               29 animation step

The Z80's R register, the original's only chance, is `rng` here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from game.engine.original import (
    CELL, MAP_AT, MAP_COLUMNS, SCENERY, UNDER, UNDER_AT, UNDER_CELLS, UNDER_LAST_COL,
)
from game.engine.blasts import Blasts
from game.engine.tables import Tables
from game.engine.terrain import Map

SLOTS, SHOT_SLOTS, SLOT_SIZE = 12, 10, 32
#: Types that mean something to the engine, by the original's numbers.
LIFE, CAPSULE, BOMB, BLAST = 0x16, 0x12, 0x13, 0x15
#: Past the blasts and the capsules (0x12-0x1A), stage 5's types; 0x1E is
#: the one that takes three slots (0x6A84).
LATE_TYPES, BIG = 0x1B, 0x1E
#: Stage 5's bouncers, and what its small pieces let out.
BOUNCER, AIMED_SLOW = 0x1B, 0x1C
#: The bouncers go one pixel a frame left, up or down at one of six speeds,
#: two faster from the second round, between row 8 and their floor (0xB8DA).
BOUNCER_ACROSS, BOUNCER_TOP, FASTER = 0xFF00, 8, 2
#: Grown stones (type 8) fire one game frame in eight (0xAD02); stage 3's
#: heads' threes (type 0x0B), from the third round, one in 0x20 (0xADEE).
STONE_FIRES_MASK, THREE_FIRES_FROM, THREE_FIRES_MASK = 7, 2, 0x1F
#: 0x9184: while 0xE066 is 1, the wait's difficulty is at most 2.
CANNON_CAPPED = 2
#: Stage 7's boss's shots and stage 8's anchors.
SPIT, ANCHOR = 0x10, 0x11
#: The bonus stages' prizes: a ship, a capsule to take once, one to take
#: eight times, a box that opens into what its mark says, and a prize taken,
#: floating up (0xA7B9..0xA817).
PRIZE_SHIP, PRIZE_ONCE, PRIZE_EIGHT, BOX, FLOATING = 0x16, 0x17, 0x18, 0x19, 0x1A
#: A box opens into its mark plus 0x13 (0x74E8): the ship's drawing, or a
#: capsule's, taken once (mark 4) or eight times.
OPENS_INTO = 0x13
#: A taken prize floats up for ten game frames showing what it paid (the
#: layout's float pattern on, 0x04 a step of the chain), then comes back
#: where it was (0x752D).
FLOAT_FRAMES, CHAIN_MAX = 0x0A, 7
#: An object past this row or column has left (0x5F8E), a shot past 0xF0 (0x65FD).
GONE_ROW, GONE_COLUMN, SHOT_GONE_COLUMN = 0xB0, 0xF9, 0xF0
#: The four groups a six-in-a-row wave can be counted in (0xE900).
GROUPS = 4
#: A blast runs sixteen game frames, each drawing two (0x5E44).
BLAST_FRAMES = 0x10
#: A marked enemy is drawn red (0x6B10), a marked type 0x0D magenta.
MARKED_COLOUR, MARKED_COLOUR_0D = 8, 6
#: Stage 7's type 0x0D: ten game frames still, ten lunging at the ship, round,
#: for 0xFF game frames (0xAF95); then drawing 0xDC in colour 0x0D, a pixel a
#: frame to the left (0xAFA8). Each of its six drawings lasts 0x0F game frames
#: or 3, as R's bit 0 says (0xB014).
STEP_0D, LIFE_0D, LEAVING_COLOUR_0D = 0x0A, 0xFF, 0x0D
DRAWING_LONG_0D, DRAWING_SHORT_0D, DRAWINGS_0D = 0x0F, 3, 6
#: A type 0x0D shot down is a blast of its own, type 0x14 (0x72E9), through
#: 0x5EE3's four, four game frames each (0x5EC8).
BLAST_0D = 0x14


def _bcd(value: int) -> int:
    """A BCD word as the number it reads as (0x0100 is 100)."""
    return int("%x" % value)


def _signed(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


class Slot:
    """32 bytes, and the reads and writes the routines make of them."""

    def __init__(self) -> None:
        self.data = bytearray(SLOT_SIZE)

    def __getitem__(self, offset: int) -> int:
        return self.data[offset]

    def __setitem__(self, offset: int, value: int) -> None:
        self.data[offset] = value & 0xFF

    def word(self, offset: int) -> int:
        return self.data[offset] | self.data[offset + 1] << 8

    def set_word(self, offset: int, value: int) -> None:
        self.data[offset] = value & 0xFF
        self.data[offset + 1] = value >> 8 & 0xFF

    @property
    def type(self) -> int:
        return self.data[0]

    @property
    def row(self) -> int:
        return self.data[4]

    @property
    def col(self) -> int:
        return self.data[6]

    def vy(self, value: int) -> None:
        """0x6CBF."""
        self.set_word(7, value)

    def vx(self, value: int) -> None:
        """0x6CC6."""
        self.set_word(9, value)

    def add_speed(self) -> bool:
        """0x5F7C: the two speeds onto the position; False once it has left."""
        self.set_word(3, self.word(3) + self.word(7))
        self.set_word(5, self.word(5) + self.word(9))
        return self.row < GONE_ROW and self.col < GONE_COLUMN


@dataclass
class World:
    """What the objects read of the rest of the game each game frame."""

    ship_row: int = 0
    ship_col: int = 0
    frames: int = 0
    difficulty: int = 0
    #: The scroll brought a column in this game frame (0xE100).
    moved: bool = False
    distance: int = 0
    #: Where the stage's script ends (0xE103), and the stage.
    stage_end: int = 0
    stage: int = 1
    #: The shield is on (0xE200 at 3), and stages played (0xE066).
    shield_on: bool = False
    rounds: int = 0
    #: 0xE06A: the round (a whole loop of the eight stages).
    round: int = 0
    #: 0xE20B, the options; 0xE20E, the laser; and the fire button went down
    #: this game frame (0xE008 bit 4).
    options: int = 0
    laser: int = 0
    fire_pressed: bool = False
    sounds: list[int] = field(default_factory=list)
    score: int = 0


class Objects:
    def __init__(self, tables: Tables, rng: random.Random, stage: int) -> None:
        self.tables = tables
        #: Which patterns and characters the rules draw with.
        self.layout = tables.layout
        #: 0xE800: the background blasts.
        self.blasts = Blasts(tables.blast_drawings)
        self.rng = rng
        self.stage = stage
        self.slots = [Slot() for _ in range(SLOTS)]
        self.shots = [Slot() for _ in range(SHOT_SLOTS)]
        #: 0xE126: slots alive.
        self.alive = 0
        #: 0xE124: the type just made, 0 if there was no room.
        self.made = 0
        #: 0xE166: the six-in-a-row wave's number.
        self.wave_number = 0
        #: 0xE900: four groups of [number, alive, still to kill].
        self.groups = [[0, 0, 0] for _ in range(GROUPS)]
        #: 0xE122: the cannon script's data byte for the cannon being made.
        self.cannon_data = 0
        #: 0xE123: the kind of background object letting a bug out.
        self.spawner_kind = 0
        #: 0xE142/0xE144: the next eruption rock's two speeds.
        self.rock_speed = (0, 0)
        #: 0xEC12/0xEC14: the next type 0x10's two speeds; 0xEC1B the next
        #: type 0x11's drawing.
        self.next_speed = (0, 0)
        self.next_drawing = 0
        #: 0xE97E: the next stage-5 bouncer's packed floor and speed.
        self.bouncer = 0
        #: 0xE128: capsules taken in a row in a bonus stage.
        self.chain = 0
        #: 0xE1C0: the screen stopped by the target -- everything but the
        #: cannons and the blasts only rides the scroll (0x5DE1).
        self.frozen = False
        #: 0xE112: a shot was fired this game frame; one a frame.
        self.shot_this_frame = False
        self.world = World()
        self.terrain = Map()
        self.movers: dict[int, Callable[[Slot], None]] = {
            1: self._move_1, 2: self._move_2, 7: self._move_bug, 3: self._move_3, 4: self._move_4, 5: self._move_5,
            6: self._move_6, 8: self._move_stone, 9: self._move_9, 0x0A: self._move_0a,
            0x0B: self._move_0b, 0x0C: self._move_0c, 0x0D: self._move_0d,
            0x0E: self._move_aimed,
            0x0F: self._move_rock, SPIT: self._move_spit, ANCHOR: self._scroll_only,
            BOUNCER: self._move_bouncer, AIMED_SLOW: self._move_aimed,
            PRIZE_SHIP: self._scroll_only, PRIZE_ONCE: self._move_prize,
            PRIZE_EIGHT: self._move_prize, BOX: self._scroll_only, FLOATING: self._move_floating,
            CAPSULE: self._scroll_only, BOMB: self._scroll_only, BLAST: self._blast,
            BLAST_0D: self._blast_0d,
        }
        self.builders: dict[int, Callable[[Slot], None]] = {
            1: self._build_1, 2: self._build_2, 7: self._build_bug, 3: self._build_3, 4: self._build_4, 5: self._build_5,
            6: self._build_6, 8: self._build_stone, 9: self._build_9, 0x0A: self._build_0a,
            0x0B: self._build_0b, 0x0C: self._build_0c, 0x0D: self._build_0d,
            0x0E: self._build_aimed,
            0x0F: self._build_rock, SPIT: self._build_spit, ANCHOR: self._build_anchor,
            PRIZE_SHIP: self._build_prize, PRIZE_ONCE: self._build_prize,
            PRIZE_EIGHT: self._build_prize, BOX: self._build_box,
            BOUNCER: self._build_bouncer, AIMED_SLOW: self._build_aimed_slow,
        }

    # -- making one ----------------------------------------------------------

    def make(self, kind: int, row: int, col: int, mark: int = 0) -> Slot | None:
        """0x6A72 ("bring out an object") for the twelve slots; type 0x0E looks for
        its slot from the last of them backwards, eight at most (0x6ABF)."""
        self.made = 0
        if kind == BIG:
            return self._make_big(row, col)
        if kind == 0x0E:
            free = next((s for s in reversed(self.slots[SLOTS - 8:]) if not s.type), None)
        else:
            free = next((s for s in self.slots if not s.type), None)
        if free is None:
            return None
        return self._fill(free, kind, row, col, mark)

    def _make_big(self, row: int, col: int) -> Slot | None:
        """0x6A98: type 0x1E wants three slots in a row, and counts three."""
        for at in range(SLOTS - 2):
            if not any(s.type for s in self.slots[at:at + 3]):
                self.alive += 2
                return self._fill(self.slots[at], BIG, row, col, 0)
        return None

    def _fill(self, s: Slot, kind: int, row: int, col: int, mark: int) -> Slot:
        """0x6ACE ("set up the object")."""
        self.alive += 1
        self.made = kind
        s[27] = 3
        s[0], s[1], s[2] = kind, 0, 0
        s[4], s[6] = row, col
        chars, pattern, colour, hits = self.tables.records[kind]
        s[11], s[12], s[13] = chars, pattern, colour
        s[14] = mark
        if mark:
            s[13] = MARKED_COLOUR_0D if kind == 0x0D else MARKED_COLOUR
        s[15] = hits
        s[16] = self._shot_delay()
        s[17] = 0
        if kind in (2, 0x0A, 0x0C):
            s[17], s[18] = 1, self.wave_number
        builder = self.builders.get(kind)
        if builder:
            builder(s)
        return s

    def _shot_delay(self) -> int:
        """0x6B84: the difficulty's step and three bits of chance."""
        return self.tables.shot_delays[self.world.difficulty] + self.rng.randrange(8)

    def mark(self, counter: int) -> int:
        """0xA5B8: every fourth enemy is marked, one in sixteen with a 2."""
        return self.tables.marks[counter & 0x0F]

    # -- a game frame ----------------------------------------------------------

    def step(self, terrain: Map) -> None:
        """0x5DC8: each slot's mover, then 0x5F66 (its speed, and whether it
        has left)."""
        self.terrain = terrain
        for s in self.slots:
            kind = s.type
            if not kind:
                continue
            if self.frozen and kind not in (1, BLAST):
                mover: Callable[[Slot], None] | None = self._scroll_only
            else:
                mover = self.movers.get(kind)
            if mover:
                mover(s)
            kind = s.type
            if kind and (2 <= kind < 0x11 or kind >= 0x1B and kind != BIG):
                if not s.add_speed():
                    self.free(s)

    def step_shots(self, terrain: Map) -> None:
        """0x65DC: the enemies' shots."""
        for s in self.shots:
            if not s.type:
                continue
            inside = s.add_speed()
            if not inside or self._shot_meets_map(s, terrain) or s.col >= SHOT_GONE_COLUMN:
                s[0], s[27] = 0, 0

    def _shot_meets_map(self, s: Slot, terrain: Map) -> bool:
        """0x98AC: a shot's own cell, walls included."""
        row, col = s.row // CELL, s.col // CELL
        if not terrain.inside(row, col):
            return False
        return self._solid(terrain[row, col], walls=True)

    def _solid(self, character: int, walls: bool) -> bool:
        """0x9864: terrain under SCENERY; and with `walls`, the stage's
        walls above it."""
        if not character:
            return False
        if character < SCENERY:
            return True
        return walls and character in self.tables.stages.object_walls.get(self.world.stage, ())

    def free(self, s: Slot) -> None:
        """0x5FA5 ("switch the object off")."""
        self.alive -= 1
        s[0], s[27] = 0, 0
        if s[17] & 1:
            group = self._group(s[18])
            if group is not None:
                group[1] -= 1
                if group[1] <= 0:
                    group[0] = 0

    def _group(self, number: int) -> list[int] | None:
        return next((g for g in self.groups if g[0] == number), None)

    def open_group(self, number: int, count: int) -> bool:
        """0x5EBA with 0 then 0xA572: a free group takes the wave."""
        free = self._group(0)
        if free is None:
            return False
        free[0], free[1], free[2] = number, count, count
        return True

    # -- shared pieces of the movers (bank 2) ---------------------------------

    def _animate(self, s: Slot, mask: int, count: int, table: tuple[int, ...]) -> None:
        """0x95D1: every (mask+1) game frames, the next drawing, round."""
        if self.world.frames & mask:
            return
        step = s[29] + 1
        if step >= count:
            step = 0
        s[29] = step
        s[12] = table[step]

    def _fire_unaimed(self, s: Slot) -> None:
        """0x9235: when the delay runs out, a shot at the ship."""
        s[16] = s[16] - 1
        if s[16]:
            return
        self.fire_now(s)

    def fire_now(self, s: Slot) -> None:
        """0x9239: one shot a game frame; the rest wait a game frame."""
        if self.shot_this_frame:
            s[16] = 1
            return
        self.fire_at_ship(s.row, s.col)

    def fire_at_ship(self, row: int, col: int) -> None:
        """0x6613: a shot from (row + 8, col) towards the ship."""
        speed = min(self.world.difficulty * 2 + 0x50, 0x60)
        row = (row + 8) & 0xFF
        vy, vx, touching = self._aim(row, col, speed)
        if touching:
            return
        free = next((s for s in self.shots if not s.type), None)
        if free is None:
            return
        self.mount_shot(free, row, col, vy, vx)

    def mount_shot(self, s: Slot, row: int, col: int, vy: int, vx: int) -> None:
        """0x6646 ("set up the shot"): an enemy shot in slot s."""
        self.shot_this_frame = True
        s[0] = 1
        s[3], s[4], s[5], s[6] = 0, row, 0, col
        s.set_word(7, vy)
        s.set_word(9, vx)
        s[11], (s[12], s[13]) = 0, self.layout.enemy_shot
        s[27] = 1

    def _aim(self, row: int, col: int, speed: int) -> tuple[int, int, bool]:
        """0x6677/0x66D5: the angle from the two distances' high nibbles, a
        quarter-sine read both ways, times the speed. Also whether the ship
        is too close to shoot at (0xE115)."""
        dy = self.world.ship_row - row
        down = dy < 0
        dy = abs(dy) & 0xFF
        dx = self.world.ship_col - col
        left = dx < 0
        dx = abs(dx) & 0xFF
        touching = (dy & 0xF0) + dx < 0x30
        angle = self.tables.angles[(dy & 0xF0) + (dx >> 4)]
        # Past difficulty 7 the aim is spoiled by R (0x6685).
        if self.world.difficulty >= 7:
            error = self.rng.randrange(16)
            angle = max(angle - error, 0) if self.rng.randrange(2) else min(angle + error, 0x3F)
        sine = self.tables.sines
        vy = self._times(sine[angle], speed)
        vx = self._times(sine[0x3F - angle], speed)
        if down:
            vy = -vy & 0xFFFF
        if left:
            vx = -vx & 0xFFFF
        return vy, vx, touching

    @staticmethod
    def _times(component: int, speed: int) -> int:
        """0x6731: the product's top, three bits up."""
        return (component * speed) >> 5

    def _scroll_only(self, s: Slot) -> None:
        """0x9251: eight pixels left each time a column comes in; freed once
        past the left edge."""
        if not self.world.moved:
            return
        col = s[6] - CELL
        s[6] = col
        if col < 0:
            self.free(s)

    # -- the types -------------------------------------------------------------

    def _cannon_wait(self, s: Slot) -> int:
        """0x9181: the wait to the next shot, off a wheel of four; on the
        second stage played the difficulty counts no more than 2."""
        difficulty = self.world.difficulty
        if self.world.rounds == 1:
            difficulty = min(difficulty, CANNON_CAPPED)
        at = difficulty * 4 + (s[24] & 3)
        s[24] = s[24] + 1
        wait = self.tables.cannon_waits[at]
        if self.world.shield_on:
            wait -= 4
        wait = max(wait - (self.world.rounds >> 2), 0)
        s[16] = max(wait, 0x0C)
        return s[16]

    def _build_1(self, s: Slot) -> None:
        """0x6C23: half a wait to the first shot, and a drawing set out of
        bits 5 and 6 of the script's byte."""
        wait = self._cannon_wait(s)
        s[16] = (wait >> 1) | (wait & 0x80)
        data = self.cannon_data
        s[23] = (2 if data & 0x20 else 0) + (0 if data & 0x40 else 1)

    def _move_1(self, s: Slot) -> None:
        """0x9119: rides the scroll, turns to the ship in five steps of
        angle, and fires when the ship is in its arc."""
        self._scroll_only(s)
        if not s.type:
            return
        angle = self._angle(s.row, s.col)
        if angle >= 0x80:
            angle = -angle & 0xFF
        turn = 5
        for _ in range(5):
            angle -= 0x15
            if angle < 0:
                break
            turn -= 1
        base = self.tables.cannon_drawings[s[23] * 12 + self.world.stage - 1]
        s[12] = (base + turn) & 0xFF
        angle = self._angle(s.row, s.col)
        if s[23] & 2:
            if (angle - 0x90) & 0xFF < 0x60:
                return
        elif (angle - 0x10) & 0xFF < 0x60:
            return
        s[16] = s[16] - 1
        if s[16]:
            return
        if self.shot_this_frame:
            s[16] = 1
            return
        self.fire_at_ship(s.row, s.col)
        self._cannon_wait(s)

    def _build_2(self, s: Slot) -> None:
        """0xA8A9: still, then four pixels a frame to the left."""
        s.vy(0)
        s.vx(0xFC00)

    def _move_2(self, s: Slot) -> None:
        """0xA8B2: to 0x81 (0x7F in the bottom half), back to 0x9F, forward
        to 0x51, and straight on once level with the ship."""
        if self.world.difficulty >= 8:
            self._fire_unaimed(s)
        self._animate(s, 3, 4, self.tables.animations[2])
        step = s[1]
        if step == 1:
            if s.col < 0x9F:
                return
            s[4] = s[4] & 0xF8
            s[1] = step + 1
            self._build_2(s)
            return
        if step == 3:
            gap = (self.world.ship_row - s.row + 4) & 0xFF
            if gap >= 9:
                return
            s[1] = step + 1
            s[4] = s[4] & 0xF8
            s.vy(0)
            return
        if step >= 4:
            return
        top, bottom = (0x81, 0x7F) if step == 0 else (0x51, 0x4F)
        limit = top if s.row < 0x50 else bottom
        if s.col >= limit:
            return
        s[1] = step + 1
        s.vy(0x0400 if s.row < 0x50 else 0xFC00)
        s.vx(0x0400)

    def _build_3(self, s: Slot) -> None:
        """0xA821: four down, two left, curving."""
        s.vy(0x0400)
        s.set_word(25, 0x0400)
        s.vx(0xFE00)
        s.set_word(23, 0xFF80)

    def _move_3(self, s: Slot) -> None:
        """0xA836: fires, turns its drawing, and curves until its row speed
        is as large as the column acceleration, when the curve reverses."""
        self._fire_unaimed(s)
        self._animate(s, 7, 8, self.tables.animations[3])
        s.set_word(7, s.word(7) + s.word(23))
        speed = abs(_signed(s.word(7)))
        if speed == s.word(25):
            s.set_word(23, -_signed(s.word(23)) & 0xFFFF)

    def _build_4(self, s: Slot) -> None:
        """0xA857."""
        s.vy(0)
        s.vx(0xFE80)

    def _move_4(self, s: Slot) -> None:
        """0xA863: to the ship's row, leaning its drawing the way it goes."""
        self._fire_unaimed(s)
        gap = (self.world.ship_row - s.row) & 0xFF
        if (gap + 3) & 0xFF >= 7:
            if self.world.ship_row < s.row:
                s[12] = 0xB4
                s.vx(0xFE80)
                s.vy(0xFE80)
            else:
                s[12] = 0xB8
                s.vx(0xFE80)
                s.vy(0x0180)
            return
        s.vx(0xFD00 if self.world.ship_col < s.col else 0xFE80)
        s[12] = 0xB0
        s.vy(0)

    def _solid_pair(self, row: int, col: int, walls: bool = False) -> bool:
        """0x9897 (choca_con_el_mapa_3): the cell at a point and the one to
        its right, unless that is past the row's end; terrain only. With
        `walls`, 0x9857: the stage's walls too."""
        cells = self.terrain
        r, c = (row & 0xFF) // CELL, (col & 0xFF) // CELL
        for cc in (c, c + 1):
            if cc >= MAP_COLUMNS:
                break
            if cells.inside(r, cc) and self._solid(cells[r, cc], walls):
                return True
        return False

    def _its_time(self, s: Slot) -> bool:
        """0x95A6: every 0x20 game frames the rope shortens and, at its end,
        true; and true once the stage is nearly over (0x95B2)."""
        if not self.world.frames & 0x1F:
            s[28] = s[28] - 1
            if not s[28]:
                return True
        margin = 0x10 if self.world.stage == 1 else 1
        return self.world.stage_end - margin < self.world.distance

    def _build_5(self, s: Slot) -> None:
        """0xA9D4: from the bottom half it walks the floor, else the roof."""
        floor = bool(s[4] & 0x80)
        s[19] = int(floor)
        s[12] = self.layout.walker_start[floor]
        s[28] = 0x0A
        s[2] = 0x2D + self.rng.randrange(0x20)
        s.vy(0)
        s.vx(0x0200)

    def _move_5(self, s: Slot) -> None:
        """0xA9FB: walks the terrain a step a frame, plants itself for 0x5A
        frames firing when the ship is in its arc, walks again, and leaves."""
        step = s[1]
        if step == 1:
            if self._its_time(s):
                s[1] = 2
                s.vx(0xFE00)
                return
            s[2] = s[2] - 1
            if s[2]:
                self._fire_in_arc(s)
                self._scroll_only(s)
                return
            s[1] = 0
            s[2] = 0x2D + self.rng.randrange(0x20)
            s.vx(0x0200 if self.world.ship_col >= s.col else 0xFE00)
            return
        if step >= 2:
            self._animate_5(s)
            self._fit(s, at_once=False)
            return
        if self._its_time(s):
            s[1] = 2
            s.vx(0xFE00)
            return
        s[2] = s[2] - 1
        if s[2]:
            self._fit(s, at_once=False)
            self._animate_5(s)
            return
        s[1] = 1
        s[2] = 0x5A
        self._face_5(s)
        self._fit(s, at_once=True)
        s[16] = (0x3C - 2 * self.world.difficulty) & 0xFF
        s.vx(0)

    def _animate_5(self, s: Slot) -> None:
        """0xAB3C: two drawings, one every four game frames, the pair by
        which way it goes (byte 10) and floor or roof (0xAB58)."""
        at = (2 if s[10] & 0x80 else 0) + (4 if s[19] & 1 else 0)
        self._animate(s, 3, 2, self.tables.animations[5][at:at + 2])

    def _face_5(self, s: Slot) -> None:
        """0xAB60: facing the ship."""
        right, left = self.layout.walker_facing[bool(s[19] & 1)]
        s[12] = right if self.world.ship_col >= s.col else left

    def _fit(self, s: Slot, at_once: bool) -> None:
        """0xAA64: onto the floor or the roof, eight pixels a frame, or at
        once."""
        if s[19] & 1:
            while True:
                if not self._solid_pair(s[4] + 0x10, s.col):
                    if s[4] >= 0x90:
                        return
                    s[4] = s[4] + 8
                    if not at_once:
                        return
                    continue
                while self._solid_pair(s[4] + 8, s.col):
                    s[4] = s[4] - 8
                    if not at_once:
                        return
                return
        while True:
            if self._solid_pair(s[4], s.col):
                s[4] = s[4] + 8
                if not at_once:
                    return
                continue
            while not self._solid_pair(s[4] - 8, s.col) and s[4] >= 9:
                s[4] = s[4] - 8
                if not at_once:
                    return
            return

    def _fire_in_arc(self, s: Slot) -> None:
        """0xAAFC: when its delay runs out, a shot if the ship is on its side
        and inside 0x30 of straight up (or down)."""
        s[16] = s[16] - 1
        if s[16]:
            return
        s[16] = (0x3C - 2 * self.world.difficulty) & 0xFF
        self._face_5(s)
        if s[19] & 1:
            if self.world.ship_row >= s.row:
                return
        elif self.world.ship_row < s.row:
            return
        angle = self._angle(s.row, s.col)
        if angle >= 0x80:
            angle = -angle & 0xFF
        if angle >= 0x40:
            angle -= 0x40
        if (angle - 8) & 0xFF >= 0x30:
            return
        # 0xAB39: one shot a game frame, as the others.
        self.fire_now(s)

    def _angle(self, row: int, col: int) -> int:
        """0x66D5's 0xEC18: the angle to the ship, a byte for a whole turn."""
        dy = self.world.ship_row - row
        dx = self.world.ship_col - col
        angle = self.tables.angles[(abs(dy) & 0xF0) + (abs(dx) >> 4)]
        up, left = dy < 0, dx < 0
        if up != left:
            angle = -angle & 0xFF
        return (angle + (0x80 if left else 0)) & 0xFF

    def _build_6(self, s: Slot) -> None:
        """0xA937: thrown up, towards the middle, with a rope of 0x78."""
        s[28] = 0x78
        s.set_word(23, 0x0060)
        s.vy(0xFA00)
        s.set_word(25, 0xFA00)
        s.vx(0xFE00 if s[6] & 0x80 else 0x0200)

    def _ground_under(self, s: Slot) -> bool:
        """0xA9AE: falling, between rows 0x58 and 0x9F, terrain 0x10 below."""
        if s[8] & 0x80:
            return False
        if s.row < 0x58:
            return False
        if s.row >= 0x9F:
            return True
        return self._solid_pair(s.row + 0x10, s.col)

    def _move_6(self, s: Slot) -> None:
        """0xA95A: falls under its acceleration and, on the ground, jumps
        again towards the ship's column; after its rope, only bounces on."""
        self._fire_unaimed(s)
        self._animate(s, 3, 4, self.tables.animations[6])
        step = s[1]
        if step == 1:
            if not self._ground_under(s):
                s.set_word(7, s.word(7) + s.word(23))
                return
            s[1] = 2
            s.vx(0xFE00)
            s.vy(s.word(25))
            return
        if step >= 2:
            if not self._ground_under(s):
                s.set_word(7, s.word(7) + s.word(23))
                return
            s.vy(s.word(25))
            return
        s[28] = s[28] - 1
        if not s[28] or self._its_time(s):
            s[1] = step + 1
        if not self._ground_under(s):
            s.set_word(7, s.word(7) + s.word(23))
            return
        s.vx(0x0200 if self.world.ship_col >= s.col else 0xFE00)
        s.vy(s.word(25))

    def _build_9(self, s: Slot) -> None:
        """0xAD27."""
        s.vy(0)
        s.vx(0xFD00)

    def _move_9(self, s: Slot) -> None:
        """0xAD33: straight across, and past the middle to the ship's row."""
        self._fire_unaimed(s)
        self._animate(s, 3, 6, self.tables.animations[9])
        if s.col >= 0x80:
            return
        gap = (self.world.ship_row - s.row) & 0xFF
        if (gap + 3) & 0xFF < 7:
            s.vy(0)
        elif self.world.ship_row < s.row:
            s.vy(0xFF00)
        else:
            s.vy(0x0100)

    #: 0xE162: how many of the wave in a row are still to come; type 0x0A
    #: curves one way or the other by its parity (0xAD74).
    rows_left = 0

    def _build_0a(self, s: Slot) -> None:
        """0xAD6E: curving up or down in turn, three to the left."""
        if self.rows_left & 1:
            accel, speed = 0x0080, 0xFC00
        else:
            accel, speed = 0xFF80, 0x0400
        s.set_word(23, accel)
        s.vy(speed)
        s.set_word(25, -_signed(speed) & 0xFFFF if speed & 0x8000 else speed)
        s.vx(0xFD00)

    def _move_0a(self, s: Slot) -> None:
        """0xAD92: the curve of type 3, and back the way it came past 0x30."""
        self._fire_unaimed(s)
        self._animate(s, 3, 6, self.tables.animations[0x0A])
        s.set_word(7, s.word(7) + s.word(23))
        if abs(_signed(s.word(7))) == s.word(25):
            s.set_word(23, -_signed(s.word(23)) & 0xFFFF)
        if s.col < 0x30:
            s.set_word(9, -_signed(s.word(9)) & 0xFFFF)

    #: The figure of eight (0xAE3B..0xAECF): per step, the column it waits
    #: for (below it when going left), and what it then does.
    def _build_0c(self, s: Slot) -> None:
        """0xAE07: from the bottom half, the whole route mirrored."""
        if s[4] & 0x80:
            s[1] = 0x80
        s.vy(0)
        s.vx(0xFE00)

    def _move_0c(self, s: Slot) -> None:
        """0xAE1B."""
        self._animate(s, 7, 6, self.tables.animations[0x0C])
        self._fire_unaimed(s)
        step = s[1] & 0x7F
        mirror = bool(s[1] & 0x80)
        up_or_down = 0xFE00 if mirror else 0x0200
        if step == 0:
            if s.col >= 0x41:
                return
            s.vy(up_or_down)
            s.vx(0xFE00)
        elif step == 1:
            if s.col >= 0x09:
                return
            s[2] = 0x11
            s.vx(0)
        elif step in (2, 6):
            s[2] = s[2] - 1
            if s[2]:
                return
            s.vx(0x0200 if step == 2 else 0xFE00)
        elif step == 3:
            if s.col < 0x40:
                return
            s.vy(0)
        elif step == 4:
            if s.col < 0xAE:
                return
            s.vy(0x0200 if mirror else 0xFE00)
        elif step == 5:
            if s.col < 0xE8:
                return
            s[2] = 0x0F
            s.vx(0)
        elif step == 7:
            if s.col >= 0xB1:
                return
            s.vy(0)
        else:
            return
        s[1] = s[1] + 1

    #: 0xE15A: which of a three a type 0x0B is (3, 2, 1).
    three = 3

    def _build_0b(self, s: Slot) -> None:
        """0xADB9: one of three speeds, faster from the second round."""
        fast = self.world.round > 0
        vy = {3: 0x0180, 2: 0, 1: 0xFE80}[self.three] if fast else \
            {3: 0x0100, 2: 0, 1: 0xFF00}[self.three]
        s.vy(vy)
        s.vx(0xFD00 if fast else 0xFE00)

    def _move_0b(self, s: Slot) -> None:
        """0xADE5: four drawings; from the third round, one in 0x20 game
        frames that the player fires, a shot at the ship."""
        self._animate(s, 3, 4, self.tables.animations[0x0B])
        w = self.world
        if w.round >= THREE_FIRES_FROM and not w.frames & THREE_FIRES_MASK and w.fire_pressed:
            self.fire_now(s)

    def _build_0d(self, s: Slot) -> None:
        """0xAF95: still, its first drawing for a game frame."""
        s[29] = 0
        s[20] = 1
        s[2] = STEP_0D
        s[28] = LIFE_0D
        s.vx(0)
        s.vy(0)

    def _move_0d(self, s: Slot) -> None:
        """0xAFBD: still, then at the ship at the speed of 0xB000's ramp by
        the difficulty, ten game frames each; and away once its life is out."""
        if s[1] >= 2:
            return
        s[28] = s[28] - 1
        if not s[28]:
            s[1] = 2
            s[12], s[13] = self.layout.leaving_0d, LEAVING_COLOUR_0D
            s.vx(0xFF00)
            s.vy(0)
            return
        self._animate_0d(s)
        if s[1] == 1:
            s[2] = s[2] - 1
            if s[2]:
                return
            s[1] = 0
            s[2] = STEP_0D
            s.vx(0)
            s.vy(0)
            return
        s[2] = s[2] - 1
        if s[2]:
            return
        s[1] = 1
        s[2] = STEP_0D
        speed = self.tables.lunge_speeds[self.world.difficulty]
        vy, vx, _ = self._aim(s.row, s.col, speed)
        s.vy(vy)
        s.vx(vx)

    def _animate_0d(self, s: Slot) -> None:
        """0xB010: the next drawing when this one's game frames are out."""
        s[20] = s[20] - 1
        if s[20]:
            return
        s[20] = DRAWING_LONG_0D if self.rng.randrange(2) else DRAWING_SHORT_0D
        step = s[29] + 1
        if step >= DRAWINGS_0D:
            step = 0
        s[29] = step
        s[12] = self.tables.animations[0x0D][step]

    def _build_aimed(self, s: Slot) -> None:
        """0x6C57: straight at the ship, 0x60 and two a difficulty step fast."""
        vy, vx, _ = self._aim(s.row, s.col, (0x60 + 2 * self.world.difficulty) & 0xFF)
        s.vy(vy)
        s.vx(vx)

    def _move_aimed(self, s: Slot) -> None:
        """0x5F4F: gone on the terrain, eight lower when bit 0 of byte 8 is
        clear."""
        row = s.row if s[8] & 1 else (s.row + 8) & 0xFF
        if self._solid_pair(row, s.col, walls=True):
            self.free(s)

    def _build_stone(self, s: Slot) -> None:
        """0xACAF: not to be touched or shot while it grows, ten frames a
        step."""
        s[27], s[29], s[2] = 0, 0, 0x0A
        s.vy(0)
        s.vx(0)

    def _move_stone(self, s: Slot) -> None:
        """0xACBD: three steps of ten frames riding the scroll, growing, and
        then it goes for where the ship is, 0x40 plus the difficulty fast."""
        if s[1]:
            self._stone_fires(s)
            return
        self._scroll_only(s)
        if not s.type:
            return
        s[2] = s[2] - 1
        if s[2]:
            return
        s[29] = s[29] + 1
        s[12], s[13] = self.tables.stone_drawings[min(s[29], 3) - 1]
        if s[29] < 3:
            s[2] = 0x0A
            return
        s[27] = 3
        s[1] = 1
        vy, vx, _ = self._aim(s.row, s.col, (0x40 + self.world.difficulty) & 0xFF)
        s.vy(vy)
        s.vx(vx)

    def _stone_fires(self, s: Slot) -> None:
        """0xACEA: grown, one in eight game frames that the player fires --
        from the third round, or in the second with the shield and the
        laser both on."""
        w = self.world
        if not w.round:
            return
        if w.round == 1 and not (w.shield_on and w.laser):
            return
        if w.fire_pressed and not w.frames & STONE_FIRES_MASK:
            self.fire_now(s)

    def _build_bug(self, s: Slot) -> None:
        """0x6C3F: out of the hatch, up from kind 1 and down from kind 2,
        four a frame."""
        s.vy(0xFC00 if self.spawner_kind & 1 else 0x0400)
        s.vx(0)

    def _move_bug(self, s: Slot) -> None:
        """0x5EE7: turns every four frames; rides the scroll; and once past
        the ship's row goes for it, four a frame to the left, firing from the
        second stage played on."""
        if not self.world.frames & 3:
            s[2] = s[2] + 1
            s[12] = self.layout.bug_drawings[s[2] & 7]
        if s[1]:
            return
        if self.world.moved:
            s[6] = s[6] - CELL
        if s[8] & 0x80:
            if self.world.ship_row < s.row:
                return
        elif self.world.ship_row >= s.row:
            return
        s[1] = 1
        s.vy(0)
        s.vx(0xFC00)
        if self.world.rounds:
            self.fire_at_ship(s.row, s.col)

    def blast_at(self, row: int, col: int) -> None:
        """0x7B4E: a blast where something drawn into the map went, in the
        background blasts' own slots."""
        self.blasts.make(row, col)

    def _build_rock(self, s: Slot) -> None:
        """0x6C77: the eruption's speeds, falling back at 0x88 a frame (up on
        stage 4, whose scroll runs the other way), colour 6 or 8."""
        vy, vx = self.rock_speed
        s.vy(vy)
        s.vx(vx)
        s.set_word(23, 0xFF78 if self.world.stage == 4 else 0x0088)
        s[13] = 6 + (2 if self.rng.randrange(2) else 0)

    def _build_spit(self, s: Slot) -> None:
        """0x6CB4: the speeds 0xEC12 and 0xEC14 hold."""
        vy, vx = self.next_speed
        s.vx(vx)
        s.vy(vy)

    def _move_spit(self, s: Slot) -> None:
        """0x71B0: 0x71AD with no fall -- it blows up on the terrain it meets,
        0x10 below going down."""
        row = s.row if s[8] & 0x80 else (s.row + 0x10) & 0xFF
        if self._solid_pair(row, s.col, walls=True):
            self.kill(s, pays=False)

    def _build_anchor(self, s: Slot) -> None:
        """0x6CA6: the drawing 0xEC1B holds, and still."""
        s[12] = self.next_drawing
        s.vy(0)
        s.vx(0)

    def _build_bouncer(self, s: Slot) -> None:
        """0xB8DA."""
        art = self.tables.stage5
        assert art is not None
        packed = self.bouncer
        s[19] = packed >> 3 & 3
        speed_at = (packed & 7) >> 1
        if self.world.round:
            speed_at += FASTER
        speed = art.bouncer_speeds[speed_at]
        if packed & 1:
            speed = -speed & 0xFFFF
        s.vy(speed)
        s.vx(BOUNCER_ACROSS)

    def _move_bouncer(self, s: Slot) -> None:
        """0xB915: turned back at row 8 going up, at its floor going down."""
        art = self.tables.stage5
        assert art is not None
        self._animate(s, 3, 8, art.bouncer_drawings)
        if s[8] & 0x80:
            if s.row < BOUNCER_TOP:
                s.vy(-s.word(7) & 0xFFFF)
        elif s.row >= art.floors[s[19]]:
            s.vy(-s.word(7) & 0xFFFF)

    def _build_aimed_slow(self, s: Slot) -> None:
        """0x6C53: as 0x6C57, from 0x50."""
        vy, vx, _ = self._aim(s.row, s.col, (0x50 + 2 * self.world.difficulty) & 0xFF)
        s.vy(vy)
        s.vx(vx)

    def _build_prize(self, s: Slot) -> None:
        """0xA7B9..0xA7D3: shots go through it; taken once or eight times."""
        s[27] = s[27] & ~2
        s[23] = {PRIZE_ONCE: 1, PRIZE_EIGHT: 8}.get(s.type, 0)
        s.vx(0)
        s.vy(0)

    def _build_box(self, s: Slot) -> None:
        """0xA7D6."""
        s.vx(0)
        s.vy(0)

    def _move_prize(self, s: Slot) -> None:
        """0xA7D9: gone off the left untaken, the chain starts again."""
        self._scroll_only(s)
        if not s.type:
            self.chain = 0

    @staticmethod
    def keep_under(slots: list[Slot], terrain: Map) -> None:
        """0x68C2 ("the object's cell"): each one drawn with characters keeps
        where it falls and the four cells it will cover."""
        cells = terrain.cells
        for s in slots:
            if not s.type or not s[11]:
                continue
            at = (s.row >> 3) * MAP_COLUMNS + (s.col >> 3)
            s.set_word(UNDER_AT, MAP_AT + at)
            for n, step in enumerate(UNDER_CELLS):
                if at + step < len(cells):
                    s[UNDER + n] = cells[at + step]

    @staticmethod
    def put_back_under(slots: list[Slot], terrain: Map) -> None:
        """0x69CB ("draw two by two"): the cells kept go back to the map,
        whatever has been drawn or wiped there since."""
        cells = terrain.cells
        for s in slots:
            if not s.type or not s[11] or s.col >= UNDER_LAST_COL:
                continue
            at = s.word(UNDER_AT) - MAP_AT
            for n, step in enumerate(UNDER_CELLS):
                if 0 <= at + step < len(cells):
                    cells[at + step] = s[UNDER + n]

    def open_box(self, s: Slot) -> None:
        """0x74E8 ("start blowing up"): shot or touched, a box becomes what
        its mark says."""
        mark = s[14]
        s[0] = (mark + OPENS_INTO) & 0xFF
        if mark == 3:
            s[12] = self.layout.ship_drawing
        else:
            s[12] = self.layout.capsule_drawing
            s[23] = 1 if mark == 4 else 8
        s[27] = s[27] & ~2
        # 0x750B: what it kept of the map, gone.
        for n in range(len(UNDER_CELLS)):
            s[UNDER + n] = 0

    def take(self, s: Slot) -> int:
        """0x74BC and 0x74CF: a prize floats up; a ship is one more life
        (the count returned), a capsule pays by the chain."""
        kind = s.type
        s[24], s[0], s[2] = kind, FLOATING, FLOAT_FRAMES
        s[25] = s[4]
        s[11], s[27] = 0, 0
        if kind == PRIZE_SHIP:
            s[13], s[12] = 2, self.layout.float_pattern
            self.world.sounds.append(0x11)
            return 1
        s[13] = 8
        self.chain = min(self.chain + 1, CHAIN_MAX)
        self.world.score += _bcd(self.tables.prize_points[self.chain])
        s[12] = self.layout.float_pattern + self.chain * 4
        self.world.sounds.append(0x10)
        return 0

    def _move_floating(self, s: Slot) -> None:
        """0xA7DF."""
        self._scroll_only(s)
        if not s.type:
            if (s[23] - 1) & 0xFF:
                self.chain = 0
            return
        if s[4]:
            s[4] = s[4] - 1
        s[2] = s[2] - 1
        if s[2]:
            return
        if s[24] == PRIZE_SHIP:
            self.free(s)
            return
        s[23] = s[23] - 1
        if not s[23]:
            self.free(s)
            return
        s[0], s[11], s[12] = s[24], 1, self.layout.capsule_drawing
        s[27] = s[27] | 1
        s[4] = s[25]

    def _move_rock(self, s: Slot) -> None:
        """0x71AD: falls, and blows up on the terrain it meets 0x10 below
        (when falling) or where it is (0x71B0)."""
        s.set_word(7, s.word(7) + s.word(23))
        self._move_spit(s)

    # -- blowing up ----------------------------------------------------------------

    def hit(self, s: Slot) -> None:
        """0x7284: one hit; the last one pays and blows it up."""
        s[15] = s[15] - 1
        if s[15]:
            return
        self.kill(s)

    def kill(self, s: Slot, pays: bool = True) -> None:
        """0x72C2 ("pay for the enemy") and 0x72D2 ("burst the enemy"): a
        point, the sound, and the slot becomes a blast."""
        if pays:
            self.world.score += 5 if s.type == 0x1F else 1
        self.world.sounds.append(self.tables.kill_sounds[s.type])
        s[0], s[12] = ((BLAST_0D, self.layout.blast_0d_pattern) if s.type == 0x0D
                       else (BLAST, self.layout.blast_pattern))
        was_characters = s[11]
        s[11] = 0
        if was_characters:
            s[13] = 0x0F
        s[2], s[27] = 0, 0

    def _blast(self, s: Slot) -> None:
        """0x5E3E: sixteen game frames through four drawings, then what it
        leaves."""
        count = s[2]
        s[2] = count + 1
        if count < BLAST_FRAMES:
            s[12], s[13] = self.tables.blast[(count >> 2) & 3]
            self._scroll_only(s)
            return
        self._leaves(s)

    def _blast_0d(self, s: Slot) -> None:
        """0x5EC8: sixteen game frames through four characters, then what it
        leaves."""
        count = s[2]
        s[2] = count + 1
        if count < BLAST_FRAMES:
            s[12] = self.tables.blast_0d[count >> 2 & 3]
            self._scroll_only(s)
            return
        self._leaves(s)

    def _leaves(self, s: Slot) -> None:
        """0x5E65: a capsule if it was marked, or the last of its group."""
        if s[17]:
            group = self._group(s[18])
            if group is None:
                self.free(s)
                return
            group[2] -= 1
            if group[2] > 0:
                self.free(s)
                return
            number, group[0] = group[0], 0
            kind = CAPSULE if number & 7 else BOMB
        else:
            if not s[14]:
                self.free(s)
                return
            kind = CAPSULE if s[14] == 1 else BOMB
        s[0] = kind
        s[12] = self.layout.capsule_drawings[kind]
        s[11] = 1
        s[27] = 1
        s[4] = (s[4] & 0xF8) + 4
        s[6] = s[6] & 0xF8
        self._scroll_only(s)
