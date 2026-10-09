"""What the rules of a stage key off, as data: the distances its end happens
at, and which characters are its walls and its breakable blocks.

The rules themselves are the stage number's -- stage 2's end is a rain of
stones, stage 1's an eruption -- and stay in the engine. What they are keyed
off is here: the cartridge's (`original.py`) by default; content with stages
of its own hands its own, with its `Tables`.
"""

from collections.abc import Collection
from dataclasses import dataclass, field

from game.engine.original import (
    BOSS_LIMIT, BREAKABLE, BREAKABLE_LATE, CRYSTAL_AT, EYE_AT, OBJECT_WALLS, RUSH_AT, SHIP_WALLS,
    SHOT_WALLS,
)

Characters = Collection[int]


@dataclass(frozen=True)
class Stages:
    #: By stage: where its end's crystal comes (stages 1 and 4).
    crystal: dict[int, int] = field(default_factory=lambda: dict(CRYSTAL_AT))
    #: By stage: where the scroll stops for the core (stage 5: for its flock).
    boss: dict[int, int] = field(default_factory=lambda: dict(BOSS_LIMIT))
    #: By stage: where its end's rush of rocks from the roof starts (stage 4).
    rush: dict[int, int] = field(default_factory=lambda: dict(RUSH_AT))
    #: By stage: the eye's upper cell (row, column) in the map (stage 7).
    eye: dict[int, tuple[int, int]] = field(default_factory=lambda: dict(EYE_AT))
    #: By stage: characters from SCENERY up that still stop the ship, a
    #: shot, an object (and an enemy shot).
    ship_walls: dict[int, Characters] = field(default_factory=lambda: dict(SHIP_WALLS))
    shot_walls: dict[int, Characters] = field(default_factory=lambda: dict(SHOT_WALLS))
    object_walls: dict[int, Characters] = field(default_factory=lambda: dict(OBJECT_WALLS))
    #: By stage: the characters a shot breaks instead of ending on, and the
    #: sound they make; and from stage 9 on, the bonus stages'.
    breakable: dict[int, tuple[Characters, int]] = field(default_factory=lambda: dict(BREAKABLE))
    breakable_late: tuple[Characters, int] = BREAKABLE_LATE
    #: The hidden targets and the bonus stages they open (target.py): the
    #: cartridge has them; content without bonus stages does not.
    targets: bool = True
