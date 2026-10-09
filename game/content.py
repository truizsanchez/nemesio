"""Where a game's content comes from: the player's cartridge, or the free assets.

The engine is handed its content already shaped -- a stage's `Terrain`, the
`Tables`, the core's `CoreArt` -- and the window fills the VDP's memory with
the characters and writes the `messages`. The sound driver reads its data by
bank and address from `cart`: the player's own, or one the free assets build
in memory with the same layout (`game/free/cart.py`).
"""

import random
from typing import Protocol

from game.engine.ending import CoreArt
from game.engine.tables import Tables
from game.engine.terrain import Terrain
from game.engine.words import Keyboard
from game.finale import Finale
from game.rom import graphics, screens
from game.rom.band import Messages, RomMessages
from game.rom.cartridge import Cartridge
from game.rom.stage import Stage
from game.rom.tables import core_art, keyboard, read
from game.vdp import Vram


class Content(Protocol):
    #: The bytes the sound driver (and, the cartridge's, the attract screens
    #: and the finale) read by bank and address.
    cart: Cartridge
    #: The band's labels and the messages.
    messages: Messages
    #: The logo, the picture and the demo between titles.
    attract: bool
    #: The game's ending after stage 8 (the rules' eighth): whether there
    #: is one, and one made.
    finale: bool
    #: Whether the game ends when its last stage does (its ending, then the
    #: title) instead of going round to the first.
    ends_after_last: bool

    def make_finale(self, rng: random.Random, round_: int, vram: Vram) -> "FinaleLike": ...

    def tables(self) -> Tables: ...

    def core_art(self) -> CoreArt | None: ...

    def keyboard(self) -> Keyboard | None: ...

    def stage(self, number: int) -> Terrain: ...

    def load_play(self, stage: int, vram: Vram) -> None: ...

    def load_boss(self, vram: Vram) -> None: ...

    def title(self) -> Vram: ...


class FinaleLike(Protocol):
    """What the host runs and draws of an ending (game/finale.py's Finale,
    game/free/finale.py's FreeFinale)."""

    vram: Vram
    names: bytearray
    border: int
    loaded: bool
    sounds: list[int]
    music_fade: bool
    bonus: int
    done: bool
    interrupts: int

    def update(self, busy: bool) -> None: ...

    def sprites(self) -> list[tuple[int, int, int, int]]: ...


class RomContent:
    """The player's cartridge, read as it always was."""

    attract = True
    finale = True
    ends_after_last = False

    def __init__(self, cart: Cartridge) -> None:
        self.cart = cart
        self.messages = RomMessages(cart)

    def tables(self) -> Tables:
        return read(self.cart)

    def core_art(self) -> CoreArt | None:
        return core_art(self.cart)

    def keyboard(self) -> Keyboard | None:
        return keyboard(self.cart)

    def stage(self, number: int) -> Terrain:
        return Stage(self.cart, number)

    def load_play(self, stage: int, vram: Vram) -> None:
        graphics.load_play(self.cart, stage, vram)

    def load_boss(self, vram: Vram) -> None:
        graphics.load_boss(self.cart, vram)

    def title(self) -> Vram:
        return screens.title(self.cart)

    def make_finale(self, rng: random.Random, round_: int, vram: Vram) -> FinaleLike:
        return Finale(self.cart, rng, round_, vram)
