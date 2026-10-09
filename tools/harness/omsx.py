"""Drive the original in openMSX, headless, from Python.

Run the cartridge with nobody at the keyboard, press what a test says to
press, and read the machine's memory and VRAM frame by frame. Nothing in `game/` imports this; it is how the
numbers `game/engine/original.py` carries get measured.

openMSX is driven over `-control stdio`: XML commands in, `<reply>` out. The
emulation is kept **paused between calls**, and `frames(n)` runs exactly n VDP
frames and pauses again, so a measurement is a function of the inputs and not of
how fast the host happened to be. Throttle is off: a frame costs what the host
takes to emulate it, not a fiftieth of a second.

The machine is C-BIOS (free, shipped with openMSX), European by default -- a
50 Hz VDP, as the European release was played. `machine="C-BIOS_MSX1"` is the
60 Hz one. Nemesis runs on either: it asks the BIOS nothing it lacks.

The keys, as the cartridge reads them (bank 0, 0x577D): the arrows and SPACE
from row 8 of the matrix, and M or N from row 4 as the second button. They land
in 0xE009 as the joystick's bits: 0 up, 1 down, 2 left, 3 right, 4 fire,
5 power-up. 0xE008 holds the ones that went down this frame.

    from tools.harness.omsx import OpenMSX
    with OpenMSX(rom) as m:
        m.frames(300)
        m.tap("space")
        print(m.peek(0xE061))
"""

import html
import os
import re
import shutil
import subprocess

#: The wrapper that sets the library path and the system ROMs of the rootless
#: install (see docs/TOOLS.md).
OPENMSX = shutil.which("openmsx") or os.path.expanduser("~/.local/opt/msx/openmsx")

#: row, bit mask of each key the cartridge reads.
KEYS = {
    "space": (8, 0x01),
    "left": (8, 0x10),
    "up": (8, 0x20),
    "down": (8, 0x40),
    "right": (8, 0x80),
    "m": (4, 0x04),
    "n": (4, 0x08),
    # Row 6 bit 5 is F1 on the standard matrix; the cartridge's pause key
    # (0x44E7). The listing's comment calls it GRAPH, which is bit 2.
    "pause": (6, 0x20),
    "return": (7, 0x80),
    # Row 7 bit 1: F5, CONTINUE on the GAME OVER screen (0x54F3).
    "f5": (7, 0x02),
}

_REPLY = re.compile(r'<reply result="(ok|nok)">(.*?)</reply>', re.S)

# Runs the emulation up to an absolute emulated time and pauses there. Frames
# are counted as multiples of the VDP's frame duration from power-on, so every
# `frames()` ends at the same point of a frame, and no renderer is needed --
# which matters: see `OpenMSX.__init__`.
_TCL_SETUP = r"""
proc nem_until {t} {
    set ::nem_done 0
    after time [expr {$t - [machine_info time]}] {set ::pause on; set ::nem_done 1}
    set ::pause off
}
"""


class OpenMSXError(RuntimeError):
    """openMSX answered `nok`, or went away."""


class OpenMSX:
    def __init__(self, rom: str, machine: str = "C-BIOS_MSX1_EU",
                 renderer: bool = False) -> None:
        """Boot `rom`, paused at time zero.

        **No GPU by default.** With SDL's offscreen driver openMSX still opens
        the graphics card, and when the host's display is asleep the NVIDIA
        driver holds its modeset lock and openMSX blocks in the kernel,
        unkillable. So SDL gets the dummy driver and there is no renderer.
        `renderer=True` is only for `screenshot`, with a display awake;
        `vram()` + `tools/harness/tms.py` is the picture otherwise.
        """
        env = dict(os.environ, SDL_AUDIODRIVER="dummy",
                   SDL_VIDEODRIVER="offscreen" if renderer else "dummy")
        self.proc = subprocess.Popen(
            [OPENMSX, "-machine", machine, "-carta", rom, "-control", "stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=env, text=True, bufsize=1)
        self._buffer = ""
        self._send_raw("<openmsx-control>\n")
        self.tcl("set pause on")
        self.tcl("set throttle off")
        self.tcl("set mute on")
        self.tcl(_TCL_SETUP)
        if renderer:
            self.tcl("set renderer SDLGL-PP")
        # Under `-control stdio` the machine starts switched off, and time
        # does not move until something switches it on.
        self.tcl("set power on")
        #: Seconds of emulated time a frame takes: 1/50-ish on a PAL machine.
        self.frame_duration = float(self.tcl("vdp::get_frame_duration"))
        self.frame = 0

    # -- the protocol -------------------------------------------------------

    def _send_raw(self, text: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(text)
        self.proc.stdin.flush()

    def tcl(self, command: str) -> str:
        """Run one Tcl command and return its result; raise if it failed."""
        self._send_raw("<command>%s</command>\n" % html.escape(command, quote=False))
        assert self.proc.stdout is not None
        while True:
            match = _REPLY.search(self._buffer)
            if match:
                self._buffer = self._buffer[match.end():]
                result = html.unescape(match.group(2))
                if match.group(1) == "nok":
                    raise OpenMSXError("%s -> %s" % (command.strip()[:80], result))
                return result
            chunk = self.proc.stdout.readline()
            if not chunk:
                raise OpenMSXError("openMSX went away")
            self._buffer += chunk

    # -- time ---------------------------------------------------------------

    def frames(self, n: int = 1) -> None:
        """Emulate exactly `n` frames, then pause."""
        if n <= 0:
            return
        self.frame += n
        self.tcl("nem_until %.12f" % (self.frame * self.frame_duration))
        while self.tcl("set ::nem_done") != "1":
            pass

    def half_frame(self) -> None:
        """Emulate half a frame: for sampling between the game frames that
        run long, which a frame boundary always lands in the middle of."""
        self._half = getattr(self, "_half", 0) + 1
        self.tcl("nem_until %.12f" % ((self.frame + self._half / 2) * self.frame_duration))
        while self.tcl("set ::nem_done") != "1":
            pass
        if self._half == 2:
            self._half = 0
            self.frame += 1

    # -- input --------------------------------------------------------------

    def down(self, *keys: str) -> None:
        for key in keys:
            row, mask = KEYS[key]
            self.tcl("keymatrixdown %d 0x%02X" % (row, mask))

    def up(self, *keys: str) -> None:
        for key in keys:
            row, mask = KEYS[key]
            self.tcl("keymatrixup %d 0x%02X" % (row, mask))

    def tap(self, key: str, hold: int = 4, then: int = 10) -> None:
        """Press, hold `hold` frames, release, run `then` more. The cartridge
        sees a key only when it changes, so a tap has to be long enough to be
        read and released long enough to be seen going up."""
        self.down(key)
        self.frames(hold)
        self.up(key)
        self.frames(then)

    # -- reading ------------------------------------------------------------

    def peek(self, address: int) -> int:
        return int(self.tcl("debug read memory %d" % address))

    def peek16(self, address: int) -> int:
        return self.peek(address) | self.peek(address + 1) << 8

    def vram(self) -> bytes:
        """The 16 KB of VRAM, byte for byte."""
        out = bytearray()
        for start in range(0, 0x4000, 0x1000):
            out += self._hex_block("VRAM", start, 0x1000)
        return bytes(out)

    def _hex_block(self, debuggable: str, start: int, size: int) -> bytes:
        """A block read through Tcl as hex, which survives the XML channel
        whatever the bytes are."""
        text = self.tcl("binary encode hex [debug read_block {%s} %d %d]"
                        % (debuggable, start, size))
        return bytes.fromhex(text)

    def memory(self, start: int, size: int) -> bytes:
        return self._hex_block("memory", start, size)

    def psg_registers(self) -> bytes:
        return self._hex_block("PSG regs", 0, 16)

    def vdp_registers(self) -> list[int]:
        return list(self._hex_block("VDP regs", 0, 8))

    def screenshot(self, path: str) -> None:
        """A PNG of what openMSX drew (needs `renderer=True`). 320x240 with the
        border; `raw` so no OSD is in it."""
        self.tcl("set throttle on")
        self.tcl("screenshot -raw {%s}" % os.path.abspath(path))
        self.tcl("set throttle off")

    # -- lifetime -----------------------------------------------------------

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.tcl("exit")
            except OpenMSXError:
                pass
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def __enter__(self) -> "OpenMSX":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
