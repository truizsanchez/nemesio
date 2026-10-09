# Tools

Nothing needs root. What it takes to measure the original and to work here.

## The game (Python)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
```

## openMSX, C-BIOS, pasmo, z80dasm -- without root

They are in Ubuntu's repositories (openmsx 21.0, cbios 0.29a), but they need not be
installed with apt: the `.deb`s are downloaded and unpacked under `~/.local/opt/msx`.

```bash
mkdir -p ~/.local/opt/msx/debs && cd ~/.local/opt/msx/debs
apt-get download openmsx openmsx-data cbios pasmo z80dasm libglew2.2 libsdl2-ttf-2.0-0
for d in *.deb; do dpkg -x "$d" ..; done
# systemroms/'s links point at /usr/share/cbios: make them again, locally
cd ../usr/share/openmsx/systemroms && for f in ~/.local/opt/msx/usr/share/cbios/*.rom; do ln -sf "$f" .; done
```

and a wrapper, `~/.local/opt/msx/openmsx` (linked from `~/.local/bin/openmsx`):

```sh
#!/bin/sh
M=$HOME/.local/opt/msx
export LD_LIBRARY_PATH=$M/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export OPENMSX_SYSTEM_DATA=$M/usr/share/openmsx
exec $M/usr/bin/openmsx "$@"
```

With `sudo apt install openmsx cbios pasmo z80dasm` it works the same and none of the
above is needed.

## The harness: `tools/harness/`

- `omsx.py` -- openMSX under `-control stdio`, paused between calls. `frames(n)` runs
  exactly n VDP frames; `down/up/tap` press the keyboard matrix; `peek`, `memory`,
  `vram`, `vdp_registers` read.
- `tms.py` -- the VRAM as a picture (Graphics II and sprites, four a line). It is how
  the original is "photographed": exact and immediate.

Traps already paid for:

- Under `-control stdio` the machine starts **switched off**: `set power on`.
- With no renderer, `after frame` never fires and counting frames hangs. The harness
  sets `SDLGL-PP` with `SDL_VIDEODRIVER=offscreen`.
- openMSX's `screenshot` with the machine paused returns the last thing it painted,
  not the current frame. Hence `tms.py`.
- The pause key is F1 (row 6, bit 5), though the listing calls it GRAPH.

## The reference disassembly

[`antxiko/Nemesis-disassembly`](https://github.com/antxiko/Nemesis-disassembly) (MIT for
its tools and notes), cloned **outside** the repository, beside it: `../Nemesis-disassembly`.
Reassembled with pasmo, its 16 banks give **the RC-742 ROM byte for byte** (measured: 0
differences), so every address in its listing holds as it is for the cartridge.
`tools/rom_map.py --listing` reads it.

## Measuring

`tools/compare_play.py --rom <your ROM>` runs the original in openMSX and the engine side
by side, game frame by game frame; its options are in `AGENTS.md`, "Measuring".
