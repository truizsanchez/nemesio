"""The free assets' ending, once their last stage is over: a screen of their
own, what `game/finale.py` is for the cartridge's.

1. once the sound has stopped: the screen cleared, and a burst;
2. fireworks: bursts of eight sparks out of a point, one after another;
3. its words (text.json's "ending"), a letter at a time, then the bonus
   ("ending_bonus"), and the bonus paid;
4. a wait, and it is over: the title.

Its sparks are the blast's sprite patterns, in the play's pictures.
"""

from __future__ import annotations

import math
import random

from game.engine.layout import Layout
from game.engine.original import VIDEO_FRAMES_A_STEP
from game.free.texts import FreeMessages
from game.vdp import COLOURS, PATTERNS, THIRD, Vram

#: The letters' characters (the view's font, text.json's).
FONT = range(0x10, 0x3B)

#: The bonus, in BCD hundreds (50000).
BONUS = 500
#: A burst every 0x18 game frames, six of them; a spark lives 0x20 game
#: frames, at two pixels a game frame.
BURSTS, BURST_EVERY, SPARK_LIFE, SPARK_SPEED, SPARKS = 6, 0x18, 0x20, 2.0, 8
#: A letter every six game frames; the wait at the end.
LETTER_EVERY, LAST_WAIT = 6, 0x80
#: The sounds: a burst, a word written.
BURST_SOUND, WORD_SOUND = 0x3B, 0x14
SPARK_COLOURS = (9, 11, 7, 13, 15, 10)


class FreeFinale:
    def __init__(self, messages: FreeMessages, layout: Layout, rng: random.Random, round_: int,
                 vram: Vram, font: Vram) -> None:
        """`vram` is the play's as the fade left it, `font` a VRAM with the
        letters in its first third (the fade ate the play's)."""
        self.messages = messages
        self.font = font
        self.layout = layout
        self.rng = rng
        self.vram = vram
        self.names = bytearray(768)
        # One ending whatever the round: the game ends after it (round_ is
        # the cartridge's finale's, which has a word for each).
        self.words = ["ending", "ending_bonus"]
        self.step = 1
        self.clock = 0
        self.bursts = 0
        #: [row, column, row speed, column speed, life, colour]
        self.sparks: list[list[float]] = []
        self.letters: list[tuple[int, int]] = []
        self.border = 0
        self.loaded = False
        self.sounds: list[int] = []
        self.music_fade = False
        self.bonus = 0
        self.done = False
        self.interrupts = VIDEO_FRAMES_A_STEP

    def update(self, busy: bool) -> None:
        self.sounds, self.bonus, self.loaded = [], 0, False
        self._sparks()
        if self.step == 1:
            if busy:
                return
            self.names[:] = bytes(768)
            # The letters into all three thirds, as the title has them.
            for third in range(3):
                for table in (PATTERNS, COLOURS):
                    at = table + FONT.start * 8
                    size = len(FONT) * 8
                    self.vram.data[at + third * THIRD:at + third * THIRD + size] = \
                        self.font.data[at:at + size]
            self.loaded = True
            self.step, self.clock = 2, 1
        elif self.step == 2:
            if self.bursts == BURSTS:
                if not self.sparks:
                    self.step = 3
                    self._next_word()
                return
            self.clock -= 1
            if self.clock:
                return
            self.bursts += 1
            self.clock = BURST_EVERY
            self._burst()
        elif self.step == 3:
            self.clock -= 1
            if self.clock:
                return
            self.clock = LETTER_EVERY
            if self.letters:
                at, char = self.letters.pop(0)
                self.names[at] = char
                return
            self.sounds.append(WORD_SOUND)
            if self.words:
                self._next_word()
                return
            self.bonus = BONUS
            self.step, self.clock = 4, LAST_WAIT
        elif self.step == 4:
            self.clock -= 1
            if not self.clock:
                self.done = True

    def _next_word(self) -> None:
        name = self.words.pop(0)
        for at, chars in self.messages.messages.get(name, []):
            self.letters += [(at + n, c) for n, c in enumerate(chars) if at + n < len(self.names)]
        self.clock = LETTER_EVERY

    def _burst(self) -> None:
        row = self.rng.randrange(0x18, 0x90)
        col = self.rng.randrange(0x30, 0xD0)
        colour = SPARK_COLOURS[self.bursts % len(SPARK_COLOURS)]
        for n in range(SPARKS):
            a = n * 2 * math.pi / SPARKS
            self.sparks.append([row, col, SPARK_SPEED * math.sin(a), SPARK_SPEED * math.cos(a),
                                SPARK_LIFE, colour])
        self.sounds.append(BURST_SOUND)

    def _sparks(self) -> None:
        for spark in self.sparks:
            spark[0] += spark[2]
            spark[1] += spark[3]
            spark[4] -= 1
        self.sparks = [s for s in self.sparks if s[4] > 0 and 0 <= s[0] < 0xB0 and 0 <= s[1] < 0xF0]

    def sprites(self) -> list[tuple[int, int, int, int]]:
        """(row, column, pattern, colour): a spark shrinks through the
        blast's four drawings."""
        out = []
        for row, col, _, _, life, colour in self.sparks:
            step = 3 - int(life) * 4 // (SPARK_LIFE + 1)
            out.append((int(row), int(col), self.layout.blast_pattern + 4 * step, int(colour)))
        return out
