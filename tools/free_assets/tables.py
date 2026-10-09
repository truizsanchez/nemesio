"""The tables: what the stages share (`tables.json`), and a stage's own,
whole, as its json's "tables" put them in place of the shared ones."""

from typing import Any

from tools.free_assets.common import (
    BLAST, BUG, CAPSULE_D, FLIER, FLOOR_CANNON, ENEMY_SHOT, ROOF_CANNON, SHIELDS, SHIP, SHIP_D,
    BLINK, Common, hatch_drawings, walker_animation,
)
from tools.free_assets.draw import (
    CYAN, DARK_RED, LIGHT_BLUE, LIGHT_RED, LIGHT_YELLOW, WHITE, Sheet,
)

TYPES = 32
#: How many steps each animation the movers read has.
ANIMATIONS = {2: 4, 3: 8, 5: 8, 6: 4, 9: 6, 0x0A: 6, 0x0B: 4, 0x0C: 6, 0x0D: 6}
#: Every type unless a stage says otherwise: an invisible sprite.
NOTHING = [0, ENEMY_SHOT, 0, 1]


def base_records() -> dict[int, list[int]]:
    """The types every stage draws the same: with characters (the cannon,
    the flier, the bug, the prizes) and the shots."""
    return {1: [1, FLOOR_CANNON, 0, 1], 2: [1, FLIER[0], 0, 1], 7: [1, BUG[0], 0, 1],
            0x0C: [1, FLIER[0], 0, 1], 0x0E: [0, ENEMY_SHOT, LIGHT_RED, 1],
            0x10: [0, ENEMY_SHOT, LIGHT_RED, 1], 0x11: [1, SHIP_D, 0, 4],
            0x16: [1, SHIP_D, 0, 1], 0x17: [1, CAPSULE_D, 0, 1], 0x18: [1, CAPSULE_D, 0, 1],
            0x19: [1, CAPSULE_D, 0, 1], 0x1A: [1, CAPSULE_D, 0, 1], 0x1C: [0, ENEMY_SHOT, LIGHT_RED, 1]}


def base_animations() -> dict[int, list[int]]:
    """Every animation the movers read, long enough: the fliers' drawings
    for the types drawn with characters, the walkers', and nothing."""
    out = {kind: [ENEMY_SHOT] * steps for kind, steps in ANIMATIONS.items()}
    out[2] = list(FLIER)
    out[0x0C] = list(FLIER) + [FLIER[2], FLIER[1]]
    out[5] = walker_animation()
    return out


def shared(common: Common) -> dict[str, object]:
    """tables.json."""
    h = hex
    waits = []
    for d in range(16):
        base = max(0x64 - 6 * d, 0x18)
        waits += [base, base, base + 8, base * 2 - 8]
    records = base_records()
    return {
        "records": [records.get(t, NOTHING) for t in range(TYPES)],
        "animations": {str(k): v for k, v in base_animations().items()},
        "trail_rows": [0x30, 0x60, 0x40, 0x50],
        "trail_counts": [3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 8, 8],
        "left_rows": [0x90, 0x10, 0x90, 0x90, 0x10, 0x90, 0x10, 0x10],
        "marks": [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 2],
        "shot_delays": [120, 110, 100, 90, 80, 70, 60, 54, 48, 42, 36, 32, 28, 24, 20, 16],
        "blast": [[h(p), c] for p, c in zip(BLAST, (WHITE, LIGHT_YELLOW, LIGHT_RED, DARK_RED))],
        "cannon_drawings": [h(FLOOR_CANNON), h(FLOOR_CANNON), h(ROOF_CANNON), h(ROOF_CANNON)],
        "cannon_waits": waits,
        # Per shield state (1 none, 2 weak, 3 on), six cards of two sprites
        # (pattern, colour): level, up, down, then the same blinking.
        "ship_cards": [
            [[b, WHITE, t, LIGHT_RED] for b, t in zip(SHIP[0::2], SHIP[1::2])]
            + [[b, WHITE, BLINK, DARK_RED] for b in SHIP[0::2]],
            [[b, WHITE, sh, DARK_RED] for b, sh in zip(SHIP[0::2], SHIELDS[3:])]
            + [[b, WHITE, sh, LIGHT_RED] for b, sh in zip(SHIP[0::2], SHIELDS[3:])],
            [[b, WHITE, sh, CYAN] for b, sh in zip(SHIP[0::2], SHIELDS[:3])]
            + [[b, WHITE, sh, LIGHT_BLUE] for b, sh in zip(SHIP[0::2], SHIELDS[:3])],
        ],
        # By type: the cannons (and the crystal) 0x0A, the rocks 0x09.
        "kill_sounds": [h(s) for s in (
            [0x0E, 0x0A, 0x08, 0x08, 0x08, 0x09, 0x09, 0x08] + [0x08] * 7 + [0x09]
            + [0x0D] * 12 + [0x0E] + [0x0D] * 3)],
        "background_drawings": [[h(c) for c in d] for d in hatch_drawings()],
        "blast_drawings": [[h(c) for c in d] for d in common.blasts],
        "prize_points": [0, 1, 2, 4, 8, 0x16, 0x32, 0x64],
        # The rows a wall of stones comes down, from the last one up.
        "wall_rows": [h(r) for r in (0x20, 0x38, 0x50, 0x68, 0x80, 0x98)],
        "layout": common.layout,
        "ending": {"core_shots": [[4, 0x10], [0x14, -8], [0x2C, -8], [0x3C, 0x10]]},
    }


def own(sheet: Sheet, records: dict[int, list[int]], animations: dict[int, list[int]],
        **more: Any) -> dict[str, object]:
    """A stage's "tables": its records and animations over the shared ones,
    its drawings (the shared ones and its own), and whatever else it has."""
    all_records = {**base_records(), **records}
    all_animations = {**base_animations(), **animations}
    out: dict[str, object] = {
        "records": [all_records.get(t, NOTHING) for t in range(TYPES)],
        "animations": {str(k): v for k, v in all_animations.items()},
        "character_drawings": {hex(k): [hex(c) for c in v] for k, v in sorted(sheet.drawings.items())},
    }
    out.update(more)
    return out
