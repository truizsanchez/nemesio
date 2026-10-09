"""The game with no cartridge: the free assets, read and played.

These are the only tests that read files of the repository's own: the free
assets in `assets/free` are the game's, not the cartridge's, and are
committed.
"""

import json
import os
import struct
import zlib

from game.engine.original import FIRE, MAP_ROWS, STARS, UP, DOWN
from game.engine.play import Play
from game.free import graphics, png
from game.free.cart import encode_sound
from game.free.content import FreeContent, assets_folder
from game.free.stage import FreeStage
from game.free.tables import angles, sines
from game.rom import band, screens
from game.rom.sound import Driver
from game.vdp import NAMES, Vram
from tests.cartridge_shape import Blank

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets", "free")

_CONTENT: list[FreeContent] = []


def content() -> FreeContent:
    if not _CONTENT:
        _CONTENT.append(FreeContent(ASSETS))
    return _CONTENT[0]


# -- the pictures ------------------------------------------------------------------------

def test_a_picture_written_reads_back_the_same(tmp_path):
    picture = png.Picture(9, 3)
    for n in range(len(picture.pixels)):
        picture.pixels[n] = n % 16
    path = str(tmp_path / "p.png")
    png.write(path, picture)
    assert png.read(path).pixels == picture.pixels


def test_an_rgb_picture_takes_the_nearest_colours(tmp_path):
    rows = [bytes((0xFF, 0xFF, 0xFF, 0xD0, 0x50, 0x50, 0x10, 0x10, 0x10))]
    raw = b"".join(b"\x00" + row for row in rows)

    def chunk(name: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + name + body + struct.pack(">I", zlib.crc32(name + body))
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 3, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    path = tmp_path / "rgb.png"
    path.write_bytes(data)
    assert list(png.read(str(path)).pixels) == [15, 6, 1]


def test_a_row_of_eight_pixels_is_its_two_colours():
    assert graphics.encode_row([0] * 8) == (0, 0)
    assert graphics.encode_row([3, 3, 12, 12, 3, 3, 3, 3]) == (0x30, 0xC3)


def test_the_characters_read_back_as_drawn():
    picture = png.read(os.path.join(ASSETS, "stage1.chars.png"))
    vram = Vram()
    assert graphics.load_chars(picture, vram) == []
    assert graphics.chars_picture(vram).pixels == picture.pixels


def test_the_sprites_read_back_as_drawn():
    vram = Vram()
    picture = png.read(os.path.join(ASSETS, "stage1.sprites.png"))
    graphics.load_sprites(picture, vram)
    again = graphics.sprites_picture(vram)
    assert [bool(p) for p in again.pixels] == [p >= 2 for p in picture.pixels]


# -- the stage ----------------------------------------------------------------------------

def test_the_stage_gives_columns_of_22_and_sky_outside():
    stage = FreeStage(ASSETS, 1)
    assert stage.number == 1 and stage.start < stage.checkpoint < stage.limit <= stage.end
    for distance in range(stage.start, stage.end):
        column = stage.column(distance)
        assert column is not None and len(column) == MAP_ROWS
    assert stage.column(stage.start - 1) is None
    rows = [stage.star_row(d) for d in range(32)]
    assert all(r is None or 0 <= r < MAP_ROWS for r in rows)


def test_the_stages_are_asked_for_by_their_rules():
    free = content()
    rules = [stage.number for stage in free.stages]
    assert rules == sorted(set(rules))
    for stage in free.stages:
        assert free.stage(stage.number) is stage
    assert free.stage(rules[-1] + 1) is free.stages[0]


def test_stages_out_of_the_originals_order_are_refused(tmp_path):
    import shutil
    import pytest
    from game.free.tables import stage_specs
    folder = tmp_path / "free"
    shutil.copytree(ASSETS, folder)
    # A second stage by stage 1's rules, as the first is.
    shutil.copy(folder / "stage1.txt", folder / "stage2.txt")
    shutil.copy(folder / "stage1.json", folder / "stage2.json")
    with pytest.raises(ValueError, match="so does an earlier one"):
        stage_specs(str(folder))


# -- the tables ----------------------------------------------------------------------------

def test_the_mathematics_is_worked_out():
    assert len(sines()) == 64 and sines()[0] == 0 and sines()[-1] == 255
    table = angles()
    assert len(table) == 256 and table[0] == 32 and max(table) < 64
    assert table[15 * 16] > 60 and table[15] < 4


def test_what_the_tables_draw_is_drawn():
    tables = content().tables()
    sprites = graphics.sprites_picture(content().play_vram)
    drawn = {n * 4 for n in range(64)
             if any(sprites[n % 16 * 16 + x, n // 16 * 16 + y] for x in range(16) for y in range(16))}
    for chars, pattern, _, _ in tables.records:
        if not chars and pattern:
            assert pattern in drawn, hex(pattern)
    for kind in (3, 5, 6, 9):
        assert set(tables.animations[kind]) <= drawn
    for pattern, _ in tables.blast:
        assert pattern in drawn


# -- the texts and sounds ---------------------------------------------------------------------

def test_the_band_and_the_messages_are_written_from_the_free_image():
    messages = content().messages
    names = bytearray(768)
    band.write_band(messages, names, 3, [False] * 6, 2, 1234, 5678)
    row = names[23 * 32:24 * 32]
    assert row[4] == 3 + band.DIGIT_ZERO
    assert any(names[22 * 32:23 * 32])
    over = screens.game_over(messages)
    assert any(over[10 * 32:11 * 32])


def test_a_free_message_is_written_whatever_its_length():
    names = bytearray(768)
    content().messages.write(band.TWO_PLAYERS_LINE, names)
    written = [c for c in names[19 * 32:20 * 32] if c]
    assert len(written) == len("2PLAYERS")


def test_the_cartridges_messages_are_its_streams():
    blank = Blank()
    blank.put(0, band.GAME_OVER, [0x4B, 0x39, 0x27, 0x21, 0xFF])
    blank.put(0, band.METER + 8 * 2, [1, 2, 3, 4, 5, 6, 7, 8])
    messages = band.RomMessages(blank.cartridge())
    names = screens.game_over(messages)
    assert names[10 * 32 + 11:10 * 32 + 13] == bytes((0x27, 0x21))
    assert messages.meter(2, False, True) == bytes((5, 6, 7, 8))


def test_every_sound_plays_and_ends():
    driver = Driver(content().cart)
    with open(os.path.join(ASSETS, "sounds.json")) as handle:
        tunes = {int(k, 0) + n for k, v in json.load(handle)["music"].items() for n in range(len(v))}
    for number in range(1, 0x80):
        channels = 1 if number < 0x16 else 2 if number < 0x26 else 3
        if tunes & set(range(number, number + channels)):
            # A tune is asked for as a melody (bit 7), and loops; nothing
            # asks for a sound whose channels run into one.
            continue
        driver.silence()
        driver.request(number)
        for _ in range(400):
            driver.tick()
        assert not any(driver.playing(n) for n in range(3)), hex(number)


def test_the_noise_period_is_the_psgs():
    driver_steps = encode_sound([["noise", 1, 12, 0, 24]])
    assert driver_steps[2] == 0x10 | 12


def test_a_step_out_of_range_says_which():
    import pytest
    with pytest.raises(ValueError, match="step 2: the volume is 16"):
        encode_sound([["rest", 1], ["tone", 2, 16, 0x100]])


def test_a_step_with_volume_1_is_not_read_as_the_noise():
    stream = encode_sound([["tone", 2, 1, 0x123]])
    assert stream[2] & 0xF0 == 0x10 and stream[3] == 0x11


def test_the_game_over_jingle_plays_and_ends():
    driver = Driver(content().cart)
    driver.request(0xCA)
    heard = 0
    for _ in range(2000):
        driver.tick()
        heard += driver.regs[8] > 0
    assert heard and not driver.playing(0)


def test_a_stage_tune_loops_on_two_channels_and_leaves_the_third_to_the_effects():
    from game.rom.sound import Music
    driver = Driver(content().cart)
    music = Music(content().cart, driver)
    music.update(1, 0x100, alive=True)
    music.update(1, 0x100, alive=True)
    tune = driver.playing(0)
    assert tune & 0x80 and driver.playing(1) == tune
    for _ in range(4000):
        driver.tick()
    assert driver.playing(0) == tune
    driver.request(1)
    assert driver.playing(2) == 1


def test_a_melody_step_out_of_range_says_which():
    import pytest
    from game.free.cart import encode_melody
    with pytest.raises(ValueError, match="step 2: the octave is 9"):
        encode_melody([["beat", 7], ["octave", 9]], 0x9000)


# -- the play ------------------------------------------------------------------------------------

def test_the_stages_play_to_their_ends_and_go_round():
    free = content()
    play = Play(free.stage(1), free.tables(), stages=free.stage)
    play.core_art = free.core_art()
    play.immortal = True
    changes = []
    kinds = set()
    for frame in range(6000 * len(free.stages)):
        play.step((FIRE if frame % 2 else 0) | (UP if frame // 60 % 2 else DOWN))
        ending = play.ending
        if ending is not None and ending.finale:
            # The host's part: the free assets have no ending of their own.
            ending.finale_done = True
        if play.objects is not None:
            kinds |= {(play.terrain.number, s.type) for s in play.objects.slots if s.type}
        if play.new_stage:
            play.new_stage = False
            changes.append((play.terrain.file, play.round))
    files = [stage.file for stage in free.stages]
    assert changes[:len(files)] == [(f, 0) for f in files[1:]] + [(1, 1)]
    assert (1, 0x0F) in kinds, "stage 1's eruption"
    assert play.score > 0


def test_the_title_has_its_messages_over_the_picture():
    names = content().title().data[NAMES:NAMES + 768]
    assert names[14 * 32 + 11] and names[17 * 32 + 13] and names[19 * 32 + 13]
    assert any(names[:6 * 32])


def test_the_maps_stars_are_the_layouts():
    stage = FreeStage(ASSETS, 1)
    cells = {c for d in range(stage.start, stage.end) for c in stage.column(d) or []}
    stars = set(content().tables().layout.stars)
    assert stars & cells and not stars & set(STARS)


def test_the_free_layout_is_read_and_the_rules_draw_with_it():
    layout = content().tables().layout
    play = Play(content().stage(1), content().tables(), stages=content().stage)
    assert play.ship.sprites == layout.ship[0]
    assert play.shots.layout is layout and play.scroll.stars == layout.stars
    assert play.objects is not None and play.objects.layout is layout


def test_what_the_layout_names_is_drawn():
    layout = content().tables().layout
    sprites = graphics.sprites_picture(content().play_vram)
    drawn = {n * 4 for n in range(64)
             if any(sprites[n % 16 * 16 + x, n // 16 * 16 + y] for x in range(16) for y in range(16))}
    named = {p for pair in layout.ship for p, _ in pair} | {p for pair in layout.explosion for p, _ in pair}
    named |= {p for state in layout.explosion_parts for _, p, _ in state}
    named |= {layout.double[0], layout.enemy_shot[0], layout.blast_pattern, *layout.missile[:2]}
    named |= {p for p, _ in layout.options} | set(layout.walker_start.values())
    named |= {p for pair in layout.walker_facing.values() for p in pair}
    assert named <= drawn
    drawings = content().tables().character_drawings
    for number in (*layout.bug_drawings, layout.ship_drawing, *layout.capsule_drawings.values()):
        assert any(drawings[number * 4:number * 4 + 4]), number


def test_a_layout_left_out_is_the_cartridges():
    from game.engine.layout import Layout
    from game.free.tables import layout
    assert layout({}) == Layout()
    assert layout({"stars": ["0x10", 17]}).stars == (0x10, 0x11)


def test_the_assets_are_found_in_the_checkout():
    assert assets_folder([]) == ASSETS


class _Sky:
    """A stage of nothing but sky."""

    def __init__(self, number: int) -> None:
        self.number, self.start, self.end, self.limit, self.checkpoint = number, 0, 0, 0x100, 0x80

    def column(self, distance: int) -> None:
        return None

    def star_row(self, distance: int) -> None:
        return None


def test_the_next_stage_is_the_one_asked_for_and_after_8_a_new_round():
    play = Play(_Sky(1), stages=_Sky)
    play._next_stage()
    assert (play.terrain.number, play.round) == (2, 0)
    play.terrain = _Sky(8)
    play._next_stage()
    assert (play.terrain.number, play.round) == (1, 1)


def test_a_game_of_one_stage_goes_round_after_it():
    play = Play(_Sky(1), stages=lambda n: _Sky(1))
    play._next_stage()
    assert (play.terrain.number, play.round, play.ship.stage) == (1, 1, 1)


# -- the checker ------------------------------------------------------------------------------

def _broken(tmp_path, change):
    import shutil
    folder = tmp_path / "free"
    shutil.copytree(ASSETS, folder)
    change(folder)
    from game.free.check import check
    return check(str(folder))


def test_the_free_assets_check_clean():
    from game.free.check import check
    assert check(ASSETS) == []


def test_a_sprite_the_tables_use_rubbed_out_is_found(tmp_path):
    def rub(folder):
        picture = png.read(str(folder / "stage1.sprites.png"))
        spinner = content().tables().records[3][1] // 4
        for y in range(16):
            for x in range(16):
                picture[spinner % 16 * 16 + x, spinner // 16 * 16 + y] = 0
        png.write(str(folder / "stage1.sprites.png"), picture)
    problems = _broken(tmp_path, rub)
    assert any("type 0x03" in p and "sprites.png has nothing" in p for p in problems)


def test_three_colours_in_a_row_are_found(tmp_path):
    def paint(folder):
        picture = png.read(str(folder / "stage1.chars.png"))
        for x, colour in zip(range(3), (2, 5, 8)):
            picture[0x43 % 32 * 8 + x, 0x43 // 32 * 8] = colour
        png.write(str(folder / "stage1.chars.png"), picture)
    problems = _broken(tmp_path, paint)
    assert any("character 0x43, row 0" in p for p in problems)


def test_a_map_letter_not_in_the_legend_is_found(tmp_path):
    def scribble(folder):
        lines = (folder / "stage1.txt").read_text().split("\n")
        lines[3] = "@" + lines[3][1:]
        (folder / "stage1.txt").write_text("\n".join(lines))
    problems = _broken(tmp_path, scribble)
    assert any("'@' is not in the legend" in p for p in problems)


def test_texts_and_sounds_that_cannot_be_written_are_found(tmp_path):
    def spoil(folder):
        text = json.loads((folder / "text.json").read_text())
        text["game_over"][0][2] = "GAME OVER?"
        (folder / "text.json").write_text(json.dumps(text))
        sounds = json.loads((folder / "sounds.json").read_text())
        sounds["sounds"]["0x01"][0][0][2] = 20
        (folder / "sounds.json").write_text(json.dumps(sounds))
    problems = _broken(tmp_path, spoil)
    assert any(p.startswith("text.json") and "'?'" in p for p in problems)
    assert any(p.startswith("sounds.json") and "volume is 20" in p for p in problems)


def test_a_solid_star_is_found(tmp_path):
    def solidify(folder):
        tables = json.loads((folder / "tables.json").read_text())
        tables["layout"]["stars"] = ["0x43", "0x44"]
        (folder / "tables.json").write_text(json.dumps(tables))
    problems = _broken(tmp_path, solidify)
    assert any("would crash into the stars" in p for p in problems)


def test_the_free_ending_writes_its_words_and_pays_the_bonus():
    import random
    free = content()
    finale = free.make_finale(random.Random(0), 0, Vram())
    paid = 0
    for _ in range(3000):
        finale.update(False)
        paid += finale.bonus
        if finale.done:
            break
    assert finale.done and paid == 500
    assert any(finale.names[10 * 32:11 * 32]) and any(finale.names[13 * 32:14 * 32])
