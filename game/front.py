"""The screens around a play, as a model: which is up and for how long.

Bank 0's states (0x52B3): the title with its blinking cursor (states 0-2),
the chosen line blinking (state 3), the play (4-5), and GAME OVER with
CONTINUE (state 7); and, with nobody at the keys, the Konami logo, the
picture and the demo, round and round (states 0 and 2) -- what they show is
game/attract.py's and the host's.
"""

from enum import Enum

#: State 3 (0x537D), an interrupt a video frame: a frame to set 0xE004 to
#: 0x50, 0x50 of the chosen line blinking with its bit 2, and the start of
#: the game (0x5558), which runs into a second interrupt; then the play.
#: Measured: 84 interrupts from the start to state 4.
CHOSEN_FRAMES, CHOSEN_COUNT, CHOSEN_BIT = 84, 0x50, 0x04
#: The title's cursor blinks with bit 3 of 0xE004 counting down from 0x100
#: (0x5BD6).
TITLE_BIT = 0x08
#: The title waits 256 video frames for a start before the picture (0x5308).
TITLE_FRAMES = 0x100
#: The screens that go round by themselves (states 0 and 2).
ATTRACT = ("logo", "picture", "demo")


class Screen(Enum):
    LOGO = "logo"
    TITLE = "title"
    PICTURE = "picture"
    DEMO = "demo"
    CHOSEN = "chosen"
    PLAY = "play"
    OVER = "over"


class Front:
    def __init__(self, attract: bool = True) -> None:
        #: Without the attract screens (the free assets have none), the title
        #: waits for a start as long as it takes.
        self.attract = attract
        self.screen = Screen.LOGO if attract else Screen.TITLE
        self.frames = 0
        #: 0xE052: 0 one player, 1 two (the second is not played yet).
        self.choice = 0

    def update(self, start: bool, down: bool, up: bool) -> None:
        self.frames += 1
        if self.screen.value in ATTRACT:
            if start:
                self._to(Screen.TITLE)
            return
        if self.screen is Screen.TITLE:
            if self.attract and self.frames >= TITLE_FRAMES and not start:
                self._to(Screen.PICTURE)
                return
            if down:
                self.choice = 1
            if up:
                self.choice = 0
            if start:
                self._to(Screen.CHOSEN)
        elif self.screen is Screen.CHOSEN:
            if self.frames >= CHOSEN_FRAMES:
                self._to(Screen.PLAY)

    def attract_over(self) -> None:
        """The host's screen has run out: the logo to the title, the picture
        to the demo, the demo round to the logo."""
        following = {Screen.LOGO: Screen.TITLE, Screen.PICTURE: Screen.DEMO,
                     Screen.DEMO: Screen.LOGO}
        self._to(following[self.screen])

    def over(self) -> None:
        self._to(Screen.OVER)

    def finish(self) -> None:
        """GAME OVER's tune has played and nobody goes on (0x54CF)."""
        self._to(Screen.TITLE)

    def to_play(self) -> None:
        self._to(Screen.PLAY)

    def _to(self, screen: Screen) -> None:
        self.screen = screen
        self.frames = 0

    @property
    def lit(self) -> bool:
        """The blink's cell: shown or not -- 0xE004's bit, as it counts
        down."""
        if self.screen is Screen.CHOSEN:
            count = CHOSEN_COUNT + 1 - self.frames
            return count > CHOSEN_COUNT or count <= 0 or not count & CHOSEN_BIT
        return bool(-self.frames & TITLE_BIT)
