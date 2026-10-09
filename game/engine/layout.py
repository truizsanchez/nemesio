"""Which characters and sprite patterns the rules draw with.

The rules name some pictures by number: the stars' characters, the shot's
and the laser's, the ship's sprites, the options', a walker's facing, the
blast an enemy becomes. The cartridge's numbers are `original.py`'s, and they
are this layout's defaults; content that draws its own pictures (the free
assets) hands its own, with its `Tables`.
"""

from dataclasses import dataclass, field

from game.engine.original import (
    BLAST_0D_PATTERN, BLAST_PATTERN, BUG_DRAWINGS, CAPSULE_DRAWING, CAPSULE_DRAWINGS,
    DOUBLE_COLOUR, DOUBLE_PATTERN, ENEMY_SHOT, EXPLOSION, EXPLOSION_PARTS, EYE_DEAD, EYE_OPEN,
    EYE_SHUT, FACING_5, FLOAT_PATTERN, FLOCK_PIECE, LEAVING_0D,
    LASER_CHARACTER, MISSILE_COLOUR, MISSILE_FALLING, MISSILE_ROLLING, OPTION_DRAWINGS, PAIR_OTHER,
    PAIRS, SHIP_DRAWING, SHIP_SPRITES, SHOT_CHARACTER, STARS, WALKER_START,
)

Sprite = tuple[int, int]


@dataclass(frozen=True)
class Layout:
    # -- characters --
    #: The two star characters; the rules rewrite their top row.
    stars: tuple[int, int] = STARS
    #: The first of the shot's four characters and of the laser's (one by
    #: where in its cell the shooter's row falls).
    shot_character: int = SHOT_CHARACTER
    laser_character: int = LASER_CHARACTER
    #: Enemy shots drawn with two characters side by side: the first, by the
    #: slot's byte 11, and for any other.
    pairs: dict[int, int] = field(default_factory=lambda: dict(PAIRS))
    pair_other: int = PAIR_OTHER
    # -- sprites: (pattern, colour) --
    #: The ship's two by the pad: neither (or both), up, down.
    ship: tuple[tuple[Sprite, Sprite], ...] = SHIP_SPRITES
    #: The ship blowing up: its two in each of the four states, and the
    #: options' two slots as parts of it, (column offset, pattern, colour).
    explosion: tuple[tuple[Sprite, Sprite], ...] = tuple(sprites for _, sprites in EXPLOSION)
    explosion_parts: tuple[tuple[tuple[int, int, int], ...], ...] = EXPLOSION_PARTS
    double: Sprite = (DOUBLE_PATTERN, DOUBLE_COLOUR)
    #: Rolling, falling, and the colour it blinks from (with the next).
    missile: tuple[int, int, int] = (MISSILE_ROLLING, MISSILE_FALLING, MISSILE_COLOUR)
    options: tuple[Sprite, ...] = OPTION_DRAWINGS
    enemy_shot: Sprite = ENEMY_SHOT
    #: A walker: the pattern it starts with (on the floor, on the roof), and
    #: facing the ship (on the floor, on the roof): (right, left).
    walker_start: dict[bool, int] = field(default_factory=lambda: dict(WALKER_START))
    walker_facing: dict[bool, tuple[int, int]] = field(default_factory=lambda: dict(FACING_5))
    blast_pattern: int = BLAST_PATTERN
    blast_0d_pattern: int = BLAST_0D_PATTERN
    #: Stage 5's piece of a big one (and, blinking, the one with bit 2 set).
    flock_piece: int = FLOCK_PIECE
    #: Stage 7's type 0x0D, leaving.
    leaving_0d: int = LEAVING_0D
    float_pattern: int = FLOAT_PATTERN
    # -- drawings of four characters --
    bug_drawings: tuple[int, ...] = BUG_DRAWINGS
    ship_drawing: int = SHIP_DRAWING
    capsule_drawing: int = CAPSULE_DRAWING
    #: Stage 7's eye: its two characters open, shut and dead.
    eye_open: tuple[int, int] = EYE_OPEN
    eye_shut: tuple[int, int] = EYE_SHUT
    eye_dead: tuple[int, int] = EYE_DEAD
    #: A marked enemy's capsule and bomb, by type.
    capsule_drawings: dict[int, int] = field(default_factory=lambda: dict(CAPSULE_DRAWINGS))
