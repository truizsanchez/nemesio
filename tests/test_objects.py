"""The object slots' rules on tables this file builds."""

import random

from dataclasses import replace

from game.engine.objects import BLAST, BLAST_0D, CAPSULE, Objects, Slot
from game.engine.options import Options
from game.engine.original import RIGHT
from game.engine.tables import EndingArt, Tables
from game.engine.terrain import Map
from game.engine.waves import Waves


def _tables() -> Tables:
    records = tuple((0, 0x80, 0x0F, 1) for _ in range(32))
    return Tables(
        records=records, sections=((0,) * 16,) * 9, rows_types=(0,) * 9,
        trail_rows=(0x20,) * 4, trail_counts=(3,) * 16, left_rows=(8,) * 8,
        marks=(0,) * 16, shot_delays=(0x80,) * 16, angles=(0x20,) * 256,
        sines=tuple(range(64)), character_drawings=(0,) * 256,
        blast=((0x78, 0x0F),) * 4, cannon_script=((),) * 9, cannon_drawings=(0,) * 48,
        cannon_waits=(0x60,) * 64, ship_cards=((),) * 4, kill_sounds=(8,) * 32,
        background_script=((),) * 9, background_drawings=((0,) * 16,) * 16,
        stone_drawings=((0, 0),) * 3, walls={}, wall_rows=(0,) * 6, rain_doors=((0, 0),) * 16,
        guns=None,
        animations={2: (0,) * 4, 3: (0,) * 8, 5: (0xF4, 0xF8, 0xD0, 0xD4, 0xE8, 0xEC, 0xDC, 0xE0),
                    6: (0,) * 4, 9: (0,) * 6},
        ending=EndingArt(
            eruption_from=((0x70, 0xB0), (0x70, 0x30)),
            eruption_speeds=((0x0A00, 0x0100),) * 8,
            core_shots=((0, 8), (8, -8), (0x20, -8), (0x30, 8)),
            head_lanes=(0x10, 0x38, 0x60, 0x88), head_floors=(0x14, 0x3C, 0x64, 0x8C),
            head_roofs=(0x08, 0x30, 0x58, 0x80), head_chars=((1,) * 16, (2,) * 16),
            walker_chars=((3,) * 12, (4,) * 12),
            crystal_pieces=((0x40, 0xF0),) * 5, crystal_blast=(5, 6, 5, 6)))


def test_a_marked_enemy_is_red_and_leaves_a_capsule():
    objects = Objects(_tables(), random.Random(0), 1)
    s = objects.make(9, 0x40, 0x80, mark=1)
    assert s is not None and s[13] == 8
    objects.hit(s)
    assert s.type == BLAST
    for _ in range(0x11):
        objects.step(Map())
    assert s.type == CAPSULE


def test_an_unmarked_enemy_blows_up_and_frees_its_slot():
    objects = Objects(_tables(), random.Random(0), 1)
    s = objects.make(9, 0x40, 0x80)
    assert s is not None
    objects.hit(s)
    for _ in range(0x11):
        objects.step(Map())
    assert s.type == 0 and objects.alive == 0


def test_the_last_of_a_group_leaves_the_capsule_not_the_first():
    objects = Objects(_tables(), random.Random(0), 1)
    objects.wave_number = 1
    assert objects.open_group(1, 2)
    first, last = objects.make(2, 0x40, 0x80), objects.make(2, 0x60, 0x80)
    assert first is not None and last is not None
    objects.hit(first)
    objects.hit(last)
    for _ in range(0x11):
        objects.step(Map())
    assert first.type == 0 and last.type == CAPSULE


def test_an_option_follows_eight_moves_behind():
    options = Options()
    options.add(0x40, 0x40)
    for n in range(1, 10):
        options.step(RIGHT, 0x40, 0x40 + n)
    assert options.options[0].col == 0x40 + 1


def test_an_option_does_not_move_while_the_ship_is_still():
    options = Options()
    options.add(0x40, 0x40)
    options.step(RIGHT, 0x40, 0x48)
    before = options.options[0].col
    options.step(0, 0x40, 0x48)
    assert options.options[0].col == before


def test_a_background_blast_takes_no_object_slot_and_goes_after_three_drawings():
    from game.engine.blasts import Blasts
    objects = Objects(_tables(), random.Random(0), 1)
    objects.blasts = Blasts(((1,) * 16, (2,) * 16, (3,) * 16))
    objects.blast_at(0x40, 0x80)
    assert not any(s.type for s in objects.slots) and objects.alive == 0
    terrain = Map()
    seen = []
    for _ in range(12):
        objects.blasts.step(False)
        objects.blasts.draw(terrain)
        seen.append(terrain[8, 16])
        objects.blasts.erase(terrain)
    assert seen == [3] * 3 + [2] * 4 + [1] * 4 + [0]
    assert not objects.blasts.any()


def _stage7(objects_rng: int = 0) -> Objects:
    tables = replace(_tables(), appearances=(0x2894, 0x3B01), lunge_speeds=(0x40,) * 16,
                     blast_0d=(0xF0, 0xF4, 0xF8, 0xFC),
                     animations={**_tables().animations, 0x0D: (0xE0, 0xE4, 0xE8, 0xEC, 0xE8, 0xE4)})
    return Objects(tables, random.Random(objects_rng), 7)


def test_stage_7s_script_lets_a_0x0d_in_at_its_distance_row_and_mark():
    objects = _stage7()
    waves = Waves(objects, 7)
    waves.appearances.step(0x94, True)
    s = objects.slots[0]
    assert (s.type, s.row, s.col, s[14]) == (0x0D, 0x28, 0xF8, 0)
    waves.appearances.step(0x101, True)
    s = objects.slots[1]
    assert (s.type, s.row, s[14], s[13]) == (0x0D, 0x38, 1, 6)


def test_the_screen_filling_skips_what_is_behind_and_leaves_the_left_half_empty():
    objects = _stage7()
    waves = Waves(objects, 7)
    waves.appearances.fill(0x94, 0x40)
    waves.appearances.fill(0x100, 0x90)
    assert not any(s.type for s in objects.slots) and waves.appearances.next == 1


def test_a_0x0d_waits_ten_lunges_ten_and_leaves_after_0xff():
    objects = _stage7()
    s = objects.make(0x0D, 0x40, 0xC0)
    assert s is not None
    objects.world.ship_row, objects.world.ship_col = 0x40, 0x20
    for _ in range(9):
        objects.step(Map())
    assert s.col == 0xC0
    objects.step(Map())
    assert s[1] == 1 and s.word(9) & 0x8000
    for _ in range(0xFF - 10):
        objects.step(Map())
    assert s[1] == 2 and s[12] == 0xDC and s[13] == 0x0D and s.word(9) == 0xFF00


def test_a_0x0d_shot_down_is_its_own_blast():
    objects = _stage7()
    s = objects.make(0x0D, 0x40, 0xC0, mark=1)
    assert s is not None
    objects.hit(s)
    assert s.type == BLAST_0D and s[12] == 0xF0
    seen = []
    for _ in range(0x11):
        objects.step(Map())
        seen.append(s[12])
    assert seen[:16:4] == [0xF0, 0xF4, 0xF8, 0xFC] and s.type == CAPSULE


def test_a_shot_drawn_with_characters_puts_back_what_it_covered_then():
    # 0x6893 keeps the cells; whatever is wiped before 0x69CB comes back.
    terrain = Map()
    shot = Slot()
    shot[0], shot[4], shot[6], shot[11] = 1, 0x40, 0x98, 2
    terrain[8, 19], terrain[9, 20] = 0xA4, 0x49
    Objects.keep_under([shot], terrain)
    terrain[8, 19] = terrain[9, 20] = 0
    Objects.put_back_under([shot], terrain)
    assert terrain[8, 19] == 0xA4 and terrain[9, 20] == 0x49


def test_one_past_column_0xf8_or_without_characters_puts_nothing_back():
    terrain = Map()
    far, sprite = Slot(), Slot()
    far[0], far[4], far[6], far[11] = 1, 0, 0xF8, 1
    sprite[0], sprite[4], sprite[6] = 1, 0, 0
    terrain[0, 31] = terrain[0, 0] = 5
    Objects.keep_under([far, sprite], terrain)
    terrain[0, 31] = terrain[0, 0] = 0
    Objects.put_back_under([far, sprite], terrain)
    assert terrain[0, 31] == 0 and terrain[0, 0] == 0


def test_a_kept_rectangle_runs_past_the_right_edge_into_the_next_row():
    terrain = Map()
    terrain[0, 31], terrain[1, 0] = 7, 9
    kept = terrain.keep(31, 2, 1)
    assert kept == bytes((7, 9))
    terrain.put_back(0, 2, kept)
    assert terrain[0, 0] == 7 and terrain[0, 1] == 9


def test_with_the_heads_a_blast_puts_back_what_its_slot_kept_last():
    # 0x690C keeps under the blasts before they are drawn; one made after
    # (a piece shot down) writes back its slot's old sixteen bytes (0x6A03).
    from game.engine.blasts import Blasts
    terrain = Map()
    blasts = Blasts(((1,) * 16,) * 3)
    blasts.make(0, 0)
    terrain[0, 0] = 0xF6
    blasts.keep(terrain)
    blasts.slots[0] = None
    blasts.make(0x40, 0x40)
    blasts.draw(terrain)
    blasts.erase(terrain, put_back=True)
    assert terrain[8, 8] == 0xF6 and terrain[8, 9] == 0 and terrain[0, 0] == 0xF6


def test_a_type_5_walks_through_its_pair_by_way_and_floor():
    # 0xAB3C: the pair out of 0xAB58 by byte 10's sign and byte 19's bit 0,
    # one drawing every four game frames.
    objects = Objects(_tables(), random.Random(0), 1)
    s = Slot()
    s[0], s[19] = 5, 1
    s.vx(0x0200)
    seen = []
    for frame in range(8):
        objects.world.frames = frame
        objects._animate_5(s)
        seen.append(s[12])
    assert set(seen) == {0xE8, 0xEC}
    s.vx(0xFE00)
    objects.world.frames = 0
    objects._animate_5(s)
    assert s[12] in (0xDC, 0xE0)


def test_a_planted_type_5_faces_the_ship():
    objects = Objects(_tables(), random.Random(0), 1)
    s = Slot()
    s[0], s[6], s[19] = 5, 0x80, 1
    objects.world.ship_col = 0x40
    objects._face_5(s)
    assert s[12] == 0xE4
    s[19] = 0
    objects.world.ship_col = 0x90
    objects._face_5(s)
    assert s[12] == 0xFC
