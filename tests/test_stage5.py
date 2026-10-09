"""Stage 5's own background, on tables built here."""

import dataclasses
import random

from game.engine.objects import Objects
from game.engine.stage5 import Stage5
from game.engine.tables import Stage5Art
from game.engine.terrain import Map
from tests.test_objects import _tables

ART = Stage5Art(
    script=((0x90, 0x78, 0x00), (0x90, 0x28, 0x24)),
    small=tuple((n,) * 25 for n in range(24)),
    big=((4, 6, (0x5A,) * 24),) * 8,
    releases=((0x10, 0xF0), (0x10, 0x28), (0x10, 0xF0), (0x10, 0x28)),
    turret_at=((0, 8), (0x18, 8), (0xF8, 0), (8, 0)),
    turret=((0x4E,) * 16, (0x56,) * 16),
    fan=((0, 0x280),) * 16,
    bouncers=(), floors=(0x90, 0x58, 0x20, 0x21), bouncer_speeds=(0x80,) * 6,
    bouncer_drawings=(0xF0,) * 8,
)


def test_a_small_piece_opens_and_throws_at_the_ship_in_range_and_a_wall_raises_a_turret():
    objects = Objects(dataclasses.replace(_tables(), stage5=ART), random.Random(0), 5)
    stage5 = Stage5(objects, ART)
    stage5.spawn(0x90, True)
    small, big = stage5.slots[0], stage5.slots[1]
    assert small[:4] == bytes([1, 0, 0x78, 0xC0]) and big[0] == 5 and big[7] == 2
    for _ in range(4 * 8):
        stage5.step(False, 0x40, 0x20, 0)
    assert small[1] == 1
    stage5.step(False, 0x40, 0x20, 0)
    assert small[1] == 2
    for _ in range(8):
        stage5.step(False, 0x40, 0x20, 0)
    assert any(s.type == 0x1C for s in objects.slots)
    for _ in range(0x30):
        stage5.step(False, 0x40, 0x20, 0)
    assert stage5.turrets[0][0] == 1
    terrain = Map()
    stage5.draw(terrain)
    assert terrain[15, 24] == small[6]
