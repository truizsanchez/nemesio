"""Stages 7 and 8's bosses and the screen going dark, on tables built here."""

import dataclasses
import random

from game.engine.eye import Eye
from game.engine.fade import Fade, apply
from game.engine.fortress import Fortress
from game.engine.objects import ANCHOR, SPIT, Objects
from game.engine.tables import FortressArt
from game.engine.terrain import Map
from tests.test_objects import _tables


def test_the_fade_eats_the_colours_then_the_patterns_then_the_map():
    fade = Fade()
    vram = bytearray([0xFF]) * 0x4000
    fade.update(False, False, sounds := [])
    assert sounds == [0x3E] and fade.interrupts == 14
    apply(vram, fade.writes)
    assert vram[0x0000] == 0xF0 and vram[0x2000] == 0xFF
    steps = 0
    costs = []
    while fade.step == 1:
        fade.update(True, False, [])
        apply(vram, fade.writes)
        costs.append(fade.interrupts)
        steps += 1
    assert steps == 8 * 4
    # By the row each pass starts at, in interrupts, measured.
    assert costs[:4] == [5, 6, 6, 5]
    assert Fade(13).colour_pass == 13
    assert vram[0x2000] == 0 and vram[0x2800] == 0
    # The band's letters, at the start of the bottom third, are spared.
    assert vram[0x3000] == 0xFF
    fade.update(True, False, [])
    assert fade.clear_map
    fade.update(True, False, [])
    assert not fade.done
    fade.update(False, False, [])
    assert fade.done


def _objects() -> Objects:
    return Objects(_tables(), random.Random(0), 7)


def test_the_eye_spits_every_other_frame_and_shuts_when_shot_out():
    objects = _objects()
    eye = Eye(objects, (0x100,) * 16)
    terrain = Map()
    eye.update(terrain, 0, False)
    eye.update(terrain, 0, False)
    assert terrain[10, 27] == 0x3E
    eye.update(terrain, 2, False)
    eye.update(terrain, 3, False)
    assert [s.type for s in objects.slots].count(SPIT) == 1
    while eye.piece:
        eye.hit(0, laser=False)
    eye.update(terrain, 4, False)
    assert terrain[10, 27] == 0x5F and objects.world.score == 100


ART = FortressArt(
    claws=(7, 0, 0, 0x78, 0, 0xF8, 0, 0x10, 0x10, 0x20, 0, 0, 0, 0, 0, 0,
           7, 1, 0, 0x20, 0, 0xF8, 0, 0x10, 0x18, 0x20, 7, 7, 0),
    rising=(1, 0x38, 0xF8, 0x20, 0), rising_drawings=((0x5A,) * 24,) * 6,
    script=((0x8A, 0x10, 0x33),), drawings=((0, 0, 1, 1, (0x44,)),) * 14,
    muzzles=((0, 0),) * 14, upper_aim=(8,) * 16, lower_aim=(1,) * 16,
)


def test_the_fortress_claws_ride_the_scroll_and_anchors_come_on_the_script():
    objects = Objects(dataclasses.replace(_tables(), fortress=ART), random.Random(0), 8)
    fortress = Fortress(objects, ART)
    # The boss's first game frame only counts it in (0x7C4F).
    fortress.update(0x16E, False, False, False)
    assert [c[0] for c in fortress.claws] == [0, 0]
    fortress.update(0x16E, False, False, False)
    assert [c[0] for c in fortress.claws] == [7, 7]
    fortress.update(0x16F, True, False, False)
    assert fortress.claws[0][5] == 0xF0
    fortress.step, fortress.clock = 4, 0x1E0
    fortress.update(0x18A, True, False, False)
    assert [s.type for s in objects.slots].count(ANCHOR) == 1


def test_the_ship_leaves_faster_and_faster_once_the_fortress_is_done():
    from game.engine.ending import LEAVING_MORE, LEAVING_SPEED, Ending
    objects = Objects(dataclasses.replace(_tables(), fortress=ART), random.Random(0), 8)
    ending = Ending(objects, 8)
    ending.update(False, 0, 0x16E)
    assert ending.fortress is not None
    ending.fortress.done = True
    ending.update(False, 0, 0x16E, alive=True)
    assert ending.leaving == LEAVING_SPEED and ending.music_frozen
    ending.leave()
    assert ending.leaving == LEAVING_SPEED + LEAVING_MORE
    ending.finale_done = True
    ending.update(False, 0, 0x16E)
    assert ending.next_stage


def test_the_front_goes_round_logo_title_picture_demo():
    from game.front import TITLE_FRAMES, Front, Screen
    front = Front()
    assert front.screen is Screen.LOGO
    front.attract_over()
    assert front.screen is Screen.TITLE
    for _ in range(TITLE_FRAMES):
        front.update(False, False, False)
    assert front.screen is Screen.PICTURE
    front.attract_over()
    assert front.screen is Screen.DEMO
    front.update(True, False, False)
    assert front.screen is Screen.TITLE


def test_the_game_s_ending_leaves_the_ship_and_its_options_at_the_start():
    from game.engine.options import Options
    from game.engine.ship import Ship
    ship, options = Ship(8), Options()
    ship.x = 0xF4_80
    options.add(0x30, 0x90)
    ship.place(0x4A, 0x50)
    options.place(0x4A, 0x50)
    assert (ship.row, ship.col, ship.x & 0xFF) == (0x4A, 0x50, 0x80)
    assert set(options.options[0].queue) == {(0x4A, 0x50)}


class _Directions:
    """A cartridge with the shrapnel's first direction, (0, 0x200)."""

    def word(self, bank: int, at: int) -> int:
        from game.finale import DIRECTIONS
        return 0x200 if at == DIRECTIONS + 2 else 0


class _R(random.Random):
    """R's bit 0 as given; every other read of R, 0."""

    def __init__(self, value: int) -> None:
        super().__init__(0)
        self.value = value

    def randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:  # type: ignore[override]
        return self.value if start == 2 else 0


def test_the_shrapnel_s_kind_is_r_s_bit_0_and_the_other_kind_goes_half_as_fast():
    from game.finale import Finale
    from game.vdp import Vram
    for bit, kind, speed in ((0, 1, 0x200), (1, 2, 0x100)):
        finale = Finale(_Directions(), _R(bit), 0, Vram())  # type: ignore[arg-type]
        finale.pieces_left, finale.piece_clock = 1, 1
        finale._release()
        piece = finale.pieces[0]
        assert piece is not None and piece[0] == kind and piece[5] == speed
