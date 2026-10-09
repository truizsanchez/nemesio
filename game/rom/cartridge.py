"""A Nemesis cartridge file, identified before anything is read from it.

128 KB with Konami's mapper **without** SCC: sixteen 8 KB banks. Bank 0 is fixed
at 0x4000; the others are paged into 0x6000, 0x8000 and 0xA000, and each bank
has exactly one window it is ever paged into (measured by the reference
disassembly on every mapper write), so an address and a bank name one byte.

Accepted only if it is the dump this code was written against -- checked by
SHA-1, the one thing that says "these addresses mean what this code thinks" --
and refused otherwise with a sentence that says which check failed. The release
is the same binary in Japan and Europe: the logo it shows is chosen at boot by
asking the BIOS which country the machine is.
"""

import hashlib
import os

SIZE = 0x20000
BANK = 0x2000
SHA1 = "e31ac6520e912c27ce96431a1dfb112bf71cb7b9"

#: Where each bank runs. 13, 14 and 15 are 0xFF end to end and nobody pages
#: them; they are given a window only so every bank has one.
WINDOW = {
    0: 0x4000,
    1: 0x6000, 4: 0x6000,
    2: 0x8000, 5: 0x8000, 7: 0x8000, 9: 0x8000, 11: 0x8000,
    3: 0xA000, 6: 0xA000, 8: 0xA000, 10: 0xA000, 12: 0xA000,
    13: 0x8000, 14: 0x8000, 15: 0x8000,
}

# The cartridge header: "AB", then INIT.
_HEADER = b"AB"


class NotTheCartridge(ValueError):
    """The file is not the Nemesis this game reads, and the message says why."""


class Cartridge:
    """The ROM's bytes, and reads of them by bank and address."""

    def __init__(self, data: bytes, check: bool = True) -> None:
        """`check` is off only for a test that builds a cartridge-shaped file."""
        if check:
            identify(data)
        self.data = bytes(data)

    @classmethod
    def from_file(cls, path: str) -> "Cartridge":
        with open(path, "rb") as handle:
            return cls(handle.read())

    def offset(self, bank: int, address: int) -> int:
        """Where in the file `address` is, with `bank` paged in."""
        base = WINDOW[bank]
        if not base <= address < base + BANK:
            raise ValueError("0x%04X is not in bank %d's window (0x%04X)"
                             % (address, bank, base))
        return bank * BANK + address - base

    def byte(self, bank: int, address: int) -> int:
        return self.data[self.offset(bank, address)]

    def word(self, bank: int, address: int) -> int:
        """Little-endian, as the Z80 stores a pointer."""
        return self.byte(bank, address) | self.byte(bank, address + 1) << 8

    def block(self, bank: int, address: int, size: int) -> bytes:
        at = self.offset(bank, address)
        return self.data[at:at + size]


class Paging:
    """Which bank is in each of the three switchable windows, as the cartridge
    sets them for one job -- the stage graphics, the map -- so that a pointer
    read out of a table resolves to the bank the running code would see."""

    def __init__(self, cart: Cartridge, banks: dict[int, int]) -> None:
        self.cart = cart
        self.banks = banks

    def bank(self, address: int) -> int:
        if address < 0x6000:
            return 0
        return self.banks[address & 0xE000]

    def byte(self, address: int) -> int:
        return self.cart.byte(self.bank(address), address)

    def word(self, address: int) -> int:
        return self.byte(address) | self.byte(address + 1) << 8


def identify(data: bytes) -> None:
    """Raise `NotTheCartridge` unless `data` is the Nemesis this game reads."""
    if len(data) != SIZE:
        raise NotTheCartridge(
            "a Nemesis ROM is %d bytes, and this file is %d" % (SIZE, len(data)))
    if data[:2] != _HEADER:
        raise NotTheCartridge("this file is not an MSX cartridge")
    if hashlib.sha1(data).hexdigest() != SHA1:
        raise NotTheCartridge(
            "this is not the Nemesis (RC-742) dump this game reads; its SHA-1 "
            "should be %s" % SHA1)


def find(folders: list[str]) -> str | None:
    """The first file in `folders` that is this Nemesis, whatever it is called.

    What lets a built executable start with no `--rom`: the player drops their
    dump beside it under any name (`nemesis.rom`, `Nemesis (Japan, Europe).mx1`)
    and it is known by its SHA-1, the one test `identify` already trusts. Only
    files of the right size are read, so a Downloads folder costs a listing.
    """
    for folder in folders:
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for name in names:
            path = os.path.join(folder, name)
            try:
                if not os.path.isfile(path) or os.path.getsize(path) != SIZE:
                    continue
                with open(path, "rb") as handle:
                    identify(handle.read())
            except (OSError, NotTheCartridge):
                continue
            return path
    return None
