"""A blank 128 KB cartridge a test writes a few bytes into."""

from game.rom.cartridge import SIZE, Cartridge, WINDOW, BANK


class Blank:
    def __init__(self) -> None:
        self.data = bytearray(SIZE)
        self.data[:2] = b"AB"

    def put(self, bank: int, address: int, values: bytes | list[int]) -> None:
        at = bank * BANK + address - WINDOW[bank]
        self.data[at:at + len(values)] = bytes(values)

    def word(self, bank: int, address: int, value: int) -> None:
        self.put(bank, address, [value & 0xFF, value >> 8])

    def cartridge(self) -> Cartridge:
        return Cartridge(bytes(self.data), check=False)
