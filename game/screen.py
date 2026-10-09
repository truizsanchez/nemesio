"""What the VDP shows during play, as the cartridge puts it in VRAM.

No Pyxel here: `main.py` draws what this holds, and `tools/compare_play.py
--screen` holds it against the original's VRAM.

- The names (0x3800): the map as 0x47FE sends it, at 0x45E5, with the shots
  and the objects drawn with characters in it (`Play.shown`); and the band,
  whose score and record are written only one game frame in eight (0x45EB).
- The sprites (0x3B00): 0x47CE sends 0xEC80, the buffer built the game frame
  before, as the next one starts -- from the entry 0xE17F says, three on each
  time, or as it is with the ship blowing up. So the sprites are always a game
  frame behind the names.
"""

from game.engine.original import (
    EMPTY_TYPES, MAP_COLUMNS, MAP_ROWS, SCORES_AT, SCORES_EVERY, SPRITE_ENTRIES, SPRITE_TURN_EVERY,
)
from game.engine.play import Play
from game.engine.shots import DOUBLE, MISSILE

#: An entry: row, column, pattern, colour. None is one the VDP draws nowhere
#: (0xE0 in its row, 0xA225, 0x4884): what else it holds is not looked at.
Sprite = tuple[int, int, int, int] | None


def build_sprites(play: Play) -> list[Sprite]:
    """0xEC80's 32 entries as the game frame leaves them: the ship's two,
    the options, the doubles, the missiles (0xA17F), the twelve objects
    (0xECA8, 0x4840) and the ten enemy shots (0xECD8, 0x481C)."""
    table: list[Sprite] = []
    ship = play.ship
    if ship.gone:
        table += [None, None]
    else:
        cards = play.ship_cards()
        table += list(cards) if cards is not None else [None, None]
    if ship.exploding is not None and not play.was_flying:
        # 0x9BB4: the options' two slots are pieces of the explosion.
        table += list(ship.parts)
    else:
        table += [(o.row, o.col, o.pattern, o.colour) for o in play.options.options[:2]]
    table += [None] * (4 - len(table))
    for kind, shots in ((DOUBLE, [pair[1] for pair in play.shots.slots]),
                        (MISSILE, list(play.shots.missiles))):
        table += [(s.row, s.col, s.character, s.colour) if s is not None and s.kind == kind
                  else None for s in (shots + [None] * 3)[:3]]
    objects = play.objects
    for o in (objects.slots + objects.shots) if objects is not None else []:
        shown = o.type not in EMPTY_TYPES and not o[11]
        table.append((o.row, o.col, o[12], o[13]) if shown else None)
    table += [None] * (SPRITE_ENTRIES - len(table))
    return table


def sent(table: list[Sprite], start: int, turning: bool) -> list[Sprite]:
    """0x47CE: the buffer as it reaches the VDP."""
    if not turning:
        return list(table)
    return [table[(start + SPRITE_TURN_EVERY * n) % SPRITE_ENTRIES]
            for n in range(SPRITE_ENTRIES)]


def names(play: Play) -> bytes:
    """The 22 rows of the name table: in play, the map as 0x47FE last sent
    it; on the tick that builds the stage for a life, nothing has sent it
    since the curtain blanked the rows (0x558A); otherwise, the map."""
    if play.sprites_on and play.shown is not None:
        return play.shown
    if play.stage_built:
        return bytes(MAP_ROWS * MAP_COLUMNS)
    return bytes(play.scroll.map.cells)


class Screen:
    """The sprite table in VRAM, game frame by game frame."""

    def __init__(self) -> None:
        #: 0xEC80 as the last game frame left it.
        self.built: list[Sprite] = [None] * SPRITE_ENTRIES
        #: 0x3B00: what the VDP draws; empty while no sprites are sent.
        self.sprites: list[Sprite] = []
        #: The score and the record as the band last had them written.
        self.score = self.record = 0
        #: The two star characters' top rows as last written (0x475B), or
        #: None for what loading the stage's characters left there.
        self.stars: tuple[int, int] | None = None

    def step(self, play: Play) -> None:
        """After a game frame of `play`."""
        if not play.sprites_on or play.frames % SCORES_EVERY == SCORES_AT:
            self.score, self.record = play.score, play.record
        if not play.sprites_on:
            # 0x55AA: 0xD0 at 0x3B00, and nothing drawn.
            self.sprites = []
            if play.stage_built:
                # The tick that builds the stage for a life: 0xEC80 left
                # empty, the stage's characters loaded.
                self.built = [None] * SPRITE_ENTRIES
                self.stars = None
            return
        # 0x4538, as the game frame started: last game frame's buffer.
        self.sprites = sent(self.built, play.sprites_from, play.was_flying)
        if play.drawn:
            self.built = build_sprites(play)
            self.stars = play.star_rows()
        elif play.stage_built:
            # A stage built in a game frame cut short: its characters loaded.
            self.stars = None
        ending = play.ending
        if ending is not None and ending.finale:
            # The game's ending draws its own sprites from 0xEC80, and leaves
            # none there.
            self.built = [None] * SPRITE_ENTRIES
