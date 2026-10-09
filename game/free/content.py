"""The game with no cartridge: the free assets in `assets/free/`.

Nothing in them comes out of the cartridge. The engine is the same; what it
is handed -- the terrain, the tables, the characters and sprites, the texts
and the sounds -- is made by `tools/make_free_assets.py` and can be edited
as pictures, text and JSON:

    stageN.chars.png    a stage's characters, three thirds of 256 (graphics.py)
    stageN.sprites.png  its 64 sprite patterns
    stageN.txt          its map, and stageN.json its rules, legend, distances
                        and own tables (stage.py, tables.py)
    title.png           the title screen, a whole picture
    tables.json         the tables every stage shares, and the layout
    text.json           the font's letters, the band's labels, the messages
    sounds.json         the sound effects and the music

Its stages are played in order, each by the rules of one of the original's
(its "rules"); after the last, its ending (finale.py), and the title.
"""

import os
import random
import sys

from game.engine.ending import CoreArt
from game.engine.tables import Tables
from game.engine.words import Keyboard
from game.free import cart as free_cart
from game.free import graphics, png
from game.free.finale import FreeFinale
from game.free.stage import FreeStage, files
from game.free.tables import read_stages
from game.free.texts import FreeMessages
from game.rom import screens
from game.vdp import COLOURS, PATTERNS, THIRD, Vram

#: The letters over the view (thirds 0 and 1 of `chars.png`): the title has
#: them in all three thirds, as the cartridge's (0x5851).
FONT = range(0x10, 0x3B)
FIRST_STAGE = 1


def assets_folder(folders: list[str]) -> str | None:
    """`assets/free` beside the program or in the directory given, inside a
    frozen build, or in this checkout."""
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = list(folders)
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidates.append(bundle)
    candidates.append(here)
    for folder in candidates:
        path = os.path.join(folder, "assets", "free")
        if os.path.isfile(os.path.join(path, "tables.json")):
            return path
    return None


class FreeContent:
    attract = False
    finale = True
    ends_after_last = True

    def __init__(self, folder: str) -> None:
        self.folder = folder
        self.cart = free_cart.build(folder)
        self.messages = FreeMessages.read(folder)
        tables = read_stages(folder)
        #: Every stage there is, read now, so a map that cannot be read says
        #: so before the game opens; in the stages' order, which is their
        #: rules' (tables.py sees to it). A stage is only read from, so each
        #: is handed out as it is.
        self.stages = [FreeStage(folder, number) for number in files(folder)]
        if not self.stages:
            raise ValueError("there is no stage%d.txt" % FIRST_STAGE)
        # Each stage brings its tables and core, and its pictures: its own
        # stageN.chars.png and stageN.sprites.png, or the shared ones.
        self.vram: dict[int, Vram] = {}
        self.problems: list[str] = []
        for stage in self.stages:
            stage.tables, stage.core_art = tables[stage.number]
            vram = self.vram[stage.number] = Vram()
            chars = self._own(stage.file, "chars.png")
            self.problems += graphics.load_chars(png.read(chars), vram)
            graphics.load_sprites(png.read(self._own(stage.file, "sprites.png")), vram)
        self._tables, self._core = tables[self.stages[0].number]
        self.play_vram = self.vram[self.stages[0].number]
        self.title_vram = Vram()
        for third in range(3):
            for char in FONT:
                for table in (PATTERNS, COLOURS):
                    at = table + char * 8
                    self.title_vram.data[at + third * THIRD:at + third * THIRD + 8] = \
                        self.play_vram.data[at:at + 8]
        self.problems += graphics.screen(png.read(self._path("title.png")), self.title_vram,
                                         range(1, 256), set(FONT))
        # 0x5B77's messages over it, as the cartridge's title has them.
        screens.write_messages(self.messages, self.title_vram)
        for problem in self.problems:
            print("nemesio: free assets: %s" % problem, file=sys.stderr)

    def _path(self, name: str) -> str:
        return os.path.join(self.folder, name)

    def _own(self, number: int, name: str) -> str:
        """stageN.<name> if the stage has one, else the shared <name>."""
        own = self._path("stage%d.%s" % (number, name))
        return own if os.path.isfile(own) else self._path(name)

    def tables(self) -> Tables:
        return self._tables

    def core_art(self) -> CoreArt | None:
        return self._core

    def keyboard(self) -> Keyboard | None:
        return None

    def stage(self, number: int) -> FreeStage:
        """What the engine asks for as the original's stage `number`: the
        first of the free stages that plays by its rules or a later
        stage's; past the last, the first again: a new round, which the
        host ends (`ends_after_last`) with the ending and the title."""
        return next((stage for stage in self.stages if stage.number >= number), self.stages[0])

    def load_play(self, stage: int, vram: Vram) -> None:
        """Stage `stage` (the rules' number the engine knows it by)'s pictures."""
        vram.data[:] = self.vram.get(stage, self.play_vram).data

    def load_boss(self, vram: Vram) -> None:
        """The core's characters are in `chars.png` from the start."""

    def make_finale(self, rng: random.Random, round_: int, vram: Vram) -> FreeFinale:
        return FreeFinale(self.messages, self._tables.layout, rng, round_, vram, self.play_vram)

    def title(self) -> Vram:
        vram = Vram()
        vram.data[:] = self.title_vram.data
        return vram
