"""The original's sound driver, run on the cartridge's data, into PSG registers.

Bank 7 is the driver and bank 8 its data (both paged in by the interrupt,
0x402C). Every interrupt `tick` does what 0x8063 does: three channel cards of
0x11 bytes (0xE010, 0xE021, 0xE032) each walk their own stream and write the
AY-3-8910's registers -- which is all this module produces. Turning those
registers into sound is `game/render/audio.py`'s.

A request (bank 0, 0x4A22) takes one card for an effect under 0x16 (channel
C's), two from 0x16 and three from 0x26 (A, B and C), unless what the first
of them already plays outranks it: a higher number wins. Bit 7 of a request
makes its channels melodies -- notes, octaves, decays -- instead of effects,
which are raw periods and volumes.

A card's bytes, as the driver names them:

    0 frames left of the note     1 the note's length       2 the sound (0 off)
    3-4 where the stream is       5 tone, noise, envelope   6 octave
    7 starting volume             8 volume now              9 when it decays
    10 loops done                 11 a beat's length        12 sharp
    13 decay's start (high nibble of 0xFx's byte)          14 decay's floor
    15-16 the period written
"""

from game.rom.cartridge import Cartridge, Paging

SOUND_BANKS = {0x8000: 7, 0xA000: 8}
SOUNDS = 0x8328
#: The twelve notes' periods at the highest octave. The table is ten bytes
#: long and runs into the next: notes 10 and 11 are the low and high byte of
#: SOUNDS' first entry, 0x393C, which is not an address -- there is no sound 0.
NOTES = 0x831E
#: The pause's sound (0x80D9): four noise periods.
PAUSE_PERIODS = 0x80D9

CARDS, CARD_SIZE = 3, 0x11
EFFECTS_BELOW, TWO_FROM, THREE_FROM = 0x16, 0x16, 0x26
MELODY = 0x80
REST = 0x0C
#: The mixer (register 7) starts with the three tones and noises off.
MIXER_START = 0xB8
#: A music change fades: every 0x60 frames one step softer, six steps (0x8145).
FADE_EVERY, FADE_STEPS = 0x60, 6
_LOOP, _END = 0xFE, 0xFF


class Card:
    def __init__(self) -> None:
        self.b = bytearray(CARD_SIZE)

    @property
    def pointer(self) -> int:
        return self.b[3] | self.b[4] << 8

    @pointer.setter
    def pointer(self, value: int) -> None:
        self.b[3], self.b[4] = value & 0xFF, value >> 8 & 0xFF


class Driver:
    def __init__(self, cart: Cartridge) -> None:
        self.data = Paging(cart, SOUND_BANKS)
        self.cards = [Card() for _ in range(CARDS)]
        #: The PSG's sixteen registers as the driver last wrote them.
        self.regs = bytearray(16)
        self.regs[7] = MIXER_START
        #: 0xE043: the mixer the driver keeps.
        self.mixer = MIXER_START
        #: 0xE044-0xE046: the fade (on, its clock, its step).
        self.fading = 0
        self.fade_clock = 0
        self.fade_step = 0
        #: 0xE047: the pause's sound; 0xE048-0xE04C its counters.
        self.paused = False
        self.pause_first = False
        self.pause_count = [0, 0, 0]
        self.pause_volume = 0
        self.touched = False

    # -- requests (bank 0, 0x4A22) ---------------------------------------------

    def request(self, sound: int) -> None:
        number = sound & 0x7F
        if number < EFFECTS_BELOW:
            first, count = 2, 1
        else:
            self.fading = 0
            first, count = 0, 3 if number >= THREE_FROM else 2
        if number < self.cards[first].b[2] & 0x7F:
            return
        entry = SOUNDS + 2 * number
        for n in range(first, first + count):
            card = self.cards[n]
            card.b[0] = 1
            card.b[2] = sound
            card.pointer = self.data.word(entry)
            card.b[0x0A] = 0
            entry += 2

    def silence(self) -> None:
        """Every channel off, as a new state's arranca_la_maquina leaves the
        PSG (0x572F): the attract screens handing over to the game."""
        for card in self.cards:
            card.b[2] = 0
        for reg in (8, 9, 10):
            self.regs[reg] = 0
        self.fading = 0

    def pause(self, on: bool) -> None:
        """0x4509: the pause writes 0x0101 into 0xE047/0xE048."""
        self.paused = on
        self.pause_first = on

    def start_fade(self) -> None:
        """0x703F: 0xE044 = 1, 0xE045 = 0x60, 0xE046 = 0."""
        self.fading, self.fade_clock, self.fade_step = 1, FADE_EVERY, 0

    def playing(self, card: int = 0) -> int:
        return self.cards[card].b[2]

    # -- a tick (0x8063) ---------------------------------------------------------

    def _write(self, reg: int, value: int) -> None:
        self.regs[reg & 0x0F] = value & 0xFF

    def tick(self) -> None:
        if self.paused:
            self._pause_tick()
            return
        if self.touched:
            self._restore()
        self._write(7, self.mixer)
        self._fade()
        for n, card in enumerate(self.cards):
            reg = 1 + 2 * n
            if not card.b[2]:
                self._silence(card, reg)
            else:
                self._channel(card, reg)

    def _pause_tick(self) -> None:
        """0x806A: the pause's noise, over everything, the channels frozen."""
        self.touched = True
        self._write(7, 0xB8)
        if self.pause_first:
            self.pause_first = False
            self.pause_count = [7, 5, 0x10]
            self._volumes(0)
            self._write(10, 0)
            self._periods_ab(0xD6)
            return
        if not self.pause_count[0] and not self.pause_count[1]:
            return
        self.pause_count[1] -= 1
        if self.pause_count[1] <= 0:
            self.pause_count[2] -= 1
            if self.pause_count[2] <= 0:
                self._volumes(0)
                self._write(10, 0)
                self.pause_count = [0, 0, 0]
                return
            self.pause_count[1] = 6
            step = (self.pause_count[2] - 1) & 3
            self._periods_ab(self.data.byte(PAUSE_PERIODS + step))
            self.pause_volume = 0x0F
            self._volumes(self.pause_volume)
            return
        if self.pause_count[1] & 1:
            return
        self.pause_volume = max(self.pause_volume - 1, 0)
        self._volumes(self.pause_volume)

    def _periods_ab(self, low: int) -> None:
        self._write(0, low)
        self._write(2, low + 1)
        self._write(1, 0)
        self._write(3, 0)

    def _volumes(self, volume: int) -> None:
        self._write(9, volume)
        self._write(8, volume)

    def _restore(self) -> None:
        """0x80ED: what the pause's sound trod on, back from the cards."""
        self.touched = False
        for n, card in enumerate(self.cards):
            self._write(2 * n, card.b[0x0F])
            self._write(2 * n + 1, card.b[0x10])
            self._write(8 + n, card.b[8])

    def _fade(self) -> None:
        """0x813A."""
        if not self.fading:
            return
        self.fade_clock -= 1
        if self.fade_clock:
            return
        self.fade_clock = FADE_EVERY
        self.fade_step += 1
        if self.fade_step != FADE_STEPS:
            return
        self.fade_step = 0
        self.fading = 0
        first = self.cards[0]
        if first.b[2] == 0xA9:
            self.cards[2].b[2] = 0
        first.b[2] = 0
        self.cards[1].b[2] = 0

    # -- a channel (0x8181) --------------------------------------------------------

    def _channel(self, card: Card, reg: int) -> None:
        if card.b[2] & MELODY:
            self._melody_tick(card, reg)
            return
        card.b[0] = (card.b[0] - 1) & 0xFF
        if card.b[0]:
            return
        self._command(card, reg)

    def _command(self, card: Card, reg: int) -> None:
        """0x818D."""
        at = card.pointer
        value = self.data.byte(at)
        if value == _LOOP:
            self._loop(card, reg, at)
            return
        if value == _END:
            self._silence(card, reg)
            return
        if card.b[2] & MELODY:
            self._melody_command(card, reg, at)
            return
        volume = 0
        period = card.b[0x0F] | card.b[0x10] << 8
        if value & 0xF0 == 0x20:
            card.b[5] = value
            card.b[1] = self.data.byte(at + 1)
            at += 2
            if card.b[5] == 0x20:
                card.pointer = at
                self._note(card, reg, period, 0)
                return
            if card.b[5] & 0x08:
                self._write(12, self.data.byte(at))
                self._write(11, self.data.byte(at + 1))
                at += 2
        value = self.data.byte(at)
        if value & 0xF0 == 0x10:
            self._write(6, (value & 0x0F) * 2)
            at += 1
        value = self.data.byte(at)
        volume = value >> 4
        period = (value & 0x0F) << 8 | self.data.byte(at + 1)
        card.pointer = at + 2
        self._note(card, reg, period, volume)

    def _note(self, card: Card, reg: int, period: int, volume: int) -> None:
        """0x81F1 ("play the note")."""
        self._period(card, reg, period)
        card.b[0] = card.b[1]
        self._volume_and_mixer(card, reg, volume)

    def _loop(self, card: Card, reg: int, at: int) -> None:
        """0x8000: 0xFE, times, where."""
        times = self.data.byte(at + 1)
        done = (card.b[0x0A] + 1) & 0xFF
        if done == times:
            card.b[0x0A] = 0
            card.pointer = at + 4
        else:
            # `jp m`: past the times asked for, the count stops climbing.
            if not (done - times) & 0x80:
                done -= 1
            card.b[0x0A] = done & 0xFF
            card.pointer = self.data.word(at + 2)
        card.b[0] = (card.b[0] + 1) & 0xFF
        self._channel(card, reg)

    def _silence(self, card: Card, reg: int) -> None:
        """0x8206."""
        card.b[2] = 0
        card.b[0x0C] = 0
        card.b[5] = 0
        self._volume_and_mixer(card, reg, 0)

    def _period(self, card: Card, reg: int, period: int) -> None:
        """0x82F0: a sharp adds one to the period."""
        if card.b[0x0C]:
            period += 1
        period &= 0xFFFF
        card.b[0x10], card.b[0x0F] = period >> 8, period & 0xFF
        self._write(reg, period >> 8)
        self._write(reg - 1, period & 0xFF)

    def _mixer(self, card: Card, reg: int) -> None:
        """0x802A: bit 1 of byte 5 is the tone, bit 0 the noise; the mixer's
        bits are set to silence."""
        bit = {1: 1, 3: 2, 5: 4}[reg]
        flags = card.b[5] & 3
        mixer = self.mixer
        mixer = mixer & ~bit if flags & 2 else mixer | bit
        noise = bit << 3
        mixer = mixer & ~noise if flags & 1 else mixer | noise
        self.mixer = mixer & 0xFF
        self._write(7, self.mixer)

    def _volume_and_mixer(self, card: Card, reg: int, volume: int) -> None:
        """0x821F."""
        self._mixer(card, reg)
        volume_reg = 8 + (reg >> 1)
        if card.b[5] & 0x08:
            self._write(13, volume)
            volume = 0x10
        self._write(volume_reg, volume)

    # -- melodies (0x823B, 0x8255) -----------------------------------------------------

    def _melody_tick(self, card: Card, reg: int) -> None:
        card.b[0] = (card.b[0] - 1) & 0xFF
        if not card.b[0]:
            self._command(card, reg)
            return
        card.b[9] = (card.b[9] - 1) & 0xFF
        if card.b[9] != card.b[0]:
            card.b[9] = (card.b[9] - 1) & 0xFF
            self._decay(card, reg)
            return
        if card.b[0x0E] >= card.b[9]:
            self._decay(card, reg)

    def _decay(self, card: Card, reg: int) -> None:
        """0x8216: one step softer, down to nothing."""
        volume = card.b[8] - 1
        if volume < 0:
            return
        card.b[8] = volume
        self._volume_and_mixer(card, reg, volume)

    def _melody_command(self, card: Card, reg: int, at: int) -> None:
        while True:
            value = self.data.byte(at)
            if value & 0xF0 == 0xD0:
                card.b[0x0B] = value & 0x0F
                at += 1
                value = self.data.byte(at)
            if value >= 0xF0:
                card.b[7] = (value & 0x0F) + 2
                at += 1
                times = self.data.byte(at)
                card.b[0x0D], card.b[0x0E] = times >> 4, times & 0x0F
                at += 1
                value = self.data.byte(at)
            if value >= 0xE0:
                low = value & 0x0F
                at += 1
                if low & 0x08:
                    card.b[0x0C] = low
                    continue
                card.b[6] = low
                value = self.data.byte(at)
            break
        beats = value & 0x0F
        length = card.b[0x0B] * (beats + 1)
        card.b[1] = length & 0xFF
        card.pointer = at + 1
        note = value >> 4
        if note == REST:
            volume = 0
        else:
            volume = card.b[7]
            if self.fading:
                volume = max(volume - self.fade_step, 0)
        card.b[8] = volume
        card.b[0] = card.b[1]
        card.b[9] = (card.b[0x0D] + card.b[1]) & 0xFF
        # A rest (note 12) still writes a period, read past the table like
        # the rest of it: 0xC8, the low byte of the second sound's address.
        period = self.data.byte(NOTES + note)
        period <<= card.b[6]
        self._period(card, reg, period)
        card.b[5] = 2
        self._volume_and_mixer(card, reg, volume)


#: Per stage, (distance, music) rows: the music until that distance (0x7056,
#: bank 1). 0xFF is silence.
MUSIC_LISTS, MUSIC_END, SILENCE = 0x7056, 0xFFFF, 0xFF


class Music:
    """0x7003 ("see which music plays"): which tune the stretch of the stage
    wants, and the change to it -- the one playing fades out first."""

    def __init__(self, cart: Cartridge, driver: Driver) -> None:
        self.cart = cart
        self.driver = driver
        #: 0xE113: the tune waiting for the channel to fall silent.
        self.waiting = 0

    def _wanted(self, stage: int, distance: int) -> int:
        at = self.cart.word(1, MUSIC_LISTS + 2 * stage)
        while True:
            until = self.cart.word(1, at)
            if distance < until or until == MUSIC_END:
                return self.cart.byte(1, at + 2)
            at += 3

    def reset(self) -> None:
        """0x41EA, a stage built: 0xE113 and 0xE044 to zero."""
        self.waiting = 0
        self.driver.fading = 0

    def update(self, stage: int, distance: int, alive: bool, stopped: bool = False) -> None:
        if not alive or stopped:
            return
        playing = self.driver.playing(0)
        if self.waiting:
            if playing:
                return
            tune, self.waiting = self.waiting, 0
            if tune != SILENCE:
                self.driver.request(tune)
            return
        tune = self._wanted(stage, distance)
        if tune == playing:
            return
        self.waiting = tune
        if playing:
            self.driver.start_fade()
