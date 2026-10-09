"""The original's tables the engine reads, as data it is handed.

The engine's scalar numbers are in `original.py`; its tables -- a record per
object type, the waves of each stage, the aiming tables -- are the
cartridge's and are not in this repo. `game/rom/tables.py` reads them out of
the player's cartridge into this shape, and a test builds one by hand.
"""

from dataclasses import dataclass, field

from game.engine.layout import Layout
from game.engine.stages import Stages


@dataclass(frozen=True)
class GunArt:
    """Stage 3's tables, out of the cartridge: per drawing, its rectangle
    (width, height, column offset, half a cell lower), its characters, and
    its wide strip (row offset, which of the 10-character rows); per kind,
    where it fires from, where it is shot, where it blows up and the
    drawing and drop it has then."""

    rects: tuple[tuple[int, int, int, bool], ...]
    chars: tuple[tuple[int, ...], ...]
    strips: tuple[tuple[int, int], ...]
    strip_rows: tuple[int, ...]
    muzzles: dict[int, tuple[int, int]]
    centres: dict[int, tuple[int, int]]
    blasts: dict[int, tuple[int, int]]
    wrecks: dict[int, tuple[int, int]]


@dataclass(frozen=True)
class FlockArt:
    """Stage 5's two flocks, out of bank 3: the spiral one's drawings
    (0xBB31), its eight places (0xBB35), its ten spirals -- centre row and
    column, game frames of it, which way (0xBB45) -- and the speeds it leaves
    on (0xBB6D); the big one's four doors (0xBBE9) and their speeds
    (0xBC43), its two sets of three drawings (0xBC83), and the speeds its
    three pieces fly apart at (0xBD71)."""

    spiral_drawings: tuple[int, ...]
    places: tuple[tuple[int, int], ...]
    spirals: tuple[tuple[int, int, int, int], ...]
    spiral_speeds: tuple[tuple[int, int], ...]
    doors: tuple[tuple[int, int], ...]
    door_speeds: tuple[tuple[int, int], ...]
    big_drawings: tuple[tuple[int, int, int], ...]
    piece_speeds: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class NucleusArt:
    """Stage 6's boss, out of banks 1, 2 and 10: the script of which nuclei
    come (0x8041), the three cards they and their arms start from (0x8051,
    0x805B, 0x8067), the nuclei's drawings (0xAAA6) and the arms' (0xAAB0) --
    each (width, height, a column offset, characters) -- the arms' ramp of
    drawings (0x81AD), which drawing an arm wants by the angle to the ship
    (0x8270 for the upper, 0x8250 for the lower), how far across an arm hangs
    (0x8377), where it fires from (0x80B0) and where it is hit (0x76EF)."""

    script: tuple[int, ...]
    nucleus: tuple[int, ...]
    upper: tuple[int, ...]
    lower: tuple[int, ...]
    nuclei: tuple[tuple[int, int, int, tuple[int, ...]], ...]
    arms: tuple[tuple[int, int, int, tuple[int, ...]], ...]
    ramp: tuple[int, ...]
    upper_aim: tuple[int, ...]
    lower_aim: tuple[int, ...]
    hang: tuple[int, ...]
    muzzles: tuple[tuple[int, int], ...]
    centres: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class FortressArt:
    """Stage 8's boss, out of bank 2: the two claws' cards (0x8812), the
    rising piece's (0x884D) and its six 4x6 drawings (0x8953), the anchors'
    script -- (distance's low byte, row, drawing) (0x88F8) -- the claws'
    drawings -- (row offset, column offset, height, width, characters)
    (0x8B4C) -- where each drawing fires from and is hit (0x8A93), and the
    drawing each claw turns to by the angle to the ship (0x8B3C, 0x8B2C)."""

    claws: tuple[int, ...]
    rising: tuple[int, ...]
    rising_drawings: tuple[tuple[int, ...], ...]
    script: tuple[tuple[int, int, int], ...]
    drawings: tuple[tuple[int, int, int, int, tuple[int, ...]], ...]
    muzzles: tuple[tuple[int, int], ...]
    upper_aim: tuple[int, ...]
    lower_aim: tuple[int, ...]


@dataclass(frozen=True)
class Stage5Art:
    """Stage 5's own background, out of bank 3: the script -- (distance,
    row, kind byte) (0xB7BF) -- the small pieces' 5x5 drawings (0xB537), the
    big ones' -- (height, width, characters) (0xB749) -- where a small one
    lets a type 0x1C out (0xB368) and where a big one puts its turret
    (0xB3C7), the turret's two 4x4 drawings (0xB729, 0xB739), its fan's
    sixteen speeds (0xB26A); and the bouncers' script -- (distance, packed)
    (0xB8B4) -- their three floors (0xB89E), six speeds (0xB909) and eight
    drawings (0xB93E)."""

    script: tuple[tuple[int, int, int], ...]
    small: tuple[tuple[int, ...], ...]
    big: tuple[tuple[int, int, tuple[int, ...]], ...]
    releases: tuple[tuple[int, int], ...]
    turret_at: tuple[tuple[int, int], ...]
    turret: tuple[tuple[int, ...], tuple[int, ...]]
    fan: tuple[tuple[int, int], ...]
    bouncers: tuple[tuple[int, int], ...]
    floors: tuple[int, ...]
    bouncer_speeds: tuple[int, ...]
    bouncer_drawings: tuple[int, ...]


@dataclass(frozen=True)
class EndingArt:
    """Stages 1-4's ends, out of the cartridge: the eruption's two mouths
    (0x7189) and eight speeds (0x718D); the core's four shots, (row,
    column) from its corner, signed (0x7E03); the heads' four lanes, their
    floors and roofs (0x8458, 0x857B, 0x857F) and their 4x4 drawings, mouth
    shut and open (0x86F1, 0x8701); the walkers' 4x3 drawings (0x8E5F,
    0x8E6B) and route; the crystal's five pieces (0x8EBA), their characters
    and its blast (0x905C)."""

    eruption_from: tuple[tuple[int, int], ...]
    eruption_speeds: tuple[tuple[int, int], ...]
    core_shots: tuple[tuple[int, int], ...]
    head_lanes: tuple[int, ...]
    head_floors: tuple[int, ...]
    head_roofs: tuple[int, ...]
    head_chars: tuple[tuple[int, ...], ...]
    walker_chars: tuple[tuple[int, ...], ...]
    crystal_pieces: tuple[tuple[int, int], ...]
    crystal_blast: tuple[int, ...]
    #: 0x9060..0x9074, read by 0x902E: each piece's characters, the third's
    #: as two rows of two.
    crystal_chars: tuple[tuple[int, ...], ...] = ()
    #: 0x8D7C..0x8DEF: the walkers' route, one leg a step of byte 1 -- (dy,
    #: dx, the coordinate waited for, its value).
    walker_route: tuple[tuple[int, int, str, int], ...] = ()


@dataclass(frozen=True)
class Tables:
    #: 0x6BA3: per type, four bytes -- drawn with characters, pattern,
    #: colour, hits it takes.
    records: tuple[tuple[int, int, int, int], ...]
    #: 0xA3A6: per stage (index 1-8), sixteen bytes, one per 0x20 of
    #: distance: which wave generators run there.
    sections: tuple[tuple[int, ...], ...]
    #: 0xA5AF (+stage): the two types a stage's six-in-a-row waves take,
    #: one per nibble.
    rows_types: tuple[int, ...]
    #: 0xA4A6: the four rows a trail (type 4) comes in on, by turn.
    trail_rows: tuple[int, ...]
    #: 0xA4AA: how many a trail brings, by difficulty.
    trail_counts: tuple[int, ...]
    #: 0xA640: the rows the ones from the left (type 5) come in on, by turn.
    left_rows: tuple[int, ...]
    #: 0xA5C7: which enemy comes out marked, in turn: 0, 1 (red) or 2.
    marks: tuple[int, ...]
    #: 0x6B97: an enemy's first shot delay, by difficulty.
    shot_delays: tuple[int, ...]
    #: 0x6753: an angle (0-0x3F in a quadrant) for each pair of distances'
    #: high nibbles.
    angles: tuple[int, ...]
    #: 0x6853: a quarter of a sine, 64 steps.
    sines: tuple[int, ...]
    #: 0x91D1: four characters per drawing, for objects drawn with them.
    character_drawings: tuple[int, ...]
    #: 0x5E5D: the four (pattern, colour) an enemy blows up through.
    blast: tuple[tuple[int, int], ...]
    #: 0x9262: per stage, the cannons' script -- (distance, data) rows; the
    #: data's five low bits are the row in cells, bits 5-6 the drawing set,
    #: bits 6-7 the mark (0x90D1).
    cannon_script: tuple[tuple[tuple[int, int], ...], ...]
    #: 0x9205: per drawing set (4) and stage (12), the cannon's first drawing.
    cannon_drawings: tuple[int, ...]
    #: 0x91C5: game frames between a cannon's shots, four by difficulty.
    cannon_waits: tuple[int, ...]
    #: 0x99E3: the ship's two sprites by its state (0xE200: 1 plain, 2 weak
    #: shield, 3 shield) -- (pattern, colour, pattern, colour) for the pad at
    #: neither, up, down, then the same three blinking.
    ship_cards: tuple[tuple[tuple[int, int, int, int], ...], ...]
    #: 0x730F: the sound each type makes when it is shot down.
    kill_sounds: tuple[int, ...]
    #: 0x64FA: per stage, the background objects' script, as the cannons'.
    background_script: tuple[tuple[tuple[int, int], ...], ...]
    #: 0x6370: the background objects' 4x4 drawings.
    background_drawings: tuple[tuple[int, ...], ...]
    #: 0xAD16: a stone's three drawings as it grows (pattern, colour).
    stone_drawings: tuple[tuple[int, int], ...]
    #: 0xAC81 (stage 2) and 0xAC8D (stage 8): where the walls of stones come,
    #: bit 15 the side; and the rows their stones fall in (0xAC7B).
    walls: dict[int, tuple[int, ...]]
    wall_rows: tuple[int, ...]
    #: 0xABD3: the sixteen doors the stone rain falls through, (row, column).
    rain_doors: tuple[tuple[int, int], ...]
    #: Stage 3's gun emplacements' drawings and offsets.
    guns: GunArt | None
    #: Animation tables, by the type that runs them.
    animations: dict[int, tuple[int, ...]]
    #: 0x9657: the acceleration towards the ship, by one distance's high
    #: nibble and the other's.
    toward_ship: tuple[int, ...] = ()
    #: Stage 5's flocks.
    flocks: FlockArt | None = None
    #: Stage 6's boss.
    nucleus: NucleusArt | None = None
    #: Stage 7's boss's sixteen spitting speeds (0x87AF), and stage 8's.
    spit_speeds: tuple[int, ...] = ()
    fortress: FortressArt | None = None
    #: 0xB2D2 (bank 12): per bonus stage, its prizes -- (distance, data):
    #: the data's five high bits the row, bit 2 a prize (0x16-0x18) or a box
    #: (0x19), the two low bits which (5D57).
    prize_script: tuple[tuple[tuple[int, int], ...], ...] = ()
    #: 0x7561: what the Nth capsule in a row pays, in BCD hundreds.
    prize_points: tuple[int, ...] = ()
    #: Stage 5's background.
    stage5: Stage5Art | None = None
    #: 0x633A: the background blasts' three 4x4 drawings.
    blast_drawings: tuple[tuple[int, ...], ...] = ()
    #: Stages 1-4's ends.
    ending: EndingArt | None = None
    #: 0xAF3F: stage 7's type 0x0D, a word per appearance: the low byte and
    #: bit 8 the distance, bits 9-10 the mark, the five high bits the row.
    appearances: tuple[int, ...] = ()
    #: 0xB000: how fast a type 0x0D lunges, by difficulty.
    lunge_speeds: tuple[int, ...] = ()
    #: 0x5EE3: the four drawings a type 0x0D blows up through.
    blast_0d: tuple[int, ...] = ()
    #: Which pictures the rules draw with: the cartridge's, unless the
    #: content draws its own.
    layout: Layout = field(default_factory=Layout)
    #: What the stages' rules key off: the cartridge's, unless the content
    #: has stages of its own.
    stages: Stages = field(default_factory=Stages)
