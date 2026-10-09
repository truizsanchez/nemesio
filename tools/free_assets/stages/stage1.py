"""Stage 1, as the original's: waves over thin volcanic ground, its peaks
and runs of firs, the crystal, the volcanoes erupting, and the core."""

from tools.free_assets import enemies
from tools.free_assets.bosses import paint_core, paint_crystal
from tools.free_assets.common import WALKERS, Common, paint_walkers
from tools.free_assets.draw import (
    CYAN, RED, DARK_RED, DARK_YELLOW, GREEN, LIGHT_BLUE, LIGHT_GREEN, LIGHT_RED, LIGHT_YELLOW, MAGENTA, Canvas, Sheet,
)
from tools.free_assets.maps import VOLCANO_ROW, VOLCANOES, Plan
from tools.free_assets.tables import own

PLAN = Plan(rules=1, start=0x80, limit=0x19F, checkpoint=0xF0, boss=0x1C0,
            floor=(18, 20), roof=(0, 1), roofs=((0x80, 0x178),),
            floor_hatches=(0xB0, 0x118, 0x178), roof_hatches=(0x138, 0x150),
            crystal=0x165, volcanoes=True,
            sections=(0, 0, 0, 1, 2, 4, 8, 3, 0x20, 2, 4, 9, 0, 0, 0, 0), rows_types=0x29,
            decor="groves", peaks=((0x98, False), (0xD0, False), (0x130, False), (0x150, False)))
TERRAIN = (DARK_RED, RED, LIGHT_RED)
DECOR = (DARK_YELLOW, GREEN, LIGHT_GREEN)


def paint(sheet: Sheet, common: Common) -> tuple[dict[str, int], dict[str, object]]:
    def crater(c: Canvas, left: bool) -> None:
        # The rim glowing with the lava, the inner wall below it, the rock around.
        c.fill(DARK_RED)
        if left:
            c.facets([([(3, 0), (8, 0), (8, 4)], LIGHT_YELLOW), ([(8, 4), (8, 8), (5, 8)], DARK_YELLOW)])
        else:
            c.facets([([(0, 0), (5, 0), (0, 4)], LIGHT_YELLOW), ([(0, 4), (3, 8), (0, 8)], DARK_YELLOW)])
    craters = sheet.solid(2)
    sheet.chars.draw(craters[0], "crater, left", lambda c: crater(c, True))
    sheet.chars.draw(craters[1], "crater, right", lambda c: crater(c, False))
    crystal = paint_crystal(sheet)
    blast = [int(c, 16) for c in crystal["crystal_blast"][:2]]  # type: ignore[index]
    core = paint_core(sheet, (blast[0], blast[1]))
    paint_walkers(sheet.sprites)
    spinner, dart, jumper, drone = (enemies.spinner(sheet), enemies.dart(sheet),
                                    enemies.jumper(sheet), enemies.drone(sheet))
    rock = enemies.rock(sheet)
    records = {3: [0, spinner[0], LIGHT_YELLOW, 1], 4: [0, dart[0], LIGHT_GREEN, 1],
               5: [0, WALKERS[True]["right"][0], DARK_YELLOW, 1], 6: [0, jumper[0], LIGHT_BLUE, 1],
               9: [0, drone[0], CYAN, 1], 0x0A: [0, drone[0], MAGENTA, 1], 0x0F: [0, rock, 0, 1]}
    animations = {3: enemies.back_and_forth(spinner, 8), 6: list(jumper),
                  9: enemies.back_and_forth(drone, 6), 0x0A: enemies.back_and_forth(drone, 6)}
    ending = {
        "eruption_from": [[VOLCANO_ROW * 8 - 1, VOLCANOES[1] * 8 + 4],
                          [VOLCANO_ROW * 8 - 1, VOLCANOES[0] * 8 + 4]],
        "eruption_speeds": [[hex(v), hex(x)] for v, x in (
            (0x0A80, 0x0100), (0x0B40, 0x0200), (0x0C00, 0x0300), (0x0A00, 0x0180),
            (0x0B00, 0x0280), (0x0BC0, 0x0380), (0x0A40, 0x0220), (0x0B80, 0x0140))],
        "core_shots": [[4, 0x10], [0x14, -8], [0x2C, -8], [0x3C, 0x10]],
        # A stack against the rock (maps.py's CRYSTAL_ROCK), the double in the middle.
        "crystal_pieces": [[0x48, 0xF0], [0x50, 0xF0], [0x58, 0xF0], [0x68, 0xF0], [0x70, 0xF0]],
        **crystal,
    }
    return {"V": craters[0], "W": craters[1]}, own(sheet, records, animations, core=core, ending=ending)
