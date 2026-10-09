# nemesio — working notes

Nemesis (Konami, MSX, 1986, RC-742) rebuilt in [Pyxel](https://github.com/kitao/pyxel):
256x192, the TMS9918's sixteen colours. **The engine is a reimplementation of the
original's, rule by rule**, in integers, in the original's order, and every number in
it has the address it came from. The player's own cartridge (`--rom`) supplies the art,
the terrain, the tables and the music; none of those is in this repo (the rules'
numbers are, each with its address).

These are the project's working notes, for whoever works on it, people or AI
assistants. Keep them true: when a rule or a trap is learned, it goes here.

How it was built and measured: `docs/ARTICLE.md`; the emulator and the harness:
`docs/TOOLS.md`. With no cartridge the game plays the free assets' one stage
(`assets/free/`, `--free`), then a short ending and the title.

## The reference

`../Nemesis-disassembly`, cloned beside this checkout ([antxiko](https://github.com/antxiko/Nemesis-disassembly), MIT for its tools and notes) is a commented,
byte-exact disassembly **of exactly this ROM** (reassembled here: 0 bytes differ).
Every "bank:address" in this code is an address in that listing. Two cautions:
its comments occasionally swap X and Y (the ship's card is Y at 0xE204, X at 0xE206),
and some labels are one stage off (the walls at bank 2, 0x9906). Its labels and
comments are in Spanish: the code names a routine by its address, with the label
translated in quotes where it helps ("end the stage" is `acaba_la_fase`).

## Layout

```
main.py            the window, the keys, --selftest, --shot (headless PNG), --free
game/content.py    where a game's content comes from: RomContent (the cartridge)
                   or FreeContent (game/free); the host asks it, not the ROM
game/vdp.py        the TMS9918's 16 KB as the cartridge lays it out (not the BIOS's)
game/engine/       the original's rules. No Pyxel, no cartridge
  original.py      every number the engine runs on, each with its address
  terrain.py       the 22x32 map buffer (0xED00) and the Terrain protocol
  tables.py        the shape of the cartridge's tables the engine is handed
  layout.py        which characters and sprite patterns the rules draw with
                   (the cartridge's by default; the free assets hand their own)
  stages.py        what a stage's rules key off: its end's distances, its walls
                   and breakable blocks, the hidden targets (the same)
  scroll.py        distance, the rotating bit, a column in (0x466A)
  ship.py          pad, speed, box, map collision, the explosion (bank 2)
  shots.py         the nine weapon slots: normal, double, laser, missile
  options.py       the options' eight-position queues (0x9C41)
  objects.py       the 32-byte object slots, their movers and builders,
                   blasts, capsules, enemy shots and their aim
  blasts.py        the background blasts (0xE800), drawn into the map
  waves.py         the section generators, the six-in-a-row wave, cannons,
                   the bonus stages' prizes (0x5D41)
  background.py    hatches (0xE700) and stage 3's moai emplacements
  ending.py        how each stage ends (0x6CCD): stages 1-4's bosses, the
                   core, and the dispatch to the others below
  flocks.py        stage 5's two flocks (types 0x1D, 0x1E, 0x1F)
  nuclei.py        stage 6's nuclei and their arms (boss 2)
  eye.py           stage 7's eye (boss 3)
  fortress.py      stage 8's claws, gate and anchors (boss 4)
  fade.py          the screen eaten dark (0xA6C0), as VRAM writes
  target.py        the hidden target that opens the bonus stages (0xB042)
  words.py         the words typed in pause (0x50C9)
  play.py          a game frame, in the original's order (0x4532)
game/front.py      the screens around a play, as a model
game/screen.py     what the VDP shows in play: names as sent, sprites a frame behind
game/attract.py    the Konami logo, the picture, the demo's recorded pad
game/finale.py     the game's ending after stage 8 (0x4AC0, steps 1-9)
game/rom/          the player's cartridge, read
  cartridge.py     identified by SHA-1; banks and the Konami4 windows
  rle.py           the graphics format (0x49B9)
  graphics.py      a stage's characters and sprite patterns (0x422A)
  stage.py         a stage's script, pieces, range, checkpoint (0x46AE)
  band.py          the band under the view (0x5632)
  screens.py       the title, GAME OVER (0x5B77)
  tables.py        the engine's tables, read out of the cartridge
  sound.py         bank 7's sound driver into PSG registers; the stage music
game/free/         the game with no cartridge: assets/free read into the same
                   shapes (Terrain, Tables, VRAM) and texts and sounds written
                   into an in-memory cartridge-shaped image (cart.py) for the
                   host's readers; PNG in and out with the standard library;
                   check.py (--check-assets); finale.py, the short ending after
                   the last free stage, before the title
game/render/       the only Pyxel in game/: the palette, VRAM drawn as a tilemap,
                   the PSG heard through Pyxel's channels (audio.py)
tools/
  harness/omsx.py  openMSX under -control stdio, paused between calls, no GPU
  harness/tms.py   a VRAM dump drawn as the TMS9918 draws it
  check_rom.py     graphics and map against the cartridge running
  rom_map.py       how much of the cartridge game/ cites (by the listing's
                   routines and data ranges) and, with --rom, reads
  make_free_assets.py  writes assets/free again, drawn from shapes
  free_assets/     its code: common.py (what any stage has), stages/stage1.py
                   (the stage's plan, colours, enemies and boss), maps.py (the
                   map, and the crystal's rock), bosses.py, music.py
  build_exe.py     the game frozen into one executable and zipped (PyInstaller);
                   --with-rom / --add-rom make a copy with your ROM in it, for
                   your own use only: never published
  compare_play.py  the engine against the original, game frame by game frame
                   (--stage N, --round N, --players 2, --objects/--types, --nuclei,
                   --shots, --heads, --sprites, --ship-sprites, --finale, --sounds,
                   --psg, --map, --screen, --band/--score N, --no-chance, --immortal,
                   --machine C-BIOS_MSX1 for the 60 Hz rhythm the engine keeps;
                   "continue" in a script is F5)
tests/             the suite: no window, no cartridge, cartridge-shaped bytes
assets/free/       the free assets: the game's own, committed (see README)
```

## Rules

1. **Pyxel stays at the edges**: `main.py` and `game/render/` only.
2. **No number in `game/engine/` outside `original.py`**, and each there says where
   it is in the cartridge.
3. **No ROM, dump or picture of the cartridge is committed**: they live outside the
   repository. The rules' numbers are the original's, each with its address. Tests build
   cartridge-shaped bytes. `assets/free/` is the
   game's own and is committed: no picture, map or sound in it is copied out of the
   cartridge (the mathematics is worked out, the rest drawn and written; a few small
   tables share many values with the original's), and the characters and
   patterns the rules draw with are the free assets' own (`Layout`).
4. **Measure before you argue.** `tools/compare_play.py` and `tools/check_rom.py` are
   the arbiters; a rule that reads right and measures wrong is wrong.

## Commands

`<rom>` is your RC-742 ROM, kept outside the repository.

```bash
.venv/bin/python -m pytest tests -q
.venv/bin/python -m mypy
.venv/bin/python -m pyflakes game tools tests main.py
.venv/bin/python main.py --rom <rom>
.venv/bin/python main.py --rom <rom> --selftest
.venv/bin/python main.py --free --selftest
.venv/bin/python main.py --check-assets
.venv/bin/python tools/make_free_assets.py
.venv/bin/python tools/check_rom.py --rom <rom>
.venv/bin/python tools/rom_map.py --rom <rom>
.venv/bin/python tools/compare_play.py --rom <rom>
.venv/bin/python tools/build_exe.py --with-rom <rom>
```

The public zip never carries the ROM, and the `release` workflow (the Windows `.exe`)
never sees it: the `-with-rom` zip is made here, and lands in the ignored `dist/`.

## Measuring, and what bit before

- `compare_play.py --machine C-BIOS_MSX1`: the 60 Hz machine, whose rhythm (two
  interrupts a game frame) is the engine's. On the 50 Hz default some things (sound
  waits, stage 5's start) look a frame or more off when they are not.
- `--stage N` starts the original at any stage, 9-12 included (a breakpoint at 0x414B
  writes 0xE061); the engine's frame counter starts at the original's 0xE003, since
  every one-in-N rule keys off it. `--round N` does the same with 0xE06A (1 is the
  second loop), before 0x41AC reads it for the difficulty.
- `--no-chance DIR` turns every `ld a,r` into `xor a / nop` in a copy of the ROM and the
  engine's chance into zeros: with it (and `--immortal DIR`) every stage, boss and stage
  change measures identical. Without it, what differs is R's dice (shot delays, aim at
  difficulty >= 7, walkers' walks, blinks), not rules.
- A stage change (0x6D53 -> 0x4100) goes on with the game frame, and keeps 0xE100-0xE2FF;
  a new life (0x414B) clears it. A frame apart after a stage change is a rule missing.
- How long a game frame is: `run_original` also returns each game frame's interrupts,
  exact (a breakpoint on the interrupt at 0x4028 counted, a watchpoint on 0xE003's
  write). Half-frame sampling guesses them wrong by one. Some lengths are rules or
  VRAM work and the engine keeps them (a stage's building, the fade's passes, the
  finale); game frames that run into a third interrupt with much on screen, or into
  only one with nothing, are the Z80's time and are not modelled.
- `--map` compares the 0xED00 buffer as each game frame leaves it: what is drawn into the
  map and kept or put back (0x6893/0x6983, 0x6936, 0x68FB) shows only there.
- `--screen` compares the VRAM (names, sprite table, star rows) with what `game/screen.py`
  says is shown; the window draws from the same, so it measures what the player sees.
- `--sounds` compares the requests each game frame makes (0x4A22), `--psg` the PSG's
  registers; both tick the engine's driver with the original's measured interrupts, so
  what they measure is the rules that ask for sounds, not the Z80's time.
- Scratch probes: `OpenMSX` + `half_frame()`, sampling only when 0xE005 (the lock) is 0;
  watchpoints (`debug set_watchpoint write_mem`) answer "who wrote this" fastest.
  A hung openMSX: `kill -9 $(pgrep -x openmsx)`, never `pkill -f`.
- The listing's comments and labels are wrong now and then (X/Y swapped, a "stage 6" that is
  stage 7, "records" that is the demo's picture, box widths): the code decides, and a
  measurement decides between readings.
