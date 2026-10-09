"""The engine against the original, game frame by game frame, on the same pad.

    python tools/compare_play.py --rom <nemesis.rom> [--script "40:right,30:up+fire,..."]

Starts a game in openMSX and in the engine, feeds both the same pad -- a
script of (game frames, keys) -- and compares, every game frame, what both
have in common: the ship's row and column, whether it is alive, the distance,
and the normal shots. The original's game frames are told apart by its frame
counter (0xE003), which moves once per game frame however many video frames
that one took.

The pad is applied to the original a video frame at a time, and a key goes
down on the video frame the script says; the original reads the pad once per
game frame (0x404E), so the two see the same pad as long as a script segment
is longer than a game frame.
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.engine.original import (  # noqa: E402
    DOWN, FIRE, LEFT, MAP_COLUMNS, MAP_ROWS, POWER, RIGHT, STARS, UP,
)
from game.engine.play import Phase, Play  # noqa: E402
from game.engine.stage5 import Stage5  # noqa: E402
from game.finale import Finale  # noqa: E402
from game.rom.cartridge import Cartridge  # noqa: E402
from game.rom.stage import Stage  # noqa: E402
from game.rom.sound import Driver, Music  # noqa: E402
from game.rom.tables import core_art as read_core_art  # noqa: E402
from game.rom.tables import read as read_tables  # noqa: E402
from game.rom import graphics  # noqa: E402
from game.rom.band import RomMessages, write_band  # noqa: E402
from game.screen import Screen  # noqa: E402
from game.screen import names as screen_names  # noqa: E402
from game.vdp import ATTRIBUTES, NAMES, PATTERNS, THIRD, Vram  # noqa: E402
from tools.harness.omsx import OpenMSX  # noqa: E402

#: Not a pad bit: F5, CONTINUE while GAME OVER waits (0x54F3).
CONTINUE = 0x100
BITS = {"up": UP, "down": DOWN, "left": LEFT, "right": RIGHT, "fire": FIRE, "power": POWER,
        "continue": CONTINUE}
KEY_OF = {UP: "up", DOWN: "down", LEFT: "left", RIGHT: "right", FIRE: "space", POWER: "m",
          CONTINUE: "f5"}
DEFAULT = "20:,40:right,30:up,30:down+fire,20:left,30:up+fire,20:fire"


def parse(script: str) -> list[tuple[int, int]]:
    out = []
    for part in script.split(","):
        count, _, keys = part.partition(":")
        pad = 0
        for key in filter(None, keys.split("+")):
            pad |= BITS[key]
        out.append((int(count), pad))
    return out


OBJECTS = False
#: With --types, only those, sorted: which slot each takes is the R
#: register's doing once anything before them differs.
TYPES: tuple[int, ...] = ()


def _objects(slots: list[tuple[int, int, int]]) -> tuple[object, ...]:
    if TYPES:
        return tuple(sorted(o for o in slots if o[0] in TYPES))
    return tuple(slots)


#: With --nuclei, stage 6's six pieces (0xE790, 0x10 apart): type, row,
#: column, drawing.
NUCLEI = False


#: With --pieces, stage 5's background (0xE700) and turrets (0xE880): kind,
#: step, row, column.
PIECES = False


#: With --shots, the ten enemy shots (0xE500): row, column.
SHOTS = False


#: With --heads, stage 3's boss slots (0xE780), or stage 4's walkers or the
#: core in them: row, column, hits left.
HEADS = False


#: With --sprites, where the sprite table is sent from (0xE17F, in entries).
SPRITES = False
#: With --ship-sprites, the ship's two entries of 0xEC80 (0xA17F): row,
#: column, pattern, colour.
SHIP_SPRITES = False
#: With --screen, what the VDP shows: the names, the sprites, the stars.
SCREEN = False
#: With --map, the 22x32 map buffer (0xED00) as the game frame leaves it.
MAP = False
#: With --band, the score, the record (0xE054), the ships and 0xE067.
BAND = False
HIDDEN = 0xE0


#: With --players 2, the turn (0xE002's bit 7) and both players' ships
#: (0xE060, 0xE090) too.
PLAYERS = 1

#: With --finale, the game's ending once 0xE1D0 is up: step 0 the ship
#: leaving (row, column, 0xE1D3); steps 1-9 0xE1D1, 0xE1D2, 0xE1D9 and the
#: 32 shrapnel slots of 0xE300 (kind, game frames, row, column).
FINALE = False


#: With --psg, the PSG's fourteen registers (the mixer's port bits masked).
#: A channel at volume 0 has its period left out: a bare 0x20 (a rest)
#: writes whatever the Z80's DE holds as its period (0x81BC), which nobody
#: hears.
PSG = False


#: With --sounds, the sounds each game frame asks the driver for (0x4A22,
#: encola_sonido), in order: the rules that ask for them, apart from where
#: in its game frame a request falls, which decides the interrupt that
#: hears it and is the Z80's time.
SOUNDS = False
REQUEST = 0x4A22


def _psg(regs: bytes | bytearray | list[int]) -> tuple[object, ...]:
    tones: list[object] = []
    for n in range(3):
        heard = regs[8 + n] != 0
        tones += [regs[2 * n], regs[2 * n + 1]] if heard else ["-", "-"]
    return tuple(tones) + (regs[6], regs[7] & 0x3F) + tuple(regs[8:14])


def _finale_original(ram: bytes) -> tuple[object, ...]:
    if not ram[0x1D0]:
        return ("-",)
    if not ram[0x1D1]:
        return ("leaving", ram[0x204], ram[0x206], ram[0x1D3] | ram[0x1D4] << 8)
    pieces = tuple((ram[at], ram[at + 1], ram[at + 3], ram[at + 5])
                   for at in range(0x300, 0x500, 0x10) if ram[at])
    return (ram[0x1D1], ram[0x1D2], ram[0x1D9], pieces)


def _finale_engine(play: Play, finale: "Finale | None") -> tuple[object, ...]:
    ending = play.ending
    if ending is None or ending.leaving is None:
        return ("-",)
    if not ending.finale:
        return ("leaving", play.ship.row, play.ship.col, ending.leaving)
    if finale is None:
        # The game frame that let the ship go: 0x4AFA has put up step 1.
        return (1, 0, 0, ())
    pieces = tuple((p[0], p[1], p[2] >> 8, p[3] >> 8) for p in finale.pieces if p is not None)
    return (finale.step, finale.clock, finale.at, pieces)


def _bcd(low_first: bytes) -> int:
    """BCD bytes, the lowest first, as the number they write."""
    return int("".join("%02X" % b for b in reversed(low_first)))


def _to_bcd(value: int, size: int) -> bytes:
    """A number as `size` BCD bytes, the lowest first."""
    digits = "%0*d" % (2 * size, value)
    return bytes(int(digits[at:at + 2], 16) for at in range(2 * size - 2, -1, -2))


def _sprites(entries: list[tuple[int, int, int, int] | None]) -> tuple[object, ...]:
    """As the VDP reads them: up to a row of 0xD0, and one at row 0xE0 is
    nowhere (what else it holds is stale)."""
    out: list[object] = []
    for e in entries:
        if e is not None and e[0] == 0xD0:
            break
        out.append(None if e is None or e[0] == 0xE0 else e)
    return tuple(out)


def _screen_original(m: "OpenMSX") -> tuple[object, ...]:
    table = m._hex_block("VRAM", NAMES, 0x380)
    attributes = table[ATTRIBUTES - NAMES:]
    stars = tuple(m._hex_block("VRAM", PATTERNS + third * THIRD + STARS[0] * 8, 9)[n]
                  for third in range(3) for n in (0, 8))
    return (table[:MAP_ROWS * MAP_COLUMNS], table[MAP_ROWS * MAP_COLUMNS:ATTRIBUTES - NAMES],
            _sprites([tuple(attributes[n:n + 4]) for n in range(0, 128, 4)]),  # type: ignore[misc]
            stars)


def _screen_engine(play: Play, screen: "Screen", cart: Cartridge) -> tuple[object, ...]:
    band = bytearray(32 * 24)
    write_band(RomMessages(cart), band, play.lives, play.taken(), play.meter, screen.score, screen.record,
               play.turn)
    rows = screen.stars
    if rows is None:
        vram = Vram()
        graphics.load_play(cart, play.terrain.number, vram)
        rows = (vram[PATTERNS + STARS[0] * 8], vram[PATTERNS + STARS[1] * 8])
    stars = rows * 3
    return (screen_names(play),
            bytes(band[MAP_ROWS * MAP_COLUMNS:]), _sprites(screen.sprites), stars)


def _screen_differences(t: tuple[object, ...], o: tuple[object, ...]) -> str:
    """Where two --screen states part: cells of the map and the band, the
    first sprite entry, the stars."""
    parts = []
    for name, a, b in zip(("map", "band"), t[:2], o[:2]):
        assert isinstance(a, bytes) and isinstance(b, bytes)
        cells = [(at // MAP_COLUMNS, at % MAP_COLUMNS, x, y)
                 for at, (x, y) in enumerate(zip(a, b)) if x != y]
        if cells:
            kinds = sorted({(x, y) for _, _, x, y in cells})
            parts.append("%s %d cells %s (%s)" % (
                name, len(cells), ", ".join("(%d,%d) %02X/%02X" % c for c in cells[:6]),
                " ".join("%02X/%02X" % k for k in kinds[:8])))
    ours, theirs = t[2], o[2]
    assert isinstance(ours, tuple) and isinstance(theirs, tuple)
    if ours != theirs:
        k = next((i for i, (x, y) in enumerate(zip(ours, theirs)) if x != y),
                 min(len(ours), len(theirs)))
        parts.append("sprite %d %s/%s" % (k, ours[k] if k < len(ours) else "-",
                                          theirs[k] if k < len(theirs) else "-"))
    if t[3] != o[3]:
        parts.append("stars %s/%s" % (t[3], o[3]))
    return "; ".join(parts)


def original_state(ram: bytes) -> tuple[object, ...]:
    if FINALE:
        return _finale_original(ram)
    if ram[0x00] < 4:
        # States 0-3: the game is over, the title and the attract.
        return ("title",)
    if ram[0x1D1]:
        # The game's ending: 0xE300 holds its shrapnel, 0xEC80 its sprites.
        return ("finale",)
    if SPRITES:
        return (ram[0x17F] >> 2,)
    if MAP:
        return (bytes(ram[0xD00:0xD00 + MAP_ROWS * MAP_COLUMNS]),)
    if BAND:
        # The score and the record, three BCD bytes each (0xE05C, 0xE054),
        # the ships (0xE060) and the next ship's score (0xE067).
        # The score is the turn's (0x55B9: 0xE058 for the second player).
        score = 0x58 if ram[0x02] & 0x80 else 0x5C
        return (_bcd(ram[score:score + 3]), _bcd(ram[0x54:0x57]), _bcd(ram[0x60:0x61]),
                _bcd(ram[0x67:0x69]))
    if SHIP_SPRITES:
        # Out of play (state 5) no sprites are sent (0x55AA); what 0xEC80
        # holds is stale.
        if ram[0x00] != 5:
            return ("off",)
        return (tuple(ram[0xC80:0xC84]), tuple(ram[0xC84:0xC88]))
    if PIECES:
        return tuple(tuple(ram[at:at + 4]) if ram[at] else () for at in
                     list(range(0x700, 0x740, 8)) + list(range(0x880, 0x8A0, 8)))
    if NUCLEI:
        return tuple((ram[at], ram[at + 3], ram[at + 5], ram[at + 6]) if ram[at] else ()
                     for at in range(0x790, 0x7F0, 0x10))
    if SHOTS:
        return tuple((ram[at + 4], ram[at + 6]) if ram[at] else () for at in range(0x500, 0x640, 0x20))
    if HEADS:
        return tuple((ram[at + 3], ram[at + 5], ram[at + 9]) for at in range(0x780, 0x800, 0x10)
                     if ram[at])
    if OBJECTS:
        return _objects([(ram[0x300 + 32 * n], ram[0x304 + 32 * n], ram[0x306 + 32 * n])
                         for n in range(12) if ram[0x300 + 32 * n]])
    shots: list[tuple[int, int]] = []
    for slot in (0x260, 0x270):
        if ram[slot]:
            shots.append((ram[slot + 3], ram[slot + 5]))
    turns = (ram[0x02] >> 7, ram[0x60], ram[0x90]) if PLAYERS == 2 else ()
    return (ram[0x204], ram[0x206], int(ram[0x200] == 1), ram[0x63] | ram[0x64] << 8,
            *turns, *sorted(shots))


def engine_state(play: Play, finale: "Finale | None" = None) -> tuple[object, ...]:
    if FINALE:
        return _finale_engine(play, finale)
    if play.phase is Phase.FINISHED:
        return ("title",)
    ending = play.ending
    if ending is not None and ending.finale and not ending.finale_done:
        return ("finale",)
    if SPRITES:
        return (play.sprites_from,)
    if MAP:
        return (bytes(play.scroll.map.cells),)
    if BAND:
        return (play.score, play.record, play.lives, play.next_ship)
    if SHIP_SPRITES:
        if play.between is not None or play.ship.gone:
            return ("off",)
        cards = play.ship_cards()
        # The tick that builds the stage leaves 0xEC80 empty: rows at 0xE0.
        return cards if cards is not None else ((HIDDEN,) * 4,) * 2
    if PIECES:
        guns = play.guns
        slots = list(guns.slots) + list(guns.turrets) if isinstance(guns, Stage5) else []
        return tuple(tuple(s[:4]) if s[0] else () for s in slots)
    if SHOTS:
        assert play.objects is not None
        return tuple((s[4], s[6]) if s[0] else () for s in play.objects.shots)
    if HEADS:
        walkers = play.ending.walkers if play.ending is not None else None
        core = play.ending.core if play.ending is not None else None
        if core is not None and core.alive:
            return ((core.row, core.col, core.life),)
        if walkers is not None:
            return tuple((w.row, w.col, w.life) for w in walkers.walkers if w is not None)
        heads = play.ending.heads if play.ending is not None else None
        if heads is None:
            return ()
        return tuple((h.y, h.x, h.life) for h in heads.heads if h is not None)
    if NUCLEI:
        nuclei = play.ending.nuclei if play.ending is not None else None
        if nuclei is None:
            return ((),) * 6
        return tuple((p[0], p[3], p[5], p[6]) if p[0] else () for p in nuclei.pieces)
    if OBJECTS:
        assert play.objects is not None
        return _objects([(o.type, o.row, o.col) for o in play.objects.slots if o.type])
    shots = sorted((s.row, s.col) for s in play.shots.slots[0] if s is not None)
    alive = int(play.ship.exploding is None)
    turns = (play.turn, play.lives, play.other_lives) if PLAYERS == 2 else ()
    return (play.ship.row, play.ship.col, alive, play.scroll.distance, *turns, *shots)


#: 0x414B ("start the stage") loads the stage 0xE061 holds, after 0x4137 has
#: turned a 9-12 into the stage it leads to: a stage written there is the one
#: the game starts at, bonus stages included. The round (0xE06A) is written
#: there too, before 0x41AC reads it for the difficulty.
STAGE_READ = 0x414B


#: The interrupt: the sound driver's tick, then a game frame if none is
#: running (0x4028); 0x52B6 counts the game frame in as it starts.
INTERRUPT, COUNTER = 0x4028, 0xE003


def run_original(rom: str, script: list[tuple[int, int]], stage: int = 1,
                 machine: str = "C-BIOS_MSX1_EU", round_: int = 0, players: int = 1,
                 score: int = 0) -> tuple[dict[int, tuple[object, ...]], int, list[int]]:
    """The original's state after each game frame it was seen whole at, its
    frame counter (0xE003) when play was caught, and how many interrupts
    each game frame from there took."""
    states: dict[int, tuple[object, ...]] = {}
    with OpenMSX(rom, machine) as m:
        m.tcl("set ::nem_irq 0; set ::nem_starts {}")
        m.tcl("debug set_bp 0x%04X {} {incr ::nem_irq}" % INTERRUPT)
        m.tcl("debug set_watchpoint write_mem 0x%04X {} {lappend ::nem_starts $::nem_irq}"
              % COUNTER)
        m.tcl("set ::nem_requests {}")
        m.tcl("debug set_bp 0x%04X {} {lappend ::nem_requests [llength $::nem_starts] [reg A]}"
              % REQUEST)
        if stage != 1:
            m.tcl("debug set_bp 0x%04X {[debug read memory 0xE061] == 1} "
                  "{debug write memory 0xE061 %d}" % (STAGE_READ, stage))
        if round_:
            m.tcl("debug set_bp 0x%04X {[debug read memory 0xE06A] == 0} "
                  "{debug write memory 0xE06A %d}" % (STAGE_READ, round_))
        if score:
            # The score written as the stage is first loaded; 0x54AA has
            # cleared it by then.
            poke = "; ".join("debug write memory 0x%04X %d" % (0xE05C + n, b)
                             for n, b in enumerate(_to_bcd(score, 3)))
            m.tcl("debug set_bp 0x%04X {[debug read memory 0xE05E] == 0 && "
                  "[debug read memory 0xE05D] == 0} {%s}" % (STAGE_READ, poke))
        m.frames(500)
        if players == 2:
            # The title is up by now: a key other than a start turns the
            # choice (0x5540).
            m.tap("down")
        m.tap("space")
        m.frames(60)
        m.tap("space")
        # Until play: state 5 and the playing flag.
        while True:
            m.frames(1)
            ram = m.memory(0xE000, 0x480)
            if ram[0x00] == 5 and ram[0x5F] == 1:
                break
        counter = start = ram[0x03]
        m.tcl("set ::nem_starts {}; set ::nem_requests {}")
        tick = 0
        held = 0
        for frames, pad in script:
            for bit, key in KEY_OF.items():
                if pad & bit and not held & bit:
                    m.down(key)
                elif held & bit and not pad & bit:
                    m.up(key)
            held = pad
            end = tick + frames
            while tick < end:
                m.half_frame()
                ram = m.memory(0xE000, 0xFC0 if MAP else 0xC90)
                tick += (ram[0x03] - counter) & 0xFF
                counter = ram[0x03]
                # 0xE005 is the game frame's lock: set, a game frame is half
                # done and its state is not one the engine ever has.
                if not ram[0x05]:
                    states[tick - 1] = (_psg(m.psg_registers()) if PSG
                                        else (("finale",) if ram[0x1D1]
                                              else _screen_original(m) if ram[0x00] == 5
                                              else ("off",)) if SCREEN
                                        else original_state(ram))
        starts = [int(n) for n in m.tcl("set ::nem_starts").split()]
        if SOUNDS:
            # A request after the k-th start is game frame k - 1's.
            asked: dict[int, list[int]] = {}
            pairs = [int(n) for n in m.tcl("set ::nem_requests").split()]
            for frame, sound in zip(pairs[::2], pairs[1::2]):
                asked.setdefault(frame - 1, []).append(sound)
            # The last game frame may not have finished asking.
            states = {n: tuple(asked.get(n, ())) for n in range(tick - 1)}
    return states, start, [b - a for a, b in zip(starts, starts[1:])]


#: Where the ship's death is patched out for --immortal: "the ship has died" and
#: muere_la_nave, both in bank 1, both made a `ret`.
DEATHS = (0x75F0, 0x73E8)
RET = 0xC9


#: Every `ld a,r` in the cartridge (banks 0-3, which never page out of their
#: windows while these run): with --no-chance each becomes `xor a / nop`, R
#: reads 0, and the engine's chance answers 0 too.
READS_OF_R = (0x4750, 0x4CDA, 0x4CFF, 0x4D20, 0x4D28, 0x6685, 0x6B90, 0x6C9C, 0x713C,
              0x7E13, 0x811F, 0x8243, 0x846F, 0x8769, 0x8B06, 0xA453, 0xAAE6, 0xABC2,
              0xB016, 0xBC59, 0xBDBE, 0xBDF5)
LD_A_R, XOR_A_NOP = b"\xED\x5F", b"\xAF\x00"


class NoChance(random.Random):
    """The engine's R, read as 0 each time."""

    def randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:  # type: ignore[override]
        return 0 if stop is None else start

    def choice(self, seq):  # type: ignore[no-untyped-def]
        return seq[0]


def patched_rom(rom: str, scratch: str, immortal: bool, no_chance: bool) -> str:
    cart = Cartridge.from_file(rom)
    data = bytearray(cart.data)
    if immortal:
        for address in DEATHS:
            data[cart.offset(1, address)] = RET
    if no_chance:
        for address in READS_OF_R:
            at = cart.offset((address - 0x4000) >> 13, address)
            assert data[at:at + 2] == LD_A_R, hex(address)
            data[at:at + 2] = XOR_A_NOP
    path = os.path.join(scratch, "patched.rom")
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def run_engine(cart: Cartridge, script: list[tuple[int, int]], immortal: bool = False,
               stage: int = 1, counter: int = 1, round_: int = 0,
               no_chance: bool = False, durations: list[int] | None = None,
               players: int = 1, score: int = 0) -> list[tuple[object, ...]]:
    """With `durations`, the sound driver ticks as many times a game frame
    as the original's took: how long a game frame runs is the Z80's time,
    not a rule, and the music runs on interrupts."""
    play = Play(Stage(cart, stage), read_tables(cart), stages=lambda n: Stage(cart, n),
                start_round=round_, players=players, opening=True)
    # The core is drawn into the map, where shots and ship meet it.
    play.core_art = read_core_art(cart)
    play.score = score
    if no_chance:
        play.rng = NoChance()
        play.scroll.rng = play.rng
        if play.objects is not None:
            play.objects.rng = play.rng
    # The frame counter as the original's was: every "one game frame in N"
    # rule keys off it, and the original's depends on how long the title
    # was looked at.
    play.frames = (counter - 1) & 0xFF
    play.immortal = immortal
    # The original is caught once its playing flag is up, which is one game
    # frame into play: the same frame, with nothing pressed, here.
    # The sound driver too: the fades and the ending wait for its channel.
    driver = Driver(cart)
    music = Music(cart, driver)
    asked: list[int] = []
    request = driver.request

    def logged(sound: int) -> None:
        asked.append(sound)
        request(sound)
    driver.request = logged  # type: ignore[method-assign]
    # The game's ending after stage 8, driven as main.py drives it.
    finale: Finale | None = None
    screen = Screen()

    def step(pad: int, frame: int = -1) -> None:
        nonlocal finale
        play.channel_busy = bool(driver.playing(0))
        if pad & CONTINUE:
            play.ask_continue()
        play.step(pad & 0xFF)
        screen.step(play)
        sounds, interrupts = list(play.sounds), play.interrupts
        ending = play.ending
        if ending is not None and ending.finale and not ending.finale_done:
            if finale is None:
                finale = Finale(cart, play.rng, play.finales, Vram())
                play.finales += 1
            else:
                finale.update(play.channel_busy)
                play.add_score(finale.bonus)
                sounds += finale.sounds
                interrupts = finale.interrupts
                if finale.music_fade:
                    driver.start_fade()
                if finale.done:
                    ending.finale_done = True
                    finale = None
        if play.music is not None:
            music.update(*play.music, alive=True)
        if play.stage_built:
            music.reset()
        for sound in sounds:
            driver.request(sound)
        if durations is not None and 0 <= frame < len(durations):
            interrupts = durations[frame]
        for n in range(interrupts):
            if n == interrupts - 1:
                # The original is seen between its game frame's end and the
                # interrupt that starts the next: before the last tick.
                seen[:] = driver.regs
            driver.tick()
    seen = bytearray(16)
    # The play opens on state 4 (the curtain, the turn's label with two
    # players); the original is caught after it.
    while play.between is not None:
        step(0)
    play.frames = (counter - 1) & 0xFF
    step(0)
    states: list[tuple[object, ...]] = []
    for frames, pad in script:
        for _ in range(frames):
            asked.clear()
            step(pad, len(states))
            if SCREEN:
                ending = play.ending
                states.append(("finale",) if ending is not None and ending.finale
                              and not ending.finale_done
                              else ("off",) if play.ship.gone
                              else _screen_engine(play, screen, cart)
                              if play.sprites_on or play.stage_built else ("off",))
                continue
            if SOUNDS:
                states.append(tuple(asked))
                continue
            states.append(_psg(seen) if PSG else engine_state(play, finale))
    return states


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", required=True)
    parser.add_argument("--script", default=DEFAULT)
    parser.add_argument("--show", type=int, default=12, help="differences to print")
    parser.add_argument("--immortal", metavar="SCRATCH_DIR",
                        help="patch the ship's death out of a copy of the ROM in this "
                             "directory, and out of the engine")
    parser.add_argument("--no-chance", metavar="SCRATCH_DIR", dest="no_chance",
                        help="make R read 0 in a copy of the ROM in this directory, and "
                             "the engine's chance 0: the rules that roll dice, measured")
    parser.add_argument("--objects", action="store_true",
                        help="compare the twelve object slots instead of the ship")
    parser.add_argument("--pieces", action="store_true",
                        help="compare stage 5's background pieces and turrets")
    parser.add_argument("--nuclei", action="store_true",
                        help="compare stage 6's two nuclei instead of the ship")
    parser.add_argument("--heads", action="store_true",
                        help="compare stage 3's boss slots (0xE780) instead of the ship")
    parser.add_argument("--shots", action="store_true",
                        help="compare the ten enemy shots (0xE500) instead of the ship")
    parser.add_argument("--ship-sprites", dest="ship_sprites", action="store_true",
                        help="compare the ship's two sprite entries (0xEC80)")
    parser.add_argument("--finale", action="store_true",
                        help="compare the game's ending after stage 8 (0xE1D0): the ship "
                             "leaving, 0xE1D1's steps and the shrapnel")
    parser.add_argument("--sounds", action="store_true",
                        help="compare the sounds each game frame asks for (0x4A22)")
    parser.add_argument("--psg", action="store_true",
                        help="compare the PSG's registers: the sound driver's output")
    parser.add_argument("--sprites", action="store_true",
                        help="compare where the sprite table is sent from (0xE17F)")
    parser.add_argument("--screen", action="store_true",
                        help="compare what the VDP shows: the names (map and band), the "
                             "sprite table and the stars")
    parser.add_argument("--map", action="store_true",
                        help="compare the map buffer (0xED00) as each game frame leaves it")
    parser.add_argument("--band", action="store_true",
                        help="compare the score, the record, the ships and the next ship's "
                             "score")
    parser.add_argument("--score", type=int, default=0,
                        help="start with this score (its six digits, 0xE05C)")
    parser.add_argument("--players", type=int, default=1, choices=(1, 2),
                        help="a game of two players, taking turns")
    parser.add_argument("--round", type=int, default=0,
                        help="play this round (0xE06A): 1 is the second loop")
    parser.add_argument("--types", default="",
                        help="with --objects, only these types (hex, comma-separated)")
    parser.add_argument("--stage", type=int, default=1,
                        help="start the game at this stage")
    parser.add_argument("--from", dest="start", type=int, default=0,
                        help="compare from this game frame on")
    parser.add_argument("--machine", default="C-BIOS_MSX1_EU",
                        help="openMSX machine; C-BIOS_MSX1 is the 60 Hz one the engine's "
                             "rhythm is (two interrupts a game frame), and what sound "
                             "timings are measured on")
    parser.add_argument("--lag", type=int, default=0,
                        help="compare the original's game frame n + LAG with the engine's n "
                             "(on the 50 Hz machine stage 5's start is caught one late)")
    args = parser.parse_args()
    global OBJECTS, TYPES, NUCLEI, PIECES, HEADS, SHOTS, SPRITES, SHIP_SPRITES, FINALE
    FINALE = args.finale
    global PSG, SOUNDS, PLAYERS
    PSG, SOUNDS, PLAYERS = args.psg, args.sounds, args.players
    SPRITES, SHIP_SPRITES = args.sprites, args.ship_sprites
    global BAND, MAP, SCREEN
    BAND, MAP, SCREEN = args.band, args.map, args.screen
    OBJECTS, NUCLEI, PIECES = args.objects, args.nuclei, args.pieces
    HEADS, SHOTS = args.heads, args.shots
    TYPES = tuple(int(t, 16) for t in filter(None, args.types.split(",")))
    script = parse(args.script)
    scratch = args.immortal or args.no_chance
    rom = (patched_rom(args.rom, scratch, bool(args.immortal), bool(args.no_chance))
           if scratch else args.rom)
    theirs, counter, durations = run_original(rom, script, args.stage, args.machine, args.round,
                                              args.players, args.score)
    ours = run_engine(Cartridge.from_file(args.rom), script, bool(args.immortal), args.stage,
                      counter, args.round, bool(args.no_chance),
                      durations, args.players, args.score)
    theirs = {n - args.lag: state for n, state in theirs.items()}
    seen = [n for n in sorted(theirs) if args.start <= n < len(ours)]
    differ = [(n, theirs[n], ours[n]) for n in seen if theirs[n] != ours[n]]
    print("game frames compared: %d; differ: %d" % (len(seen), len(differ)))
    print("   frame  original (y, x, alive, distance, shots...)  |  engine")
    for n, t, o in differ[:args.show]:
        if SCREEN and len(t) == 4 and len(o) == 4:
            print("  %5d  %s" % (n, _screen_differences(t, o)))
            continue
        if MAP and isinstance(t[0], bytes) and isinstance(o[0], bytes):
            # Only the cells that differ: (row, column, original, engine).
            cells = [(at // MAP_COLUMNS, at % MAP_COLUMNS, a, b)
                     for at, (a, b) in enumerate(zip(t[0], o[0])) if a != b]
            print("  %5d  %s" % (n, ", ".join("(%d,%d) %02X/%02X" % c for c in cells[:8])))
            continue
        print("  %5d  %-45s  |  %s" % (n, t, o))
    return 0 if not differ else 1


if __name__ == "__main__":
    sys.exit(main())
