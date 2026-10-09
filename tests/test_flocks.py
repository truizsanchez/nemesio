"""Stage 5's flocks on tables this file builds."""

import dataclasses
import random

from game.engine.flocks import BIG, PIECE, SPIRAL, Flocks, _sra3
from game.engine.objects import Objects
from game.engine.tables import FlockArt
from game.engine.terrain import Map
from tests.test_objects import _tables

ART = FlockArt(
    spiral_drawings=(0xA0, 0xA4, 0xA8, 0xAC),
    places=((0x60, 0x80),) * 8,
    spirals=((0x50, 0x70, 0x10, 1),) * 10,
    spiral_speeds=((0, 0xFC00),) * 10,
    doors=((0x48, 0x12), (0x18, 0xDE), (0x48, 0xDE), (0x70, 0xDE)),
    door_speeds=((0, 0x40), (0, 0xFF40), (0, 0xFFC0), (0, 0xFF80)),
    big_drawings=((0xD0, 0xD4, 0xD8), (0xDC, 0xE0, 0xE4)),
    piece_speeds=((0xFF80, 0), (0x80, 0xFF80), (0x80, 0x80)),
)


def _flocks() -> tuple[Objects, Flocks]:
    tables = dataclasses.replace(_tables(), toward_ship=(0,) * 256, flocks=ART)
    objects = Objects(tables, random.Random(0), 5)
    return objects, Flocks(objects, ART)


def test_an_eighth_is_signed():
    assert _sra3(0x10) == 2
    assert _sra3(-2) == -1
    assert _sra3(0xF0) == -2


def test_the_long_flock_lets_one_out_each_cadence_until_its_clock_runs_out():
    objects, flocks = _flocks()
    objects.world.ship_row = 0x40
    flocks.start_long(0)
    assert flocks.long_clock == 0x14 * 0x1E
    for _ in range(0x1F):
        flocks.release()
    assert [s.type for s in objects.slots].count(SPIRAL) == 1
    while not flocks.done:
        flocks.release()


def test_a_spiral_one_appears_harmless_then_turns():
    objects, flocks = _flocks()
    s = objects.make(SPIRAL, 0x60, 0x80)
    assert s is not None and s[27] == 0
    for _ in range(0x32):
        objects.step(Map())
    assert s[1] == 1 and s[27] == 3
    objects.step(Map())
    assert (s.row, s.col) != (0x60, 0x80)


def test_a_big_one_takes_three_slots_and_breaks_into_three():
    objects, flocks = _flocks()
    objects.world.ship_row = 0x40
    flocks.door = 1
    s = objects.make(BIG, 0x18, 0xDE)
    assert s is not None
    assert [o.type for o in objects.slots[:3]] == [BIG] * 3
    assert objects.alive == 3
    assert (objects.slots[1].row, objects.slots[1].col) == (0x28, 0xD6)
    assert (objects.slots[2].row, objects.slots[2].col) == (0x28, 0xE6)
    for _ in range(0x5A):
        objects.step(Map())
    assert [o.type for o in objects.slots[:3]] == [PIECE] * 3
