"""The PSG's registers, heard through Pyxel's synthesizer.

`game/rom/sound.py` runs the original's driver and leaves the AY-3-8910's
registers as it wrote them. Here each of the PSG's three tone channels is a
Pyxel channel holding one long square note, and the PSG's one noise generator
is Pyxel's fourth, as loud as the loudest channel that has noise switched on.

Pyxel reads a channel's `detune` and `gain` only when a note starts
(`MmlCommand::Note` in its `channel.rs`), so a channel whose pitch or level the
driver changed is played again: that starts a new note without resetting the
oscillator's phase, and Pyxel crossfades from the old level in 0.8 ms -- a
change of note does not restart the wave, as it does not on the chip.

It is an approximation of the chip, not an emulation: Pyxel's square and
noise are its own, tone and noise on one channel are heard side by side
rather than ANDed, and the envelope generator is heard as a steady level
(only effect 0x03 uses it).
"""

import math

import pyxel

from game.rom.sound import Driver

#: The MSX's PSG runs at 3.579545 MHz / 2; a tone's frequency is the clock
#: over 16 times its period, and the noise's shift register steps at the same
#: rate for its own period. A period of 0 counts as 1.
PSG_CLOCK = 3579545 / 2
#: Pyxel's note 33 is A2, 440 Hz; a channel's pitch is set by detuning it.
BASE_NOTE, BASE_HZ = 33, 440.0
SQUARE, NOISE = 1, 3
#: Pyxel's own channel gain, the level a whole channel sits at.
CHANNEL_GAIN = 0.125
#: Pyxel's square tone has a gain of 0.3 and its noise 0.6 (`DEFAULT_TONE_*`
#: in its `settings.rs`); on the chip both swing the same, so the noise is
#: brought down to the square's scale.
NOISE_SCALE = 0.3 / 0.6
#: Pyxel mixes at 22050 Hz: a tone above half of it is inaudible on the chip
#: and would alias here.
NYQUIST = 22050 / 2
#: The AY-3-8910's DAC, its sixteen volume steps normalized (MAME's table).
LEVELS = (0.0, 0.0106, 0.0150, 0.0222, 0.0320, 0.0466, 0.0665, 0.1039,
          0.1237, 0.1986, 0.2803, 0.3548, 0.4702, 0.5936, 0.7440, 1.0)
#: With the envelope on, a steady level in its place.
ENVELOPE_LEVEL = 12
SILENT = 0.0


def amplitude(volume: int) -> float:
    return LEVELS[volume & 0x0F]


def cents(hz: float) -> int:
    return round(1200 * math.log2(hz / BASE_HZ))


def frequency(period: int) -> float:
    return PSG_CLOCK / (16 * max(period, 1))


class Audio:
    def __init__(self, driver: Driver) -> None:
        self.driver = driver
        self.sounds: list[pyxel.Sound] = []
        #: What each channel was last played with, (detune, gain).
        self.playing: list[tuple[int, float] | None] = [None] * 4
        for tone in (SQUARE, SQUARE, SQUARE, NOISE):
            sound = pyxel.Sound()
            sound.set_notes("a2")
            sound.set_tones("n" if tone == NOISE else "s")
            sound.set_volumes("7")
            sound.set_effects("n")
            sound.speed = 120
            self.sounds.append(sound)
        self.silence()

    def _set(self, channel: int, detune: int, gain: float) -> None:
        """A channel's pitch and level, heard from now: its note played again
        if either changed."""
        before = self.playing[channel]
        if gain == SILENT and before is not None:
            # Silent, the pitch is not heard: no note for it alone.
            detune = before[0]
        if before == (detune, gain):
            return
        self.playing[channel] = (detune, gain)
        out = pyxel.channels[channel]
        out.detune = detune
        out.gain = gain
        out.play(self.sounds[channel], loop=True)

    def tick(self) -> None:
        """One interrupt of the driver, and what it wrote, heard."""
        self.driver.tick()
        regs = self.driver.regs
        mixer = regs[7]
        noise_level = 0.0
        for channel in range(3):
            level = regs[8 + channel]
            gain = amplitude(ENVELOPE_LEVEL if level & 0x10 else level)
            period = regs[2 * channel] | (regs[2 * channel + 1] & 0x0F) << 8
            tone_on = not mixer & (1 << channel)
            noise_on = not mixer & (8 << channel)
            hz = frequency(period)
            if tone_on and gain and hz < NYQUIST:
                self._set(channel, cents(hz), CHANNEL_GAIN * gain)
            else:
                self._set(channel, 0, SILENT)
            if noise_on:
                noise_level = max(noise_level, gain)
        noise_hz = frequency(regs[6] & 0x1F)
        self._set(3, cents(noise_hz), CHANNEL_GAIN * NOISE_SCALE * noise_level)

    def silence(self) -> None:
        for channel in range(4):
            self._set(channel, 0, SILENT)
