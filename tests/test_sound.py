"""The sound driver's rules on streams this file writes into bank 7."""

from game.rom.sound import MELODY, NOTES, SOUNDS, Driver
from tests.cartridge_shape import Blank

STREAM = 0x9000


SILENT = 0x9100


def _driver(stream: list[int], sound: int = 0x05) -> Driver:
    """The sound's first channel plays `stream`; any others it takes, nothing."""
    blank = Blank()
    blank.word(7, SOUNDS + 2 * (sound & 0x7F), STREAM)
    for n in (1, 2):
        blank.word(7, SOUNDS + 2 * ((sound & 0x7F) + n), SILENT)
    blank.put(7, STREAM, stream)
    blank.put(7, SILENT, [0xFF])
    blank.put(7, NOTES, [0x6B, 0x65, 0x5F, 0x5A, 0x55, 0x50, 0x4C, 0x47, 0x43, 0x40])
    return Driver(blank.cartridge())


def test_an_effect_takes_channel_c_and_writes_its_period_and_volume():
    driver = _driver([0x22, 0x03, 0xC1, 0x23, 0xFF])
    driver.request(0x05)
    driver.tick()
    assert driver.regs[4] | driver.regs[5] << 8 == 0x123
    assert driver.regs[10] == 0x0C
    assert not driver.regs[7] & 0x04, "C's tone is on"


def test_a_note_lasts_its_length_then_the_stream_ends():
    driver = _driver([0x22, 0x02, 0xC1, 0x23, 0xFF])
    driver.request(0x05)
    for _ in range(3):
        driver.tick()
    assert driver.playing(2) == 0


def test_a_lower_request_does_not_take_a_channel_from_a_higher_one():
    driver = _driver([0x22, 0x40, 0xC1, 0x23, 0xFF], sound=0x10)
    driver.request(0x10)
    driver.tick()
    driver.request(0x03)
    assert driver.playing(2) == 0x10


def test_a_melody_note_is_the_tables_period_shifted_by_its_octave():
    # A beat of 4 frames, volume 0x0D (0xFB + 2), octave 2, note 3 for one beat.
    driver = _driver([0xD4, 0xFB, 0x00, 0xE2, 0x30, 0xFF], sound=MELODY | 0x20)
    driver.request(MELODY | 0x20)
    driver.tick()
    assert driver.regs[0] | driver.regs[1] << 8 == 0x5A << 2
    assert driver.regs[8] == 0x0D
