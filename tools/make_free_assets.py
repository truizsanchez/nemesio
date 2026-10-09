"""Make the free assets: faceted shapes, the stages, the texts, the sounds.

    python tools/make_free_assets.py [--out assets/free] [--seed 1]

Nothing is read from a cartridge: every picture is drawn out of polygons,
"low poly": facets shaded flat from a light above on the left (characters
keep two colours a row, which draw.py enforces; one-colour sprites show their
facets as cuts), the maps come from height profiles, and the tables
are the generator's own numbers. Run once; after that the files are edited
by hand. Running it again writes them all over (`--out` somewhere else to
compare). The code is in `tools/free_assets/`: drawing (draw.py), what every
stage has (common.py), what more than one has (bosses.py, enemies.py), a
module a stage (stages/), the maps, the tables, the texts, sounds and title.

Each stage has its own pictures (stageN.chars.png, stageN.sprites.png); what
every stage has is at the same numbers in all of them, and a stage lays its
own out after it:

    characters (the same in all three thirds unless said)
    0x00          empty
    0x01-0x0F     third 2: the band's digits (1-10), ship, H I P
    0x10-0x2F     third 2: the power meter's letters, plain and chosen
    0x10-0x3A     thirds 0-1: the letters over the view (0-9, - , ship, A-Z)
    0x43-0x57     solid, every stage: terrain, hatches, bricks, crystal shots
    0x58-0x76     solid, the stage's own (its boss, its crystal...)
    0x77-         scenery, every stage: stars, shot, laser, enemy shots,
                  fliers, bugs, cannons, capsules, blasts; the stage's decor
                  (its plan's: firs, crystals, tendrils, a lattice...); then
                  the stage's own
    sprite patterns 0x00-0xA8 every stage's (the ship, the options, the
    blasts, the walkers), 0xAC- the stage's own; drawings of four characters
    0-23 every stage's, 24- the stage's own.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.free_assets.build import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
