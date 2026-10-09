"""How much of the cartridge this game cites and reads, bank by bank.

    python tools/rom_map.py [--listing ../Nemesis-disassembly] [--json out.json]
                            [--rom <nemesis.rom>]

The reference listing explains every byte of the cartridge: traced code, or a
data range with a name (its `D` directives). This measures the other side:
which of those routines and ranges `game/` names by address, which is how the
engine says "this rule is that code". A routine counts as cited when any
address inside it is; a data range the same. Nothing here reads the ROM: the
listing's `;xxxx` column and the `.notes` files give the layout, and `game/`'s
text the citations.

An address of 0x6000-0xBFFF names a byte only with its bank. The bank comes, in
this order, from "bank N" or "pNN:" written just before it on the same line;
from a `..._BANKS = {0x8000: N, ...}` map in the same file; or from the window's
code bank (1, 2, 3). The first of those where the address falls on an
instruction, a label or inside a data range wins; one that fits none of them is
reported as loose rather than guessed. RAM (0xC000 up) is counted apart.

With `--rom`, a second measure: which bytes the game actually reads out of the
player's cartridge -- every stage's map and graphics, the tables, the screens,
the demo's recordings, the finale in every round, every sound played out. The
cartridge is read through a reader that notes each offset; what comes out is
counts, not bytes.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK_SIZE = 0x2000
BANKS = 16
#: Where each bank runs (the listing's tools/paginas.py; 13-15 are never paged).
WINDOW = {0: 0x4000, 1: 0x6000, 4: 0x6000,
          2: 0x8000, 5: 0x8000, 7: 0x8000, 9: 0x8000, 11: 0x8000,
          3: 0xA000, 6: 0xA000, 8: 0xA000, 10: 0xA000, 12: 0xA000,
          13: 0x8000, 14: 0x8000, 15: 0x8000}
#: The bank the code runs with in each window during play.
CODE_BANK = {0x4000: 0, 0x6000: 1, 0x8000: 2, 0xA000: 3}
#: The sound table at 0x8328 of bank 7, 80 words (it ends at 0x83C8); its
#: streams run on into bank 8, up to 0xA3DE, the empty sound.
SOUND_TABLE, SOUND_WORDS, SOUND_END = 0x8328, 80, 0xA3DE

LABEL = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*):(?!\s*equ\b)")
CODE_LINE = re.compile(r"^\t(?!def[bws])\S.*;([0-9a-f]{4})\b")
DATA_LINE = re.compile(r"^\tdef[bws]\b.*;\s*([0-9a-f]{4})\b")
ADDRESS = re.compile(r"\b0x([0-9A-Fa-f]{4})\b")
NAMED_BANK = re.compile(r"(?:\bbank\s+(\d{1,2})\b|\bp(\d\d):)[^.;]{0,40}$", re.I)
BANK_MAP = re.compile(r"_BANKS\s*=\s*\{([^}]*)\}")
BANK_PAIR = re.compile(r"0x([0-9A-Fa-f]{4})\s*:\s*(\d{1,2})")
CALL = re.compile(r"^\tcall\s+(?:(?:n?[zc]|p[oe]?|m),)?([A-Za-z_][A-Za-z_0-9]*)")
DISPATCHED = re.compile(r"->\s+(.*)$")


@dataclass
class Unit:
    """A routine (a label to the next) or a data range, in one bank."""
    bank: int
    start: int
    end: int
    name: str
    kind: str  # "code" or "data"
    size: int = 0   # bytes; a data range's that are not also code
    cited: bool = False

    @property
    def filler(self) -> bool:
        """The listing names its 0xFF tails and empty banks "relleno"."""
        return self.kind == "data" and self.name.startswith("relleno")


@dataclass
class Bank:
    number: int
    code: set[int] = field(default_factory=set)      # instruction starts
    code_bytes: set[int] = field(default_factory=set)  # every byte of them
    units: list[Unit] = field(default_factory=list)
    #: Routines in the coarser sense: from an entry (a `call`'s target, a
    #: dispatcher table's, or one of the listing's .entries) to the next.
    routines: list[Unit] = field(default_factory=list)

    def fits(self, address: int) -> bool:
        """Whether `address` is an instruction, a label or inside a data range."""
        if address in self.code:
            return True
        return any(u.start <= address < u.end for u in self.units
                   if u.kind == "data" or u.start == address)

    def unit_at(self, address: int) -> "Unit | None":
        for u in self.units:
            if u.start <= address < u.end:
                return u
        return None


def parse_notes(text: str) -> list[tuple[int, int, str]]:
    """The `D start end name ...` ranges of a .notes file (end exclusive)."""
    out = []
    for line in text.splitlines():
        if line.startswith("D "):
            parts = line.split(None, 4)
            out.append((int(parts[1], 0), int(parts[2], 0), parts[3]))
    return out


def parse_entries(text: str) -> set[int]:
    """The addresses of a .entries file, one to a line before its comment."""
    out = set()
    for line in text.splitlines():
        word = line.split("#")[0].strip()
        if word:
            out.add(int(word, 0))
    return out


def parse_bank(number: int, asm: str, notes: str, entries: str = "") -> Bank:
    """A bank's code, labels and routines out of its listing, its data ranges
    out of its notes."""
    bank = Bank(number)
    end_of_bank = WINDOW[number] + BANK_SIZE
    positions: list[tuple[int, str]] = []   # (address, "code"/"data")
    labels: list[tuple[int, str]] = []
    pending: list[str] = []
    called: set[str] = set()
    for line in asm.splitlines():
        m = CALL.match(line)
        if m:
            called.add(m.group(1))
        m = DISPATCHED.search(line)
        if m and line.startswith("\tdefw"):
            called.update(m.group(1).split())
        m = LABEL.match(line)
        if m:
            pending.append(m.group(1))
            continue
        m = CODE_LINE.match(line)
        kind = "code"
        if not m:
            m, kind = DATA_LINE.match(line), "data"
        if not m:
            continue
        at = int(m.group(1), 16)
        positions.append((at, kind))
        labels.extend((at, name) for name in pending)
        pending = []
    positions.sort()
    for i, (at, kind) in enumerate(positions):
        if kind == "code":
            bank.code.add(at)
            nxt = positions[i + 1][0] if i + 1 < len(positions) else end_of_bank
            bank.code_bytes.update(range(at, nxt))
    # routines: from a label on code to the next label, over code only
    code_labels = sorted({at for at, _ in labels if at in bank.code})
    names = {at: name for at, name in reversed(labels)}
    for i, at in enumerate(code_labels):
        end = code_labels[i + 1] if i + 1 < len(code_labels) else end_of_bank
        bank.units.append(Unit(number, at, end, names[at], "code"))
    for start, end, name in parse_notes(notes):
        size = sum(1 for a in range(start, end) if a not in bank.code_bytes)
        bank.units.append(Unit(number, start, end, name, "data", size=size))
    # a label's span can run into data after its last instruction: code bytes
    # are counted by instruction, so a routine's size is clipped to its code
    for u in bank.units:
        if u.kind == "code":
            u.end = min([u.end] + [d.start for d in bank.units
                                   if d.kind == "data" and u.start < d.start < u.end])
            u.size = sum(1 for a in range(u.start, u.end) if a in bank.code_bytes)
    starts = sorted(({at for at, name in labels if name in called} | parse_entries(entries))
                    & bank.code)
    for i, at in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else end_of_bank
        size = sum(1 for a in range(at, end) if a in bank.code_bytes)
        bank.routines.append(Unit(number, at, end, names.get(at, "0x%04X" % at), "code", size))
    return bank


def load_listing(path: str) -> dict[int, Bank]:
    banks = {}
    for n in range(BANKS):
        with open(os.path.join(path, "src", "nemesis_p%02d.asm" % n), encoding="utf-8") as f:
            asm = f.read()
        side = []
        for kind in ("notes", "entries"):
            side_path = os.path.join(path, "src", "p%02d.%s" % (n, kind))
            text = ""
            if os.path.exists(side_path):
                with open(side_path, encoding="utf-8") as f:
                    text = f.read()
            side.append(text)
        banks[n] = parse_bank(n, asm, side[0], side[1])
    return banks


@dataclass
class Citation:
    address: int
    where: str      # file:line
    candidates: list[int]


def citations(text: str, where: str) -> list[Citation]:
    """Every ROM address in `text` with the banks it may be, most likely first."""
    file_map = {}
    for m in BANK_MAP.finditer(text):
        for window, bank in BANK_PAIR.findall(m.group(1)):
            file_map[int(window, 16)] = int(bank)
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in ADDRESS.finditer(line):
            address = int(m.group(1), 16)
            if not 0x4000 <= address < 0xC000:
                continue
            window = address & 0xE000
            candidates = []
            named = NAMED_BANK.search(line[:m.start()])
            if named:
                n = int(named.group(1) or named.group(2))
                if WINDOW.get(n) == window:
                    candidates.append(n)
            if window in file_map:
                candidates.append(file_map[window])
            candidates.append(CODE_BANK[window])
            candidates += [b for b, w in sorted(WINDOW.items()) if w == window]
            seen: list[int] = []
            for b in candidates:
                if b not in seen:
                    seen.append(b)
            out.append(Citation(address, "%s:%d" % (where, lineno), seen))
    return out


def ram_citations(text: str) -> set[int]:
    return {int(a, 16) for a in ADDRESS.findall(text) if int(a, 16) >= 0xC000}


def game_sources() -> list[str]:
    out = []
    for base, _, files in os.walk(os.path.join(ROOT, "game")):
        out += [os.path.join(base, f) for f in files if f.endswith(".py")]
    return sorted(out)


def measure(banks: dict[int, Bank], sources: list[str]) -> dict[str, object]:
    loose = []
    ram: set[int] = set()
    for path in sources:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        ram |= ram_citations(text)
        for c in citations(text, os.path.relpath(path, ROOT)):
            chosen = next((b for b in c.candidates if banks[b].fits(c.address)), None)
            if chosen is None and len(c.candidates) == 1:
                chosen = c.candidates[0]     # bank 0's: inside an instruction
            if chosen is None:
                loose.append(c)
                continue
            unit = banks[chosen].unit_at(c.address)
            if unit is not None and not unit.filler:
                unit.cited = True
            for r in banks[chosen].routines:
                if r.start <= c.address < r.end:
                    r.cited = True
    rows = []
    for n, bank in banks.items():
        code = [u for u in bank.units if u.kind == "code"]
        data = [u for u in bank.units if u.kind == "data"]
        filler = sum(u.size for u in data if u.filler)
        rows.append({
            "bank": n,
            "window": WINDOW[n],
            "code_bytes": len(bank.code_bytes),
            "routines": len(code),
            "routines_cited": sum(u.cited for u in code),
            "code_bytes_cited": sum(u.size for u in code if u.cited),
            "entries": len(bank.routines),
            "entries_cited": sum(r.cited for r in bank.routines),
            "entry_bytes_cited": sum(r.size for r in bank.routines if r.cited),
            "data_bytes": sum(u.size for u in data),
            "data_ranges": len(data),
            "data_ranges_cited": sum(u.cited for u in data),
            "data_bytes_cited": sum(u.size for u in data if u.cited),
            "filler_bytes": filler,
        })
    return {
        "banks": rows,
        "loose": [{"address": "0x%04X" % c.address, "where": c.where,
                   "banks": c.candidates} for c in loose],
        "ram": ["0x%04X" % a for a in sorted(ram)],
    }


class Reads:
    """The offsets a `Cartridge` has been asked for."""

    def __init__(self) -> None:
        self.offsets: set[int] = set()


def read_everything(path: str) -> set[int]:
    """Load and play out everything the game takes from the cartridge."""
    import random
    sys.path.insert(0, ROOT)
    from game.attract import Logo, Picture, demo_pad
    from game.finale import Finale, ROUNDS
    from game.rom import graphics, screens
    from game.rom.band import RomMessages
    from game.rom.cartridge import Cartridge, Paging
    from game.rom.sound import CARDS, MELODY, NOTES, SOUND_BANKS, Driver
    from game.rom.stage import Stage
    from game.rom.tables import core_art, keyboard, read
    from game.vdp import Vram, NAMES

    reads = Reads()

    class Tracking(Cartridge):
        def byte(self, bank: int, address: int) -> int:
            reads.offsets.add(self.offset(bank, address))
            return super().byte(bank, address)

        def block(self, bank: int, address: int, size: int) -> bytes:
            at = self.offset(bank, address)
            reads.offsets.update(range(at, at + size))
            return super().block(bank, address, size)

    with open(path, "rb") as f:
        cart = Tracking(f.read())
    read(cart)
    core_art(cart)
    keyboard(cart)
    for number in range(1, 13):
        stage = Stage(cart, number)
        for distance in range(0, stage.limit + 0x40):
            stage.column(distance)
            stage.star_row(distance)
        graphics.load_play(cart, number, Vram())
    graphics.load_boss(cart, Vram())
    for number in range(1, 9):
        demo_pad(cart, number)
    for japanese in (False, True):
        title = screens.title(cart, japanese)
    messages = RomMessages(cart)
    screens.game_over(messages)
    for line in (screens.ONE_PLAYER, screens.TWO_PLAYERS):
        screens.blank_message(messages, line, bytearray(768))
    for name in RomMessages.STREAMS:
        messages.write(name, bytearray(768))
    rng = random.Random(0)
    logo = Logo(cart)
    while not logo.done:
        logo.update()
    picture = Picture(cart, rng, bytes(title.data[NAMES:NAMES + 768]))
    for _ in range(0x4000):
        if picture.done:
            break
        picture.update(False)
    for round_ in range(ROUNDS):
        for japanese in (False, True):
            finale = Finale(cart, rng, round_, Vram(), japanese)
            for _ in range(0x4000):
                if finale.done:
                    break
                finale.update(False)
    # The table at 0x8328 (bank 7) holds 80 words; sound 0 is not one. Bit 7
    # of a request says how its streams are read (a melody or an effect), and
    # the game asks for some of each above 0x16 (0x38 and 0x41 plain, 0xA6 and
    # 0xCA melodies), so each word is tried both ways. A run counts only if
    # it read nothing but the driver's tables and its own streams (from each
    # of its words to the next stream up); one that runs off them, or off the
    # banks, was read the wrong way.
    sound_banks = Paging(cart, SOUND_BANKS)
    starts = sorted({cart.word(7, SOUND_TABLE + 2 * n) for n in range(1, SOUND_WORDS)}
                    | {SOUND_END})

    def stream(at: int) -> set[int]:
        end = next((s for s in starts if s > at), SOUND_END)
        return {cart.offset(sound_banks.bank(a), a) for a in range(at, end)}

    for number in range(1, SOUND_WORDS):
        for sound in (number, number | MELODY):
            before = set(reads.offsets)
            reads.offsets = set()
            driver = Driver(cart)
            kept = False
            try:
                driver.request(sound)
                words = [cart.word(7, SOUND_TABLE + 2 * n)
                         for n in range(number, min(number + CARDS, SOUND_WORDS))]
                # the notes' periods, which a melody's high notes read on
                # into the table's first word, and the table itself
                table = {cart.offset(7, a)
                         for a in range(NOTES, SOUND_TABLE + 2 * SOUND_WORDS)}
                for _ in range(0x2000):
                    driver.tick()
                    if not any(driver.playing(card) for card in range(CARDS)):
                        break
                own = set().union(*(stream(w) for w in words if w in starts))
                kept = reads.offsets <= own | table
            except (KeyError, ValueError):
                pass
            reads.offsets = before | reads.offsets if kept else before
    return reads.offsets


def reads_by_bank(banks: dict[int, Bank], offsets: set[int]) -> list[dict[str, object]]:
    """Per bank, the data bytes read; and used, which is read or inside a
    range the code cites (a dispatcher's table, the pad's speeds: the engine
    carries those as its own code and constants, with the address)."""
    rows: list[dict[str, object]] = []
    for n, bank in banks.items():
        data = [u for u in bank.units if u.kind == "data" and not u.filler]
        mine = {WINDOW[n] + o - n * BANK_SIZE for o in offsets
                if n * BANK_SIZE <= o < (n + 1) * BANK_SIZE}
        read = used = 0
        unused = []
        for u in data:
            left = 0
            for a in range(u.start, u.end):
                if a in bank.code_bytes:
                    continue
                read += a in mine
                if a in mine or u.cited:
                    used += 1
                else:
                    left += 1
            if left:
                unused.append({"name": u.name, "at": "0x%04X" % u.start, "bytes": left})
        rows.append({"bank": n, "data_bytes": sum(u.size for u in data),
                     "data_bytes_read": read, "data_bytes_used": used, "unused": unused})
    return rows


def pct(a: int, b: int) -> str:
    return "%5.1f %%" % (100.0 * a / b) if b else "    -  "


def report(result: dict[str, object]) -> None:
    rows = result["banks"]
    assert isinstance(rows, list)
    print("  bank  window   code B    labels  cited   code cited |  data B  ranges cited"
          "  data cited (w/o filler)")
    tot = dict.fromkeys(("code_bytes", "code_bytes_cited", "routines", "routines_cited",
                         "entries", "entries_cited", "entry_bytes_cited",
                         "data_bytes", "data_bytes_cited", "filler_bytes"), 0)
    for r in rows:
        for k in tot:
            tot[k] += r[k]
        print("  %4d  0x%04X %7d  %8d  %5d  %s  | %6d  %6d %5d  %s"
              % (r["bank"], r["window"], r["code_bytes"], r["routines"], r["routines_cited"],
                 pct(r["code_bytes_cited"], r["code_bytes"]), r["data_bytes"],
                 r["data_ranges"], r["data_ranges_cited"],
                 pct(r["data_bytes_cited"], r["data_bytes"] - r["filler_bytes"])))
    print("  " + "-" * 96)
    print("  code:  %d bytes; by label (a label to the next): %d; cited %d, %d bytes (%s)"
          % (tot["code_bytes"], tot["routines"], tot["routines_cited"],
             tot["code_bytes_cited"], pct(tot["code_bytes_cited"], tot["code_bytes"]).strip()))
    print("         by routine (an entry to the next): %d routines; cited %d, %d bytes (%s)"
          % (tot["entries"], tot["entries_cited"], tot["entry_bytes_cited"],
             pct(tot["entry_bytes_cited"], tot["code_bytes"]).strip()))
    print("  data:  %d bytes (%d of them 0xFF filler); cited %d bytes (%s of the non-filler)"
          % (tot["data_bytes"], tot["filler_bytes"], tot["data_bytes_cited"],
             pct(tot["data_bytes_cited"], tot["data_bytes"] - tot["filler_bytes"]).strip()))
    loose = result["loose"]
    ram = result["ram"]
    assert isinstance(loose, list) and isinstance(ram, list)
    print("  RAM:   %d addresses cited" % len(ram))
    print("  loose: %d citations fit no bank's instruction, label or range" % len(loose))
    for c in loose:
        print("    %s  %-40s banks tried %s" % (c["address"], c["where"], c["banks"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--listing", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "Nemesis-disassembly"))
    parser.add_argument("--json", help="write the measure here as well")
    parser.add_argument("--rom", help="also measure what the game reads out of it")
    args = parser.parse_args()
    banks = load_listing(args.listing)
    result = measure(banks, game_sources())
    report(result)
    if args.rom:
        rows = reads_by_bank(banks, read_everything(args.rom))
        result["reads"] = rows
        print()
        print("  bank   data B (w/o filler)      read       used (read or cited)")
        tot = [0, 0, 0]
        for r in rows:
            d, rd, u = (int(str(r[k])) for k in ("data_bytes", "data_bytes_read",
                                                 "data_bytes_used"))
            tot = [tot[0] + d, tot[1] + rd, tot[2] + u]
            print("  %4s   %8d   %8d %s   %8d %s" % (r["bank"], d, rd, pct(rd, d), u, pct(u, d)))
        print("  data: %d non-filler bytes; read %d (%s), used %d (%s)"
              % (tot[0], tot[1], pct(tot[1], tot[0]).strip(), tot[2],
                 pct(tot[2], tot[0]).strip()))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
