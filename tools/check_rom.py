"""What this game reads out of the cartridge, against the cartridge running.

    python tools/check_rom.py --rom <nemesis.rom>

Boots the original in openMSX (tools/harness), starts a game and lets the demo
play, and compares:

- **the characters and sprite patterns** of stage 1, as `game/rom/graphics.py`
  loads them, with VRAM once play has started;
- **the map**, as `game/rom/stage.py` builds it, with the 22x32 buffer the
  cartridge keeps at 0xED00, sampled every 50 frames of the demo.

Not everything is expected to match, and what is not is named rather than
hidden: characters the stage never loads keep what the title screen left
there; the star characters blink; and objects the cartridge draws *into* the
map (the shots, the hatches) overwrite cells. A map cell is counted against
the reader only where the original holds a terrain character from the stage's
own script range and ours differs: a character the stage's script never
produces anywhere is an object's (the volcanoes, the hatches, the shots), and
so is a cell that is empty in the original where ours has terrain -- an
object erased it. The report prints the counts either way.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.rom import graphics  # noqa: E402
from game.rom.cartridge import Cartridge  # noqa: E402
from game.rom.stage import ROWS, Stage  # noqa: E402
from game.vdp import COLOURS, PATTERNS, SPRITE_PATTERNS, THIRD, Vram  # noqa: E402
from tools.harness.omsx import OpenMSX  # noqa: E402

#: Characters left over from the screens before a stage, which no stage-1 map
#: cell names, and the blinking stars.
NOT_THE_STAGES = set(range(0x40, 0x5B)) | set(range(0xAA, 0xCC)) | {0xF6, 0xF7, 0xF8}
MAP = 0xED00
STAR_CHARACTERS = (0xF6, 0xF7)


def start_a_game(m: OpenMSX) -> None:
    m.frames(500)
    m.tap("space")
    m.frames(60)
    m.tap("space")
    m.frames(150)


def check_graphics(cart: Cartridge, vram: bytes) -> int:
    ours = Vram()
    graphics.load_play(cart, 1, ours)
    failures = 0
    for name, base in (("patterns", PATTERNS), ("colours", COLOURS)):
        for third in range(3):
            differ = [c for c in range(256)
                      if ours.data[base + third * THIRD + c * 8:base + third * THIRD + c * 8 + 8]
                      != vram[base + third * THIRD + c * 8:base + third * THIRD + c * 8 + 8]]
            real = [c for c in differ if c not in NOT_THE_STAGES]
            failures += len(real)
            print("  %-8s third %d: %3d differ, %d of them the stage's %s"
                  % (name, third, len(differ), len(real), [hex(c) for c in real][:12]))
    sprites = [p for p in range(64) if ours.data[SPRITE_PATTERNS + p * 32:SPRITE_PATTERNS + p * 32 + 32]
               != vram[SPRITE_PATTERNS + p * 32:SPRITE_PATTERNS + p * 32 + 32]]
    print("  sprite patterns: %d of 64 differ" % len(sprites))
    return failures + len(sprites)


def terrain_characters(stage: Stage) -> set[int]:
    """Every character the stage's script puts anywhere."""
    found: set[int] = set()
    for d in range(stage.start, stage.end):
        found.update(stage.column(d) or ())
    return found


def check_map(stage: Stage, ram: bytes, terrain_set: set[int]) -> tuple[int, int]:
    """(terrain cells that differ, object cells), for one sample."""
    distance = ram[0x63] | ram[0x64] << 8
    terrain = objects = 0
    for col in range(32):
        d = distance - 31 + col
        cells = stage.column(d)
        star = stage.star_row(d)
        for row in range(ROWS):
            theirs = ram[MAP - 0xE000 + row * 32 + col]
            ours = cells[row] if cells else 0
            if cells is None and row == star and theirs in STAR_CHARACTERS:
                continue
            if theirs == ours:
                continue
            if theirs not in terrain_set or theirs == 0:
                objects += 1
            else:
                terrain += 1
    return terrain, objects


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", required=True)
    args = parser.parse_args()
    cart = Cartridge.from_file(args.rom)
    failures = 0
    with OpenMSX(args.rom) as m:
        print("stage 1 once play starts:")
        start_a_game(m)
        failures += check_graphics(cart, m.vram())
    stage = Stage(cart, 1)
    print("stage 1's map through the demo (every 50 frames):")
    samples = 0
    terrain_set = terrain_characters(stage) - {0}
    with OpenMSX(args.rom) as m:
        for _ in range(100):
            m.frames(50)
            ram = m.memory(0xE000, 0x1000)
            if ram[0x5F] != 1 or ram[0x61] != 1:
                continue
            terrain, objects = check_map(stage, ram, terrain_set)
            samples += 1
            failures += terrain
            if terrain:
                print("  frame %d, distance %d: %d terrain cells differ"
                      % (m.frame, ram[0x63] | ram[0x64] << 8, terrain))
    print("  %d samples" % samples)
    print("OK" if failures == 0 and samples else "FAILED: %d" % failures)
    return 0 if failures == 0 and samples else 1


if __name__ == "__main__":
    sys.exit(main())
