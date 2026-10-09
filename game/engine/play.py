"""A game: the stage, the ship, its shots, the lives -- a game frame at a time.

The order inside `step` is the original's (bank 0, 0x4532, "a game frame"):
the map scrolls, the ship moves, the shots move, a new shot is fired, the
ship meets the map, the shots meet the map. Only what this engine has so far
is in it; the rest of that list (enemies, the meter, the options) is not.
"""

import copy
import random
from enum import Enum
from typing import Callable

from game.engine.background import STAGE_3, Background, Guns
from game.engine.stage5 import Stage5
from game.engine.ending import GONE_PAST, Core, CoreArt, Crystal, Ending, Heads, Walkers
from game.engine.eye import Eye
from game.engine.fortress import Fortress
from game.engine.nuclei import Nuclei
from game.engine.objects import (
    BIG, BOMB, BOX, CAPSULE, LATE_TYPES, PRIZE_EIGHT, PRIZE_ONCE, PRIZE_SHIP, Objects, Slot,
)
from game.engine.original import (
    CAPSULE_POINTS, ENEMY_REACH, HIT_COLS, HIT_LAST_COLUMN, HIT_OFFSET, HIT_ROWS, LIVES, METER_CELLS,
    FIRE, POWER, RIGHT, SHOT_PROOF, STAGE_5, STAGE_START, VIDEO_FRAMES_A_STEP, STAR_MASKS,
    FIRST_SHIP_AT, MAP_COLUMNS, MAX_LIVES, ONE_MORE_SOUND, DRAWN_BELOW, DRAWN_LEFT_OF, EMPTY_TYPES, MAP_AT,
    PIECE_UNDER, PIECES_KEPT, SCORE_TOP, SCORE_WRAP, SHIP_AT_TOP, SHIP_EVERY, SHIP_START_X, SHIP_START_Y, TAKEN_AT, TOUCH_COLS, TOUCH_DX, TOUCH_DY,
    UNDER_AT, UNDER_CELLS,
    SHIELD_SPRITE_DX, SHOT_REACH, SPRITE_ENTRIES, SPRITE_TURN_STEP, TOUCH_ROWS,
)
from game.engine.layout import Layout
from game.engine.stages import Stages
from game.engine.options import Options
from game.engine.original import (
    SHIELD_COLS, SHIELD_DX, SHIELD_HITS, SHIELD_ROWS, SHIELD_SHOT_COLS,
    SHIELD_SHOT_COLS_CHARS, SHIELD_SHOT_ROWS, SHIELD_WEAK, WORD_LASER, WORD_MISSILE,
)
from game.engine.scroll import Scroll
from game.engine.ship import Ship
from game.engine.shots import LASER, NORMAL, Card, Shot, Shots
from game.engine.tables import Tables
from game.engine.terrain import Terrain
from game.engine.target import AFTER_BONUS, Target
from game.engine.words import Keyboard

from game.engine.waves import Cannons, Prizes, Waves

#: Between lives, state 4 (0x53B1) runs once an interrupt, and 0xE003 with
#: it: the game frame that finds the ship gone comes in (0x5367 leaves 0x20
#: in 0xE004), then the curtain
#: (0x558A) blanks a column of the 22 rows a tick for 0x20 ticks; a tick
#: takes the ship out of the reserve and loads the band (0x53CC, two
#: interrupts), then 0x10 ticks of wait, 0x78 with two players to read
#: whose turn it is (0x5457, 0x545F); on the last the stage is built, which
#: takes more interrupts with 0xE003 still, by the stage built (measured at
#: 60 Hz: 17.4 video frames for stage 1 up to 22.8 for stage 5; a life lost
#: on a bonus stage goes on at stage 3, 4, 5 or 8, and takes as long).
CURTAIN_TICKS, CURTAIN_ROWS, WAIT_ONE, WAIT_TWO = 0x20, 22, 0x10, 0x78
BUILD_INTERRUPTS = (0, 0x11, 0x13, 0x15, 0x15, 0x16, 0x0E, 0x15, 0x16,
                    0x0F, 0x0F, 0x0F, 0x0F)
#: The jump to a bonus stage or back (0x6FB9) cuts its game frame and
#: builds: one and the building, measured into 9 and 10 (16) and back into
#: 3 and 4 (21, 22) -- give or take the interrupt the Z80's time rounds to.
#: The game frame that changes stage (0x6D53 into 0x4100) takes the
#: building and its own: by the stage it leads to, measured (0xE003's
#: writes against the interrupts, 60 Hz). Two more than a new life's
#: building, but for stage 3's.
STAGE_CHANGE_INTERRUPTS = (0, 19, 21, 22, 23, 24, 16, 23, 24)
#: The game frame that loads the core's characters (0x4A6D) takes seven.
BOSS_ART_INTERRUPTS = 7


def _within(value: int, window: int, reach: int | None = None) -> bool:
    """0x7376: a difference, as eight bits, inside [-reach, window) -- reach
    is the window unless the caller's BC says otherwise."""
    value &= 0xFF
    return value < window or value + (window if reach is None else reach) > 0xFF


class Phase(Enum):
    PLAYING = "playing"
    #: State 7: GAME OVER, until its tune has played.
    OVER = "over"
    #: State 7 done with nobody to go on: back to the title.
    FINISHED = "finished"


#: State 6 asks for the GAME OVER tune (0x5492).
GAME_OVER_TUNE = 0xCA


class Over:
    """State 7 (0x549A): the curtain, GAME OVER written, and the wait for
    its tune, CONTINUE listened for all the while."""

    def __init__(self) -> None:
        self.curtain = 0
        self.written = False
        #: 0xE06F: CONTINUE was asked for.
        self.go_on = False


class Between:
    """State 4: the curtain, the ship out of the reserve, the wait."""

    def __init__(self, wait: int, curtain: bool = True) -> None:
        #: The columns blanked so far; all of them when there is none.
        self.curtain = 0 if curtain else CURTAIN_TICKS
        self.loaded = not curtain
        self.wait = wait
        #: The game's opening: the curtain comes down over the title.
        self.opening = False


class Play:
    def __init__(self, terrain: Terrain, tables: Tables | None = None, seed: int = 0,
                 stages: Callable[[int], Terrain] | None = None, players: int = 1,
                 start_round: int = 0, opening: bool = False) -> None:
        """`opening`: the game opens as the cartridge's does, from the title
        (state 3 into 4): the curtain over it, a ship out of the reserve,
        the wait (the turn's label with two players), the stage built."""
        self.terrain = terrain
        self.tables = tables
        #: Which characters and sprites the rules draw with, and what the
        #: stages' rules key off.
        self.layout = tables.layout if tables is not None else Layout()
        self.stage_rules = tables.stages if tables is not None else Stages()
        #: Where the next stage's terrain comes from; none, and a stage's end
        #: is the end of the game.
        self.stages = stages
        #: 0xE06A, the round; 0xE066, stages played; 0xE111, the difficulty.
        self.round = start_round
        self.stages_played = 0
        self.difficulty = 0
        #: The stage just changed: the window reloads its characters.
        self.new_stage = False
        self.rng = random.Random(seed)
        self.lives = LIVES
        self.phase = Phase.PLAYING
        self.pad = 0
        #: 0xE003: game frames counted.
        self.frames = 0
        #: Sounds asked for this game frame, by the original's numbers.
        self.sounds: list[int] = []
        self.scroll = Scroll(terrain, self.rng, self.layout.stars)
        self.ship = Ship(terrain.number, self.layout, self.stage_rules)
        self.shots = Shots(terrain.number, self.layout, self.stage_rules)
        #: Points, as the original counts them: each is a hundred on the band.
        self.score = 0
        #: 0xE067: the score's top four digits the next ship comes at.
        self.next_ship = FIRST_SHIP_AT
        #: 0xE054: the best score this play has seen (the host keeps the best
        #: across plays), or all nines once a score has wrapped.
        self.record = 0
        #: 0xE130: the meter's lit cell, 0 for none.
        self.meter = 0
        #: For measuring against the original with its death patched out
        #: (tools/compare_play.py --immortal): the ship does not die.
        self.immortal = False
        #: Set by the host each game frame: the sound driver's first channel
        #: still sounds (0xE012) -- the fade and the ending wait for it.
        self.channel_busy = False
        #: What this game frame did to the VRAM (the fade's), for the host.
        self.vram_writes: list[tuple[int, int, int, bool]] = []
        #: 0xE070: the game's endings seen, which picks the ending's word.
        self.finales = 0
        #: 0xE06E: HYPER has been typed this game.
        self.hyper_used = False
        #: The words and names, when the host has the cartridge's.
        self.keyboard: Keyboard | None = None
        #: 0xE06C/0xE06D: the kind of the last target counted, and how many
        #: in a row differ (stages 1 and 4); both cleared each round.
        self.targets_taken = [0, 0]
        #: Two players (0xE002 bit 5): whose turn (bit 7), the other's 0x30
        #: bytes of state (0xE090, copied from the first's at the start,
        #: 0x557C), and the turn's label, shown this many game frames
        #: before a life (0x545F: 0x78 interrupts).
        self.players = players
        self.turn = 0
        self.resume = STAGE_START
        self.other: dict[str, object] | None = self._state() if players == 2 else None
        if self.other is not None:
            # 0x557C copies the block before any stage has set its distance.
            self.other["resume"] = 0
        #: State 4 between two lives, while it lasts.
        self.between: Between | None = None
        #: How many interrupts this game frame took: two on the 60 Hz machine
        #: (VIDEO_FRAMES_A_STEP), more when it had much VRAM to move.
        self.interrupts = VIDEO_FRAMES_A_STEP
        self._start_life(STAGE_START, first=True, take=not opening)
        if players == 2 and not opening:
            self.between = Between(WAIT_TWO, curtain=False)
        if opening:
            self.between = Between(WAIT_TWO if players == 2 else WAIT_ONE)
            self.between.opening = True

    def _start_life(self, distance: int, first: bool = False, take: bool = True) -> None:
        """State 4 (0x53C8) and "start the stage" (0x414B): a ship out of the
        reserve with a fresh card (0x4193), the difficulty the stage and the
        round say (0x41A3), and the stage from its checkpoint if the last
        life had passed it (0x41C3)."""
        if take:
            self.lives -= 1
        if self.terrain.number in AFTER_BONUS and self.stages is not None and not first:
            # 0x4137: a life lost on a bonus stage goes on at the stage it
            # leads to, from the start.
            self.terrain = self.stages(AFTER_BONUS[self.terrain.number])
            distance = 0
        if distance >= self.terrain.checkpoint:
            distance = self.terrain.checkpoint
        else:
            distance = STAGE_START
        self.ship = Ship(self.terrain.number, self.layout, self.stage_rules)
        self.shots = Shots(self.terrain.number, self.layout, self.stage_rules)
        self.meter = 0
        self.options = Options(self.layout.options)
        #: 0xE200 and 0xE201: 1 no shield, 2 weak, 3 on; the hits left.
        self.shield = 1
        self.shield_hits = 0
        if self.terrain.number < 9:
            self.difficulty = min(self.round * 4 + self.terrain.number - 1, 0x0F)
        self._start_stage(distance)

    def _next_stage(self) -> None:
        """0x6FD0 ("go on to the next stage") then 0x4100: the difficulty up a
        step, the next stage from its start; the ship keeps everything."""
        assert self.stages is not None
        self._harder(1)
        self.stages_played += 1
        number = self.terrain.number + 1
        # The stage that comes is the terrain's own number: the cartridge's is
        # always the one asked for; a game of its own stages may answer with
        # a later one (it has none like the one asked), or with an earlier
        # one -- its first again -- and that is a new round.
        terrain = self.stages(1 if number > 8 else number)
        if terrain.number < number:
            self.difficulty = max(self.difficulty - 4, 0)
            self.round = min(self.round + 1, 0xFF)
            self.targets_taken = [0, 0]
        number = terrain.number
        self.terrain = terrain
        self.ship.stage = number
        self.shots.stage = number
        self.new_stage = True
        self._next_start()

    def _jump(self, number: int) -> None:
        """0x6FB9 ("jump to the stage"): to a bonus stage or back from one; the
        difficulty and the stages played stay."""
        assert self.stages is not None
        self.terrain = self.stages(number)
        number = self.terrain.number
        self.ship.stage = number
        self.shots.stage = number
        self.new_stage = True
        self._next_start()
        self.interrupts = 1 + BUILD_INTERRUPTS[number]

    def _next_start(self) -> None:
        """0x4100: the stage built with 0xE300-0xEBFF cleared and a few
        counters set (0x41EA), but not the rest of 0xE100-0xE2FF, as a new
        life's 0x414B does: the waves' number (0xE166) and the enemies asked
        for (0xE125), the wave in a row (0xE160-0xE165) and the sprite
        table's turn (0xE17F) run on."""
        objects, waves, sprites_from = self.objects, self.waves, self.sprites_from
        self._start_stage(STAGE_START)
        self.sprites_from = sprites_from
        if objects is not None and self.objects is not None:
            self.objects.wave_number = objects.wave_number
            self.objects.rows_left = objects.rows_left
        if waves is not None and self.waves is not None:
            new = self.waves
            new.asked = waves.asked
            new.rows_step, new.rows_delay, new.rows_left = (
                waves.rows_step, waves.rows_delay, waves.rows_left)
            new.rows_type, new.rows_row = waves.rows_type, waves.rows_row

    def _harder(self, steps: int) -> None:
        """0x70CA: up to 0x0F."""
        if self.difficulty + steps < 0x10:
            self.difficulty += steps

    def _stage_tables(self) -> None:
        """A stage that brings its own tables (and core) is played with
        them: the free assets' stages do; the cartridge's stages share
        one set, handed in at the start, and bring none."""
        tables = getattr(self.terrain, "tables", None)
        if tables is not None:
            self.tables = tables
            self.stage_rules = tables.stages
            self.ship.stages = self.shots.stages = self.stage_rules
        core_art = getattr(self.terrain, "core_art", None)
        if core_art is not None:
            self.core_art = core_art

    def _start_stage(self, distance: int) -> None:
        self._stage_tables()
        # 0x41EA: the music's pending change and its fade are cleared.
        self.stage_built = True
        self.sprites_from = 0
        self.target = Target()
        #: 0xE071: a word has paid on this stage (0x4107).
        self.stage_word = 0
        self.prizes: Prizes | None = None
        self.scroll = Scroll(self.terrain, self.rng, self.layout.stars)
        self.objects: Objects | None = None
        self.waves: Waves | None = None
        self.cannons: Cannons | None = None
        if self.tables is not None:
            self.objects = Objects(self.tables, self.rng, self.terrain.number)
            self.waves = Waves(self.objects, self.terrain.number)
            if self.terrain.number == STAGE_5 and self.tables.stage5 is not None:
                self.waves.bouncers = self.tables.stage5.bouncers
            if self.terrain.number in AFTER_BONUS:
                self.prizes = Prizes(self.objects, self.tables.prize_script[self.terrain.number])
            self.cannons = Cannons(self.objects, self.terrain.number)
            self.objects.world.stage = self.terrain.number
            self.ending: Ending | None = Ending(self.objects, self.terrain.number)
            self.waves.flocks = self.ending.flocks
            number = self.terrain.number
            tables = self.tables
            script = (tables.background_script[number]
                      if number < len(tables.background_script) else ())
            self.guns: Guns | Stage5 | None = None
            if number == STAGE_3 and tables.guns is not None:
                self.guns = Guns(self.objects, script, tables.guns)
                script = ()
            elif number == STAGE_5 and tables.stage5 is not None:
                # 0x5FE4: stage 5's background is its own.
                self.guns = Stage5(self.objects, tables.stage5)
                script = ()
            self.background: Background | None = Background(
                self.objects, script, tables.background_drawings, number)
            background, guns = self.background, self.guns

            def each(distance: int, col: int) -> None:
                # 0x460C: the cannons' script, then the background's.
                assert self.cannons is not None
                self.cannons.fill(distance, col)
                background.fill(distance, col)
                # 0x463E: stage 7's type 0x0D.
                assert self.waves is not None
                self.waves.appearances.fill(distance, col)
                if guns is not None:
                    guns.fill(distance, col)
            self.scroll.start(distance, each)
        else:
            self.ending = None
            self.background = None
            self.guns = None
            self.scroll.start(distance)

    #: The stage and distance the music is looked at with this game frame
    #: (0x7003), for the host's sound driver; None when it is not.
    music: tuple[int, int] | None = None
    #: A stage was built this game frame (0x41EA): the host's music forgets
    #: its pending change and its fade, after looking at the music.
    stage_built = False

    @property
    def music_frozen(self) -> bool:
        """0xE114 or 0xE1C0 (0x7008): the stage's music is left alone."""
        return bool(self.target.mode) or (self.ending is not None and self.ending.music_frozen)

    def taken(self) -> list[bool]:
        """0xA022: which meter cells the ship already has."""
        w = self.shots
        return [self.ship.speed >= TAKEN_AT, w.missile >= 2, bool(w.double),
                w.laser >= 2, len(self.options.options) >= 2, self.shield > 1]

    def shooters(self) -> list[Card]:
        """The ship's card and its options' (0xE200, 0xE220, 0xE240)."""
        cards = [Card(self.ship.row, self.ship.col, self.ship.exploding is None)]
        cards += [Card(o.row, o.col) for o in self.options.options]
        return cards

    #: 0xE17F, in entries: where the sprite table is sent from (0x415A).
    sprites_from = 0
    #: The ship was flying as this game frame began; 0xE200 shows it blown
    #: up only from the next (0x9B7B), and its cards with it.
    was_flying = True
    #: Sprites are sent this game frame: not between lives, nor on the tick
    #: that builds the stage (0x55AA; 0xEC80 is left empty).
    sprites_on = True

    def ship_cards(self) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]] | None:
        """0xA17F: the ship's two entries of 0xEC80, (row, column, pattern,
        colour); None with no ship on screen."""
        ship = self.ship
        if ship.gone or not self.sprites_on:
            return None
        (p1, c1), (p2, c2) = self.ship_sprites()
        flying = ship.exploding is None or self.was_flying
        dx = SHIELD_SPRITE_DX if self.shield != 1 and flying else 0
        return (ship.row, ship.col, p1, c1), (ship.row, (ship.col + dx) & 0xFF, p2, c2)

    def ship_sprites(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """0x99A1: the ship's two sprites by its state, the pad, and the
        shield's blink every four frames."""
        if (self.ship.exploding is not None and not self.was_flying) or self.tables is None:
            return self.ship.sprites
        vertical = self.pad & 3
        at = 0 if vertical == 3 else vertical
        if self.shield != 1 and self.frames & 4:
            at += 3
        p1, c1, p2, c2 = self.tables.ship_cards[self.shield][at]
        return (p1, c1), (p2, c2)

    def _set_world(self, objects: Objects, pressed: int) -> None:
        """What the objects' rules read of the rest of the game."""
        objects.shot_this_frame = False
        world = objects.world
        world.ship_row, world.ship_col = self.ship.row, self.ship.col
        world.frames = self.frames
        world.sounds = self.sounds
        world.stage, world.stage_end = self.terrain.number, self.terrain.end
        world.shield_on = self.shield == 3
        world.difficulty = self.difficulty
        world.rounds = self.stages_played
        world.round = self.round
        world.options = len(self.options.options)
        world.laser = self.shots.laser
        world.fire_pressed = bool(pressed & FIRE)

    def step(self, pad: int) -> None:
        """One game frame, with the pad as 0x577D reads it."""
        pressed = pad & ~self.pad
        self.pad = pad
        self.frames = (self.frames + 1) & 0xFF
        self.sounds = []
        self.music = None
        self.stage_built = False
        self.drawn = False
        changed = False
        if self.phase is Phase.FINISHED:
            return
        if self.phase is Phase.OVER:
            self.sprites_on = False
            self._over_tick()
            return
        self.sprites_on = False
        if self.between is not None:
            self._between_tick()
            return
        if self.ship.gone:
            self._life_over()
            return
        self.sprites_on = True
        self.was_flying = self.ship.exploding is None
        if self.ship.exploding is None:
            # 0x4538: the sprite table turns, but not for a ship blowing up.
            self.sprites_from = (self.sprites_from + SPRITE_TURN_STEP) % SPRITE_ENTRIES
        objects = self.objects
        if objects is not None:
            self._set_world(objects, pressed)
        if self.ship.exploding is None and not self.music_frozen:
            # 0x7003, first thing 0x6CCD does: the stage's music looked at
            # with the ship, the distance and 0xE1C0/0xE114 as they are now.
            self.music = (self.terrain.number, self.scroll.distance)
        ending = self.ending
        if ending is not None:
            # 0x453B: how the stage ends, before anything moves.
            ending.update(self.scroll.at_limit, self.frames, self.scroll.distance,
                          self.difficulty, self.ship.exploding is None, bool(self.target.mode))
            if ending.jump_to is not None:
                # 0x6FB9 drops its way back: the game frame ends here.
                self._jump(ending.jump_to)
                return
            if ending.next_stage:
                # 0x6D53: the next stage is loaded, and the game frame goes
                # on with it; its end is looked at from the next.
                if ending.finale_done:
                    # 0x4C93: the game's ending left the ship, and each
                    # option with its queue, at 0x504A.
                    self.ship.place(SHIP_START_Y, SHIP_START_X)
                    self.options.place(SHIP_START_Y, SHIP_START_X)
                terrain = self.terrain
                self._stage_over()
                if self.phase is Phase.OVER:  # type: ignore[comparison-overlap]
                    return
                changed = self.terrain is not terrain
                objects, ending = self.objects, None
                if objects is not None:
                    self._set_world(objects, pressed)
        if ending is not None:
            if ending.limit is not None:
                self.scroll.limit = ending.limit
            if ending.finale:
                # 0x4545: with 0xE1D1 up the game frame ends here.
                return
            if ending.leaving is not None:
                # 0x4ADE: the pad held right, nothing pressed; gone past
                # column 0xF0, the screen is cleared and the finale starts.
                ending.leave()
                pad, pressed = RIGHT, 0
                if self.ship.col >= GONE_PAST:
                    # 0x4AFA puts 0xE1D1 up, and 0x4545 cuts this game
                    # frame short too: one interrupt.
                    self.scroll.map.clear()
                    ending.finale = True
                    self.interrupts = 1
                    return
        target = self.target
        if self.ship.exploding is None and objects is not None and self.stage_rules.targets:
            # 0x454A: the hidden target, with the last game frame's column.
            limit = target.update(self.terrain.number, self.scroll.distance, self.scroll.moved,
                                  self.ship.row, self.ship.col, self.targets_taken, self.sounds)
            if limit is not None:
                self.scroll.limit = limit
                if self.prizes is not None:
                    self.prizes.row = 0
                # 0x7596: everything on screen blows up, and pays, from the
                # last slot back.
                for s in reversed(objects.slots):
                    if 1 <= s.type <= 0x0F:
                        objects.kill(s)
        stopped = bool(target.mode)
        self.scroll.mode = target.mode
        if objects is not None:
            objects.frozen = stopped
        self.scroll.step()
        if objects is not None:
            objects.world.moved = self.scroll.moved
            objects.world.distance = self.scroll.distance
        self.vram_writes = []
        self.interrupts = (STAGE_CHANGE_INTERRUPTS[self.terrain.number] if changed
                           else VIDEO_FRAMES_A_STEP)
        if ending is not None and ending.fortress is not None:
            # 0x457C: the gate, early in the game frame.
            ending.fortress.rise(self.scroll.map, self.scroll.moved)
        if not stopped:
            # 0x9955: with the screen stopped the ship stays where it is.
            self.ship.step(pad, ending.leaving if ending is not None else None)
        flying = self.ship.exploding is None
        if flying and pressed & POWER:
            self._take_power()
        if flying:
            self.options.step(pad, self.ship.row, self.ship.col)
        self.shots.sounds = self.sounds
        self.shots.move(self.shooters(), self.scroll.map, self.frames)
        if flying:
            self.shots.trigger(pad, pressed, self.shooters())
        core = ending.core if ending is not None else None
        if objects is not None and self.waves is not None and self.cannons is not None:
            # 0xE204 is read where it is used: the ship has moved by now.
            objects.world.ship_row, objects.world.ship_col = self.ship.row, self.ship.col
            objects.step(self.scroll.map)
            if (ending is None or not ending.erupting) and not stopped:
                self.waves.step(self.scroll.distance, self.scroll.moved,
                                ending.boss if ending is not None else None)
            if self.prizes is not None:
                self.prizes.step(self.scroll.distance, self.scroll.moved)
            if ending is not None:
                ending.rain()
            objects.step_shots(self.scroll.map)
            self.cannons.step(self.scroll.distance, self.scroll.moved)
            if self.background is not None:
                self.background.step(self.scroll.moved)
                self.background.spawn(self.scroll.distance, self.scroll.moved)
            if self.guns is not None:
                self.guns.step(self.scroll.moved, self.ship.row, self.ship.col, self.difficulty)
                self.guns.spawn(self.scroll.distance, self.scroll.moved)
            # 0x45AF: the background blasts.
            objects.blasts.step(self.scroll.moved)
            if core is not None:
                core.update(self.ship.row, self.frames, self.difficulty)
                if core.needs_art:
                    core.needs_art = False
                    self.boss_art = True
                    self.interrupts = BOSS_ART_INTERRUPTS
            if ending is not None:
                ending.erupt(self.frames, self.scroll.moved)
                if ending.walkers is not None:
                    ending.walkers.update(self.ship.row, self.frames)
                if ending.crystal is not None:
                    ending.crystal.update(self.scroll.moved)
                if ending.heads is not None:
                    ending.heads.update(self.ship.row, self.ship.col, self.difficulty)
                if ending.nuclei is not None:
                    ending.nuclei.update(self.scroll.distance, self.difficulty)
                if ending.eye is not None:
                    ending.eye.update(self.scroll.map, self.frames, self.channel_busy)
                if ending.fortress is not None:
                    ending.fortress.update(self.scroll.distance, self.scroll.moved,
                                           self.scroll.at_limit, self.channel_busy)
                fade = ending.fade
                if fade is not None:
                    self.vram_writes = fade.writes
                    self.interrupts = fade.interrupts or self.interrupts
                    if fade.clear_map:
                        self.scroll.map.clear()
            if core is not None:
                self._shots_against_core(core)
            if ending is not None and ending.heads is not None:
                self._shots_against_heads(ending.heads)
            if ending is not None and ending.walkers is not None:
                self._shots_against_heads(ending.walkers)
            if ending is not None and ending.nuclei is not None:
                self._shots_against_heads(ending.nuclei)
            if ending is not None and ending.eye is not None:
                self._shots_against_heads(ending.eye)
            if ending is not None and ending.fortress is not None:
                self._shots_against_heads(ending.fortress)
        self.shots.boss = core is not None and core.alive
        # 0x9F81: the laser meets the map before the core is drawn into it.
        self.shots.meet_lasers(self.scroll.map)
        # 0x68FB: with 0xE152 at 1, 5 or 6 what the background blasts will
        # cover, kept; 0x6936: what the boss's pieces will.
        blasts_kept = ending is not None and ending.boss in PIECES_KEPT
        if objects is not None and blasts_kept:
            objects.blasts.keep(self.scroll.map)
        kept = self._keep_under_pieces(ending)
        # 0x7C5A: the boss drawn; 0x61AF the background; 0x8FFE the
        # crystal; 0xB431 the turrets.
        drawn = self._draw_core(core)
        heads = ending.heads if ending is not None else None
        walkers = ending.walkers if ending is not None else None
        nuclei = ending.nuclei if ending is not None else None
        head_cells: list[tuple[int, int, int]] = []
        if heads is not None or walkers is not None or nuclei is not None:
            cells = heads.cells() if heads is not None else []
            if walkers is not None:
                cells += walkers.cells(self.frames)
            if nuclei is not None:
                cells += nuclei.cells()
            head_cells = [(r, c, ch) for r, c, ch in cells if self.scroll.map.inside(r, c)]
            for r, c, ch in head_cells:
                self.scroll.map[r, c] = ch
        fortress = ending.fortress if ending is not None else None
        if fortress is not None:
            claws = [(r, c, ch) for r, c, ch in fortress.cells() if self.scroll.map.inside(r, c)]
            for r, c, ch in claws:
                self.scroll.map[r, c] = ch
        if self.background is not None:
            self.background.draw(self.scroll.map)
        crystal = ending.crystal if ending is not None else None
        if crystal is not None:
            crystal.draw(self.scroll.map)
        if self.guns is not None:
            self.guns.draw(self.scroll.map)
        if not stopped:
            # 0x71E8 looks only at the screen stopped (0xE1C0): the shots
            # still flying meet the enemies with the ship blowing up.
            self._collide()
        # 0x9F85: the other shots, after. One that ends on the map sounds
        # only with 0xE151 up and 0xE152 at 0, the core (0x9FC8).
        if self.shots.meet(self.scroll.map) and ending is not None and ending.boss == 0:
            self.sounds.append(6)
        # 0x6893: what the objects drawn with characters will cover, kept;
        # the enemy shots' too with the crystal up (0xE1B0) or the core's
        # boss on (0xE151 up, 0xE152 at 0).
        crystal_on = crystal is not None
        boss_shots = ending is not None and ending.boss == 0
        if objects is not None:
            objects.keep_under(objects.slots, self.scroll.map)
            if crystal_on or boss_shots:
                objects.keep_under(objects.shots, self.scroll.map)
            # 0x47B7: the background blasts, after all has met the map.
            objects.blasts.draw(self.scroll.map)
        self.shown = self._shown(objects)
        self.drawn = True
        # 0x6983, once the screen is up, in its order: the objects' cells
        # put back, the crystal, the enemy shots' cells, the background,
        # the turrets, the boss, the enemy shots' cells again, the blasts.
        # What is put back is what was there at 0x6893: something wiped in
        # between comes back under an enemy shot.
        if objects is not None:
            objects.put_back_under(objects.slots, self.scroll.map)
        if crystal is not None:
            crystal.restore(self.scroll.map)
        if objects is not None and crystal_on:
            objects.put_back_under(objects.shots, self.scroll.map)
        if self.background is not None:
            self.background.erase(self.scroll.map)
        if isinstance(self.guns, Stage5):
            self.guns.erase(self.scroll.map)
        for row, col, _ in drawn:
            # 0x7EC8: the core's rectangle is cleared once it is on screen.
            self.scroll.map[row, col] = 0
        if kept:
            self._put_back_under_pieces(ending, kept)
        else:
            for r, c, _ in head_cells:
                self.scroll.map[r, c] = 0
        if fortress is not None:
            fortress.wipe(self.scroll.map)
        if objects is not None and boss_shots:
            objects.put_back_under(objects.shots, self.scroll.map)
        if objects is not None:
            objects.blasts.erase(self.scroll.map, put_back=blasts_kept)
        if objects is not None:
            self.add_score(objects.world.score)
            objects.world.score = 0

    @staticmethod
    def _pieces(ending: "Ending | None") -> list[tuple[int, int] | None]:
        """0xE780's slots, as (row, column) or None for an empty one, with
        0xE152 at 1, 5 or 6."""
        if ending is None:
            return []
        boss = ending.boss
        if boss not in PIECES_KEPT:
            return []
        if ending.walkers is not None:
            return [None if w is None else (w.row, w.col) for w in ending.walkers.walkers]
        assert ending.heads is not None
        return [None if h is None else (h.y, h.x) for h in ending.heads.heads]

    def _keep_under_pieces(self, ending: "Ending | None") -> list[tuple[int, int, bytes]]:
        """0x6936 (corre_los_de_e780_y_ea00)."""
        if ending is None or ending.boss not in PIECES_KEPT:
            return []
        kept = []
        for n, piece in enumerate(self._pieces(ending)[:PIECES_KEPT[ending.boss]]):
            if piece is not None:
                at = (piece[0] >> 3) * MAP_COLUMNS + (piece[1] >> 3)
                kept.append((n, at, self.scroll.map.keep(at, PIECE_UNDER, PIECE_UNDER)))
        return kept

    def _put_back_under_pieces(self, ending: "Ending | None",
                               kept: list[tuple[int, int, bytes]]) -> None:
        """0x6A37 ("save what the eight cover") and 0x6A2C: the kept cells back, for
        the slots still taken, at where each piece is now."""
        pieces = self._pieces(ending)
        for n, _, cells in kept:
            piece = pieces[n] if n < len(pieces) else None
            if piece is not None:
                at = (piece[0] >> 3) * MAP_COLUMNS + (piece[1] >> 3)
                self.scroll.map.put_back(at, PIECE_UNDER, cells)

    #: The map as 0x47FE last sent it to the screen (0x45E5); None until
    #: a game frame of play has.
    shown: bytes | None = None
    #: Whether this game frame got as far as drawing: one cut short (a
    #: jump, the finale) sends no map, builds no sprites, rewrites no stars.
    drawn = False

    def _shown(self, objects: "Objects | None") -> bytes:
        """The map as it goes up: with the shots (0xA27F) and the objects
        drawn with characters -- the enemy shots (0x481C) before the twelve
        (0x4840) -- where 0x6893 said they fall (0x48B6)."""
        terrain = self.scroll.map
        cells = bytearray(terrain.cells)
        for shot in self.shots.all():
            if shot.kind not in (NORMAL, LASER):
                continue
            row, col = shot.cell
            for n in range(shot.length if shot.kind == LASER else 1):
                if terrain.inside(row, col + n):
                    cells[row * MAP_COLUMNS + col + n] = shot.character
        if objects is not None:
            drawings = self.tables.character_drawings if self.tables is not None else ()
            for o in objects.shots + objects.slots:
                if o.type in EMPTY_TYPES or not o[11]:
                    continue
                if o.row >= DRAWN_BELOW or o.col >= DRAWN_LEFT_OF:
                    continue
                at = o.word(UNDER_AT) - MAP_AT
                if o[11] == 1:
                    # 0x48C3: the pattern doubled in eight bits, then again.
                    first = (o[12] * 2 & 0xFF) * 2
                    chars = tuple(drawings[first:first + 4])
                else:
                    first = self.layout.pairs.get(o[11], self.layout.pair_other)
                    chars = (first, first + 1)
                for step, character in zip(UNDER_CELLS, chars):
                    if 0 <= at + step < len(cells):
                        cells[at + step] = character
        return bytes(cells)

    #: Set when the boss's characters must be loaded (0x4A6D); the window
    #: clears it once it has.
    boss_art = False
    #: The core's drawings, handed in by whoever read the cartridge.
    core_art: "CoreArt | None" = None

    def _draw_core(self, core: "Core | None") -> list[tuple[int, int, int]]:
        """0x7E70: the core drawn into the map, where the ship and the shots
        meet it as terrain."""
        if core is None or self.core_art is None:
            return []
        cells = [(r, c, ch) for r, c, ch in core.cells(self.core_art)
                 if self.scroll.map.inside(r, c)]
        for row, col, character in cells:
            self.scroll.map[row, col] = character
        return cells


    def _shots_against_core(self, core: "Core") -> None:
        """0x760E: the nine slots against the core, before the enemies --
        whatever the ship is doing."""
        for pair in self.shots.slots:
            for i, shot in enumerate(pair):
                if shot is None:
                    continue
                cols = (shot.length + 1) * 8 if shot.kind == LASER else 0
                if core.box(shot.row, shot.col, cols) and core.hit(shot.kind, shot.row):
                    pair[i] = None

    def _stage_over(self) -> None:
        """0x6D53 ("end the stage"): with the ship alive, the next stage; with
        it blowing up, nothing -- the life's end takes over."""
        if self.stages is None:
            self.phase = Phase.OVER
            return
        if self.ship.exploding is not None:
            return
        self._next_stage()

    def _collide(self) -> None:
        """0x71E8 ("run the ship"): the shots against the enemies, the ship
        against the map, the enemies and their shots."""
        objects = self.objects
        if objects is not None:
            for s in objects.slots:
                if s.type and s[27] & 2:
                    self._shots_against(s)
        if self.ending is not None and self.ending.crystal is not None:
            self._shots_against_crystal(self.ending.crystal)
        if self.background is not None:
            self._shots_against_background(self.background)
        if self.guns is not None:
            self._shots_against_guns(self.guns)
        if self.ship.exploding is not None:
            # 0x732F, 0x733B, 0x7395, 0x7420, 0x745E: 0xE200 at 0xFF, no ship.
            return
        if self.ship.hits(self.scroll.map):
            self._ship_dies()
            if self.ship.exploding is not None:
                return
        if objects is None:
            return
        if self.shield >= SHIELD_WEAK:
            self._shield_against(objects)
        for s in objects.slots:
            if s.type and s[27] & 1 and self._touches_ship(s, ENEMY_REACH):
                # 0x7389: the first one found, and no more this game frame.
                self._ship_touches(s)
                if self.ship.exploding is not None:
                    return
                break
        for s in objects.shots:
            if s.type and s[27] & 1 and self._touches_ship(s, SHOT_REACH):
                s[0], s[27] = 0, 0
                self._ship_dies()
                return

    def _shots_against_crystal(self, crystal: "Crystal") -> None:
        """0x7208: the crystal's pieces meet the shots as the enemies do."""
        for piece in crystal.pieces:
            if piece is None or piece.blast is not None:
                continue
            for pair in self.shots.slots:
                for i, shot in enumerate(pair):
                    if shot is None:
                        continue
                    if (piece.row - shot.row + HIT_OFFSET) & 0xFF >= HIT_ROWS:
                        continue
                    if shot.kind == LASER:
                        ahead = (piece.col - shot.col) & 0xFF
                        if ahead < 0xF0 and ahead >= shot.length * 8:
                            continue
                    else:
                        if shot.col >= HIT_LAST_COLUMN:
                            continue
                        if (shot.col - piece.col + HIT_OFFSET) & 0xFF >= HIT_COLS:
                            continue
                        pair[i] = None
                    crystal.hit(piece)
                    break
                else:
                    continue
                break

    def _shots_against_heads(self, heads: "Heads | Walkers | Nuclei | Eye | Fortress") -> None:
        """0x760E with a boss made of pieces: stage 3's heads, 4's walkers,
        6's nuclei, 7's eye, 8's claws."""
        for pair in self.shots.slots:
            for i, shot in enumerate(pair):
                if shot is None:
                    continue
                laser = shot.kind == LASER
                head = heads.meets(shot.row, shot.col, (shot.length + 1) * 8 if laser else 0)
                if head is None:
                    continue
                if not laser:
                    pair[i] = None
                heads.hit(head, laser)  # type: ignore[arg-type]

    def _shots_against_guns(self, guns: "Guns | Stage5") -> None:
        """0x7902: stage 3's emplacements, only while awake."""
        for pair in self.shots.slots:
            for i, shot in enumerate(pair):
                if shot is None:
                    continue
                laser = shot.kind == LASER
                gun = guns.meets(shot.row, shot.col, shot.length if laser else 0)
                if gun is None:
                    continue
                if not laser:
                    pair[i] = None
                guns.hit(gun, laser)  # type: ignore[arg-type]

    def _shots_against_background(self, background: Background) -> None:
        """0x7898: the nine slots against the hatches."""
        assert self.objects is not None
        for pair in self.shots.slots:
            for i, shot in enumerate(pair):
                if shot is None:
                    continue
                laser = shot.kind == LASER
                hatch = background.meets(shot.row, shot.col, shot.length if laser else 0)
                if hatch is None:
                    continue
                if not laser:
                    pair[i] = None
                background.hit(hatch, laser)
                if hatch not in background.hatches:
                    self.objects.blast_at(hatch.row, hatch.col)

    def _shield_against(self, objects: Objects) -> None:
        """0x7420 and 0x7395: with the shield, the bigger boxes."""
        row, col = self.ship.row, (self.ship.col + SHIELD_DX) & 0xFF
        for s in objects.slots:
            if not s.type or not s[27] & 2:
                continue
            if ((row - s.row + 0x10) & 0xFF < SHIELD_ROWS
                    and (col - s.col + 0x0C) & 0xFF < SHIELD_COLS):
                self._shield_down()
                if s.type == BIG:
                    self._big_touched(s)
                if not CAPSULE <= s.type < LATE_TYPES:
                    objects.kill(s)
                # 0x7457: the first one found is the only one this game frame.
                break
        for s in objects.shots:
            if not s.type:
                continue
            cols = SHIELD_SHOT_COLS_CHARS if s[11] else SHIELD_SHOT_COLS
            if ((row - s.row + 0x10) & 0xFF < SHIELD_SHOT_ROWS
                    and (col - s.col + 0x0C) & 0xFF < cols):
                if s[11]:
                    self._ship_dies()
                    return
                self._shield_down()
                s[0], s[27] = 0, 0
                return

    def _shield_down(self) -> None:
        """0x740C."""
        self.shield_hits -= 1
        if self.shield_hits <= 0:
            self.shield = 1
        else:
            self.shield = 2 if self.shield_hits < SHIELD_WEAK else 3

    def _shots_against(self, s: Slot) -> None:
        """0x7229: the nine slots, in order, against one enemy."""
        assert self.objects is not None
        slots: list[tuple[list[Shot | None], int]] = []
        for pair in self.shots.slots:
            slots += [(pair, 0), (pair, 1)]
        slots += [(self.shots.missiles, n) for n in range(len(self.shots.missiles))]
        for holder, at in slots:
            shot = holder[at]
            if shot is None:
                continue
            if (s.row - shot.row + HIT_OFFSET) & 0xFF >= HIT_ROWS:
                continue
            if shot.kind == LASER:
                # 0x728B: the laser is not spent, and its length is its box.
                ahead = (s.col - shot.col) & 0xFF
                if ahead < 0xF0 and ahead >= shot.length * 8:
                    continue
            else:
                if shot.col >= HIT_LAST_COLUMN:
                    continue
                if (shot.col - s.col + HIT_OFFSET) & 0xFF >= HIT_COLS:
                    continue
                holder[at] = None
            if s.type in SHOT_PROOF:
                self.sounds.append(6)
            elif s.type == BOX:
                self._open_box(s)
            else:
                self.objects.hit(s)
            return

    def _touches_ship(self, s: Slot, reach: tuple[int, int]) -> bool:
        return (_within(s.row - self.ship.row - TOUCH_DY, TOUCH_ROWS, reach[0])
                and _within(s.col - self.ship.col - TOUCH_DX, TOUCH_COLS, reach[1]))

    def _ship_touches(self, s: Slot) -> None:
        """0x7470: an enemy pays and the ship dies; a capsule lights the next
        meter cell; the blue one blows up everything on screen."""
        assert self.objects is not None
        if s.type < CAPSULE or s.type >= LATE_TYPES:
            if s.type == BIG:
                self._big_touched(s)
            self.objects.kill(s)
            self._ship_dies()
        elif s.type == CAPSULE:
            self.meter = self.meter % METER_CELLS + 1
            self.objects.free(s)
            self.objects.world.score += CAPSULE_POINTS
            self.sounds.append(0x11)
        elif s.type in (PRIZE_SHIP, PRIZE_ONCE, PRIZE_EIGHT):
            # 0x74BC, 0x74CF.
            if self.objects.take(s):
                self._one_more_ship()
        elif s.type == BOX:
            self._open_box(s)
        elif s.type == BOMB:
            self.objects.free(s)
            self.sounds.append(0x12)
            # 0x7596, from the last slot back.
            for other in reversed(self.objects.slots):
                if 1 <= other.type <= 0x0F:
                    self.objects.kill(other)

    def add_score(self, points: int) -> None:
        """0x55B4: points onto the score; past 0xE067, a ship (0x55DE);
        then the record (0x55F8)."""
        if not points:
            return
        self.score += points
        if self.score >= SCORE_WRAP:
            self.score -= SCORE_WRAP
            self.record = SCORE_TOP
            return
        if self.score // 100 >= self.next_ship:
            if self.next_ship + SHIP_EVERY <= SHIP_AT_TOP:
                self.next_ship += SHIP_EVERY
            self._one_more_ship()
        self.record = max(self.record, self.score)

    def _one_more_ship(self) -> None:
        """0x561C."""
        if self.lives >= MAX_LIVES:
            return
        self.lives += 1
        ending = self.ending
        if ending is None or (ending.leaving is None and not ending.finale):
            self.sounds.append(ONE_MORE_SOUND)

    def _open_box(self, s: Slot) -> None:
        """0x74E8: a box opens, and the four cells it was drawn in go from
        the map, with what it had saved of them (0x750B): the terrain under
        a box is gone."""
        assert self.objects is not None
        self.objects.open_box(s)
        at = (s.row >> 3) * MAP_COLUMNS + (s.col >> 3)
        cells = self.scroll.map.cells
        for n in (at, at + 1, at + MAP_COLUMNS, at + MAP_COLUMNS + 1):
            if n < len(cells):
                cells[n] = 0

    def _big_touched(self, s: Slot) -> None:
        """0x7488: a big one of stage 5's breaks where it is touched."""
        flocks = self.ending.flocks if self.ending is not None else None
        if flocks is not None:
            flocks.touched(s)

    # -- the words typed in pause (0x50C9) ------------------------------------------

    def type_key(self, letter: str) -> None:
        """A key newly down while paused; "\r" is RETURN."""
        if self.keyboard is None:
            return
        typed = self.keyboard.key(letter)
        if typed is None:
            return
        if typed == "HYPER":
            if not self.hyper_used:
                self.hyper_used = True
                self._everything()
            return
        if typed in ("BAKA", "AHO"):
            # 0x5127: no ships left, and the playing flag down: state 6,
            # GAME OVER.
            self.lives = 0
            self._life_over()
            return
        if self.stage_word or self.ship.exploding is not None:
            return
        keyboard = self.keyboard
        if keyboard.name(typed, self.terrain.number):
            self.stage_word = 1
            self._everything()
            return
        w = self.shots
        for word in ("MISSILE", "LASER", "SHIELD", "DOUBLE", "DOWN", "OPTION"):
            if not keyboard.matches(typed, word):
                continue
            self.stage_word += 1
            if word == "MISSILE":
                w.missile = WORD_MISSILE
            elif word == "LASER":
                w.normal, w.double, w.laser = 0, 0, WORD_LASER
            elif word == "SHIELD":
                self.shield, self.shield_hits = 3, SHIELD_HITS
            elif word == "DOUBLE":
                w.normal, w.double, w.laser = 1, 1, 0
            elif word == "DOWN":
                self.ship.speed = 0
            else:
                self._both_options()
            return

    def _everything(self) -> None:
        """0xA0D8: the shield, one speed, the laser, the missile, two options."""
        self.shield, self.shield_hits = 3, SHIELD_HITS
        self.ship.speed = 1
        w = self.shots
        w.normal, w.double, w.laser = 0, 0, WORD_LASER
        w.missile = WORD_MISSILE
        self._both_options()

    def _both_options(self) -> None:
        """0xA146: up to two."""
        while len(self.options.options) < 2:
            self.options.add(self.ship.row, self.ship.col)

    def _take_power(self) -> None:
        """0xA068: the button takes the lit cell unless it is taken."""
        cell = self.meter
        if not cell or self.taken()[cell - 1]:
            return
        self.meter = 0
        self.sounds.append(0x14)
        w = self.shots
        if cell == 1:
            self.ship.speed += 1
        elif cell == 2:
            w.missile += 1
            self._harder(1)
        elif cell == 3:
            w.normal, w.double, w.laser = 1, 1, 0
        elif cell == 4:
            w.normal, w.double = 0, 0
            w.laser += 1
        elif cell == 5:
            self.options.add(self.ship.row, self.ship.col)
            self._harder(1)
        else:
            self.shield, self.shield_hits = 3, SHIELD_HITS
            self._harder(2)

    def _ship_dies(self) -> None:
        if self.immortal:
            return
        self.ship.die()
        self.sounds.append(0x47)

    def star_rows(self) -> tuple[int, int]:
        """The top row of the two star characters (the layout's: 0xF6 and 0xF7
        on the cartridge) (0x475B)."""
        first, second = STAR_MASKS[self.frames >> 1 & 3]
        return self.scroll.bit & first, self.scroll.bit & second

    #: What each player keeps of their own (0xE060..0xE08F, and the score).
    PLAYER_STATE = ("lives", "terrain", "round", "stages_played", "difficulty", "score",
                    "next_ship", "targets_taken", "hyper_used", "finales", "resume")

    def _state(self) -> dict[str, object]:
        return {name: copy.copy(getattr(self, name)) for name in self.PLAYER_STATE}

    @property
    def other_lives(self) -> int:
        return int(self.other["lives"]) if self.other is not None else 0  # type: ignore[call-overload]

    def _swap(self) -> None:
        """0x547B ("change player")."""
        assert self.other is not None
        mine = self._state()
        for name, value in self.other.items():
            setattr(self, name, value)
        self.other = mine
        self.turn ^= 1
        # 0xE063, the distance, is in the block: the other's where it was.
        self.scroll.distance = self.resume
        self.new_stage = True

    def _life_over(self) -> None:
        """State 6 (0x546F): no ships left, GAME OVER; the other player
        with ships left takes the turn; then state 4, between lives."""
        self.resume = self.scroll.distance
        self.interrupts = 1
        if self.lives == 0:
            self.phase = Phase.OVER
            self.over = Over()
            self.sounds.append(GAME_OVER_TUNE)
            return
        if self.other_lives:
            self._swap()
        self.between = Between(WAIT_TWO if self.players == 2 else WAIT_ONE)

    #: State 7 while it runs.
    over: Over | None = None

    def ask_continue(self) -> None:
        """F5 held (0x54F3, keyboard row 7): heard only once GAME OVER is
        written."""
        if self.over is not None and self.over.written:
            self.over.go_on = True

    def _over_tick(self) -> None:
        """A tick of state 7: once the tune has stopped, CONTINUE's three
        ships, then the other player's turn if they have ships, or this
        one's if it went on (state 4); or the title."""
        over = self.over
        assert over is not None
        self.interrupts = 1
        if over.curtain < CURTAIN_TICKS:
            over.curtain += 1
            return
        if not over.written:
            over.written = True
            return
        if self.channel_busy:
            return
        self.over = None
        if over.go_on:
            # 0x54AA: the score to nought, three ships.
            self.score = 0
            self.lives = LIVES
        if self.other_lives:
            self._swap()
        elif not over.go_on:
            self.phase = Phase.FINISHED
            return
        self.phase = Phase.PLAYING
        self.between = Between(WAIT_TWO if self.players == 2 else WAIT_ONE)

    @property
    def intro(self) -> bool:
        """0x545C: the turn's label is up."""
        between = self.between
        return between is not None and self.players == 2 and between.loaded

    def _between_tick(self) -> None:
        """A tick of state 4 (0x53B1)."""
        between = self.between
        assert between is not None
        self.interrupts = 1
        if between.curtain < CURTAIN_TICKS:
            between.curtain += 1
            return
        if not between.loaded:
            # 0x53CC: a ship out of the reserve, the band written again.
            between.loaded = True
            self.lives -= 1
            self.interrupts = 2
            return
        between.wait -= 1
        if between.wait:
            return
        # 0x53B8: the label gone, the stage built (0x53BE), and play.
        self.between = None
        self._start_life(self.resume, first=between.opening, take=False)
        self.interrupts = 1 + BUILD_INTERRUPTS[self.terrain.number]

