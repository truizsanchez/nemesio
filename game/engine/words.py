"""The words typed with the game paused (bank 0, 0x50C9).

While paused every new key goes into 0xE1E8, eight at most; RETURN compares
what was typed with the cartridge's words (0x51BF) -- a word matches if what
was typed starts with it -- and clears it either way. HYPER, once a game,
gives everything at once (0xA0D8); the name of the stage's girl (0x5163:
MOMOKO for stage 1 ... YOHKO for 12) does the same, once a stage; MISSILE,
LASER, SHIELD, DOUBLE, OPTION give one thing each, and DOWN takes the speed
back -- one of those a stage too, and not after the name (0xE071). BAKA and
AHO, idiot and fool, end the game (0x5127).
"""

from __future__ import annotations

from dataclasses import dataclass, field

TYPED_MAX = 8
RETURN = 0x0D


@dataclass
class Keyboard:
    """0xE1E0, 0xE1E1 and 0xE1E8."""

    words: dict[str, str]
    names: tuple[str, ...]
    typed: list[str] = field(default_factory=list)

    def clear(self) -> None:
        """0x50B4."""
        self.typed = []

    def key(self, letter: str) -> str | None:
        """A new key down; on RETURN, the word it made (its effect's name),
        if any."""
        if letter != "\r":
            if len(self.typed) < TYPED_MAX:
                self.typed.append(letter)
            return None
        typed = "".join(self.typed)
        self.clear()
        for word in ("HYPER", "BAKA", "AHO"):
            if typed.startswith(self.words[word]):
                return word
        return typed

    def matches(self, typed: str, word: str) -> bool:
        return typed.startswith(self.words[word])

    def name(self, typed: str, stage: int) -> bool:
        """0x5157: the girl's name of this stage."""
        return 1 <= stage <= len(self.names) and typed.startswith(self.names[stage - 1])
