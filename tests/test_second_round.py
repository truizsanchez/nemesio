"""What changes from the second round: stage 3's other boss (0x83A5), the
core's bursts, the stones that fire, and the waits between shots."""

import dataclasses
import random

from game.engine.ending import (
    CORE_BURST, FAST_LIFE, FAST_STAY, OTHER_BOSS_AT, Core, Ending, Heads, LoneHead,
)
from game.engine.objects import Objects
from tests.test_objects import _tables


def _ending(round_: int) -> Ending:
    objects = Objects(_tables(), random.Random(0), 3)
    objects.world.round = round_
    return Ending(objects, 3)


def test_the_other_boss_comes_at_0x60_only_from_the_second_round():
    first = _ending(0)
    first.update(False, 0, OTHER_BOSS_AT)
    assert first.heads is None
    second = _ending(1)
    second.update(False, 0, OTHER_BOSS_AT - 1)
    assert second.heads is None
    second.update(False, 0, OTHER_BOSS_AT)
    assert isinstance(second.heads, LoneHead) and second.boss == 6


def test_the_lone_head_comes_a_game_frame_late_in_lane_0_with_its_own_life():
    boss = LoneHead(Objects(_tables(), random.Random(0), 3))
    boss.update(0x60, 0x20, 0)
    assert boss.heads == [None] * 8
    boss.update(0x60, 0x20, 0)
    head = boss.heads[0]
    assert head is not None and head.fast
    lane = boss.objects.tables.ending.head_lanes[0]  # type: ignore[union-attr]
    assert (head.y, head.x, head.life, head.stay) == (lane, 0xF7, FAST_LIFE, FAST_STAY)


def test_the_fast_head_chases_four_at_a_time_and_stops_at_row_0x90():
    boss = LoneHead(Objects(_tables(), random.Random(0), 3))
    boss.update(0xB0, 0xE0, 0)
    for _ in range(0x20):
        boss.update(0xB0, 0xE0, 0)
    head = boss.heads[0]
    assert head is not None and head.step == 1
    rows = []
    for _ in range(0x40):
        boss.update(0xB0, 0xE0, 0)
        rows.append(head.y)
    steps = {b - a for a, b in zip(rows, rows[1:])}
    assert steps <= {0, 4} and max(rows) == 0x90


def test_once_the_head_is_gone_the_other_boss_is_done_and_the_heads_can_come():
    ending = _ending(1)
    ending.update(False, 0, OTHER_BOSS_AT)
    boss = ending.heads
    assert isinstance(boss, LoneHead)
    boss.update(0x60, 0x20, 0)
    boss.update(0x60, 0x20, 0)
    boss.heads[0] = None
    boss.update(0x60, 0x20, 0)
    assert boss.done
    ending.update(False, 0, OTHER_BOSS_AT + 1)
    assert ending.heads is None
    ending.update(True, 0, OTHER_BOSS_AT + 1)
    assert isinstance(ending.heads, Heads) and ending.boss == 1


def _staying_core(round_: int) -> Core:
    objects = Objects(_tables(), random.Random(0), 1)
    objects.world.round = round_
    core = Core(objects)
    core.step, core.alive, core.clock, core.starting = 2, True, 0x200, False
    return core


def test_from_the_second_round_the_core_answers_a_press_of_fire_with_six_shots():
    for round_, fired in ((0, 0), (1, CORE_BURST)):
        core = _staying_core(round_)
        world = core.objects.world
        world.fire_pressed = True
        core.update(0x60, 1, 0)
        world.fire_pressed = False
        shots = 0
        for frame in range(10):
            core.objects.shot_this_frame = False
            core.update(0x60, frame, 0)
            shots = sum(1 for s in core.objects.shots[4:] if s[0])
        assert shots == fired


def test_a_grown_stone_fires_from_the_third_round_or_the_second_with_shield_and_laser():
    for round_, shield, laser, fires in ((0, True, 1, False), (1, False, 1, False),
                                         (1, True, 1, True), (2, False, 0, True)):
        objects = Objects(_tables(), random.Random(0), 2)
        world = objects.world
        world.round, world.shield_on, world.laser = round_, shield, laser
        world.fire_pressed, world.frames = True, 8
        world.ship_row, world.ship_col = 0xA0, 0x10
        stone = objects.make(8, 0x40, 0x80)
        assert stone is not None
        stone[1] = 1
        objects._move_stone(stone)
        assert any(s[0] for s in objects.shots) == fires


def test_on_the_second_stage_played_the_wait_between_shots_counts_difficulty_2():
    objects = Objects(_tables(), random.Random(0), 2)
    waits = tuple(range(0x10, 0x50))
    objects.tables = dataclasses.replace(objects.tables, cannon_waits=waits)
    s = objects.make(9, 0x40, 0x80)
    assert s is not None
    objects.world.difficulty = 5
    objects.world.rounds = 1
    s[24] = 0
    assert objects._cannon_wait(s) == waits[2 * 4]
    objects.world.rounds = 2
    s[24] = 0
    assert objects._cannon_wait(s) == waits[5 * 4]
