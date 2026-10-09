"""Write the free assets: every stage's pictures, map and json, the shared
tables, the texts, the sounds, the title."""

import argparse
import json
import os
import random

from game.free import graphics
from game.free.png import read, write
from game.vdp import Vram
from tools.free_assets import extras
from tools.free_assets.common import Common
from tools.free_assets.draw import Sheet
from tools.free_assets.maps import make_map, place, stage_spec
from tools.free_assets.music import music
from tools.free_assets.stages import STAGES
from tools.free_assets.tables import shared


def build(out: str, seed: int) -> int:
    rng = random.Random(seed)
    os.makedirs(out, exist_ok=True)
    files: dict[str, object] = {}
    notes = ["Which character and which sprite pattern is what, stage by stage.",
             "Written by tools/make_free_assets.py.", ""]
    first: Common | None = None
    columns = []
    for number, stage in enumerate(STAGES, start=1):
        sheet = Sheet()
        common = Common(sheet, stage.TERRAIN, stage.PLAN.decor, stage.DECOR)
        first = first or common
        painted = stage.paint(sheet, common)
        letters, tables = painted[0], painted[1]
        extra = painted[2] if len(painted) > 2 else {}
        legend = {**common.legend, **common.scenery, **letters}
        rows, floor, roof = make_map(rng, stage.PLAN)
        used = {letter for row in rows for letter in row} - {" "}
        legend = {k: v for k, v in legend.items() if k in used}
        cannons, hatches = place(floor, roof, rng, stage.PLAN)
        if hasattr(stage, "after_map"):
            # What the stage places on its map, by the map's rows.
            tables.update(stage.after_map(floor, roof))
        spec = stage_spec(stage.PLAN, legend, floor, roof, cannons, hatches)
        spec.update(extra)
        spec["tables"] = tables
        files["stage%d.json" % number] = spec
        with open(os.path.join(out, "stage%d.txt" % number), "w") as handle:
            handle.write("\n".join(rows) + "\n")
        write(os.path.join(out, "stage%d.chars.png" % number), sheet.chars.picture)
        write(os.path.join(out, "stage%d.sprites.png" % number), sheet.sprites.picture)
        notes += ["== stage%d (plays by stage %d's rules)" % (number, stage.PLAN.rules), "",
                  "characters:"]
        notes += ["  0x%02X  %s" % (c, n) for c, n in sorted(sheet.chars.names.items())]
        notes += ["", "sprite patterns (16x16, four numbers each):"]
        notes += ["  0x%02X  %s" % (p, n) for p, n in sorted(sheet.sprites.names.items())]
        notes.append("")
        columns.append(len(rows[0]))
    assert first is not None
    for name in ("chars.png", "sprites.png", "stage1.txt.bak"):
        # The shared pictures of an earlier layout: each stage has its own now.
        path = os.path.join(out, name)
        if os.path.isfile(path):
            os.remove(path)
    write(os.path.join(out, "title.png"), extras.title(rng))
    files.update({"tables.json": shared(first), "text.json": extras.text(first.font, first.meter),
                  "sounds.json": {**extras.sounds(), **music()}})
    for name, data in files.items():
        with open(os.path.join(out, name), "w") as handle:
            json.dump(data, handle, indent=1)
            handle.write("\n")
    with open(os.path.join(out, "chars.txt"), "w") as handle:
        handle.write("\n".join(notes) + "\n")
    problems = []
    for number in range(1, len(STAGES) + 1):
        problems += graphics.load_chars(read(os.path.join(out, "stage%d.chars.png" % number)), Vram())
    for problem in problems:
        print(problem)
    print("free assets written to %s (%d stages, of %s columns)"
          % (out, len(STAGES), ", ".join(map(str, columns))))
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Make the free assets.")
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument("--out", default=os.path.join(here, "assets", "free"))
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    return build(args.out, args.seed)
