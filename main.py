"""nemesio: Nemesis (Konami, MSX, 1986), rule for rule, in Pyxel.

    python main.py --rom <nemesis.rom>              play, from stage 1
    python main.py                                  ...with the ROM found beside it
    python main.py --rom <nemesis.rom> --stage 4    ...from another stage
    python main.py --rom <nemesis.rom> --selftest   a minute of play, no window
    python main.py --free                           the free assets, no cartridge
    python main.py --check-assets [folder]          the free assets checked, no window
    python main.py --rom <nemesis.rom> --shot out.png --steps 600 [--pad-script right+fire]

The keys: the arrows (or WASD) move, SPACE or K fires, M, N or J takes the
power-up. Esc quits.
"""

import argparse
import os
import random
import sys

import pyxel

from game.engine.original import DOWN, FIRE, LEFT, POWER, RIGHT, UP, VIDEO_FRAMES_A_STEP
from game.engine import fade
from game.attract import BACKDROP, DEMO_UNTIL, Logo, Picture, demo_pad
from game.engine.play import CURTAIN_ROWS, Phase, Play
from game.front import Front, Screen
from game.screen import Screen as PlayScreen
from game.screen import names as screen_names
from game.render.audio import Audio
from game.content import Content, FinaleLike, RomContent
from game.free.check import check
from game.free.content import FreeContent, assets_folder
from game.rom.sound import Driver, Music
from game.rom import screens
from game.rom.band import TURN_LABELS, write_band
from game.rom.cartridge import Cartridge, NotTheCartridge, find
from game.render import palette, vdp_draw
from game.vdp import HEIGHT, NAMES, WIDTH, Vram

#: The title's cursor: the ship of the font (0x581D) at row 17, column 10,
#: or two rows down for two players (0x5BDD).
TITLE_CURSOR = 17 * 32 + 10
TITLE_CURSOR_CHARACTERS = bytes((0x1B, 0x1C))

KEYS = (
    (UP, (pyxel.KEY_UP, pyxel.KEY_W)),
    (DOWN, (pyxel.KEY_DOWN, pyxel.KEY_S)),
    (LEFT, (pyxel.KEY_LEFT, pyxel.KEY_A)),
    (RIGHT, (pyxel.KEY_RIGHT, pyxel.KEY_D)),
    (FIRE, (pyxel.KEY_SPACE, pyxel.KEY_K)),
    (POWER, (pyxel.KEY_M, pyxel.KEY_N, pyxel.KEY_J)),
)
BAND_ROW, BAND_ROWS = 22, 2
PAD_NAMES = {"up": UP, "down": DOWN, "left": LEFT, "right": RIGHT, "fire": FIRE,
             "power": POWER}


#: The keys the words are typed with, and what they type (RETURN ends one).
TYPED = [(getattr(pyxel, "KEY_" + c), c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
TYPED.append((pyxel.KEY_RETURN, "\r"))


def read_pad() -> int:
    pad = 0
    for bit, keys in KEYS:
        if any(pyxel.btn(key) for key in keys):
            pad |= bit
    return pad




class Game:
    """What is on screen: one stage's play, drawn from the content's art."""

    def __init__(self, content: Content, stage: int, players: int = 1,
                 opening: bool = False) -> None:
        self.content = content
        self.cart = content.cart
        self.stage_number = stage
        self.players = players
        #: From the title: the play opens on state 4 (a demo does not).
        self.opening = opening
        self.band = bytearray(32 * 24)
        #: The record: the best score this session (0xE053), kept across games.
        self.record = 0
        self.tables = content.tables()
        self.core_art = content.core_art()
        self.frame = 0
        #: Video frames to the next game frame, and whether this one stepped.
        self.wait = VIDEO_FRAMES_A_STEP
        self.stepped = False
        #: The game's ending, while it plays; and its asking the music out.
        self.finale: FinaleLike | None = None
        self.music_fade = False
        #: The game's end after its last stage (content that ends there).
        self.closing = False
        self.new_game()

    def new_game(self) -> None:
        self.play = Play(self.content.stage(self.stage_number), self.tables,
                         stages=self.content.stage, players=self.players,
                         opening=self.opening)
        self.play.core_art = self.core_art
        self.play.keyboard = self.content.keyboard()
        #: What the VDP holds of the play: the sprites a game frame behind,
        #: the band's scores as last written.
        self.screen = PlayScreen()
        self._reload(self.stage_number)


    def _reload(self, stage: int) -> None:
        """A stage's characters into VRAM and Pyxel's image (0x422A)."""
        self.vram = Vram()
        self.content.load_play(stage, self.vram)
        vdp_draw.load(self.vram)

    def update(self, pad: int) -> list[int]:
        """A video frame; on the ones that step the play, the sounds that
        step asked for. A game frame lasts as many video frames as it took
        the original: two, or more when it moved much VRAM."""
        self.frame += 1
        self.wait -= 1
        self.stepped = self.wait <= 0
        if self.stepped:
            play = self.play
            if self.closing:
                return self._closing(play)
            round_ = play.round
            play.step(pad)
            self.screen.step(play)
            self.wait = play.interrupts
            if play.new_stage:
                play.new_stage = False
                if play.round > round_ and self.content.ends_after_last:
                    # The last stage is over (the free assets'): not round
                    # to the first, but the ending and the title.
                    self._close(play)
                    return []
                self._reload(play.terrain.number)
            if play.boss_art:
                play.boss_art = False
                self.content.load_boss(self.vram)
                vdp_draw.load(self.vram)
            if play.vram_writes:
                # 0xA6C0: the screen going dark, eaten out of the VRAM.
                fade.apply(self.vram.data, play.vram_writes)
                vdp_draw.load(self.vram)
            return list(play.sounds) + self._finale(play)
        return []

    def _close(self, play: Play) -> None:
        """The game's end after its last stage: the music out, the ending."""
        vram = Vram()
        vram.data[:] = self.vram.data
        self.finale = self.content.make_finale(play.rng, play.finales, vram)
        self.closing = True
        self.music_fade = True
        play.music = None

    def _closing(self, play: Play) -> list[int]:
        """The ending's steps; once over, the play is (the title follows)."""
        finale = self.finale
        assert finale is not None
        self.music_fade = False
        finale.update(play.channel_busy)
        if finale.loaded:
            vdp_draw.load(finale.vram)
        play.add_score(finale.bonus)
        self.wait = finale.interrupts
        if finale.done:
            play.phase = Phase.FINISHED
        return finale.sounds

    def _finale(self, play: Play) -> list[int]:
        """0x4AC0's steps 1-9, once the engine has let the ship go."""
        ending = play.ending
        self.music_fade = False
        if ending is None or not ending.finale or ending.finale_done:
            return []
        if not self.content.finale:
            # Content with no ending of its own after stage 8: the game goes
            # on, round after round.
            ending.finale_done = True
            return []
        if self.finale is None:
            # The game frame that lets the ship go ends there (0x4AFA); the
            # finale's first step is the next one's.
            vram = Vram()
            vram.data[:] = self.vram.data
            self.finale = self.content.make_finale(play.rng, play.finales, vram)
            play.finales += 1
            return []
        finale = self.finale
        finale.update(play.channel_busy)
        if finale.loaded:
            vdp_draw.load(finale.vram)
        play.add_score(finale.bonus)
        self.music_fade = finale.music_fade
        self.wait = finale.interrupts
        if finale.done:
            ending.finale_done = True
            self.finale = None
        return finale.sounds

    def draw(self) -> None:
        play = self.play
        if self.finale is not None:
            finale = self.finale
            vdp_draw.put_names(finale.names)
            pyxel.cls(finale.border)
            vdp_draw.draw_screen(backdrop=True)
            for row, col, pattern, colour in reversed(finale.sprites()):
                vdp_draw.draw_sprite(row, col, pattern, colour)
            return
        names = bytearray(screen_names(play))
        vdp_draw.put_names(names)
        if self.screen.stars is not None:
            for character, bits in zip(play.layout.stars, self.screen.stars):
                vdp_draw.set_pattern_row(self.vram, character, 0, bits)
        self.record = max(self.record, play.record)
        curtain = (play.between.curtain if play.between is not None
                   else play.over.curtain if play.over is not None else 0)
        if curtain:
            # 0x558A: the curtain blanks the 22 rows a column a tick.
            for row in range(CURTAIN_ROWS):
                names[row * 32:row * 32 + curtain] = bytes(curtain)
            vdp_draw.put_names(names)
        if play.intro:
            self.content.messages.write(TURN_LABELS[play.turn], names)
            vdp_draw.put_names(names)
        write_band(self.content.messages, self.band, play.lives, play.taken(), play.meter,
                   self.screen.score, self.screen.record, play.turn)
        vdp_draw.put_names(self.band[BAND_ROW * 32:], BAND_ROW)
        pyxel.cls(0)
        vdp_draw.draw_screen()
        if not play.sprites_on:
            # 0x55AA: and no sprites.
            return
        vdp_draw.draw_sprite_table(self.screen.sprites)

class App:
    """The window: the front end around the play."""

    def __init__(self, content: Content, stage: int, headless: bool = False) -> None:
        if headless:
            pyxel.init(WIDTH, HEIGHT, headless=True)
        else:
            pyxel.init(WIDTH, HEIGHT, title="nemesio", fps=60)
        palette.apply()
        self.content = content
        cart = self.cart = content.cart
        self.stage = stage
        self.front = Front(attract=content.attract)
        self.title_vram = content.title()
        self.over_names = screens.game_over(content.messages)
        self.game: Game | None = None
        self.loaded = ""
        self.paused = False
        self.record = 0
        #: The logo or the picture, and the demo, while they run.
        self.attract: Logo | Picture | None = None
        self.demo: Game | None = None
        self.demo_pad: list[int] = []
        self.demo_step = 0
        #: 0xE006: which stage the next demo shows.
        self.demo_stage = 0
        self.rng = random.Random()
        self.driver = Driver(cart)
        self.music = Music(cart, self.driver)
        self.audio = Audio(self.driver)

    def run(self) -> None:
        pyxel.run(self.update, self.draw)

    def update(self) -> None:
        front = self.front
        start = any(pyxel.btnp(k) for k in (pyxel.KEY_RETURN, pyxel.KEY_SPACE, pyxel.KEY_K))
        front.update(start, pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S),
                     pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W))
        if front.screen in (Screen.LOGO, Screen.PICTURE, Screen.DEMO):
            self._attract()
        elif self.attract is not None or self.demo is not None:
            self.attract = self.demo = None
            self.driver.silence()
        if front.screen is Screen.PLAY or (front.screen is Screen.OVER
                                           and self.game is not None):
            if self.game is None:
                self.game = Game(self.content, self.stage, players=2 if front.choice else 1,
                                 opening=True)
                self.game.record = self.game.play.record = self.record
                self.loaded = "play"
            play = self.game.play
            if front.screen is Screen.PLAY and pyxel.btnp(pyxel.KEY_F1):
                # 0x44E7: F1 pauses; the driver plays its pause and holds.
                self.paused = not self.paused
                self.driver.pause(self.paused)
                if self.paused and play.keyboard is not None:
                    play.keyboard.clear()
            if self.paused:
                # 0x50C9: the words, typed while paused.
                for key, letter in TYPED:
                    if pyxel.btnp(key):
                        play.type_key(letter)
            else:
                if pyxel.btn(pyxel.KEY_F5):
                    # 0x54F3: CONTINUE, listened for while GAME OVER waits.
                    play.ask_continue()
                self._step(self.game)
            # State 7 is the engine's: GAME OVER until its tune has played,
            # then the play again (CONTINUE, the other player) or the title.
            phase = self.game.play.phase
            if phase is Phase.OVER and front.screen is Screen.PLAY:
                front.over()
            elif phase is Phase.PLAYING and front.screen is Screen.OVER:
                front.to_play()
            elif phase is Phase.FINISHED:
                front.finish()
        elif front.screen is Screen.TITLE:
            if self.game is not None:
                self.record = self.game.record
            self.game = None
        self.audio.tick()

    def _attract(self) -> None:
        """States 0 and 2: the logo, the picture, the demo."""
        front = self.front
        if front.screen is Screen.LOGO:
            if not isinstance(self.attract, Logo):
                self.attract = Logo(self.cart)
                self.loaded = ""
            self.attract.update()
            if self.attract.done:
                self.attract = None
                front.attract_over()
        elif front.screen is Screen.PICTURE:
            if not isinstance(self.attract, Picture):
                self.attract = Picture(self.cart, self.rng, bytes(
                    self.title_vram.data[NAMES:NAMES + 768]))
                self.loaded = ""
            picture = self.attract
            picture.update(bool(self.driver.playing(0)))
            for sound in picture.sounds:
                self.driver.request(sound)
            if picture.loaded:
                self.loaded = ""
            if picture.done:
                self.attract = None
                front.attract_over()
        else:
            if self.demo is None:
                # 0x5C88: the next stage's recording, with everything HYPER gives.
                stage = max(self.demo_stage, 1)
                self.demo_stage = self.demo_stage + 1 if self.demo_stage < 8 else 1
                self.demo = Game(self.content, stage)
                self.demo.play._everything()
                # No game on (0xE002 bit 6): no ships in reserve, nothing scored.
                self.demo.play.lives = 0
                self.demo_pad = demo_pad(self.cart, stage)
                self.demo_step = 0
                self.loaded = ""
            demo = self.demo
            pad = self.demo_pad[min(self.demo_step, len(self.demo_pad) - 1)]
            self._step(demo, pad)
            if demo.stepped:
                self.demo_step += 1
                demo.play.score = 0
            if demo.play.scroll.distance >= DEMO_UNTIL or demo.play.phase is not Phase.PLAYING:
                self.demo = None
                self.driver.silence()
                front.attract_over()

    def _step(self, game: "Game", pad: int | None = None) -> None:
        play = game.play
        play.channel_busy = bool(self.driver.playing(0))
        sounds = game.update(read_pad() if pad is None else pad)
        if game.stepped and play.music is not None:
            # 0x7003 looks at the music early in the game frame, before
            # the frame's sounds are asked for.
            self.music.update(*play.music, alive=True)
        if game.stepped and play.stage_built:
            self.music.reset()
        for sound in sounds:
            self.driver.request(sound)
        if game.music_fade:
            self.driver.start_fade()

    def draw(self) -> None:
        front = self.front
        attract = self.attract
        if front.screen in (Screen.LOGO, Screen.PICTURE) and attract is not None:
            if self.loaded != "attract":
                vdp_draw.load(attract.vram)
                self.loaded = "attract"
            vdp_draw.put_names(attract.names)
            if isinstance(attract, Logo):
                pyxel.cls(BACKDROP)
                vdp_draw.draw_screen(backdrop=True)
                return
            pyxel.cls(0)
            vdp_draw.draw_screen()
            for row, col, pattern, colour in reversed(attract.sprites()):
                vdp_draw.draw_sprite(row, col, pattern, colour)
            return
        if front.screen is Screen.DEMO:
            if self.demo is not None:
                if self.loaded != "demo":
                    vdp_draw.load(self.demo.vram)
                    self.loaded = "demo"
                self.demo.draw()
            return
        between = self.game.play.between if self.game is not None else None
        opening = (front.screen is Screen.PLAY and between is not None and between.opening
                   and not between.loaded)
        if front.screen in (Screen.TITLE, Screen.CHOSEN) or opening:
            if self.loaded != "title":
                vdp_draw.load(self.title_vram)
                self.loaded = "title"
            names = bytearray(self.title_vram.data[NAMES:NAMES + 768])
            cursor = TITLE_CURSOR + 64 * front.choice
            chosen_line = screens.TWO_PLAYERS if front.choice else screens.ONE_PLAYER
            if front.screen is Screen.TITLE:
                if front.lit:
                    names[cursor:cursor + 2] = TITLE_CURSOR_CHARACTERS
            else:
                names[cursor:cursor + 2] = TITLE_CURSOR_CHARACTERS
                if front.screen is Screen.CHOSEN and not front.lit:
                    screens.blank_message(self.content.messages, chosen_line, names)
            if opening:
                # 0x53C8: the curtain comes down over the title.
                assert between is not None
                for row in range(CURTAIN_ROWS):
                    names[row * 32:row * 32 + between.curtain] = bytes(between.curtain)
            vdp_draw.put_names(names)
            pyxel.cls(0)
            vdp_draw.draw_screen()
            return
        if self.game is None:
            return
        if self.loaded != "play":
            vdp_draw.load(self.game.vram)
            self.loaded = "play"
        self.game.draw()
        over = self.game.play.over
        if front.screen is Screen.OVER and over is not None and over.written:
            names = bytearray(self.over_names)
            if self.game.play.players == 2:
                self.content.messages.write(TURN_LABELS[self.game.play.turn], names)
            vdp_draw.put_names(names[:22 * 32])
            pyxel.cls(0)
            vdp_draw.draw_screen()


def scripted_pad(script: str) -> int:
    pad = 0
    for name in filter(None, script.split("+")):
        pad |= PAD_NAMES[name]
    return pad


def headless(content: Content, stage: int, steps: int, script: str) -> Game:
    """A game driven with no window, `steps` game frames of the same pad
    (the fire button tapped every other frame, so shots keep coming)."""
    pyxel.init(WIDTH, HEIGHT, headless=True)
    palette.apply()
    game = Game(content, stage)
    pad = scripted_pad(script)
    for n in range(steps * VIDEO_FRAMES_A_STEP):
        held = pad if not pad & FIRE or n // VIDEO_FRAMES_A_STEP % 2 else pad & ~FIRE
        game.update(held)
    game.draw()
    return game


def selftest(content: Content, stage: int) -> int:
    """The whole window's loop with no window: the title, a start, a play
    with the fire held and the ship weaving, until GAME OVER and back."""
    app = App(content, stage, headless=True)
    held: set[int] = set()
    pressed: set[int] = set()
    pyxel.btn = lambda key: key in held  # type: ignore[assignment]
    pyxel.btnp = lambda key, *_: key in pressed  # type: ignore[assignment]
    seen = []
    for frame in range(60 * 60 * 3):
        pressed.clear()
        if app.front.screen is Screen.TITLE and frame % 120 == 60:
            pressed.add(pyxel.KEY_SPACE)
        held.clear()
        if app.front.screen is Screen.PLAY:
            held.add(pyxel.KEY_SPACE if frame % 4 < 2 else pyxel.KEY_K)
            held.add(pyxel.KEY_UP if frame // 90 % 2 else pyxel.KEY_DOWN)
        app.update()
        app.draw()
        if not seen or seen[-1] != app.front.screen:
            seen.append(app.front.screen)
    print("selftest:", " -> ".join(screen.value for screen in seen),
          "| record", app.record)
    return 0 if Screen.PLAY in seen else 1


def rom_folders() -> list[str]:
    """Where a ROM is looked for when `--rom` is not given: beside the built
    executable (what a player double-clicks has no arguments), then the
    directory the game was started from."""
    folders = [os.getcwd()]
    if getattr(sys, "frozen", False):
        folders.insert(0, os.path.dirname(os.path.abspath(sys.executable)))
    return list(dict.fromkeys(folders))


NO_ROM = ("No Nemesis ROM was found.", "",
          "Put your Nemesis (RC-742) dump,", "128 KB, beside this program",
          "(any name will do) and start it", "again.", "", "Esc quits.")


def no_rom(lines: tuple[str, ...] = NO_ROM) -> None:
    """Say so in a window: a double-clicked Windows build has no console, and a
    message on stderr would be a game that silently never opens."""
    pyxel.init(WIDTH, HEIGHT, title="nemesio", fps=60)

    def draw() -> None:
        pyxel.cls(0)
        for n, line in enumerate(lines):
            pyxel.text(8, 16 + 8 * n, line, 15)

    pyxel.run(lambda: None, draw)


class BrokenAssets(Exception):
    """The free assets cannot be played: what `check` says of them."""

    def __init__(self, folder: str, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.folder, self.problems = folder, problems

    def lines(self) -> tuple[str, ...]:
        """The problems for a window of 60 columns: the first ones, cut."""
        out = ["The free assets have problems:", self.folder[-60:], ""]
        for problem in self.problems[:12]:
            out += [problem[n:n + 60] for n in range(0, min(len(problem), 120), 60)]
        if len(self.problems) > 12:
            out.append("... and %d more" % (len(self.problems) - 12))
        return tuple(out[:20]) + ("", "main.py --check-assets says them all.", "Esc quits.")


def bundle_selftest() -> int:
    """`--selftest` with no cartridge: what a build machine can ask. Getting
    here already means every module imported; this also opens Pyxel headless,
    which is where a bundle missing its native libraries fails."""
    pyxel.init(WIDTH, HEIGHT, headless=True)
    print("selftest: no cartridge, the bundle only: ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Nemesis, from your own cartridge.")
    parser.add_argument("--rom", help="your Nemesis (RC-742) ROM (default: the one "
                        "beside the program or in the current directory)")
    parser.add_argument("--free", action="store_true",
                        help="play the free assets (assets/free), not a cartridge")
    parser.add_argument("--check-assets", nargs="?", const="", metavar="FOLDER",
                        help="check the free assets (default: the ones the game plays) "
                        "and say what is wrong")
    parser.add_argument("--stage", type=int, default=1, choices=range(1, 13))
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--shot", help="draw headless after --steps and save a PNG")
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--pad-script", default="")
    args = parser.parse_args()
    if args.check_assets is not None:
        return check_assets(args.check_assets or assets_folder(rom_folders()))
    try:
        content = load_content(args.rom, args.free)
    except BrokenAssets as broken:
        print("nemesio: the free assets in %s cannot be played:\n%s"
              % (broken.folder, broken), file=sys.stderr)
        if not (args.selftest or args.shot):
            no_rom(broken.lines())
        return 2
    if content is None:
        if args.selftest:
            return bundle_selftest()
        if not args.shot:
            no_rom()
        return 2
    stage = args.stage if isinstance(content, RomContent) else 1
    if args.selftest:
        return selftest(content, stage)
    if args.shot:
        headless(content, stage, args.steps, args.pad_script)
        pyxel.screen.save(args.shot, 1)
        return 0
    App(content, stage).run()
    return 0


def check_assets(folder: str | None) -> int:
    """Every problem in the free assets, a line each; 0 if there is none."""
    if folder is None:
        print("nemesio: no free assets found", file=sys.stderr)
        return 2
    problems = check(folder)
    for problem in problems:
        print(problem)
    print("%s: %s" % (folder, "%d problems" % len(problems) if problems else "ok"))
    return 1 if problems else 0


def load_content(rom: str | None, free: bool) -> Content | None:
    """The cartridge given or found; without one, or with `free`, the free
    assets (beside the program, or in the checkout); None if neither is."""
    if not free:
        rom = rom or find(rom_folders())
        if rom is not None:
            try:
                return RomContent(Cartridge.from_file(rom))
            except (OSError, NotTheCartridge) as error:
                print("nemesio: %s" % error, file=sys.stderr)
                raise SystemExit(2)
    folder = assets_folder(rom_folders())
    if folder is None:
        print("nemesio: no Nemesis ROM given (--rom) or found in %s, and no free "
              "assets" % ", ".join(rom_folders()), file=sys.stderr)
        return None
    try:
        return FreeContent(folder)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        raise BrokenAssets(folder, check(folder) or ["%s: %s" % (type(error).__name__, error)])


if __name__ == "__main__":
    sys.exit(main())
