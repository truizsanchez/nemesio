"""What the VDP shows, as `game.screen` keeps it."""

from game.engine.original import SCORES_AT, SCORES_EVERY, UP
from game.engine.play import Play
from game.screen import Screen, sent

from tests.test_engine import Flat


def _playing() -> Play:
    play = Play(Flat())
    while not play.sprites_on:
        play.step(0)
    return play


def test_the_sprites_are_a_game_frame_behind():
    # 0x4538 sends, as a game frame starts, the buffer the last one built.
    play = _playing()
    screen = Screen()
    play.step(UP)
    screen.step(play)
    before = play.ship.row
    play.step(UP)
    screen.step(play)
    assert play.ship.row != before
    assert screen.built[0] is not None and screen.built[0][0] == play.ship.row
    assert any(e is not None and e[0] == before for e in screen.sprites)
    assert not any(e is not None and e[0] == play.ship.row for e in screen.sprites)


def test_turning_starts_at_the_entry_and_goes_three_on():
    table = list(range(32))
    turned = sent(table, 7, True)  # type: ignore[arg-type]
    assert turned[:3] == [7, 10, 13] and sent(table, 7, False) == table  # type: ignore[arg-type]


def test_the_band_scores_are_written_one_game_frame_in_eight():
    play = _playing()
    screen = Screen()
    for _ in range(SCORES_EVERY):
        play.step(0)
        screen.step(play)
        if play.frames % SCORES_EVERY != SCORES_AT:
            play.score += 1
    assert screen.score < play.score
    while play.frames % SCORES_EVERY != SCORES_AT:
        play.step(0)
        screen.step(play)
    assert screen.score == play.score
