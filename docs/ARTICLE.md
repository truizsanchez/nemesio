# Nemesis, rule by rule

*How a 1986 MSX cartridge was read, mapped and rebuilt in Python, AI-assisted, and
measured frame by frame against the original until the two could not be told apart.*

---

## 1. What this is

**Nemesis** (Konami, 1986, catalogue number RC-742) is the MSX version of Gradius: a
horizontal shooter with twelve stages, a power-up meter and options that trail the
ship. **nemesio** rebuilds it in [Pyxel](https://github.com/kitao/pyxel), a small
Python engine for retro games, at the original's 256x192 and with the TMS9918's
sixteen colours.

Most remakes redraw a game and tune it until it feels right. Emulators run the
original's machine code. nemesio does neither. **The engine is a reimplementation of
the original's rules, one routine at a time, in integers and in the original's order,
and every number in it carries the cartridge address it came from.** A rule that reads
right but measures wrong against the original running in an emulator is treated as
wrong.

Two consequences shape the whole project:

- **No ROM, art, music or maps of the cartridge are in the repository.** The engine
  holds the rules, with the original's own numbers and each one's address; the art, the
  terrain, the music and the tables are read at start-up from the player's own ROM
  (`--rom`), and the ROM is checked by SHA-1 before a byte of it is trusted. The tests
  build cartridge-shaped bytes of their own, a few with short fragments of the
  original's records.
- **The measure is the original.** A harness drives openMSX, a cycle-exact MSX
  emulator, headless and paused between calls, and compares its RAM with the engine's
  after every game frame. At the time of writing, with the original's randomness pinned
  (section 12), 112 comparisons spanning all twelve stages, both loops, the bosses, the
  ending, the sound requests, the map buffer and what the VDP shows **differ in zero
  frames**.

None of this would have been possible without Antxiko Gorjón's
[Nemesis disassembly](https://github.com/antxiko/Nemesis-disassembly): a commented,
byte-exact listing of this very ROM (reassembled here: 0 bytes differ in 131,072). Every
"bank:address" in this article and in the code is an address in that listing.

The work was AI-assisted and took four days, 24 to 28 September 2026: about 7,600 lines
of engine, 1,400 of cartridge readers, and 145 tests. Section 16 says how it was made.

---

## 2. The machine in five minutes

| part | what it gives the game |
|---|---|
| **Z80A** at 3.58 MHz | the CPU. No multiply, no divide, and no random number instruction; the `R` register (DRAM refresh) counts instructions and doubles as a dice. |
| **TMS9918A** VDP | 16 KB of its own video RAM, reached only through two I/O ports. Graphics II mode: a 32x24 grid of 8x8 characters, each row of each character with two colours. 32 sprites, 16x16, one colour each, **at most four on a scanline**. **No scroll registers.** One interrupt per video frame: 60 Hz on a Japanese machine, 50 on a European one. |
| **AY-3-8910** PSG | three square-wave channels, a noise generator and an envelope. |
| **Konami mapper** (no SCC) | 128 KB seen through a 32 KB window: 0x4000-0x5FFF is fixed, and 0x6000, 0x8000 and 0xA000 each page in any 8 KB bank written to that address. |

The two limits that shape Nemesis most are the missing scroll register and the four
sprites per line. You will see both answered below: the screen scrolls by whole
characters, redrawn from a map in RAM, and the sprite table is rotated every frame so the
flicker is shared out.

---

## 3. The cartridge's map

### Sixteen banks, six with code

The ROM is sixteen banks of 8 KB. Bank 0 is nailed to 0x4000; each of the others
always runs in the same one of the three switchable windows, which is why the listing
can give every bank a single `org`.

| bank | window | what it holds |
|---|---|---|
| 0 | 0x4000 (fixed) | the interrupt and the main loop, the modes (title, demo, play, game over), the scroll, the VDP, the sprite upload, the sound requests, the score, the pause words |
| 1 | 0x6000 | the enemy engines, the collisions, the stage endings, the core and the nuclei |
| 2 | 0x8000 | the ship, its weapons, the options, the map collisions, the other five bosses, the aiming tables |
| 3 | 0xA000 | the power-up meter, the laser, twenty of the thirty-one enemy types, the waves, the screen fade, the hidden target |
| 4, 5, 6 | 0x6000/0x8000/0xA000 | the stages' graphics, compressed (6 is empty) |
| 7 | 0x8000 | the sound driver, and the first 7 KB of music and effects |
| 8 | 0xA000 | the rest of the sound data |
| 9, 10 | 0x8000/0xA000 | the title and the ending's pictures; bank 10 carries a little sprite engine of its own |
| 11, 12 | 0x8000/0xA000 | the map pieces, the stage scripts, the demo's recorded joystick |
| 13, 14, 15 | — | 0xFF from end to end: never paged in |

Measured on the listing, byte by byte:

| | bytes | share |
|---|---:|---:|
| traced code | 25,471 | 19.4 % |
| data with a name and an explanation | 57,382 | 43.8 % |
| 0xFF filler | 48,219 | 36.8 % |
| **total** | **131,072** | 100 % |

More than a third of the chip is empty: four whole banks and the tails of five more.
Only 19 % of it is code.

### The video RAM, upside down

The eight bytes at 0x575A are written to VDP registers 0-7 at boot, and they put
nothing where the MSX BIOS puts it:

| table | BIOS default | Nemesis |
|---|---|---|
| character patterns | 0x0000 | **0x2000** |
| character colours | 0x2000 | **0x0000** |
| names (the 32x24 screen) | 0x1800 | **0x3800** |
| sprite attributes | 0x1B00 | **0x3B00** |
| sprite patterns | 0x3800 | **0x1800** |

Everything the cartridge draws goes through one small decompressor at 0x49B9, whose
format is the reverse of the usual one: bit 7 set means *copy the next N-0x80 bytes as
they are*, clear means *repeat the next byte N times*, 0x80 is a new VRAM address and
0x00 ends the block. The stage characters are loaded by six-byte records (which thirds,
where the patterns are, which character to start at, where the colours are), and then
two more lists **mirror** part of what was loaded, bit-reversed for a horizontal flip
or byte-reversed for a vertical one, so half the terrain is made from the other half.

### The RAM the game lives in

The MSX1 gives a cartridge 16 KB of RAM at 0xC000-0xFFFF, and Nemesis keeps its world
in the top 4 KB. The engine models these structures by their original addresses (the
code cites 181 RAM addresses in all):

| address | size | what |
|---|---|---|
| 0xE002 | 1 | game flags: a game running, two players, whose turn |
| 0xE003 | 1 | the game-frame counter; every "one frame in N" rule keys off it |
| 0xE005 | 1 | the lock that keeps a slow game frame from being re-entered |
| 0xE010, 0xE021, 0xE032 | 3 x 0x11 | the sound driver's three channel cards |
| 0xE053 | 4 | the high score |
| 0xE060-0xE071 | | lives, stage (0xE061), scroll bit (0xE062), distance (0xE063), difficulty, round (0xE06A) |
| 0xE100-0xE1FF | | the play's state: the scroll moved, the limit, the music waiting (0xE113), the meter (0xE130), the boss (0xE151/0xE152), the sprite rotation (0xE17F), the screen stopped (0xE1C0), the ending (0xE1D1), the typed words (0xE1E8) |
| 0xE200 | 0x20 | the ship's card: row at 0xE203/0xE204, column at 0xE205/0xE206, all 8.8 fixed point |
| 0xE220, 0xE240 | 2 x 0x20 | the two options, each with an eight-position queue (0xE230, 0xE250) |
| 0xE260-0xE2FF | 9 x 0x10 | the nine weapon slots |
| 0xE300 | 12 x 0x20 | **the twelve object slots**: enemies, capsules, blasts |
| 0xE500 | 10 x 0x20 | the enemy shots |
| 0xE700 | 8 x 8 | the background objects: hatches, stage 3's moai, stage 5's walls and turrets |
| 0xE780-0xE7FF | | the boss's pieces |
| 0xE800 | 4 x 8 | the background blasts |
| 0xE900 | 4 x 3 | the groups a wave is counted in |
| 0xEA00, 0xEA80 | | map cells saved from under the boss's pieces and the blasts |
| 0xEB00 | | stage 1's crystal |
| 0xEC80 | 0x80 | the sprite buffer, 32 entries of four bytes |
| **0xED00** | 22 x 32 | **the map**: the screen's characters, in RAM |

The whole game is those tables. Section 4 onwards is about the code that turns them
over, one game frame at a time.

### Things in the cartridge that are not for this cartridge

Three findings from the listing, and one from this project's measure, are worth a
stop before the engine:

- **A header for another cartridge.** Right behind the standard `AB` header, 21 bytes
  at 0x4010 that no instruction ever reads. They are for Konami's *Game Master*, a cheat
  cartridge in the other slot: they tell it where this game keeps its state, its stage,
  its lives and its scores (identified by Néstor Sancho, format documented in Ricardo
  Bittencourt's disassembly of the Game Master).
- **A search for TwinBee.** At boot, 0x505A reads six bytes backwards from 0xBFFF of
  every other slot and compares them with 0x50AE: the tail of the hidden Konami mark of
  RC-740, *TwinBee*. If it is plugged in, 0xF0F4 is set and the game loads extra
  graphics: an 811-byte block in bank 5 (0x98B9-0x9BE3) that nothing else reads.
  nemesio does not implement this, and it is the largest piece of real data the port
  never touches.
- **The hidden mark.** At the end of bank 3, eleven bytes spell RC-742 and, in
  katakana, グラディウス, *Gradius*: the signature Konami hid in its cartridges (found by
  Manuel Pazos). The cartridge's own name for itself is the Japanese one.
- **Dead code, labelled as such.** The listing names what no path reaches:
  83 bytes at 0x4E3B that disassemble cleanly but follow a `ret`, a dead `jp` at 0x40FD,
  a dead VRAM read at 0x4956, and a handful more.

---

## 4. How much of it is understood

The listing already explains every byte: **100 %** of the cartridge is either traced
code or inside a named data range, and 23.4 % of its instructions carry a comment. That
answers "is it identified". nemesio asks a different question: **how much of it has
been rebuilt?** `tools/rom_map.py` measures it two ways, without reading the ROM's
bytes into the repository.

**Code, by citation.** Every `0xNNNN` in `game/` is a claim that "this rule is that
code". The tool resolves each to a bank (by a "bank N" written next to it, by the
file's bank map, or by the window's code bank, and only where the address lands on an
instruction, a label or a data range), then counts which routines contain a cited
address. A routine here is an entry point, meaning a `call` target, a dispatcher
table's target or one of the listing's cross-bank entries, up to the next entry.

**Data, by use.** With `--rom`, the tool loads everything the game takes from the
cartridge through a reader that notes each offset: every stage's map, column by
column; every graphics load; the tables; the title, game-over and ending screens; the
demo's recordings; the finale in all five rounds, in both languages; and all 79 sound
entries played out, each in both of its formats. It keeps only the offsets, as counts.
Data the engine carries as its own code, such as a dispatcher's jump table or the pad's
speed table, counts as used when it is cited.

| bank | code: routines named | data: bytes used (without filler) |
|---|---:|---:|
| 0 | 97 of 150 (82.0 % of bytes) | 80.9 % |
| 1 | 108 of 131 (93.6 %) | 92.0 % |
| 2 | 114 of 177 (82.5 %) | 93.1 % |
| 3 | 121 of 160 (87.9 %) | 95.6 % |
| 4 | — | 100 % |
| 5 | — | 88.6 % |
| 7 | 8 of 11 (92.7 %) | 100 % |
| 8 | — | 100 % |
| 9 | — | 100 % |
| 10 | 1 of 9 (2.4 %) | 94.3 % |
| 11 | — | 100 % |
| 12 | — | 100 % |
| **all** | **449 of 638 routines, 85.4 % of the code** | **96.9 % of the data (95.4 % read from the ROM)** |

Put together, **93 % of the cartridge's non-empty bytes are either code the engine
names or data it uses.**

What is left, and why:

- **The machine's plumbing.** Booting and finding its own slot (0x4071, 0x40E1), the
  TwinBee search, the VRAM uploads and the decompressor's inner loops, the keyboard
  matrix, the BIOS calls. Pyxel draws from a VRAM model and reads keys its own way, so
  these have nothing to be rebuilt as.
- **Bank 10's little sprite engine** for the fixed screens. nemesio draws those screens
  and the ending (`game/attract.py`, `game/finale.py`, the ending measured identical step
  by step) but cites their steps and tables rather than bank 10's inner routines.
- **The TwinBee graphics** (811 bytes in bank 5), the Game Master header, the Konami
  marks, the dead fragments.
- **Jump tables** turned into Python dispatch (`movers` and `builders` in
  `objects.py`) and cited by their targets rather than by the table.
- A few routines implemented but cited by a neighbouring address. The measure is a
  lower bound.

---

## 5. The frame

### Everything runs inside the interrupt

The VDP interrupts sixty times a second. The hook at 0x4028 reads the VDP status (that
is what acknowledges it), calls the sound driver at 0x8063 so that music never stutters,
and then tries to run a game frame, behind a lock at 0x4045. A game frame takes longer
than a video frame, so the next interrupt finds the lock taken and only plays the sound.
Measured over 3,000 frames: **on a 60 Hz machine, the Japanese one it was made for, a
game frame takes exactly two interrupts, whatever is on screen** — thirty game frames a
second. On a 50 Hz machine it takes one with the screen empty and two with three or more
objects, so the game speeds up and slows down. nemesio is the 60 Hz machine.

A few game frames are longer, and those are rules, not accidents: building a stage
(16 to 24 interrupts, by the stage), loading the boss's characters (7), each pass of the
screen fade (4 to 14). The engine returns, with each game frame, how many interrupts it
takes, and the window waits that long. The sound driver ticks once per interrupt, as
the original's does.

### The game frame, in order

The routine at 0x4532, "a game frame" in the listing (whose labels are Spanish,
translated here), is the spine, and `Play.step` in `game/engine/play.py`
follows it call for call:

1. **Sprites up.** 0x4538 uploads the sprite buffer the *previous* game frame built, so
   sprites are always drawn one game frame behind the map.
2. **The stage's ending** (0x453B → 0x6CCD): the music is looked at, and the stage's own
   end routine runs (the eruption, the boss, the jump to a bonus stage).
3. **The hidden target** (0x454A).
4. **The scroll** (0x466A): maybe a new column.
5. **The ship** (0x9955), the **power-up button**, the **options** (0x9C41).
6. **The ship's shots** move, and a new one is fired.
7. **The enemies** (0x5DC8): each slot's mover, then its speed; the **waves** that
   spawn new ones; the **enemy shots** (0x65DC); the cannons; the background objects;
   the background blasts (0x45AF); the boss.
8. **The laser meets the map** (0x9F81), *before* the boss is drawn into it.
9. **Things drawn with characters are written into the map**: the boss, the hatches,
   stage 5's walls.
10. **Collisions** (0x71E8): shots against enemies, the ship against the map, the
    enemies and their shots.
11. **The other shots meet the map** (0x9F85).
12. **What the character-drawn enemies will cover is saved** (0x6893), they are drawn,
    and the **map goes to the screen** (0x47FE).
13. **Everything drawn into the map is taken out again** (0x6983), in a fixed order, so
    the terrain is clean for the next frame's collisions.

The order matters more than it looks. In step 8, the laser is checked against the map
before the boss is painted into it; in step 10, the ship's shots still hit enemies while
the ship is blowing up (0x71E8 only looks at whether the screen is stopped), but the
ship's own collisions are skipped. Each of these was a frame of difference against the
original before it was a line in `step`.

---

## 6. The map lives in RAM

The TMS9918 cannot scroll, so Nemesis does it by hand. The screen's play area is 22 rows
of 32 characters, kept at **0xED00** in RAM, and every rule that meets the terrain reads
that buffer, never the VRAM.

**The scroll** (0x466A). The distance travelled is 0xE063, in columns. A rotating bit at
0xE062 is rotated left once per game frame, and a column comes in only when it lands on
bit 0: **one game frame in eight**, so the screen moves eight pixels every sixteen video
frames. Two other modes exist, stopped and one column every game frame, used by the
hidden target (section 10). When a column comes in:

1. 0x469D moves the whole buffer one column left with twenty-two `ldir`s of 31 bytes;
2. 0x46AE works out which column enters and 0x46E1 writes it in on the right;
3. at the end of the game frame, 0x47FE sends all 704 bytes to the name table with
   `outi`, skipping the BIOS.

**The column** comes from the stage's script. The distance, less the start of the
stage's script range, divided by four, indexes rows of **six piece numbers**; each piece
is four by four characters, and five pieces make twenty rows while the sixth gives the
last two. Outside the script's range the column is sky: empty but for one star, on a row
the table at 0x478E gives, drawn with one of two characters that the `R` register picks.
Stages 3 and 6 have a script range of 0xFFFF, so they are all sky.

**What counts as solid** is decided by the character alone. 0 is empty; 1 to 0x76 is
terrain; 0x77 and above is scenery a ship flies through, except a few walls by stage
(bank 2, 0x9906). The listing's labels for those walls are one stage off; the code
(`sub 3 / jr z`, then `dec a / jr z`) decides.

Once this buffer matched the original's cell for cell, everything else could be built
on it, and `compare_play.py --map` checks it after every game frame.

---

## 7. The ship and its weapons

**The ship** (bank 2, 0x9955) is a 32-byte card at 0xE200, position in 8.8 fixed point.
The pad is read once a game frame (0x577D) and each held direction is looked up in the
table at 0x9B0D: 0x80, half a pixel, per axis. That step is added to itself three more
times, plus once per SPEED UP taken (up to seven): **two pixels a game frame** with no
power-up. It is clamped to a box (0x9AAB, 0x9ABB) that is a little taller on stages 2,
6 and 9 onwards, where the ceiling is open.

**The ship against the map** (0x98DA) is two probes, not a box: the character at the
ship's row plus eight, at its column and the next, or only the next once the column's
low three bits reach four. That is the whole of it, and it is why the ship can tuck its
nose into gaps that look too narrow.

**The weapons** (bank 2, 0x9CC5 onwards) live in nine slots of sixteen bytes at 0xE260:
for each of three shooters (the ship and two options), a normal shot or laser, a double,
and a missile. **The normal shot and the laser are characters written into the map**
(0xA27F), not sprites; the double and the missile are sprites. Held down, the button
fires again every fifteen game frames. The normal shot moves twelve pixels a game frame.
The laser grows four cells a game frame to eight cells, or fifteen with a second LASER,
runs, and is cut on terrain.

**The options** (0x9C41) each keep a queue of eight positions (16 bytes at 0xE230 and
0xE250). On a game frame when the pad moves the ship, the ship's position goes in at one
end and the first option takes the oldest from the other; the second option does the
same with the first's. With the pad still, or held both ways, the queues do not move,
and that is why the options bunch up when you stop and string out when you fly.

**The meter** is six cells at 0xE130: SPEED UP, MISSILE, DOUBLE, LASER, OPTION and the
shield. A red capsule advances it (and pays five points); the second button takes what
is lit, unless it is already maxed (0xA022), and resets it.

**The ship's end** (0x9B7B) is four states of ten, twenty, ten and ten game frames
(table 0x9BD2), each drawn with two sprites plus two more borrowed from the option
slots, which are wiped when the ship is hit.

---

## 8. Enemies: thirty-one small machines

### A slot and a type

Every enemy, capsule and explosion is **a 32-byte slot**, twelve of them at 0xE300.
nemesio keeps them as the same 32 bytes, read and written at the same offsets, because
every mover in the cartridge is a small program over those bytes, and renaming them
would mean checking each routine through a translation.

| offset | what |
|---|---|
| 0 | the type, 1 to 0x1F; 0 is a free slot |
| 1, 2 | the step of its own state machine, and a counter |
| 3-4, 5-6 | row and column, 8.8 |
| 7-8, 9-10 | row and column speeds |
| 11 | drawn with characters instead of a sprite |
| 12, 13 | drawing and colour |
| 14 | the **mark** |
| 15 | hits left |
| 16 | frames to its next shot |
| 17, 18 | in a group, and which |
| 23-26 | two accelerations |
| 27 | flags: bit 0 touches the ship, bit 1 can be shot |

**Making one.** 0x6A72 ("bring out an object"), the most called routine in bank 1, takes a
type, a place and a mark, finds a free slot and fills it from a four-byte record per type
at 0x6BA3 (characters or sprite, drawing, colour, hits). Two types break the pattern:
0x0E looks for its slot from the end, and 0x1E needs **three slots in a row** (0x6A98).

**Running one.** The type indexes two twin tables of routines: **p00:0x5DFD** says who
moves it every game frame, and **p01:0x6B46** says who finishes building it. Twenty of
the thirty-one types have at least one of the two in bank 3, which is why 0xA7B9-0xB537
is the longest stretch of code in the cartridge. In `objects.py` those tables are two
dictionaries, `movers` and `builders`, and each entry is one of the original's routines,
named by its address.

**The mark.** The sixteen bytes at 0xA5C7 are read round and round as enemies are made:
three in four come out unmarked, one in four with a 1, one in sixteen with a 2. A marked
enemy is painted red (colour 8, set at 0x6B10), and when its blast is over (0x5E65) it
leaves a red capsule for a 1 or a blue one, which blows up everything on screen, for a
2. The "red one in the formation" is not chance; it is a counter.

### How they move

None of the movers uses trigonometry. A few of them:

- **Type 2** turns back at column 0x81, stops at 0x9F, comes forward to 0x51 and flies
  straight once level with the ship, in four steps counted in byte 1.
- **Type 5** walks on the terrain with no height map: it asks the map what is eight
  pixels under its feet and steps up or down until it fits. It turns to face the ship
  (0xAB60), and its two drawings alternate every four frames.
- **Type 0x0C** has its whole route written down: nine steps, each waiting for its
  column to reach a number. Bit 7 of byte 1 mirrors it, so the ones that come in from
  the bottom fly the same route upside down.
- **Type 0x1D**, stage 5's long flock, closes in a spiral with no sine table: the
  distance to the centre divided by eight (three `sra a`) is added to the other axis, so
  it turns about seven degrees a step, while both coordinates are multiplied by a byte
  that drops by one every 0x3C frames, so the radius shrinks.
- **Type 0x1E** takes three slots. The second and third are made with one
  self-overlapping `ldir` of 0x40 bytes from the slot onto itself shifted by 0x20. When
  its time runs out, all three become type 0x1F and fly apart.

### Waves

On stages 1-8, 0xA310 cuts the stage into sections of 0x20 distance; each section has a
byte whose bits turn on up to six generators (0xA3A6): a pair, a trail, eight from the
left, four from below, a flock, eight mixed. Before them all runs the six-in-a-row wave
(0xA4BA), counted in one of four groups at 0xE900: the last of a group shot down leaves
a capsule, and every eighth wave's leaves the blue one. Stage 7 is different: its forty-three appearances are written out one by one,
each packed into a single word at 0xAF3F (a nine-bit distance, a two-bit variant, a
five-bit row).

### Enemy shots, and how they aim

Enemy shots have their own ten slots at 0xE500. **Only one enemy may fire per game
frame** (0xE112); any other whose delay runs out waits a frame. Each shot's delay is a
difficulty step from a table plus three bits of `R` (0x6B84).

Aiming (0x6677) is where the cartridge does use a table: the high nibbles of the row and
column distances to the ship index an angle table, and a quarter-sine table read both
ways gives the two components, multiplied by the shot's speed (0x50 plus twice the
difficulty, at most 0x60). From difficulty 7 on, `R` spoils the angle by up to fifteen
steps either way (0x6685), and with the ship too close, nothing is fired at all.

---

## 9. Collisions

There is no general collision system. There are four separate tests, each written for
its case, and each with its own quirks.

**The ship against the map**: two character probes (section 7).

**Shots against enemies** (0x7229). For each live enemy that can be shot, the nine
weapon slots are tried in order, and the first that hits wins. A normal shot hits inside
0x12 rows and 0x20 columns of the enemy (offset by 0x10), and never past column 0xF0; a
laser's box is its length, and it is not spent by the hit. Three types (0x0B, 0x1B,
0x1E) take shots without harm and only make a sound.

**Enemies against the ship** (0x7357) have a lopsided box, and the listing's comment
misses why: the routine compares one axis with `BC'`, set inside it to 0x0C08, and after
an `exx` the other axis with `BC`, whatever the caller left there: 0x0C0C for the
enemies (0x7469), 0x0202 for their shots (0x7346). So an enemy touches the ship from
twelve pixels above but only eight below. Fixing this took stage 1 from 168 matching
frames to 1,089. **The first enemy found touching wins, and no more are checked that
frame** (0x7389).

**Things drawn into the map are terrain.** The boss, the hatches, stage 5's walls,
stage 6's arms: the cartridge writes them into the 0xED00 buffer as characters, so the
ship dies on them exactly as on rock, and the ship's shots end on them the same way.
Twelve slots' worth of character-drawn enemies go further: 0x6893 saves the four cells
each will cover (in the slot's own bytes 19-22) before they are drawn, and 0x6983 puts
them back after the screen is sent, but not for one at column 0xF8 or more (0x69D7). Get
the save and restore order wrong and a shot fired through a gap on one frame hits a
ghost on the next. `compare_play.py --map` is what found those rules.

---

## 10. Stages, and the four you do not see in order

The stage number lives in 0xE061, and it does not simply count up. 0x6D53
("end the stage") adds one; 0x6FB9 ("jump to the stage") writes a number straight in, and eight
places jump there. Put together, the running order is:

    1 - 2 - 9 - 3 - 10 - 4 - 11 - 5 - 6 - 7 - 12 - 8 - ending - 1

**Stages 9-12 are bonus stages**, and what opens them is a **hidden target** (bank 3,
0xB042). Five stages hide one: at a distance of the stage's own, a spot enters at column
0xF0 and rides the scroll. Nothing draws it; it is three bytes, 0xE1C1-0xE1C3. Fly within
0x10 of it on stages 2, 3 or 7 and the screen stops (0xE1C0): everything on it blows up,
and 0x40 game frames later the scroll runs a column every game frame up to a limit of the
stage's, where its ending jumps to bonus stage 9, 10 or 12 instead of going on. Stage 4
counts instead: the third target in a row of a different kind sends it to stage 11.

Each stage also has a **checkpoint** (table at 0x4214): after a death, the stage restarts
there if you had got that far. The table has eleven entries, and stage 12 reads past its
end into the next routine's code, getting 0xBACD, a distance nobody reaches, so it always
restarts from the beginning. The bug is real and its effect is nothing.

---

## 11. How stages end, and the bosses

Every stage's end is a routine of its own, dispatched from 0x6CCD through a table of
twelve at 0x6CD7, and counted in steps at 0xE065. A boss, once it is on, is one of seven
entries in a second table at 0x7C41 (0xE152 says which):

| stage | how it ends | boss routine |
|---|---|---|
| 1 | the volcanoes erupt (0x1C2 rocks, one every other frame); a red crystal of five pieces at distance 0x165; the core | 0x7C8D |
| 2 | the core, or the target to stage 9 | 0x7C8D |
| 3 | eight heads in lanes, each firing threes (a lone fast head from the second loop); the core, or stage 10 | 0x839F, 0x83A5 |
| 4 | a rush and a crystal, then pieces flying a fixed route; the core, or stage 11 | 0x8CE4 |
| 5 | two flocks (types 0x1D, then 0x1E), then the core | 0xB946, 0xBB95 |
| 6 | nuclei with two arms each, most of the stage, then the core | 0x7F74 |
| 7 | the brain's eye, spitting; the screen fades; or stage 12 | 0x8719 |
| 8 | the fortress: two claws, a gate, six anchors; the fade; the game's ending | 0x87F3 |
| 9-12 | back to stage 3, 4, 5 or 8 (the table at 0x418F) | |

The listing labels the routine at 0x7F74 as stage 5's boss; the nuclei are stage 6's.
The code, and a measurement, decide.

**The core** (0x7C8D) is the recurring boss. It waits for the screen to empty, loads its
own characters over the stage's (0x4A6D, a seven-interrupt game frame), slides in, rides
up and down towards the ship firing four shots at each turn, and opens its mouth for a
while, the only time its eye can be hit. It is drawn into the map, so the ship dies on it
as on terrain, and the laser is checked against the map before the core is painted in.

**The screen fade** at the end of stages 7 and 8 (0xA6C0) cannot fade a palette; the
TMS9918 has none. So the cartridge eats the VRAM: blocks come down, get an AND and go
back up: once over the colour table with 0xF0, then eight passes over the patterns with
0xFE, 0xFC, 0xF8 down to 0x00, the mask rotated three bits per byte so the dark comes in
crumbs. In nemesio the engine keeps no VRAM, so the fade comes out of a game frame as a
list of writes for whoever holds it.

**The ending** after stage 8 (0x4AC0) is nine steps: the ship leaves, the shrapnel, the
pictures, the words. Measured against the original, each step lasts the same number of
interrupts.

---

## 12. Chance without a generator

There is no seed and no random number routine in the 128 KB. What stands in for chance is
`ld a,r`: the Z80's refresh register, which counts on its own with every instruction
executed. There are **twenty-two** of them, and they pick which star drawing goes in each
sky column (0x4750), which door each falling rock comes through (0xABC2), how long each
drawing of a blinking enemy lasts (0xB016), how far the walker gets (0xAAE6), and three
bits of every enemy's shot delay (0x6B84).

`R` depends on exactly how many instructions ran, which is the one thing a
reimplementation cannot reproduce without emulating the Z80. nemesio uses an ordinary
generator where the original reads `R`, and the measuring harness settles the question
differently: **`--no-chance` patches all twenty-two `ld a,r` (ED 5F) into `xor a / nop`
(AF 00)** in a copy of the ROM, and makes the engine's dice answer zero too. With chance
pinned on both sides, every stage, boss and stage change measures identical, and any
difference left is a rule.

---

## 13. What the player sees and hears

**The screen.** What goes to the name table is the 0xED00 map as it stands at 0x45E5,
with the shots and the character-drawn objects written in (enemy shots first, then the
twelve slots). The score band is rewritten only one game frame in eight (0x45EB), and the
two star characters' top rows every other frame (0x475B), which is what makes the stars
twinkle and walk.

**The sprites.** The buffer at 0xEC80 is uploaded as thirty-two four-byte entries, but
not from the same place each time: 0xE17F moves seven entries further every game frame,
and the upload then steps three at a time (0x47DB). Every object lands in a different slot
of the attribute table each frame, so when more than four share a scanline, which one
the VDP drops rotates. The flicker is shared out on purpose. nemesio's renderer applies
the same four-per-line limit, so it flickers the same way.

**The sound.** Bank 7 is a small driver, 794 bytes. Each interrupt it walks three channel
cards, each reading its own stream of commands (a note and its length, a loop, a jump, a
volume or noise change) and writing the PSG through the BIOS. The table at 0x8328 has
eighty words: entry 0 is not an address, so sound 0 does not exist, and the last three
point at the first filler byte of bank 8, silence. Bit 7 of a request picks how the
streams are read, as melody or as effect. The note table at 0x831E is ten bytes long, and
the melodies' notes 10 and 11 read on into the sound table's first entry: the driver reads
past its own table, and so does nemesio's. `game/rom/sound.py` runs the original's rules on
the cartridge's data and produces the PSG's sixteen registers each tick; `game/render/`
turns them into Pyxel channels. The registers match the original's; the audio chip
itself is approximated.

---

## 14. Measuring as the arbiter

### The harness

`tools/harness/omsx.py` runs openMSX under `-control stdio`: no window, no GPU, paused
between calls, so the test decides exactly how many video frames pass. It reads RAM, VRAM
and VDP registers, presses keys in the keyboard matrix, and sets breakpoints and
watchpoints. The original runs headless at about 400 frames a second. `tms.py` draws a
VRAM dump the way the TMS9918 does, which is how the original is "photographed".

### compare_play

`tools/compare_play.py` starts a game in openMSX and in the engine, feeds both the same
pad script, and after every **game** frame, told apart by the original's frame counter
at 0xE003, compares what both hold. It can compare the ship and the distance; the twelve
object slots (`--objects`); the enemy shots; the bosses' pieces (`--nuclei`, `--heads`);
the sprite buffer; the map buffer (`--map`); the name table, sprite table and star rows
as the VDP holds them (`--screen`); the sound requests (`--sounds`) and the PSG registers
(`--psg`); the ending (`--finale`); two players; any stage, loop or starting score. With
`--immortal` the ship's death is patched out (two `ret`s in bank 1), and with
`--no-chance` the dice are pinned.

How long each game frame lasted is measured exactly, not sampled: a breakpoint on the
interrupt at 0x4028 is counted, and a watchpoint on 0xE003's write marks the frame.
Sampling every half frame guessed some lengths wrong by one, and a length off by one is
a sound that starts a frame late.

### What it found

The measure found rules no reading of the listing would have:

- the lopsided touch box (`BC'` against the caller's `BC`);
- sprites drawn a game frame behind the map;
- shots still hitting enemies while the ship blows up;
- a character table read too short (0x100 bytes instead of 0x200), which left the
  cannons of stages 4, 5 and 11 undrawn;
- the destroyed box in bonus stages leaving a hole in the ceiling that later shots fly
  through;
- a new ship every 1,000 on the cartridge's six-digit score (100,000 on screen, where
  two fixed zeros follow it), with its own sound, and at most 99;
- the music checked only once per game frame, with the state as it was when the frame
  began.

And it corrected the listing where the listing was wrong: comments that swap X and Y
(the ship's card is Y at 0xE204, X at 0xE206), the wall labels a stage off, the "stage 5"
boss that is stage 6's.

### Where it stands

With `--no-chance --immortal` and long games: stages 1-8 in both loops, in ship, objects,
enemy shots, map, sounds and screen; stages 9-12 in ship, objects, map and screen.
**112 measurements, zero differences.** With deaths, the screen and objects of stages 1
and 3, and two players in ship, objects, band, screen and sounds, also zero. What still
differs without `--no-chance` is `R`'s dice, which are not rules.

Two things were deliberately left out: the Z80's own time (a game frame that runs into a
third interrupt because the screen is crowded) and `R`. Both would need numbers with no
address in the cartridge, so neither passes the project's own test.

---

## 15. Numbers, and what was learned

| | |
|---|---|
| cartridge | 131,072 bytes, 16 banks: 19.4 % code, 43.8 % data, 36.8 % filler |
| the listing | 100 % of bytes explained, 1,540 routines, 916 labels |
| code nemesio names | 449 of 638 routines, **85.4 %** of the code bytes |
| data nemesio uses | **96.9 %** of the non-filler data (95.4 % read from the ROM) |
| both | **93 %** of the cartridge's non-empty bytes |
| engine | ~7,600 lines, no Pyxel in it, no number without an address |
| comparisons at zero differences | 112 |
| time | four days |

Lessons:

1. **A byte-exact disassembly turns a port from discovery into volume.** The hard part
   was never finding out what Nemesis does; it was doing all of it, in order.
2. **Keep the original's data structures.** Thirty-two bytes per slot, offsets and all,
   meant every mover could be checked against the listing line by line.
3. **Order is a rule.** Most bugs were not wrong numbers but right steps in the wrong
   place: the laser before the boss is drawn, the save before the draw, one shooter per
   frame.
4. **Measure the frame, not the second.** A game frame of the original is not a video
   frame, and not a fixed number of them either.
5. **Pin the dice.** Twenty-two two-byte patches turned "roughly the same" into "the same"
   and made every remaining difference mean something.
6. **The listing's comments are a reading; the code is the fact.** Where they disagreed,
   a measurement decided.

---

## 16. How it was made

nemesio is AI-assisted. What made that work on a target this exact:

- **A ground truth outside the code.** The byte-exact disassembly said what the code
  was, and openMSX said what it did.
- **A measure that runs on its own.** The harness came first: before a line of the game,
  the tools to run the original headless and read its memory, and a measure of whether
  the port was feasible at all. After that, "done" meant "measures identical", which can
  be checked without reading the code.
- **Rules written down.** `AGENTS.md` holds the project's rules (no number in the engine
  without its cartridge address, nothing from the cartridge committed, measure before
  arguing) and the traps already paid for, so each new session starts from them.
- **Decisions kept by a person.** Leaving out the Z80's timing and `R`, what goes in a
  public repository, and what the stage without a cartridge should look like.

Where it did less well is where there was nothing to measure against. The stages without
a cartridge had no original to compare with: eight were drawn, judged not good enough,
and seven were dropped to polish one. In that one, the rock
the stage's missile launchers sit on (part of the original's map, not of the launchers)
was missing, and it was a person playing who saw it, not a test. The sound chip is
approximated for the same reason: its registers match the original's, but only an ear
can judge how the result sounds.

---

*nemesio is an AI-assisted personal preservation and study project. It contains no ROM, art, music or maps of the cartridge, only the rules' numbers: to play
it you need your own Nemesis (RC-742) ROM. Nemesis and Gradius are
trademarks of Konami. The reference disassembly is Antxiko Gorjón's; the Game Master
header was identified by Néstor Sancho; the hidden Konami mark was documented by Manuel
Pazos.*
