"""A TMS9918 picture out of a VRAM dump: what the screen shows, as colour indexes.

The harness reads VRAM rather than asking openMSX for a screenshot because a
dump is exact and immediate -- openMSX's renderer only draws while running in
real time, and a screenshot of a paused machine is whatever it last drew.

Graphics II (SCREEN 2) and the sprites, which is all Nemesis uses. The table
bases come from the VDP registers, so the cartridge's upside-down VRAM map
(patterns 0x2000, colours 0x0000, names 0x3800, sprite attributes 0x3B00,
sprite patterns 0x1800 -- bank 0, 0x575A) is read as the VDP reads it, not as
the BIOS would have left it.
"""

import numpy as np

W, H = 256, 192

#: The TMS9918's sixteen colours, as openMSX draws them by default. 0 is
#: transparent: whatever is behind shows, down to the backdrop (register 7).
PALETTE = [
    (0x00, 0x00, 0x00), (0x00, 0x00, 0x00), (0x21, 0xC8, 0x42), (0x5E, 0xDC, 0x78),
    (0x54, 0x55, 0xED), (0x7D, 0x76, 0xFC), (0xD4, 0x52, 0x4D), (0x42, 0xEB, 0xF5),
    (0xFC, 0x55, 0x54), (0xFF, 0x79, 0x78), (0xD4, 0xC1, 0x54), (0xE6, 0xCE, 0x80),
    (0x21, 0xB0, 0x3B), (0xC9, 0x5B, 0xBA), (0xCC, 0xCC, 0xCC), (0xFF, 0xFF, 0xFF),
]

#: A sprite's Y of 208 ends the attribute table.
_END = 208
#: Four sprites on a line and the fifth is not drawn.
SPRITES_PER_LINE = 4


def tables(regs: list[int]) -> dict[str, int]:
    """Where Graphics II keeps each table, from registers 2-6."""
    return {
        "name": (regs[2] & 0x0F) << 10,
        "colour": (regs[3] & 0x80) << 6,
        "pattern": (regs[4] & 0x04) << 11,
        "attributes": (regs[5] & 0x7F) << 7,
        "sprite_pattern": (regs[6] & 0x07) << 11,
    }


def background(vram: bytes, regs: list[int]) -> np.ndarray:
    """The 256x192 of characters, backdrop where a colour is 0."""
    t = tables(regs)
    backdrop = regs[7] & 0x0F
    out = np.zeros((H, W), dtype=np.uint8)
    for row in range(24):
        third = (row // 8) * 0x800
        for col in range(32):
            char = vram[t["name"] + row * 32 + col]
            at = third + char * 8
            for y in range(8):
                bits = vram[t["pattern"] + at + y]
                colour = vram[t["colour"] + at + y]
                fg, bg = colour >> 4, colour & 0x0F
                for x in range(8):
                    c = fg if bits & (0x80 >> x) else bg
                    out[row * 8 + y, col * 8 + x] = c or backdrop
    return out


def sprites(vram: bytes, regs: list[int], out: np.ndarray) -> np.ndarray:
    """The sprites over `out`: the lower-numbered one wins a pixel, and only the
    first four sprites that touch a line are drawn on it."""
    t = tables(regs)
    size = 16 if regs[1] & 0x02 else 8
    scale = 2 if regs[1] & 0x01 else 1
    height = size * scale
    table = []
    for n in range(32):
        y, x, pattern, colour = vram[t["attributes"] + n * 4:t["attributes"] + n * 4 + 4]
        if y == _END:
            break
        top = (y + 1) & 0xFF
        if top > 0xE0:          # wraps: partly above the screen
            top -= 256
        if colour & 0x80:       # early clock: 32 pixels to the left
            x -= 32
        table.append((top, x, pattern & (0xFC if size == 16 else 0xFF), colour & 0x0F))
    drawn = np.zeros((H, W), dtype=bool)
    for sy in range(H):
        on_line = [s for s in table if s[0] <= sy < s[0] + height][:SPRITES_PER_LINE]
        for top, x, pattern, c in on_line:
            row = (sy - top) // scale
            base = t["sprite_pattern"] + pattern * 8 + row
            for dx in range(height):
                sx = x + dx
                if not 0 <= sx < W or drawn[sy, sx]:
                    continue
                col = dx // scale
                if vram[base + (16 if col >= 8 else 0)] & (0x80 >> (col & 7)):
                    drawn[sy, sx] = True
                    if c:
                        out[sy, sx] = c
    return out


def screen(vram: bytes, regs: list[int]) -> np.ndarray:
    """What the VDP shows: 256x192 colour indexes."""
    if not regs[1] & 0x40:      # display blanked
        return np.full((H, W), regs[7] & 0x0F, dtype=np.uint8)
    return sprites(vram, regs, background(vram, regs))


def rgb(indexes: np.ndarray) -> np.ndarray:
    return np.array(PALETTE, dtype=np.uint8)[indexes]


def save_png(indexes: np.ndarray, path: str, scale: int = 1) -> None:
    from PIL import Image
    image = Image.fromarray(rgb(indexes))
    if scale != 1:
        image = image.resize((W * scale, H * scale), Image.Resampling.NEAREST)
    image.save(path)
