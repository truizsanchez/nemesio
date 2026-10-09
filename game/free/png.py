"""PNG in and out with the standard library, in the TMS9918's sixteen colours.

The free assets are pictures anyone edits with any program, so a PNG is read
whatever it was saved as -- indexed, grey, RGB, with or without alpha, 8 bits
a channel or fewer for an indexed one -- and every pixel becomes the nearest
of the sixteen colours. A pixel with alpha under half is colour 0. They are
written back indexed, with the palette in the TMS9918's order, so an editor
shows index n as colour n.
"""

import struct
import zlib

#: The TMS9918's colours as `game/render/palette.py` gives them to Pyxel.
PALETTE = (
    0x000000, 0x000000, 0x21C842, 0x5EDC78, 0x5455ED, 0x7D76FC, 0xD4524D, 0x42EBF5,
    0xFC5554, 0xFF7978, 0xD4C154, 0xE6CE80, 0x21B03B, 0xC95BBA, 0xCCCCCC, 0xFFFFFF,
)
_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class Picture:
    """Colour indices (0-15), row by row."""

    def __init__(self, width: int, height: int, fill: int = 0) -> None:
        self.width, self.height = width, height
        self.pixels = bytearray([fill]) * (width * height)

    def __getitem__(self, at: tuple[int, int]) -> int:
        x, y = at
        return self.pixels[y * self.width + x]

    def __setitem__(self, at: tuple[int, int], colour: int) -> None:
        x, y = at
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = colour


def nearest(rgb: int) -> int:
    """The index of the nearest colour; black is 1, not the transparent 0."""
    r, g, b = rgb >> 16, rgb >> 8 & 0xFF, rgb & 0xFF
    best, index = None, 1
    for n, colour in enumerate(PALETTE):
        if n == 0:
            continue
        cr, cg, cb = colour >> 16, colour >> 8 & 0xFF, colour & 0xFF
        d = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if best is None or d < best:
            best, index = d, n
    return index


def _unfilter(data: bytes, width: int, height: int, bpp: int, row_bytes: int) -> list[bytearray]:
    rows, at, prior = [], 0, bytearray(row_bytes)
    for _ in range(height):
        kind = data[at]
        line = bytearray(data[at + 1:at + 1 + row_bytes])
        at += 1 + row_bytes
        for i in range(row_bytes):
            left = line[i - bpp] if i >= bpp else 0
            up = prior[i]
            corner = prior[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                pred = left if pa <= pb and pa <= pc else up if pb <= pc else corner
                line[i] = (line[i] + pred) & 0xFF
        rows.append(line)
        prior = line
    return rows


def read(path: str) -> Picture:
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != _SIGNATURE:
        raise ValueError("%s is not a PNG" % path)
    at, idat, palette, alphas = 8, bytearray(), [], b""
    width = height = depth = kind = 0
    while at < len(data):
        size, = struct.unpack(">I", data[at:at + 4])
        name, body = data[at + 4:at + 8], data[at + 8:at + 8 + size]
        at += 12 + size
        if name == b"IHDR":
            width, height, depth, kind, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if interlace:
                raise ValueError("%s: interlaced PNGs are not read" % path)
        elif name == b"PLTE":
            palette = [body[n] << 16 | body[n + 1] << 8 | body[n + 2] for n in range(0, len(body), 3)]
        elif name == b"tRNS":
            alphas = body
        elif name == b"IDAT":
            idat += body
        elif name == b"IEND":
            break
    if kind != 3 and depth != 8:
        raise ValueError("%s: only 8 bits a channel (or indexed) is read" % path)
    channels = _CHANNELS[kind]
    bits = depth * channels
    row_bytes = (width * bits + 7) // 8
    rows = _unfilter(zlib.decompress(bytes(idat)), width, height, max(bits // 8, 1), row_bytes)
    picture = Picture(width, height)
    cache: dict[tuple[int, int], int] = {}

    def colour(rgb: int, alpha: int) -> int:
        key = (rgb, alpha)
        if key not in cache:
            cache[key] = 0 if alpha < 128 else nearest(rgb)
        return cache[key]

    for y, line in enumerate(rows):
        for x in range(width):
            if kind == 3:
                per = 8 // depth
                value = line[x // per] >> (8 - depth * (x % per + 1)) & (1 << depth) - 1
                if palette == list(PALETTE[:len(palette)]) and value < 16:
                    # Written by `write`: the index is the colour, 0 included.
                    picture[x, y] = value
                    continue
                alpha = alphas[value] if value < len(alphas) else 255
                picture[x, y] = colour(palette[value], alpha)
            else:
                px = line[x * channels:(x + 1) * channels]
                if kind == 0:
                    rgb, alpha = px[0] * 0x010101, 255
                elif kind == 4:
                    rgb, alpha = px[0] * 0x010101, px[1]
                else:
                    rgb = px[0] << 16 | px[1] << 8 | px[2]
                    alpha = px[3] if kind == 6 else 255
                picture[x, y] = colour(rgb, alpha)
    return picture


def _chunk(name: bytes, body: bytes) -> bytes:
    return (struct.pack(">I", len(body)) + name + body
            + struct.pack(">I", zlib.crc32(name + body) & 0xFFFFFFFF))


def write(path: str, picture: Picture) -> None:
    """Indexed, 8 bits a pixel, the TMS9918's palette in order."""
    raw = bytearray()
    for y in range(picture.height):
        raw.append(0)
        raw += picture.pixels[y * picture.width:(y + 1) * picture.width]
    plte = b"".join(bytes((c >> 16, c >> 8 & 0xFF, c & 0xFF)) for c in PALETTE)
    with open(path, "wb") as handle:
        handle.write(_SIGNATURE)
        handle.write(_chunk(b"IHDR", struct.pack(">IIBBBBB", picture.width, picture.height,
                                                 8, 3, 0, 0, 0)))
        handle.write(_chunk(b"PLTE", plte))
        handle.write(_chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        handle.write(_chunk(b"IEND", b""))
