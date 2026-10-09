"""A stage's map: a height profile for the ground and the roof, the
features a plan asks for, the cannons and hatches placed on it, and the
stage's json."""

import random
from dataclasses import dataclass

from game.engine.original import MAP_COLUMNS, MAP_ROWS
from tools.free_assets.common import BRICK, BRICK_B

#: What a brick makes when a shot breaks it.
BRICK_SOUND = 0x05


@dataclass
class Plan:
    """A stage: which of the original's it plays like, its distances, and
    what its map has."""

    rules: int
    start: int
    limit: int
    checkpoint: int
    #: Where the scroll stops for the core, after the end's own part.
    boss: int
    #: The ground's top row, lowest and highest; the roof's bottom row where
    #: there is one (-1 none), and the stretches of distance with a roof.
    floor: tuple[int, int]
    roof: tuple[int, int]
    roofs: tuple[tuple[int, int], ...]
    #: Where hatches go on the floor and on the roof (if flat there).
    floor_hatches: tuple[int, ...] = ()
    roof_hatches: tuple[int, ...] = ()
    #: Rules 1: the crystal's distance and the volcanoes on the last screen.
    crystal: int | None = None
    volcanoes: bool = False
    #: Rules 2: walls of bricks a shot breaks (distances), the walls of stones
    #: (distance, from the right side), and the rain's last screen open.
    bricks: tuple[int, ...] = ()
    stone_walls: tuple[tuple[int, bool], ...] = ()
    rain: bool = False
    #: Rules 4: where the rush of rocks from the roof starts; a volcano hangs
    #: from the roof there.
    rush: int | None = None
    #: Rules 3: gun emplacements, (distance, kind): kinds 3, 4 and 6 on the
    #: ground, 5 on the roof; each on ground (or roof) flat for a strip.
    guns: tuple[tuple[int, int], ...] = ()
    #: Rules 7: the brain on the last screen, the eye's upper cell (row,
    #: column on the screen) in it; and type 0x0D's appearances, (distance,
    #: row).
    eye: tuple[int, int] | None = None
    #: Rules 8: where the fortress's walls start: roof and ground thick,
    #: the claws on their faces, a corridor for the gate between.
    fortress: int | None = None
    #: Rules 5: pods (distance, kind 1-4: 1 and 2 on the ground, 3 and 4 on
    #: the roof), which pop up at column 0xC0; bunkers (distance, kind 5 on
    #: the ground or 6 on the roof, a turret's steps), in at the right.
    pods: tuple[tuple[int, int], ...] = ()
    bunkers: tuple[tuple[int, int, int], ...] = ()
    appearances: tuple[tuple[int, int], ...] = ()
    #: One byte per 0x20 of distance: 1 pairs, 2 a trail, 4 walkers from the
    #: left, 8 jumpers from below, 0x10 a flock, 0x20 walkers and jumpers.
    sections: tuple[int, ...] = (0,) * 16
    #: The six-in-a-row waves before distance 0x80: two types, a nibble each.
    rows_types: int = 0x29
    #: What grows on the terrain or hangs in the sky (scenery, see DECOR):
    #: on the ground, under the roof, or both.
    decor: str = "groves"
    decor_floor: bool = True
    decor_roof: bool = False
    #: Peaks of terrain: (distance, from the roof), a volcano's shape.
    peaks: tuple[tuple[int, bool], ...] = ()


#: The kinds of scenery a plan's decor is: on the terrain ("Y" and "y" on
#: the ground, "U" and "u" under the roof), how often and in what runs; or
#: patches in the sky ("h" and "H").
DECOR = {
    # kind: (on the terrain, share of columns on, shortest and longest run)
    "groves": (True, 0.6, 6, 20),
    "shards": (True, 0.3, 2, 5),
    "tendrils": (True, 0.35, 1, 3),
    "lattice": (False, 0, 0, 0),
    "bubbles": (False, 0, 0, 0),
    "lights": (False, 0, 0, 0),
}
#: A peak: its top row on the ground (bottom row under the roof).
PEAK_TOP, PEAK_BOTTOM = 14, 6

#: Where the two volcanoes' craters are on the last screen (columns).
VOLCANOES = (7, 23)
VOLCANO_ROW = 16
#: Stage 4's rush comes out at row 0x20 (a cell's 4) under column 0xD0
#: (26), riding the scroll (game/engine/ending.py).
RUSH_ROW, RUSH_COLUMN = 4, 0xD0 // 8
#: Rules 5: a pod is 5x5 and pops up at column 0xC0 (cell 24); a bunker is
#: 3 tall and 4 wide.
POD, POD_COLUMN, BUNKER = 5, 0xC0 // 8, (3, 4)
#: The fortress's roof and ground (rules 8): the upper claw (row 0x20) on
#: the one, the lower (0x78) on the other, the gate (rows 9-14) between.
FORTRESS_ROOF, FORTRESS_FLOOR = 6, 15
#: The brain's half height and half width, in cells (rules 7).
BRAIN_ROWS, BRAIN_COLS = 7.5, 5.5
#: An emplacement (rules 3): the kind on the roof, how wide its strip is,
#: and how tall it stands.
ROOF_GUN, GUN_STRIP, GUN_HEIGHT = 5, 10, 3
#: A brick wall's thickness in columns.
BRICK_WALL = 3
#: The rain's sixteen doors on the last screen: eight in the roof, eight in
#: the ground, at these columns.
RAIN_COLUMNS = (3, 7, 11, 15, 19, 23, 27, 30)


def profile(rng: random.Random, width: int, plan: Plan) -> tuple[list[int], list[int]]:
    """For each column, the row of the ground's top and of the roof's
    bottom (-1, none): steps of one row, never one column wide."""
    floor, roof = [], []
    h, target, run = 19, 19, 0
    r, rtarget = -1, -1
    for c in range(width):
        d = plan.start + c
        if run <= 0:
            target = rng.randint(*plan.floor)
            run = rng.randint(6, 18)
            under = any(a <= d < b for a, b in plan.roofs)
            rtarget = rng.randint(*plan.roof) if under else -1
        run -= 1
        if c % 2 == 0:
            h += (target > h) - (target < h)
            if rtarget >= 0 and r < 0:
                r = 0
            elif rtarget < 0 and r >= 0:
                r -= 1
            else:
                r += (rtarget > r) - (rtarget < r)
        floor.append(h)
        roof.append(r)
    return floor, roof


#: The rock the crystal's launchers are anchored to, as the original's map has
#: it: from the column after theirs (they come in at the crystal's distance, at
#: the right edge), as map letters, its top at CRYSTAL_ROCK_ROW.
CRYSTAL_ROCK_ROW, CRYSTAL_ROCK_AFTER = 8, 1
CRYSTAL_ROCK = ("/^^^^^\\ ",
                "#######\\",
                "########",
                "########",
                "########",
                "########",
                "#######p",
                "qvvvvvp ")


def make_map(rng: random.Random, plan: Plan) -> tuple[list[str], list[int], list[int]]:
    """The map's rows (in the legend's letters), the ground's top row and
    the roof's bottom row per column."""
    start = plan.start
    width = plan.limit + 1 - start
    floor, roof = profile(rng, width, plan)
    first = plan.limit - 31 - start
    for at, on_roof in plan.peaks:
        top = at - start
        for c in range(top - 9, top + 11):
            if 0 <= c < width:
                away = max(top - c, c - (top + 1), 0)
                if on_roof:
                    roof[c] = max(roof[c], PEAK_BOTTOM - away)
                else:
                    floor[c] = min(floor[c], PEAK_TOP + away)
    # A flat, open stretch for the checkpoint and the end (and the crystal).
    for c in range(width):
        d = start + c
        # Flat where the plan's hatches go: ground two rows over the rock,
        # a roof two rows thick.
        if any(at - 2 <= d < at + 6 for at in plan.floor_hatches):
            floor[c] = 19
        if any(at - 2 <= d < at + 6 for at in plan.roof_hatches):
            roof[c] = 2
        if plan.checkpoint - 4 <= d < plan.checkpoint + 12:
            floor[c] = max(floor[c], 18)
            roof[c] = min(roof[c], 2)
        if c >= first - 8:
            floor[c] = 20 if plan.volcanoes else 19
            roof[c] = -1 if plan.volcanoes else 2
        if plan.crystal is not None and plan.crystal - 8 <= d < plan.crystal + 0x24:
            roof[c] = min(roof[c], 1)
            floor[c] = max(floor[c], 18)
        if any(b - 6 <= d < b + BRICK_WALL + 6 for b in plan.bricks):
            floor[c], roof[c] = 19, 2
        for at, kind in plan.pods:
            under = at - (MAP_COLUMNS - 1 - POD_COLUMN)
            if under - 2 <= d < under + POD + 2:
                if kind <= 2:
                    floor[c] = 19
                else:
                    roof[c] = 2
        for at, kind, _ in plan.bunkers:
            if at - 2 <= d < at + BUNKER[1] + 2:
                if kind == 5:
                    floor[c] = 19
                else:
                    roof[c] = 2
        if plan.fortress is not None and d >= plan.fortress:
            roof[c], floor[c] = FORTRESS_ROOF, FORTRESS_FLOOR
        for at, kind in plan.guns:
            if at - 2 <= d < at + GUN_STRIP + 2:
                if kind == ROOF_GUN:
                    roof[c] = 3
                else:
                    floor[c] = 19
    if plan.volcanoes:
        for crater in VOLCANOES:
            top = first + crater
            for c in range(top - 8, top + 10):
                if 0 <= c < width:
                    away = max(top - c, c - (top + 1), 0)
                    floor[c] = min(floor[c], VOLCANO_ROW + (away + 1) // 2)
    hanging = None
    if plan.rush is not None:
        # The rocks come out at row 0x20 below column 0xD0 when the rush
        # starts: the distance under that column then, its crater a row up.
        hanging = plan.rush - (MAP_COLUMNS - 1 - RUSH_COLUMN) - start
        for c in range(hanging - 12, hanging + 14):
            if 0 <= c < width:
                away = max(hanging - c, c - (hanging + 1), 0)
                roof[c] = max(RUSH_ROW - 1 - (away + 1) // 2, 0)
                floor[c] = max(floor[c], 19)
    grid = [[" "] * width for _ in range(MAP_ROWS)]
    for c in range(width):
        t = floor[c]
        for row in range(t, MAP_ROWS):
            grid[row][c] = "#"
        grid[t][c] = "^"
        before = floor[c - 1] if c else t
        after = floor[c + 1] if c + 1 < width else t
        if after < t:
            grid[t - 1][c] = "/"
        elif before < t:
            grid[t - 1][c] = "\\"
        b = roof[c]
        if b >= 0:
            for row in range(0, b + 1):
                grid[row][c] = "#"
            grid[b][c] = "v"
            rb = roof[c - 1] if c else b
            ra = roof[c + 1] if c + 1 < width else b
            if ra > b:
                grid[b + 1][c] = "q"
            elif rb > b:
                grid[b + 1][c] = "p"
    if plan.volcanoes:
        for crater in VOLCANOES:
            top = first + crater
            grid[VOLCANO_ROW][top], grid[VOLCANO_ROW][top + 1] = "V", "W"
    if hanging is not None:
        grid[RUSH_ROW - 1][hanging], grid[RUSH_ROW - 1][hanging + 1] = "X", "Z"
    if plan.eye is not None:
        # The brain: an ellipse of terrain round the eye, its socket where
        # the eye's two cells go.
        er, ec = plan.eye
        for row in range(MAP_ROWS):
            for col in range(MAP_COLUMNS):
                dy, dx = (row - er - 0.5) / BRAIN_ROWS, (col - ec) / BRAIN_COLS
                if dy * dy + dx * dx <= 1:
                    grid[row][first + col] = "#"
        grid[er][first + ec], grid[er + 1][first + ec] = "E", "E"
    # Walls of bricks, from the roof down to the ground.
    for wall in plan.bricks:
        for k in range(BRICK_WALL):
            c = wall - start + k
            for row in range(roof[c] + 1, floor[c]):
                grid[row][c] = "B" if (row + k) % 2 else "b"
    decorate(grid, floor, roof, rng, plan)
    for c in range(width):
        for row in range(MAP_ROWS):
            if grid[row][c] == " " and rng.random() < 0.012:
                grid[row][c] = rng.choice("*+")
    if plan.crystal is not None:
        left = plan.crystal + CRYSTAL_ROCK_AFTER - start
        for r, line in enumerate(CRYSTAL_ROCK):
            for k, letter in enumerate(line):
                grid[CRYSTAL_ROCK_ROW + r][left + k] = letter
    return ["".join(row) for row in grid], floor, roof


def decorate(grid: list[list[str]], floor: list[int], roof: list[int], rng: random.Random,
             plan: Plan) -> None:
    """The plan's scenery into the map's empty cells: runs of it on flat
    ground and under a flat roof, or patches in the sky."""
    width = len(floor)
    on_terrain, share, shortest, longest = DECOR[plan.decor]
    if on_terrain:
        for lines, letters, at in ((plan.decor_floor, "Yy", lambda c: floor[c] - 1),
                                   (plan.decor_roof, "Uu", lambda c: roof[c] + 1 if roof[c] >= 0 else -1)):
            if not lines:
                continue
            c = 0
            while c < width:
                run = rng.randint(shortest, longest)
                if rng.random() < share:
                    for k in range(c, min(c + run, width)):
                        row = at(k)
                        flat = 0 < k < width - 1 and at(k - 1) == row == at(k + 1)
                        if flat and 0 <= row < MAP_ROWS and grid[row][k] == " ":
                            grid[row][k] = letters[rng.random() < 0.35]
                c += run
        return
    # Patches in the sky, between the terrain, every so often.
    for centre in range(rng.randint(6, 14), width - 4, 22):
        mid = (max(roof[centre], 0) + floor[centre]) // 2
        radius = rng.randint(2, 4)
        for c in range(centre - 2 * radius, centre + 2 * radius + 1):
            if not 0 <= c < width:
                continue
            for row in range(mid - radius, mid + radius + 1):
                inside = abs(c - centre) / 2 + abs(row - mid) <= radius
                if not inside or not 0 <= row < MAP_ROWS or grid[row][c] != " ":
                    continue
                if row <= roof[c] + 1 or row >= floor[c] - 1:
                    continue
                if plan.decor == "lattice":
                    grid[row][c] = "h"
                elif plan.decor == "bubbles":
                    if rng.random() < 0.22:
                        grid[row][c] = "hH"[rng.random() < 0.5]
                elif (c % 3 == 0) and (row % 2 == 0):
                    grid[row][c] = "hH"[(c // 3 + row // 2) % 3 == 0]


def place(floor: list[int], roof: list[int], rng: random.Random, plan: Plan) -> tuple[list, list]:
    """Cannons on flat ground or roof, and hatches where the plan has them
    and it is flat, away from the checkpoint, the crystal, the bricks and
    the end."""
    width = len(floor)
    cannons, hatches = [], []
    taken: set[int] = set()

    def flat(values: list[int], c: int, n: int) -> bool:
        return c + n <= width and len(set(values[c:c + n])) == 1 and values[c] >= 0

    def clear(d: int) -> bool:
        if plan.checkpoint - 8 <= d < plan.checkpoint + 12:
            return False
        if plan.crystal is not None and plan.crystal - 0x10 <= d < plan.crystal + 0x28:
            return False
        if plan.rush is not None and plan.rush - 0x20 <= d < plan.rush + 0x10:
            return False
        if any(at - 0x10 <= d < at + 0x08 for at, _ in plan.pods):
            return False
        if any(at - 4 <= d < at + 8 for at, _, _ in plan.bunkers):
            return False
        return not any(b - 8 <= d < b + BRICK_WALL + 8 for b in plan.bricks)
    for at, kind in plan.guns:
        c = at - plan.start
        row = roof[c] + 1 if kind == ROOF_GUN else floor[c] - GUN_HEIGHT
        hatches.append([at, (kind - 3) << 6 | row])
        taken.update(range(c - 2, c + GUN_STRIP + 2))
    # The plan's hatches first, then cannons where there is room.
    for c in range(0x10, width - 0x40):
        d = plan.start + c
        if not clear(d) or any(t in taken for t in range(c - 3, c + 5)):
            continue
        if d in plan.floor_hatches and flat(floor, c, 4):
            hatches.append([d, floor[c] - 2])
            taken.update(range(c, c + 4))
        elif d in plan.roof_hatches and flat(roof, c, 4) and roof[c] >= 1:
            hatches.append([d, 0x80 | (roof[c] - 1)])
            taken.update(range(c, c + 4))
    for c in range(0x10, width - 0x40):
        d = plan.start + c
        if not clear(d) or any(t in taken for t in range(c - 3, c + 5)):
            continue
        if rng.random() < 0.09 and flat(floor, c, 2) and floor[c] - 2 > 3:
            cannons.append([d, (floor[c] - 2) | (0x40 if rng.random() < 0.25 else 0)])
            taken.update(range(c, c + 2))
        elif rng.random() < 0.09 and flat(roof, c, 2) and roof[c] >= 1:
            cannons.append([d, 0x20 | (roof[c] + 1)])
            taken.update(range(c, c + 2))
    hatches.sort()
    return cannons, hatches


def stage_spec(plan: Plan, legend: dict[str, int], floor: list[int], roof: list[int],
               cannons: list[list[int]], hatches: list[list[int]]) -> dict[str, object]:
    """The stage's json: its rules, distances, legend and own tables."""
    spec: dict[str, object] = {
        "rules": plan.rules, "start": hex(plan.start), "limit": hex(plan.limit),
        "checkpoint": hex(plan.checkpoint), "boss": hex(plan.boss),
        "legend": {k: hex(v) for k, v in legend.items()},
        "star_rows": [(n * 7) % 23 if n % 3 else 0 for n in range(32)],
        "sections": [hex(b) for b in plan.sections], "rows_types": hex(plan.rows_types),
        "cannons": [[hex(d), hex(x)] for d, x in cannons],
        "hatches": [[hex(d), hex(x)] for d, x in hatches],
    }
    if plan.crystal is not None:
        spec["crystal"] = hex(plan.crystal)
    if plan.rush is not None:
        spec["rush"] = hex(plan.rush)
    if plan.eye is not None:
        spec["eye"] = list(plan.eye)
    if plan.bricks:
        # What a shot breaks, and the sound it makes.
        spec["breakable"] = [[hex(BRICK), hex(BRICK_B)], hex(BRICK_SOUND)]
    if plan.stone_walls:
        spec["walls"] = [hex(d | (0x8000 if right else 0)) for d, right in plan.stone_walls]
    if plan.rain:
        # The doors on the last screen: in the roof and in the ground, where
        # a stone fits.
        first = plan.limit - 31 - plan.start
        doors = []
        for col in RAIN_COLUMNS:
            doors.append([(roof[first + col] + 1) * 8, col * 8])
            doors.append([(floor[first + col] - 2) * 8, col * 8])
        spec["rain_doors"] = [[hex(r), hex(c)] for r, c in doors]
    return spec


