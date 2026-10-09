"""The free assets checked, file by file: what an editor gets wrong, said in a
sentence each, all of it at once (`main.py --check-assets`).

- the pictures: their size, and no pixel row of a character with more than
  two colours (the TMS9918 has two a row);
- the map: its rows, its legend, the distances in order, and no character
  on the bottom six rows that is the band's there;
- the tables: what they and the layout draw with is drawn -- sprite patterns
  in `sprites.png`, characters in `chars.png` -- and every animation, record
  and drawing is there;
- the texts: every letter in the font, every message on the screen;
- the sounds: every step writable, on the channels its number takes.

A problem that stops a file being read at all is its only one: the rest of
that file is not looked at.
"""

import json
import os
from typing import Any

from game.engine.original import MAP_COLUMNS, MAP_ROWS, SCENERY
from game.free import cart, graphics, png
from game.free.stage import FreeStage
from game.free.numbers import num
from game.free.stage import files
from game.free.tables import read_stages
from game.engine.ending import CoreArt
from game.engine.tables import Tables
from game.free.texts import FreeMessages
from game.vdp import COLOURS, PATTERNS, SPRITE_PATTERNS, THIRD, Vram

#: The band's own characters, in the third third (text.json's "band" font
#: and the meter): a map character among them shows the band's picture on the
#: map's bottom rows.
BAND_CHARACTERS = range(0x01, 0x43)
BAND_THIRD_FROM = 16
SIZES = {"chars.png": (graphics.CHARS_WIDTH, graphics.CHARS_HEIGHT),
         "sprites.png": (graphics.SPRITES_WIDTH, graphics.SPRITES_HEIGHT),
         "title.png": (256, 192)}
SCREEN_ROWS = 24


class Report:
    def __init__(self) -> None:
        self.problems: list[str] = []

    def add(self, where: str, what: str) -> None:
        self.problems.append("%s: %s" % (where, what))


def _drawn_patterns(vram: Vram) -> set[int]:
    out = set()
    for n in range(64):
        at = SPRITE_PATTERNS + n * 32
        if any(vram.data[at:at + 32]):
            out.add(n * 4)
    return out


def _drawn_characters(vram: Vram) -> set[int]:
    """A character with a pixel in any colour but 0, in any third."""
    out = set()
    for char in range(256):
        for third in range(3):
            at = third * THIRD + char * 8
            for y in range(8):
                bits, colour = vram[PATTERNS + at + y], vram[COLOURS + at + y]
                if (bits and colour >> 4) or (bits != 0xFF and colour & 0x0F):
                    out.add(char)
    return out


def _picture(folder: str, name: str, report: Report) -> png.Picture | None:
    try:
        picture = png.read(os.path.join(folder, name))
    except (OSError, ValueError, KeyError) as error:
        report.add(name, str(error))
        return None
    width, height = SIZES[name.split(".", 1)[-1] if name.startswith("stage") else name]
    if (picture.width, picture.height) != (width, height):
        report.add(name, "is %dx%d, and should be %dx%d" % (picture.width, picture.height,
                                                            width, height))
        return None
    return picture


def check(folder: str) -> list[str]:
    report = Report()
    title = _picture(folder, "title.png", report)
    if title is not None:
        for problem in graphics.screen(title, Vram(), range(1, 256), set(range(0x10, 0x3B))):
            report.problems.append(problem)
    _map(folder, report)
    try:
        stages_ = read_stages(folder)
    except (OSError, ValueError, KeyError, TypeError) as error:
        report.add("tables", "%s: %s" % (type(error).__name__, error))
        stages_ = {}
    # Each stage against its own pictures (or the shared ones).
    read_pictures: dict[str, png.Picture | None] = {}
    for number in files(folder):
        with open(os.path.join(folder, "stage%d.json" % number)) as handle:
            rules = num(json.load(handle).get("rules", number))
        vram = Vram()
        found = {}
        for kind in ("chars.png", "sprites.png"):
            name = "stage%d.%s" % (number, kind)
            if not os.path.isfile(os.path.join(folder, name)):
                name = kind
            if name not in read_pictures:
                read_pictures[name] = _picture(folder, name, report)
                if kind == "chars.png" and read_pictures[name] is not None:
                    picture = read_pictures[name]
                    assert picture is not None
                    report.problems += graphics.load_chars(picture, Vram())
            found[kind] = read_pictures[name]
        chars, sprites = found["chars.png"], found["sprites.png"]
        if chars is not None:
            graphics.load_chars(chars, vram)
        if sprites is not None:
            graphics.load_sprites(sprites, vram)
        if rules in stages_:
            tables, core = stages_[rules]
            _tables(report, "stage%d" % number, tables, core,
                    _drawn_patterns(vram) if sprites is not None else None,
                    _drawn_characters(vram) if chars is not None else None)
    _texts(folder, report)
    try:
        cart.build(folder)
    except (OSError, ValueError, KeyError, TypeError) as error:
        report.add("sounds.json", str(error))
    return report.problems


def _map(folder: str, report: Report) -> None:
    number = 1
    while os.path.isfile(os.path.join(folder, "stage%d.txt" % number)):
        where = "stage%d" % number
        try:
            stage = FreeStage(folder, number)
        except (OSError, ValueError, KeyError) as error:
            report.add(where, str(error))
            number += 1
            continue
        if not stage.start < stage.checkpoint < stage.limit:
            report.add(where + ".json", "start (0x%X), checkpoint (0x%X) and limit (0x%X) "
                       "should come in that order" % (stage.start, stage.checkpoint, stage.limit))
        with open(os.path.join(folder, "stage%d.txt" % number)) as handle:
            lines = handle.read().split("\n")
        widths = {len(line.rstrip("\r")) for line in lines[:MAP_ROWS]}
        if len(widths) > 1:
            report.add(where + ".txt", "its rows are not all as long (%s)"
                       % ", ".join(str(w) for w in sorted(widths)))
        band = set()
        for distance in range(stage.start, stage.end):
            column = stage.column(distance) or []
            for row in range(BAND_THIRD_FROM, MAP_ROWS):
                if column[row] in BAND_CHARACTERS:
                    band.add(column[row])
            for value in column:
                if not 0 <= value < 0x100:
                    report.add(where + ".json", "the legend has 0x%X, and a character is "
                               "0x00-0xFF" % value)
        if band:
            report.add(where, "characters %s are on the map's bottom rows, where they are "
                       "the band's font" % ", ".join("0x%02X" % c for c in sorted(band)))
        number += 1
    if number == 1:
        report.add("stage1.txt", "there is none")


def _tables(report: Report, stage: str, tables: Tables, core: CoreArt | None,
            patterns: set[int] | None, characters: set[int] | None) -> None:
    """A stage's tables against its pictures: what they use is drawn."""
    layout = tables.layout
    drawings = tables.character_drawings

    def sprite(pattern: int, what: str) -> None:
        if patterns is not None and pattern & 0xFC not in patterns:
            report.add(stage, "%s is sprite pattern 0x%02X, and sprites.png has "
                       "nothing there" % (what, pattern))

    def drawing(number: int, what: str) -> None:
        if not 0 <= number < 128:
            report.add(stage, "%s is drawing %d, and there are 128" % (what, number))
            return
        chars = drawings[number * 4:number * 4 + 4]
        if not any(chars):
            report.add(stage, "%s is drawing 0x%02X, and character_drawings has "
                       "none" % (what, number))
        for char in chars:
            character(char, "%s's drawing 0x%02X" % (what, number))

    def character(char: int, what: str) -> None:
        if char and characters is not None and char not in characters:
            report.add(stage, "%s uses character 0x%02X, and chars.png has nothing "
                       "there" % (what, char))

    for kind, (chars, pattern, _, _) in enumerate(tables.records):
        if chars:
            if pattern:
                drawing(pattern, "type 0x%02X" % kind)
        elif pattern:
            sprite(pattern, "type 0x%02X" % kind)
    for kind, steps in tables.animations.items():
        drawn_with_chars = kind < len(tables.records) and tables.records[kind][0]
        for step in steps:
            if drawn_with_chars:
                drawing(step, "type 0x%02X's animation" % kind)
            else:
                sprite(step, "type 0x%02X's animation" % kind)
    for pattern, _ in tables.blast:
        sprite(pattern, "the blast")
    for state in tables.ship_cards:
        for card in state:
            sprite(card[0], "the ship")
            sprite(card[2], "the ship")
    for (a, _), (b, _) in layout.ship + layout.explosion:
        sprite(a, "the layout's ship")
        sprite(b, "the layout's ship")
    for parts in layout.explosion_parts:
        for _, pattern, _ in parts:
            sprite(pattern, "the layout's explosion")
    for what, pattern in (("double", layout.double[0]), ("missile", layout.missile[0]),
                          ("missile", layout.missile[1]), ("enemy shot", layout.enemy_shot[0]),
                          ("blast", layout.blast_pattern)):
        sprite(pattern, "the layout's " + what)
    for pattern, _ in layout.options:
        sprite(pattern, "the layout's option")
    for pattern in list(layout.walker_start.values()) + [
            p for pair in layout.walker_facing.values() for p in pair]:
        sprite(pattern, "the layout's walker")
    for number in set(layout.bug_drawings):
        drawing(number, "the bug")
    drawing(layout.ship_drawing, "the prize ship")
    drawing(layout.capsule_drawing, "the capsule")
    for kind, number in layout.capsule_drawings.items():
        drawing(number, "type 0x%02X's capsule" % kind)
    base = [tables.cannon_drawings[s * 12] for s in range(4)]
    for s, first in enumerate(base):
        for turn in range(6):
            drawing(first + turn, "cannon set %d" % s)
    for char in layout.stars:
        character(char, "the layout's star")
    for first in (layout.shot_character, layout.laser_character):
        for n in range(4):
            character(first + n, "the layout's shot")
    for first in list(layout.pairs.values()) + [layout.pair_other]:
        character(first, "the layout's pair")
        character(first + 1, "the layout's pair")
    for n, cells in enumerate(tables.background_drawings[:4]):
        for char in cells:
            character(char, "hatch drawing %d" % n)
    for n, cells in enumerate(tables.blast_drawings):
        for char in cells:
            character(char, "background blast %d" % n)
    if core is not None:
        for what, part in (("body", core.body), ("eyes", core.eyes), ("mouths", core.mouths)):
            for char in part:
                character(char, "the core's " + what)
    if tables.ending is not None:
        for piece in tables.ending.crystal_chars:
            for char in piece:
                character(char, "the crystal")
        for char in tables.ending.crystal_blast:
            character(char, "the crystal's blast")
    for n in range(len(tables.cannon_script)):
        for distance, data in tables.cannon_script[n]:
            if (data & 0x1F) >= MAP_ROWS:
                report.add(stage, "a cannon at 0x%X is on row %d, past the map"
                           % (distance, data & 0x1F))
    rules = tables.stages
    for n, (found, _) in rules.breakable.items():
        for char in found:
            character(char, "stage %d's breakable block" % n)
            if not 0 < char < SCENERY:
                report.add(stage, "stage %d's breakable 0x%02X is not solid (it should "
                           "be under 0x%02X): no shot would ever meet it" % (n, char, SCENERY))
    for row, col in tables.rain_doors:
        if not (0 <= row < MAP_ROWS * 8 and 0 <= col < MAP_COLUMNS * 8):
            report.add(stage, "a rain door at row 0x%X, column 0x%X is off the screen"
                       % (row, col))
    for n, boss in rules.boss.items():
        crystal = rules.crystal.get(n)
        if crystal is not None and crystal >= boss:
            report.add(stage, "stage %d's crystal (0x%X) comes after its boss (0x%X)"
                       % (n, crystal, boss))
    for char in layout.stars:
        if char < SCENERY:
            report.add(stage, "the star 0x%02X is solid (under 0x%02X): the ship "
                       "would crash into the stars" % (char, SCENERY))


def _texts(folder: str, report: Report) -> None:
    try:
        with open(os.path.join(folder, "text.json")) as handle:
            spec: dict[str, Any] = json.load(handle)
        FreeMessages(spec)
    except (OSError, ValueError, KeyError, TypeError) as error:
        report.add("text.json", "%s: %s" % (type(error).__name__, error))
        return
    for name, pieces in spec.items():
        if name in ("font", "meter"):
            continue
        for row, col, text in pieces:
            row, col = num(row), num(col)
            if not 0 <= row < SCREEN_ROWS or col < 0 or col + len(text) > MAP_COLUMNS:
                report.add("text.json", "%r's %r does not fit on the screen at row %d, "
                           "column %d" % (name, text, row, col))
    cells = spec["meter"]["cells"]
    if len(cells) != 6 or any(len(four) != 4 for cell in cells for four in cell):
        report.add("text.json", "the meter is six cells of two sets of four characters")
