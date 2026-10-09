"""The PSG heard: a channel is played again when, and only when, it changes.

Pyxel is replaced by stand-ins that note what they are handed, so no window
and no audio device are needed.
"""

import pytest

from game.render import audio
from game.render.audio import CHANNEL_GAIN, LEVELS, NOISE_SCALE, PSG_CLOCK, Audio, cents


class Channel:
    def __init__(self) -> None:
        self.detune = 0
        self.gain = 0.125
        self.plays = 0

    def play(self, sound: object, loop: bool = False) -> None:
        assert loop
        self.plays += 1


class Sound:
    speed = 0

    def set_notes(self, notes: str) -> None: ...
    def set_tones(self, tones: str) -> None: ...
    def set_volumes(self, volumes: str) -> None: ...
    def set_effects(self, effects: str) -> None: ...


class Driver:
    def __init__(self) -> None:
        self.regs = bytearray(16)
        self.regs[7] = 0xFF

    def tick(self) -> None: ...


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> tuple[Audio, Driver, list[Channel]]:
    channels = [Channel() for _ in range(4)]
    monkeypatch.setattr(audio.pyxel, "channels", channels, raising=False)
    monkeypatch.setattr(audio.pyxel, "Sound", Sound, raising=False)
    driver = Driver()
    out = Audio(driver)  # type: ignore[arg-type]
    for channel in channels:
        channel.plays = 0
    return out, driver, channels


def _tone(driver: Driver, channel: int, period: int, volume: int) -> None:
    driver.regs[2 * channel] = period & 0xFF
    driver.regs[2 * channel + 1] = period >> 8
    driver.regs[8 + channel] = volume
    driver.regs[7] &= ~(1 << channel)


def test_it_starts_silent(heard):
    _, _, channels = heard
    assert all(channel.gain == 0 for channel in channels)


def test_a_new_note_is_played_on_its_channel_alone(heard):
    out, driver, channels = heard
    _tone(driver, 1, 0x1AC, 15)
    out.tick()
    assert [channel.plays for channel in channels] == [0, 1, 0, 0]
    assert channels[1].detune == cents(PSG_CLOCK / (16 * 0x1AC))
    assert channels[1].gain == CHANNEL_GAIN


def test_nothing_changed_nothing_played_again(heard):
    out, driver, channels = heard
    _tone(driver, 0, 0x100, 12)
    out.tick()
    out.tick()
    assert channels[0].plays == 1


def test_a_decay_is_heard_every_step(heard):
    out, driver, channels = heard
    for volume in (15, 14, 13):
        _tone(driver, 2, 0x80, volume)
        out.tick()
    assert channels[2].plays == 3
    assert channels[2].gain == CHANNEL_GAIN * LEVELS[13]


def test_a_silent_channel_is_not_played_for_its_pitch(heard):
    out, driver, channels = heard
    _tone(driver, 0, 0x100, 0)
    out.tick()
    _tone(driver, 0, 0x200, 0)
    out.tick()
    assert channels[0].plays == 0


def test_the_noise_steps_at_the_tones_rate(heard):
    out, driver, channels = heard
    driver.regs[6] = 0x08
    driver.regs[9] = 15
    driver.regs[7] &= ~0x10
    out.tick()
    assert channels[3].detune == cents(PSG_CLOCK / (16 * 8))
    assert channels[3].gain == CHANNEL_GAIN * NOISE_SCALE


def test_a_tone_past_nyquist_is_mute(heard):
    out, driver, channels = heard
    _tone(driver, 0, 1, 15)
    out.tick()
    assert channels[0].gain == 0


def test_the_dac_climbs():
    assert LEVELS[0] == 0 and LEVELS[15] == 1
    assert list(LEVELS) == sorted(LEVELS)
