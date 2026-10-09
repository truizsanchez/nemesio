# Nemesio

**Nemesis** (Konami, MSX, 1986) rebuilt in Python with [Pyxel](https://github.com/kitao/pyxel),
rule by rule: not an emulator and not a remake, but a reimplementation of the original's
own game logic, routine by routine, measured frame by frame against the real cartridge
running in an emulator until the two could not be told apart.

It plays from **your own cartridge**: the art, the terrain, the music and the tables are
read out of your ROM at start-up, and none of it is in this repository. Without a ROM it
plays one stage of its own, with art, map and music made for this project.

## How it was made

Nemesio is **AI-assisted**. It took four days (24-28 September 2026) and came to:

- the whole game with a cartridge, twelve stages, bosses, ending and second loop, with
  112 frame-by-frame comparisons against the original showing no differences (see
  [What is there](#what-is-there));
- about 7,600 lines of engine, 11,900 of game in all, 4,000 of tools and 2,000 of tests.

What kept it honest was measurement: a harness drives the original in openMSX and
compares its RAM with the engine's after every game frame, and a rule that read right
but measured wrong was treated as wrong. How that was done, and what the cartridge
turned out to contain, is told in [docs/ARTICLE.md](docs/ARTICLE.md).

## Running it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py --rom "Nemesis (Japan, Europe).rom"
.venv/bin/python main.py --rom <rom> --stage 2      # start on another stage (1-12)
.venv/bin/python main.py --free                     # the stage of its own, no cartridge
```

The ROM must be the 128 KB RC-742 dump, SHA-1 `e31ac6520e912c27ce96431a1dfb112bf71cb7b9`;
any other is refused. Without `--rom` the game looks for it, under any name, beside the
program and in the directory it was started from, and with none found it plays the free
stage.

| | |
|---|---|
| start (title) | SPACE, K or RETURN; DOWN/UP chooses one or two players |
| move | arrows or WASD |
| fire | SPACE or K |
| take the lit power-up | M, N or J |
| pause | F1 |
| continue after GAME OVER | F5 |
| quit | Esc |

## What is there

**With your cartridge**, the whole game: the twelve stages in the original's order, the
bonus stages and the hidden targets that open them, the core and the four other bosses,
the ending and the second loop; the waves, the cannons, the hatches, the power meter and
every weapon on it, one or two players, the words typed in pause, the attract screens,
and the music and effects through the original's own sound driver.

It is measured against the original running in openMSX with `tools/compare_play.py`:
ship, enemies, enemy shots, the map, the sound requests and what the screen shows. With
the original's randomness pinned on both sides (it rolls its dice from the Z80's `R`
register, which only an emulator can reproduce), 112 comparisons across all the stages,
both loops, the bosses and the ending show **no differences**. Two things are
deliberately not modelled: `R` itself and the Z80's own timing (a crowded frame running
late). The sound registers match; the sound chip itself is approximated.

**Without it**, one stage made for this project, played by the rules of the original's
first: volcanic ground and firs, cannons and hatches, the rock with its missile
launchers, the volcanoes erupting, and the core; then a short ending of its own and the
title. Its art is "low poly": flat facets lit from the top left, within the TMS9918's two
colours per pixel row.

## The free stage's files

Everything the game plays without a cartridge is in `assets/free/`, as files meant to be
edited:

| file | what it is |
|---|---|
| `stage1.chars.png` | the stage's characters: 256x192, three thirds of 256 characters of 8x8; at most two colours in each pixel row of a character (the TMS9918's rule) |
| `stage1.sprites.png` | the stage's 64 sprite patterns of 16x16, one colour each (the tables give it) |
| `stage1.txt` | the map, 22 rows, one text character per column |
| `stage1.json` | the map's legend, its distances, which of the original's stages it plays like (`"rules"`), its waves, cannons, hatches, crystal and boss, and under `"tables"` its enemies |
| `tables.json` | what any stage shares: the ship, the blasts, the hatches, and the `"layout"`: which characters and patterns the rules draw with |
| `title.png` | the title screen, as a picture |
| `text.json` | the font, the labels under the play and the messages |
| `sounds.json` | the sound effects (steps of tone or noise) and the music (notes) |
| `chars.txt` | which character and which sprite pattern is what |
| `LICENSE` | CC BY 4.0 |

The pictures use the TMS9918's sixteen colours (any other is taken to the nearest).
Characters below 0x77 are solid, the ship and its shots meet them; from 0x77 on they are
scenery.

```bash
.venv/bin/python main.py --check-assets                      # what is wrong in them, if anything
.venv/bin/python tools/make_free_assets.py                   # write them again from the generator
.venv/bin/python tools/make_free_assets.py --out /tmp/free   # ...elsewhere, to compare
```

`--check-assets` says, a line each, what the game would trip on: a character row with
more than two colours, a map letter missing from the legend, a character or sprite the
tables use and the pictures leave empty, a letter the font lacks, a sound step out of
range. With assets it cannot play, the game shows the same list in its window.

More stages can be added: a `stage2.txt` and `stage2.json` beside the first are played
after it, each by the rules of a later stage of the original (stage 2's end in a rain of
stones, 3's heads, and so on); after the last comes the ending.

## Building a single executable

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python tools/build_exe.py      # dist/nemesio-<version>-<system>-x64.zip
```

The zip holds one file, `nemesio` (or `nemesio.exe`): no Python, no install. Put your ROM
beside it and run it; without one it plays the free stage. The free assets go beside the
binary too, and the ones there win over the copy inside it, so they can be edited. The
Windows build is made by the `release` workflow on a Windows runner; no ROM goes near it.
The zip also carries the licence.

## For developers

- [docs/ARTICLE.md](docs/ARTICLE.md): the cartridge, the engine and how it was measured.
- [docs/TOOLS.md](docs/TOOLS.md): openMSX, the harness and the reference disassembly.
- [AGENTS.md](AGENTS.md): the code's layout, its rules and the measuring gotchas.

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q     # no window and no cartridge needed
.venv/bin/python -m mypy
```

The tests never read a ROM: they build cartridge-shaped bytes of their own.
The `gate` workflow runs the suite, mypy, pyflakes and the free self-test on every pull
request and push to `main`; the comparisons against the original need a ROM and openMSX,
and are run by hand.

## Legal

Nemesio is a fan-made study and preservation project. It is not affiliated with,
endorsed by or connected to Konami. *Nemesis* (© 1986 Konami) and *Gradius* are trademarks of
Konami Digital Entertainment; they are named here only to say which game the engine plays.

**No ROM, graphics, music or maps of the cartridge are in this repository or in its
builds.** They are read at start-up from a ROM the player supplies, checked by its SHA-1.
What the repository does hold of the original is numbers: the engine's rules carry the
original's own values (speeds, timings, positions, a few short tables of sprite numbers),
each with the cartridge address it was read at, and some tests use short fragments of the
original's records as fixtures. Please do not open issues asking for ROMs, and do not
attach them anywhere in this project.

The engine is a reimplementation written from a study of the original's behaviour, with
the help of [antxiko's Nemesis disassembly](https://github.com/antxiko/Nemesis-disassembly)
(MIT for its tools and notes); the addresses in the code point into that listing.

## Licence

- The code: [MIT](LICENSE).
- The free assets (`assets/free/`: pictures, map, tables, texts, music and sounds):
  [CC BY 4.0](assets/free/LICENSE).
