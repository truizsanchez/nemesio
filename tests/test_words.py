"""The words typed in pause."""

from game.engine.play import Phase, Play
from game.engine.words import Keyboard
from tests.test_engine import Flat


def _play() -> Play:
    return Play(Flat())

WORDS = {w: w for w in ("HYPER", "BAKA", "AHO", "LASER", "MISSILE", "SHIELD", "OPTION",
                        "DOUBLE", "DOWN")}


def _typing(play: Play, text: str) -> None:
    for letter in text:
        play.type_key(letter)
    play.type_key("\r")


def test_hyper_gives_everything_once_a_game():
    play = _play()
    play.keyboard = Keyboard(WORDS, ("MOMOKO",))
    _typing(play, "HYPER")
    assert play.shield == 3 and play.shots.laser == 2 and len(play.options.options) == 2
    play.shield = 1
    _typing(play, "HYPER")
    assert play.shield == 1


def test_one_word_a_stage_and_baka_ends_the_game():
    play = _play()
    play.keyboard = Keyboard(WORDS, ("MOMOKO",))
    _typing(play, "MISSILEX")
    assert play.shots.missile == 2
    _typing(play, "LASER")
    assert play.shots.laser != 2
    _typing(play, "BAKA")
    assert play.lives == 0 and play.phase is Phase.OVER


def test_two_players_take_turns_when_a_life_is_lost():
    play = Play(Flat(), players=2)
    assert play.turn == 0 and play.other_lives == 3
    lives = play.lives
    play.resume = 0x40
    play.between = None
    play._life_over()
    _through_state_4(play)
    assert play.turn == 1 and play.lives == 2 and play.other_lives == lives
    play._life_over()
    assert play.intro is False
    _through_state_4(play)
    assert play.turn == 0 and play.lives == lives - 1


def _through_state_4(play: Play) -> None:
    turn_shown = False
    while play.between is not None:
        play.step(0)
        turn_shown = turn_shown or play.intro
    assert turn_shown
