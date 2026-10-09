"""The engine's tables out of the free assets' `tables.json` and each stage's
`stageN.json`.

`tables.json` names the fields of `game.engine.tables.Tables` the stages
share (and the core's drawings under "core", the pictures' numbers under
"layout"); a number may be written as an integer or as a string ("0x8C").
What is only mathematics -- the sines, the angle between two distances, the
pull towards the ship -- is worked out here unless the file gives it.

What is a stage's own is in its `stageN.json`, and goes into the tables
under the number of the original's stage it plays like ("rules"):

    "sections"     16 bytes, one per 0x20 of distance: the waves (waves.py)
    "rows_types"   the six-in-a-row waves' two types, a nibble each
    "cannons"      [distance, data] rows: the data's five low bits the row,
                   0x20 on the roof, 0x40 marked
    "hatches"      [distance, data] rows: the data's five low bits the row,
                   0x80 on the roof
    "crystal"      where its end's crystal comes (rules 1 and 4)
    "boss"         where the scroll stops for the core
    "rush"         where the rush of rocks from the roof starts (rules 4)
    "eye"          the eye's upper cell, [row, column], in the last screen (rules 7)
    "walls"        distances of the walls of stones (rules 2), 0x8000 the side
    "breakable"    [characters, sound]: what a shot breaks (rules 2)
    "ship_walls", "shot_walls", "object_walls"   scenery that still stops them

A stage's rules are the original's stage's, and no two stages can share
them: the tables are the rules' own.
"""

import json
import math
import os
from typing import Any

from game.free.numbers import num, nums, pairs
from game.free.stage import files

from game.engine.ending import CoreArt
from game.engine.layout import Layout
from game.engine.stages import Characters, Stages
from game.engine.tables import (
    EndingArt, FlockArt, FortressArt, GunArt, NucleusArt, Stage5Art, Tables,
)

#: Stages 1-8, and with the four bonus stages 1-12 (index 0 is no stage).
STAGES, ALL_STAGES = 8, 12
_ANGLE_SIDE = 16
_QUARTER = 64


def sines() -> tuple[int, ...]:
    """A quarter of a sine in 64 steps, 0 to 255."""
    return tuple(min(round(256 * math.sin(n * math.pi / 2 / _QUARTER)), 255)
                 for n in range(_QUARTER))


def angles() -> tuple[int, ...]:
    """For a row distance's high nibble and a column distance's, the angle
    inside a quadrant, 0 (along the columns) to 0x3F (along the rows)."""
    return tuple(min(round(math.atan2(dy + 0.5, dx + 0.5) * 2 * _QUARTER / math.pi), _QUARTER - 1)
                 for dy in range(_ANGLE_SIDE) for dx in range(_ANGLE_SIDE))


def toward_ship(strength: float = 190.0, top: int = 0xC0) -> tuple[int, ...]:
    """A pull that falls with the square of the distance, along one axis,
    for each pair of distances' high nibbles."""
    out = []
    for a in range(_ANGLE_SIDE):
        for b in range(_ANGLE_SIDE):
            d = math.hypot(a, b)
            out.append(top if d == 0 else min(int(strength * a / d ** 3), top))
    return tuple(out)


def _per_stage(spec: dict[str, Any], count: int, make: Any, empty: Any) -> tuple[Any, ...]:
    return tuple(make(spec[str(n)]) if str(n) in spec else empty for n in range(count + 1))


def _script(rows: Any) -> tuple[tuple[int, int], ...]:
    return pairs(rows)


def _ending(spec: dict[str, Any]) -> EndingArt:
    return EndingArt(
        eruption_from=pairs(spec.get("eruption_from", [[0, 0], [0, 0]])),
        eruption_speeds=pairs(spec.get("eruption_speeds", [[0, 0]] * 8)),
        core_shots=pairs(spec.get("core_shots", [[0, 0]] * 4)),
        head_lanes=nums(spec.get("head_lanes", [0] * 4)),
        head_floors=nums(spec.get("head_floors", [0] * 4)),
        head_roofs=nums(spec.get("head_roofs", [0] * 4)),
        head_chars=tuple(nums(d) for d in spec.get("head_chars", [[0] * 16] * 2)),
        walker_chars=tuple(nums(d) for d in spec.get("walker_chars", [[0] * 12] * 2)),
        crystal_pieces=pairs(spec.get("crystal_pieces", [])),
        crystal_blast=nums(spec.get("crystal_blast", [0])),
        crystal_chars=tuple(nums(d) for d in spec.get("crystal_chars", [])),
        walker_route=tuple((num(a), num(b), str(c), num(d))
                           for a, b, c, d in spec.get("walker_route", [])),
    )


def _sprite(value: Any) -> tuple[int, int]:
    pattern, colour = value
    return num(pattern), num(colour)


def layout(spec: dict[str, Any]) -> Layout:
    """Which pictures the rules draw with: the file's "layout", each key
    left out the cartridge's (game/engine/layout.py)."""
    given: dict[str, Any] = {}
    readers: dict[str, Any] = {
        "stars": lambda v: (num(v[0]), num(v[1])),
        "shot_character": num, "laser_character": num, "pair_other": num,
        "pairs": lambda v: {num(k): num(c) for k, c in v.items()},
        "ship": lambda v: tuple((_sprite(a), _sprite(b)) for a, b in v),
        "explosion": lambda v: tuple((_sprite(a), _sprite(b)) for a, b in v),
        "explosion_parts": lambda v: tuple(tuple((num(dx), num(p), num(c)) for dx, p, c in state)
                                           for state in v),
        "double": _sprite, "enemy_shot": _sprite,
        "missile": lambda v: (num(v[0]), num(v[1]), num(v[2])),
        "options": lambda v: tuple(_sprite(d) for d in v),
        "walker_start": lambda v: {True: num(v["floor"]), False: num(v["roof"])},
        "walker_facing": lambda v: {True: (num(v["floor"][0]), num(v["floor"][1])),
                                    False: (num(v["roof"][0]), num(v["roof"][1]))},
        "blast_pattern": num, "blast_0d_pattern": num, "float_pattern": num, "leaving_0d": num,
        "eye_open": lambda v: (num(v[0]), num(v[1])), "eye_shut": lambda v: (num(v[0]), num(v[1])),
        "eye_dead": lambda v: (num(v[0]), num(v[1])), "flock_piece": num,
        "bug_drawings": nums, "ship_drawing": num, "capsule_drawing": num,
        "capsule_drawings": lambda v: {num(k): num(d) for k, d in v.items()},
    }
    for key, value in spec.items():
        if key not in readers:
            raise ValueError("tables.json's layout has no %r" % key)
        given[key] = readers[key](value)
    return Layout(**given)


def stage_specs(folder: str) -> dict[int, dict[str, Any]]:
    """Each stage's json by the rules it plays by, in the stages' order."""
    out: dict[int, dict[str, Any]] = {}
    for number in files(folder):
        with open(os.path.join(folder, "stage%d.json" % number)) as handle:
            spec = json.load(handle)
        rules = num(spec.get("rules", number))
        if rules in out:
            raise ValueError("stage%d.json plays by stage %d's rules, and so does an earlier "
                             "one: each stage has its own" % (number, rules))
        if out and rules < max(out):
            raise ValueError("stage%d.json plays by stage %d's rules, before the stage ahead "
                             "of it (%d): the stages go on in the original's order"
                             % (number, rules, max(out)))
        out[rules] = spec
    return out


def stages(specs: dict[int, dict[str, Any]]) -> Stages:
    """What the stages' rules key off, the cartridge's where a stage says
    nothing; no hidden targets (there are no bonus stages)."""
    default = Stages()

    def chars(key: str) -> dict[int, Characters]:
        return {rules: frozenset(nums(spec[key])) for rules, spec in specs.items() if key in spec}
    breakable: dict[int, tuple[Characters, int]] = {
        rules: (frozenset(nums(spec["breakable"][0])), num(spec["breakable"][1]))
        for rules, spec in specs.items() if "breakable" in spec}
    return Stages(
        crystal={**default.crystal, **{r: num(s["crystal"]) for r, s in specs.items() if "crystal" in s}},
        boss={**default.boss, **{r: num(s["boss"]) for r, s in specs.items() if "boss" in s}},
        rush={**default.rush, **{r: num(s["rush"]) for r, s in specs.items() if "rush" in s}},
        eye={**default.eye, **{r: (num(s["eye"][0]), num(s["eye"][1]))
                               for r, s in specs.items() if "eye" in s}},
        # A stage's own characters are not the cartridge's: what it does not
        # name is not a wall and does not break.
        ship_walls=chars("ship_walls"), shot_walls=chars("shot_walls"),
        object_walls=chars("object_walls"), breakable=breakable,
        breakable_late=(frozenset(), 0), targets=False)


def read(folder: str) -> tuple[Tables, CoreArt | None]:
    """The first stage's tables and core (every stage's: `read_stages`)."""
    stages_ = read_stages(folder)
    return stages_[min(stages_)]


def read_stages(folder: str) -> dict[int, tuple[Tables, CoreArt | None]]:
    """Each stage's tables and core, by the rules it plays by: `tables.json`
    with what the stage's "tables" put in its place. The layout is the
    stages' shared one: a stage cannot have its own."""
    with open(os.path.join(folder, "tables.json")) as handle:
        base = json.load(handle)
    specs = stage_specs(folder)
    out = {}
    for rules, stage in specs.items():
        own = stage.get("tables", {})
        if "layout" in own:
            raise ValueError("a stage's tables cannot have a layout of their own: the ship, "
                             "the shots and the options go on from one stage to the next")
        out[rules] = _read({**base, **own}, specs)
    return out


def _read(spec: dict[str, Any], specs: dict[int, dict[str, Any]]) -> tuple[Tables, CoreArt | None]:

    def per_stage(key: str, count: int, make: Any, empty: Any) -> tuple[Any, ...]:
        return _per_stage({str(r): s[key] for r, s in specs.items() if key in s}, count, make, empty)
    drawings = [num(d) for d in spec["cannon_drawings"]]
    tables = Tables(
        records=tuple(tuple(nums(r)) for r in spec["records"]),  # type: ignore[misc]
        sections=per_stage("sections", STAGES, nums, (0,) * 16),
        rows_types=per_stage("rows_types", STAGES, num, 0),
        trail_rows=nums(spec["trail_rows"]),
        trail_counts=nums(spec["trail_counts"]),
        left_rows=nums(spec["left_rows"]),
        marks=nums(spec["marks"]),
        shot_delays=nums(spec["shot_delays"]),
        angles=nums(spec["angles"]) if "angles" in spec else angles(),
        sines=nums(spec["sines"]) if "sines" in spec else sines(),
        character_drawings=_character_drawings(spec["character_drawings"]),
        blast=pairs(spec["blast"]),
        cannon_script=per_stage("cannons", ALL_STAGES, _script, ()),
        # Per drawing set, the same first drawing on every stage.
        cannon_drawings=tuple(drawings[s] for s in range(4) for _ in range(ALL_STAGES)),
        cannon_waits=nums(spec["cannon_waits"]),
        ship_cards=((),) + tuple(tuple(tuple(nums(c)) for c in state)  # type: ignore[misc]
                                 for state in spec["ship_cards"]),
        kill_sounds=nums(spec["kill_sounds"]),
        background_script=per_stage("hatches", ALL_STAGES, _script, ()),
        background_drawings=tuple(nums(d) for d in spec["background_drawings"]),
        stone_drawings=pairs(spec.get("stone_drawings", [[0, 0]] * 3)),
        walls={r: nums(s["walls"]) for r, s in specs.items() if "walls" in s},
        wall_rows=nums(spec.get("wall_rows", [0] * 6)),
        # The rain's doors are the last screen's of the stage that has one.
        rain_doors=pairs(next((s["rain_doors"] for s in specs.values() if "rain_doors" in s),
                              spec.get("rain_doors", [[0, 0]]))),
        guns=_guns(spec["guns"]) if "guns" in spec else None,
        nucleus=_nucleus(spec["nucleus"]) if "nucleus" in spec else None,
        fortress=_fortress(spec["fortress"]) if "fortress" in spec else None,
        flocks=_flocks(spec["flocks"]) if "flocks" in spec else None,
        stage5=_stage5(spec["stage5"]) if "stage5" in spec else None,
        animations={num(k): nums(v) for k, v in spec["animations"].items()},
        toward_ship=nums(spec["toward_ship"]) if "toward_ship" in spec else toward_ship(),
        prize_script=(),
        prize_points=nums(spec["prize_points"]),
        blast_drawings=tuple(nums(d) for d in spec["blast_drawings"]),
        ending=_ending(spec["ending"]),
        blast_0d=nums(spec.get("blast_0d", [0] * 4)),
        lunge_speeds=nums(spec.get("lunge_speeds", [0] * 16)),
        spit_speeds=nums(spec.get("spit_speeds", [])),
        appearances=nums(spec.get("appearances", [])),
        layout=layout(spec.get("layout", {})),
        stages=stages(specs),
    )
    # A stage whose end has no core (5-8) has no drawings of it.
    core = spec.get("core")
    if core is None:
        return tables, None
    return tables, CoreArt(nums(core["body"]), nums(core["eyes"]), nums(core["mouths"]))


def _guns(spec: dict[str, Any]) -> GunArt:
    """Stage 3's emplacements: per drawing its rectangle [width, height,
    column offset, half a cell lower], its characters and its strip [row
    offset, which of the 10-character rows]; the strips' rows; and per kind
    (3-6) where it fires from, where it is shot, where it blows up, and the
    drop and drawing of its wreck."""
    def by_kind(key: str) -> dict[int, tuple[int, int]]:
        return {num(k): (num(v[0]), num(v[1])) for k, v in spec[key].items()}
    return GunArt(
        rects=tuple((num(w), num(h), num(dx), bool(lower)) for w, h, dx, lower in spec["rects"]),
        chars=tuple(nums(c) for c in spec["chars"]),
        strips=pairs(spec["strips"]),
        strip_rows=nums(spec["strip_rows"]),
        muzzles=by_kind("muzzles"), centres=by_kind("centres"),
        blasts=by_kind("blasts"), wrecks=by_kind("wrecks"))


def _nucleus(spec: dict[str, Any]) -> NucleusArt:
    """Stage 6's nuclei: the script of which arms each comes with (bit 0 the
    upper, bit 1 the lower), the three slots they start as, the nuclei's
    drawings (by how hurt, and blinking) and the arms' -- each [width,
    height, the column the arms hang from, characters] -- the arms' ramp of
    drawings, the one each wants by the angle to the ship (angle / 8), and
    per arm drawing how far across it hangs, where it fires from and where
    it is hit."""
    def drawings(key: str) -> tuple[tuple[int, int, int, tuple[int, ...]], ...]:
        return tuple((num(w), num(h), num(x), nums(c)) for w, h, x, c in spec[key])
    return NucleusArt(
        script=nums(spec["script"]), nucleus=nums(spec["nucleus"]),
        upper=nums(spec["upper"]), lower=nums(spec["lower"]),
        nuclei=drawings("nuclei"), arms=drawings("arms"), ramp=nums(spec["ramp"]),
        upper_aim=nums(spec["upper_aim"]), lower_aim=nums(spec["lower_aim"]),
        hang=nums(spec["hang"]), muzzles=pairs(spec["muzzles"]), centres=pairs(spec["centres"]))


def _fortress(spec: dict[str, Any]) -> FortressArt:
    """Stage 8's fortress: the two claws' slots as they start (sixteen bytes
    each), the gate's (five), the gate's six 4x6 drawings, the anchors'
    script [the distance's low byte, row, drawing], the claws' drawings
    [row offset, column offset, height, width, characters], where each fires
    from, and the drawing each claw wants by its turn to the ship."""
    return FortressArt(
        claws=nums(spec["claws"]), rising=nums(spec["rising"]),
        rising_drawings=tuple(nums(d) for d in spec["rising_drawings"]),
        script=tuple((num(a), num(r), num(d)) for a, r, d in spec["script"]),
        drawings=tuple((num(dy), num(dx), num(h), num(w), nums(c))
                       for dy, dx, h, w, c in spec["drawings"]),
        muzzles=pairs(spec["muzzles"]), upper_aim=nums(spec["upper_aim"]),
        lower_aim=nums(spec["lower_aim"]))


def _flocks(spec: dict[str, Any]) -> FlockArt:
    """Stage 5's two flocks: the long one's four drawings, its eight places
    (row, column), ten spirals [centre row, centre column, game frames, which
    way], the ten speeds it leaves at; the big ones' four doors and their
    speeds, their two sets of three drawings, the three speeds its pieces
    fly apart at. Speeds are (row, column), 8.8."""
    return FlockArt(
        spiral_drawings=nums(spec["spiral_drawings"]), places=pairs(spec["places"]),
        spirals=tuple((num(a), num(b), num(c), num(d)) for a, b, c, d in spec["spirals"]),
        spiral_speeds=pairs(spec["spiral_speeds"]), doors=pairs(spec["doors"]),
        door_speeds=pairs(spec["door_speeds"]),
        big_drawings=tuple((num(a), num(b), num(c)) for a, b, c in spec["big_drawings"]),
        piece_speeds=pairs(spec["piece_speeds"]))


def _stage5(spec: dict[str, Any]) -> Stage5Art:
    """Stage 5's own background: its script [distance, row, kind byte] (the
    low nibble plus one the kind: 1-4 small, 5-8 big; the high nibble a
    turret's steps), the small ones' 5x5 drawings (six a kind), the big
    ones' [height, width, characters] (then broken), where a small one lets
    its shots out and a big one puts its turret, the turret's two 4x4
    drawings (in, out), its fan's sixteen speeds; and the bouncers' script
    [distance, packed], their three floors, six speeds and eight drawings."""
    return Stage5Art(
        script=tuple((num(d), num(r), num(k)) for d, r, k in spec["script"]),
        small=tuple(nums(c) for c in spec["small"]),
        big=tuple((num(h), num(w), nums(c)) for h, w, c in spec["big"]),
        releases=pairs(spec["releases"]), turret_at=pairs(spec["turret_at"]),
        turret=(nums(spec["turret"][0]), nums(spec["turret"][1])),
        fan=pairs(spec["fan"]), bouncers=pairs(spec["bouncers"]), floors=nums(spec["floors"]),
        bouncer_speeds=nums(spec["bouncer_speeds"]),
        bouncer_drawings=nums(spec["bouncer_drawings"]))


def _character_drawings(spec: dict[str, Any]) -> tuple[int, ...]:
    """Drawings of four characters (top left, top right, bottom left,
    bottom right), by number; 128 of them."""
    out = [0] * (128 * 4)
    for key, chars in spec.items():
        at = num(key) * 4
        out[at:at + 4] = nums(chars)
    return tuple(out)
