"""The free game's music, composed here: a tune a stage and a jingle for
GAME OVER, all of it the generator's own.

A stage's tune is eight bars on a progression of four chords, a bar each
twice over, in its key and mode: channel A a melody -- a walk over the
chord's notes and the scale's, in rhythms of a bar each, landing on the
tonic -- and channel B a bass of roots and fifths in eighths, two octaves
down. Both last the same and loop for ever; channel C is the effects'.
Steps are game/free/cart.py's melody steps.
"""

import random
from dataclasses import dataclass
from typing import Any

from game.free.cart import NOTE_NAMES

SCALES = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10),
          "dorian": (0, 2, 3, 5, 7, 9, 10), "phrygian": (0, 1, 3, 5, 7, 8, 10)}
#: Progressions, as scale degrees (0 the tonic).
PROGRESSIONS = ((0, 5, 3, 4), (0, 3, 4, 0), (0, 6, 5, 4), (0, 4, 5, 3), (0, 2, 3, 4))
#: The melody's rhythms, a bar (eight eighths) each.
RHYTHMS = ((2, 2, 2, 2), (1, 1, 2, 2, 2), (2, 1, 1, 2, 2), (3, 1, 2, 2), (4, 2, 2), (2, 2, 4),
           (1, 1, 1, 1, 2, 2))
#: The driver's octaves: 0 the highest (C5-B5), each one down an octave.
MELODY_OCTAVE, BASS_OCTAVE = 1, 3


@dataclass
class Theme:
    key: int
    mode: str
    #: Game frames (interrupts) an eighth lasts.
    beat: int
    seed: int


#: A stage's tune: the free game's one stage.
THEMES = {1: Theme(0, "major", 7, 11)}
#: The tunes' sound numbers: two channels (0x16-0x25), so channel C stays the
#: effects'; requested with bit 7, a melody.
TUNES = {stage: 0x16 + 2 * (stage - 1) for stage in THEMES}
GAME_OVER = 0x4A
MELODY = 0x80


def _note(theme: Theme, degree: int, octave: int) -> tuple[str, int]:
    """A scale degree (may go past seven) as a note name and a driver octave."""
    scale = SCALES[theme.mode]
    semitone = theme.key + scale[degree % 7] + 12 * (degree // 7)
    return NOTE_NAMES[semitone % 12], octave - semitone // 12


def _steps(notes: list[tuple[str, int, int]], beat: int, volume: int, decay: tuple[int, int],
           repeat: bool = True) -> list[list[Any]]:
    out: list[list[Any]] = [["beat", beat], ["voice", volume, *decay]]
    octave = None
    for name, oct_, beats in notes:
        if name != "-" and oct_ != octave:
            out.append(["octave", oct_])
            octave = oct_
        out.append([name, beats])
    if repeat:
        out.append(["repeat"])
    return out


def tune(theme: Theme) -> list[list[list[Any]]]:
    rng = random.Random(theme.seed)
    progression = rng.choice(PROGRESSIONS)
    chords = [c for c in progression for _ in range(2)]
    melody: list[tuple[str, int, int]] = []
    degree = 7
    for bar, chord in enumerate(chords):
        rhythm = (8,) if bar == len(chords) - 1 else rng.choice(RHYTHMS)
        tones = [chord + t for t in (0, 2, 4, 7)]
        for n, beats in enumerate(rhythm):
            if bar == len(chords) - 1:
                degree = 7
            elif n == 0 or rng.random() < 0.5:
                degree = min(tones, key=lambda t: abs(t + (7 if t < 5 else 0) - degree))
                degree += 7 if degree < 5 else 0
            else:
                degree = max(3, min(12, degree + rng.choice((-2, -1, 1, 2))))
            if rng.random() < 0.08 and n:
                melody.append(("-", 0, beats))
                continue
            name, octave = _note(theme, degree, MELODY_OCTAVE + 1)
            melody.append((name, octave, beats))
    bass: list[tuple[str, int, int]] = []
    for chord in chords:
        for n in range(4):
            name, octave = _note(theme, chord + (4 if n % 2 else 0), BASS_OCTAVE)
            bass.append((name, octave, 2))
    return [_steps(melody, theme.beat, 11, (1, 6)), _steps(bass, theme.beat, 9, (1, 4))]


def game_over() -> list[list[list[Any]]]:
    """Three channels falling to the tonic of A minor, once."""
    theme = Theme(9, "minor", 8, 0)
    lines = ((7, 6, 5, 4, 2, 0), (4, 3, 2, 1, -1, -3), (0, -3, -2, -4, -5, -7))
    out = []
    for n, line in enumerate(lines):
        notes = []
        for k, degree in enumerate(line):
            name, octave = _note(theme, degree + 7, MELODY_OCTAVE + n + 1)
            notes.append((name, octave, 2 if k < len(line) - 1 else 8))
        out.append(_steps(notes, 8, 11 - n, (2, 5), repeat=False))
    return out


def music() -> dict[str, object]:
    """sounds.json's "music" and "stage_music"."""
    tunes: dict[str, object] = {hex(TUNES[stage]): tune(theme) for stage, theme in THEMES.items()}
    tunes[hex(GAME_OVER)] = game_over()
    return {"music": tunes,
            "stage_music": {str(stage): [["0xffff", hex(MELODY | number)]]
                            for stage, number in TUNES.items()}}
