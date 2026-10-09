"""The free assets' sounds as a cartridge-shaped image, in memory.

The sound driver (`game/rom/sound.py`) runs on its data by bank and address,
and its format -- a stream of steps of tone or noise -- is a good one to
write effects in. So the free effects are written where the driver reads
them: a 128 KB image with nothing but them in it, never a cartridge and never
saved.

- `sounds.json`: the effects ("sounds") and the tunes ("music", melodies),
  in the driver's own stream formats, behind its table of sounds (0x8328),
  and the notes' periods; every sound not given is silence;
- per stage, which tune until which distance ("stage_music", 0x7056).
"""

import json
import os
from typing import Any

from game.free.numbers import num
from game.rom import sound
from game.rom.cartridge import BANK, SIZE, WINDOW, Cartridge

#: Where the sounds' streams go: after the table, up to the end of bank 8.
SOUNDS_COUNT = 0x82
STREAMS_FROM, STREAMS_END = 0x8500, 0xC000
_END = 0xFF
#: A sound's stream: 0x2X starts a step (bit 1 tone, bit 0 noise, 0x20 a
#: rest) with its length; 0x1N the noise's period; then the volume in the
#: high nibble and the period's twelve bits.
_STEP, _NOISE = 0x20, 0x10
_TONE_BIT, _NOISE_BIT = 2, 1
#: The music's list: until distance 0xFFFF, nothing.
MUSIC_AT = 0x7100


class Image:
    """A blank 128 KB image to write by bank and address."""

    def __init__(self) -> None:
        self.data = bytearray(SIZE)
        self.data[:2] = b"AB"

    def put(self, bank: int, address: int, values: bytes | list[int]) -> None:
        at = bank * BANK + address - WINDOW[bank]
        self.data[at:at + len(values)] = bytes(values)

    def word(self, bank: int, address: int, value: int) -> None:
        self.put(bank, address, [value & 0xFF, value >> 8 & 0xFF])

    def cartridge(self) -> Cartridge:
        return Cartridge(bytes(self.data), check=False)


#: What a step's numbers can be: game frames, volume, period, and the noise's
#: period as the PSG takes it (register 6) -- the driver keeps its half, so
#: an odd one sounds as the even one under it.
FRAMES, VOLUMES, PERIODS, NOISES = range(1, 0x100), range(0x10), range(0x1000), range(0x20)
KINDS = {"tone": _TONE_BIT, "noise": _NOISE_BIT, "both": _TONE_BIT | _NOISE_BIT}


def encode_sound(steps: list[Any]) -> list[int]:
    """A stream from steps: ["rest", frames] or [kind, frames, volume,
    period, noise period], kind "tone", "noise" or "both". Raises
    ValueError, saying which step, on one it cannot write."""
    out: list[int] = []
    for n, step in enumerate(steps):
        if not isinstance(step, list) or not step:
            raise ValueError("step %d is not a list" % (n + 1))
        kind = step[0]
        if kind != "rest" and kind not in KINDS:
            raise ValueError("step %d: %r is not rest, tone, noise or both" % (n + 1, kind))
        if len(step) < (2 if kind == "rest" else 4):
            raise ValueError("step %d is short: %r" % (n + 1, step))

        def value(at: int, allowed: range, what: str, step: list[Any] = step, n: int = n) -> int:
            got = num(step[at])
            if got not in allowed:
                raise ValueError("step %d: the %s is %d, and it goes from %d to %d"
                                 % (n + 1, what, got, allowed.start, allowed.stop - 1))
            return got
        frames = value(1, FRAMES, "length in game frames")
        if kind == "rest":
            out += [_STEP, frames]
            continue
        flags = KINDS[kind]
        volume, period = value(2, VOLUMES, "volume"), value(3, PERIODS, "period")
        noise = value(4, NOISES, "noise period") if len(step) > 4 else 0
        out += [_STEP | flags, frames]
        if flags & _NOISE_BIT or volume == 1:
            # A volume of 1 would read as the noise's command: give it one.
            out.append(_NOISE | noise >> 1)
        out += [volume << 4 | period >> 8, period & 0xFF]
    out.append(_END)
    return out


#: A melody: 0xDn a beat of n game frames; 0xFv then a byte, the volume
#: (v + 2) and when it decays (high nibble) down to what (low); 0xEo the
#: octave (each one down doubles the period); a note, its number in the high
#: nibble (12 a rest) and its beats less one in the low; 0xFE times and an
#: address, a loop (times 0, for ever); 0xFF the end.
_BEAT, _VOICE, _OCTAVE, _LOOP = 0xD0, 0xF0, 0xE0, 0xFE
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
REST = "-"
#: The twelve notes' periods at the highest octave (C5 to B5 on the MSX's
#: PSG, 1789772.5 / 16 / the note's frequency).
NOTE_PERIODS = (214, 202, 190, 180, 170, 160, 151, 143, 135, 127, 120, 113)


def encode_melody(steps: list[Any], at: int) -> list[int]:
    """A melody's stream from steps: ["beat", frames], ["voice", volume,
    decay start, decay floor], ["octave", n], [note, beats] -- a note C to B
    (C#...) or "-", a rest -- and ["repeat"], back to the start for ever.
    `at` is where the stream goes (the loop's address)."""
    out: list[int] = []
    for n, step in enumerate(steps):
        what = step[0]

        def value(k: int, allowed: range, name: str, step: list[Any] = step, n: int = n) -> int:
            got = num(step[k])
            if got not in allowed:
                raise ValueError("step %d: the %s is %d, and it goes from %d to %d"
                                 % (n + 1, name, got, allowed.start, allowed.stop - 1))
            return got
        if what == "beat":
            out.append(_BEAT | value(1, range(1, 0x10), "beat"))
        elif what == "voice":
            out += [_VOICE | value(1, range(0x0E), "volume"),
                    value(2, range(0x10), "decay's start") << 4 | value(3, range(0x10), "decay's floor")]
        elif what == "octave":
            out.append(_OCTAVE | value(1, range(8), "octave"))
        elif what == "repeat":
            out += [_LOOP, 0, at & 0xFF, at >> 8]
            return out
        elif what in NOTE_NAMES or what == REST:
            note = NOTE_NAMES.index(what) if what != REST else sound.REST
            out.append(note << 4 | value(1, range(1, 0x11), "beats") - 1)
        else:
            raise ValueError("step %d: %r is not beat, voice, octave, repeat, a note or -"
                             % (n + 1, what))
    out.append(_END)
    return out


def write_sounds(image: Image, spec: dict[str, Any]) -> None:
    at = STREAMS_FROM
    silence = at
    image.put(7, at, [_END])
    at += 1
    entries = [silence] * SOUNDS_COUNT
    for section, melody in (("sounds", False), ("music", True)):
        for key, channels in spec.get(section, {}).items():
            number = num(key)
            if not 0 < number < 0x80:
                raise ValueError("sounds.json's %s is not a sound (1 to 0x7F)" % key)
            wanted = 1 if number < sound.TWO_FROM else 2 if number < sound.THREE_FROM else 3
            if len(channels) != wanted:
                raise ValueError("sounds.json's %s plays on %d channels, not %d"
                                 % (key, wanted, len(channels)))
            for n, steps in enumerate(channels):
                size = len(encode_melody(steps, 0) if melody else encode_sound(steps))
                if at < WINDOW[8] <= at + size:
                    # A stream does not straddle the two banks' windows.
                    at = WINDOW[8]
                if at + size > STREAMS_END:
                    raise ValueError("sounds.json is too long")
                try:
                    data = encode_melody(steps, at) if melody else encode_sound(steps)
                except ValueError as error:
                    raise ValueError("sounds.json's %s, %s, channel %d, %s"
                                     % (section, key, n + 1, error))
                image.put(7 if at < WINDOW[8] else 8, at, data)
                entries[number + n] = at
                at += len(data)
    # Notes 10 and 11 are the first entry's two bytes, as the cartridge's
    # table runs into it: there is no sound 0.
    entries[0] = NOTE_PERIODS[10] | NOTE_PERIODS[11] << 8
    for n, entry in enumerate(entries):
        image.word(7, sound.SOUNDS + 2 * n, entry)
    image.put(7, sound.NOTES, list(NOTE_PERIODS[:10]))
    periods = [num(p) for p in spec.get("pause_periods", [0x40, 0x50, 0x60, 0x70])]
    image.put(7, sound.PAUSE_PERIODS, periods[:4])


def write_music(image: Image, spec: dict[str, Any]) -> None:
    """Per stage, [until distance, tune] rows (the tune with bit 7, a
    melody); a stage not given has silence."""
    lists = spec.get("stage_music", {})
    at = MUSIC_AT
    image.put(1, at, [0xFF, 0xFF, sound.SILENCE])
    silence = at
    at += 3
    for stage in range(13):
        rows = lists.get(str(stage))
        if not rows:
            image.word(1, sound.MUSIC_LISTS + 2 * stage, silence)
            continue
        image.word(1, sound.MUSIC_LISTS + 2 * stage, at)
        for until, tune in rows:
            image.put(1, at, [num(until) & 0xFF, num(until) >> 8, num(tune)])
            at += 3


def build(folder: str) -> Cartridge:
    image = Image()
    with open(os.path.join(folder, "sounds.json")) as handle:
        spec = json.load(handle)
    write_sounds(image, spec)
    write_music(image, spec)
    return image.cartridge()
