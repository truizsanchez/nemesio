"""The hidden target and the bonus stages' prizes, on tables built here."""

import dataclasses
import random

from game.engine.objects import BOX, FLOATING, PRIZE_EIGHT, Objects
from game.engine.target import COUNTED_LIMIT, FAST, STOPPED, Target
from game.engine.terrain import Map
from game.engine.waves import Prizes
from tests.test_objects import _tables


def test_the_target_comes_rides_the_scroll_and_stops_the_screen_when_flown_through():
    target = Target()
    sounds: list[int] = []
    assert target.update(2, 0x190, True, 0x4A, 0x50, [0, 0], sounds) is None
    assert (target.row, target.col) == (0x88, 0xE8)
    limit = None
    for _ in range(20):
        limit = target.update(2, 0x191, True, 0x80, 0x50, [0, 0], sounds) or limit
    assert limit == 0x1CF and target.mode == STOPPED and sounds == [0xCD]
    for _ in range(0x40):
        target.update(2, 0x191, False, 0x80, 0x50, [0, 0], sounds)
    assert target.mode == FAST


def test_stages_1_and_4_count_three_different_targets():
    counted = [0, 0]
    for stage, distance, row, kind_limit in ((1, 0xFC, 0x88, None), (4, 0xC0, 0x10, None),
                                              (4, 0x104, 0x10, COUNTED_LIMIT)):
        target = Target()
        target.update(stage, distance, True, 0, 0, counted, [])
        result = target.update(stage, distance, False, row, 0xF0, counted, [])
        assert result == kind_limit
    assert counted[1] == 0


def test_a_box_opens_into_its_mark_and_a_capsule_is_taken_again_and_again():
    tables = dataclasses.replace(_tables(), prize_points=(0, 1, 2, 5, 0x10, 0x20, 0x50, 0x100))
    objects = Objects(tables, random.Random(0), 9)
    prizes = Prizes(objects, ((0x50, 0x40 | 1), (0x50, 0x48 | 4 | 2)))
    prizes.step(0x50, True)
    box, capsule = objects.slots[0], objects.slots[1]
    assert box.type == BOX and capsule.type == PRIZE_EIGHT and capsule[23] == 8
    objects.open_box(box)
    assert box.type == 0x17
    objects.take(capsule)
    assert capsule.type == FLOATING and objects.chain == 1
    for _ in range(0x0A):
        objects.step(Map())
    assert capsule.type == PRIZE_EIGHT and capsule[23] == 7

