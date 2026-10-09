"""Stage 6's nuclei on tables this file builds."""

import dataclasses
import random

from game.engine.nuclei import ARM, NUCLEUS, Nuclei
from game.engine.objects import Objects
from game.engine.tables import NucleusArt
from tests.test_objects import _tables

DRAWING = (2, 2, 0, (1, 2, 3, 4))
ART = NucleusArt(
    script=(3,) * 16,
    nucleus=(3, 0, 0, 0x40, 0, 0xF0, 0, 0, 0x0A, 0x7F),
    upper=(4, 0, 0, 0, 0, 0, 0x21, 0x18, 6, 0x10, 6, 6),
    lower=(4, 0, 0, 0, 0, 0, 0x16, 0x14, 6, 0x10, 0x20, 0x20),
    nuclei=(DRAWING,) * 5, arms=(DRAWING,) * 40, ramp=tuple(range(40)),
    upper_aim=(0x10,) * 32, lower_aim=(0x10,) * 32, hang=(0,) * 40,
    muzzles=((0, 0),) * 40, centres=((0, 0),) * 40,
)


def _nuclei() -> Nuclei:
    objects = Objects(dataclasses.replace(_tables(), nucleus=ART), random.Random(0), 6)
    return Nuclei(objects, ART)


def _started(nuclei: Nuclei) -> None:
    for _ in range(2 + 0x40):
        nuclei.update(0xA0, 0)


def test_a_nucleus_comes_with_its_arms_when_the_screen_is_clear():
    nuclei = _nuclei()
    _started(nuclei)
    assert [p[0] for p in nuclei.pieces] == [NUCLEUS, ARM, ARM, 0, 0, 0]
    assert (nuclei.pieces[0][3], nuclei.pieces[0][5]) == (0x40, 0xF0)


def test_a_nucleus_drifts_left_and_its_arms_hang_above_and_below():
    nuclei = _nuclei()
    _started(nuclei)
    for _ in range(0x0A):
        nuclei.update(0xA0, 0)
    assert nuclei.pieces[0][5] == 0xE8
    nuclei.cells()
    nucleus, upper, lower = nuclei.pieces[:3]
    assert upper[3] == nucleus[3] - 2 * 8
    assert lower[3] == nucleus[3] + 2 * 8


def test_a_burst_nucleus_takes_its_arms_with_it():
    nuclei = _nuclei()
    _started(nuclei)
    while nuclei.pieces[0][0]:
        nuclei.hit(0, laser=False)
    assert [p[0] for p in nuclei.pieces[:3]] == [0, 0, 0]
    assert nuclei.objects.world.score == 50 + 10 + 10


def test_the_boss_is_done_past_the_script_once_the_nuclei_are_gone():
    nuclei = _nuclei()
    _started(nuclei)
    for p in nuclei.pieces:
        p[0] = 0
    nuclei.update(0x1A0, 0)
    nuclei.update(0x1A0, 0)
    assert nuclei.done
