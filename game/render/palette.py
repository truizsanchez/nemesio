"""The TMS9918's sixteen colours as Pyxel's palette, index for index.

Colour 0 is the VDP's transparent: over nothing but the backdrop, and the
backdrop in play is black (register 7's low nibble is 0), so it is drawn
black here.
"""

import pyxel

TMS9918 = [
    0x000000, 0x000000, 0x21C842, 0x5EDC78, 0x5455ED, 0x7D76FC, 0xD4524D, 0x42EBF5,
    0xFC5554, 0xFF7978, 0xD4C154, 0xE6CE80, 0x21B03B, 0xC95BBA, 0xCCCCCC, 0xFFFFFF,
]


def apply() -> None:
    pyxel.colors[:] = TMS9918
