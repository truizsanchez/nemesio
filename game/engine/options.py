"""The options: up to two, trailing the ship.

Bank 2, 0x9BFB ("set up an option") and 0x9C41 ("run the options"). Each option
keeps a queue of eight positions (16 bytes at 0xE230 / 0xE250). A game frame
the pad moves the ship -- any direction but none, or a pair of opposites --
the newest position goes in at one end and the option takes the oldest from
the other: the first option follows the ship, the second the first.
"""

from collections import deque

from game.engine.original import DOWN, LEFT, OPTION_DRAWINGS, RIGHT, UP

QUEUE = 8
MAX_OPTIONS = 2
#: The drawings an option blinks through (the cartridge's; `Options` is
#: handed the layout's).
DRAWINGS = OPTION_DRAWINGS
_STILL = (0, UP | DOWN, LEFT | RIGHT, UP | DOWN | LEFT | RIGHT)


class Option:
    def __init__(self, row: int, col: int,
                 drawing: tuple[int, int] = DRAWINGS[0]) -> None:
        self.row, self.col = row, col
        #: 0x9C39: eight pushes of the position it starts at.
        self.queue: deque[tuple[int, int]] = deque([(row, col)] * QUEUE, maxlen=QUEUE)
        self.pattern, self.colour = drawing


class Options:
    def __init__(self, drawings: tuple[tuple[int, int], ...] = DRAWINGS) -> None:
        #: The four (pattern, colour) they blink through: the layout's.
        self.drawings = drawings
        self.options: list[Option] = []
        #: 0xE182, 0xE183: the drawing's clock.
        self.tick = 0
        self.drawing = 0

    def add(self, ship_row: int, ship_col: int) -> None:
        """0xA146 / 0x9BFB: the new one where the ship (or the first option)
        is."""
        if len(self.options) >= MAX_OPTIONS:
            return
        if self.options:
            leader = self.options[-1]
            self.options.append(Option(leader.row, leader.col, self.drawings[0]))
        else:
            self.options.append(Option(ship_row, ship_col, self.drawings[0]))

    def place(self, row: int, col: int) -> None:
        """0x4CB8: each option and all eight of its queue at one place."""
        for option in self.options:
            option.row, option.col = row, col
            option.queue.extend([(row, col)] * QUEUE)

    def step(self, pad: int, ship_row: int, ship_col: int) -> None:
        """0x9C41."""
        if not self.options:
            return
        self._animate()
        if pad & (UP | DOWN | LEFT | RIGHT) in _STILL:
            return
        leader = (ship_row, ship_col)
        for option in self.options:
            option.row, option.col = option.queue[0]
            option.queue.append(leader)
            leader = (option.row, option.col)

    def _animate(self) -> None:
        """0x9C90: every other frame, the next of four drawings."""
        self.tick += 1
        if self.tick < 2:
            return
        self.tick = 0
        self.drawing += 1
        for option in self.options:
            option.pattern, option.colour = self.drawings[self.drawing & 3]
