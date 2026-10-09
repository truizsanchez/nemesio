"""The engine's rules on terrains a test builds.

Whether the engine rides as the original does, frame for frame, is measured
against the cartridge by `tools/compare_play.py`; these are the rules one at a
time, each a case a reader can see.
"""

from dataclasses import dataclass, field

from game.engine.original import (
    AUTOFIRE, DOWN, EXPLOSION, FIRE, LEFT, LIVES, MAP_ROWS, RIGHT, SHIP_START_X, SHIP_START_Y,
    UP,
)
from game.engine.play import (
    BUILD_INTERRUPTS, CURTAIN_TICKS, GAME_OVER_TUNE, WAIT_ONE, Phase, Play,
)
from game.engine.ship import Ship
from game.engine.terrain import Map


@dataclass
class Flat:
    """Sky, except rows given as solid from a distance on."""
    number: int = 1
    start: int = 0x80
    end: int = 0x200
    limit: int = 0x1FF
    checkpoint: int = 0x100
    solid_rows: list[int] = field(default_factory=list)
    from_distance: int = 0

    def column(self, distance: int) -> list[int] | None:
        if not self.solid_rows or distance < self.from_distance:
            return None
        return [0x40 if row in self.solid_rows else 0 for row in range(MAP_ROWS)]

    def star_row(self, distance: int) -> int | None:
        return None


def test_the_ship_moves_two_pixels_a_game_frame_with_no_speed_up():
    ship = Ship(1)
    ship.step(RIGHT | DOWN)
    assert (ship.row, ship.col) == (SHIP_START_Y + 2, SHIP_START_X + 2)


def test_each_speed_up_adds_half_a_pixel():
    ship = Ship(1)
    ship.speed = 2
    ship.step(LEFT)
    assert ship.x == (SHIP_START_X << 8) - 6 * 0x80


def test_opposite_directions_cancel():
    ship = Ship(1)
    ship.step(LEFT | RIGHT | UP | DOWN)
    assert (ship.row, ship.col) == (SHIP_START_Y, SHIP_START_X)


def test_the_ship_stays_in_its_box_and_stage_2_has_a_higher_roof():
    low, high = Ship(1), Ship(2)
    for _ in range(100):
        low.step(UP | LEFT)
        high.step(UP)
    assert (low.row, low.col) == (0x13 - 0x10, 0x08)
    assert high.row == 0x10 - 0x10


def test_the_ship_meets_the_map_at_its_row_plus_eight():
    terrain = Map()
    ship = Ship(1)
    row = (ship.row + 8) // 8
    terrain[row, ship.col // 8 + 1] = 0x40
    assert ship.hits(terrain)
    terrain[row, ship.col // 8 + 1] = 0x80
    assert not ship.hits(terrain), "0x77 and above is scenery"


def test_a_shot_fires_on_the_press_and_again_after_fifteen_frames_held():
    play = Play(Flat())
    play.step(FIRE)
    assert play.sounds == [1]
    fired = []
    for n in range(AUTOFIRE * 2):
        play.step(FIRE)
        fired.append(bool(play.sounds))
    assert fired.index(True) == AUTOFIRE - 1


def test_two_shots_at_most():
    play = Play(Flat())
    for _ in range(3):
        play.step(FIRE)
        play.step(0)
    assert len(play.shots.all()) == 2


def test_a_shot_ends_on_terrain_and_only_sounds_with_the_core_on():
    play = Play(Flat(solid_rows=[(SHIP_START_Y + 8) // 8], from_distance=0x10))
    play.step(FIRE)
    heard = []
    for _ in range(40):
        play.step(0)
        heard += play.sounds
        if not any(play.shots.slots[0]):
            break
    assert not any(play.shots.slots[0]) and 6 not in heard


def test_the_scroll_brings_a_column_in_every_eighth_game_frame():
    play = Play(Flat())
    first = play.scroll.distance
    for _ in range(24):
        play.step(0)
    assert play.scroll.distance - first == 3


def test_hitting_the_terrain_costs_a_life_after_the_explosion():
    play = Play(Flat(solid_rows=list(range(MAP_ROWS)), from_distance=0))
    lives = play.lives
    play.step(0)
    assert play.ship.exploding is not None
    for _ in range(sum(frames for frames, _ in EXPLOSION) + 1):
        play.step(0)
    assert play.between is not None and play.lives == lives
    # State 4: the curtain's 0x20 ticks, the ship out of the reserve, 0x10
    # of wait; then play.
    for _ in range(CURTAIN_TICKS):
        play.step(0)
    assert play.lives == lives
    play.step(0)
    assert play.lives == lives - 1 and play.between is not None
    for _ in range(WAIT_ONE):
        play.step(0)
    assert play.between is None and play.ship.exploding is None
    # Building the stage takes its own interrupts, the stage's.
    assert play.interrupts == 1 + BUILD_INTERRUPTS[1]


def test_the_ship_is_touched_in_a_lopsided_box():
    from game.engine.original import ENEMY_REACH, SHOT_REACH, TOUCH_ROWS
    from game.engine.play import _within
    # 0x0B rows above the ship's point: an enemy touches, a shot does not.
    assert _within(-0x0B, TOUCH_ROWS, ENEMY_REACH[0])
    assert not _within(-0x0B, TOUCH_ROWS, SHOT_REACH[0])
    assert not _within(TOUCH_ROWS, TOUCH_ROWS, ENEMY_REACH[0])


def test_a_stage_change_keeps_the_wave_count_and_the_sprite_turn_a_life_does_not():
    from tests.test_objects import _tables
    play = Play(Flat(), _tables(), stages=lambda n: Flat(number=n))
    assert play.objects is not None and play.waves is not None
    play.objects.wave_number, play.waves.asked, play.sprites_from = 5, 3, 9
    play._next_stage()
    assert play.terrain.number == 2
    assert (play.objects.wave_number, play.waves.asked, play.sprites_from) == (5, 3, 9)
    play._start_life(play.scroll.distance, take=False)
    assert (play.objects.wave_number, play.waves.asked, play.sprites_from) == (0, 0, 0)


def _game_over(play: Play) -> None:
    play.lives = 0
    play._life_over()
    assert play.phase is Phase.OVER and play.sounds == [GAME_OVER_TUNE]
    play.channel_busy = True
    for _ in range(CURTAIN_TICKS + 1):
        play.ask_continue()
        play.step(0)
    assert play.over is not None and play.over.written and not play.over.go_on


def test_game_over_waits_for_its_tune_then_goes_back_to_the_title():
    play = Play(Flat())
    _game_over(play)
    play.step(0)
    assert play.phase is Phase.OVER
    play.channel_busy = False
    play.step(0)
    assert play.phase is Phase.FINISHED


def test_continue_is_heard_once_game_over_is_written_and_acted_on_after_the_tune():
    play = Play(Flat())
    play.score = 1234
    _game_over(play)
    play.ask_continue()
    play.step(0)
    assert play.phase is Phase.OVER
    play.channel_busy = False
    play.step(0)
    assert play.phase is Phase.PLAYING and play.between is not None
    assert play.score == 0 and play.lives == LIVES


def test_after_one_player_s_game_over_the_other_plays_on():
    play = Play(Flat(), players=2)
    _game_over(play)
    play.channel_busy = False
    play.step(0)
    assert play.phase is Phase.PLAYING and play.turn == 1 and play.between is not None


def test_a_game_from_the_title_opens_on_state_4():
    play = Play(Flat(), opening=True)
    assert play.lives == LIVES and play.between is not None and play.between.opening
    steps = 0
    while play.between is not None:
        play.step(0)
        steps += 1
    # The curtain, a ship out of the reserve, the wait, the stage built.
    assert steps == CURTAIN_TICKS + 1 + WAIT_ONE and play.lives == LIVES - 1


def test_a_ship_every_thousand_points_with_its_sound():
    play = Play(Flat())
    lives = play.lives
    play.add_score(999)
    assert play.lives == lives and 0x15 not in play.sounds
    play.add_score(1)
    assert play.lives == lives + 1 and play.sounds == [0x15]
    play.add_score(999)
    assert play.lives == lives + 1
    play.add_score(1)
    assert play.lives == lives + 2


def test_a_score_past_six_nines_wraps_and_the_record_is_nines():
    play = Play(Flat())
    play.add_score(999990)
    assert play.record == 999990
    lives = play.lives
    play.add_score(20)
    # 0x55D1: the score goes on from its six digits, the record is nines,
    # and that time no ship and no record compared.
    assert play.score == 10 and play.record == 999999 and play.lives == lives
    play.add_score(50)
    assert play.score == 60 and play.record == 999999
