"""Every number the engine runs on, and each is the original's.

Where it comes from is the address in the cartridge (bank:address, bank 0
unless said) of the instruction or table that holds it, as the reference
listing numbers them. `game/engine/` carries no other integer past two.
"""

# -- the frame ---------------------------------------------------------------

#: The whole game runs inside the VDP interrupt behind a lock (0x4045): a game
#: frame takes longer than a video frame, so the next interrupt finds the lock
#: taken and does nothing. Measured in openMSX over 3000 frames of stage 1: on
#: a 60 Hz machine -- the Japanese one it was made for -- exactly one game
#: frame every two interrupts, whatever is on screen; on a 50 Hz one, nearly
#: one per interrupt with the screen empty and one every two from three
#: objects up. This game is the 60 Hz machine.
VIDEO_FRAMES_A_STEP = 2

# -- the map -----------------------------------------------------------------

#: The map buffer at 0xED00: 22 rows of 32 characters (0x469B, 0x469E).
MAP_ROWS, MAP_COLUMNS = 22, 32
#: A character is eight pixels.
CELL = 8
#: 0x571B turns a card's row and column into a cell of the map in RAM.
MAP_AT = 0xED00
#: The objects drawn with characters (byte 11 up) are not in the map while
#: things meet it: 0x6893 (after the ship and the shots have met the map)
#: keeps the four cells each one will cover in its bytes 19-22 and where in
#: bytes 30-31; 0x47B7 draws them, the screen goes up, and 0x6983 puts the
#: kept cells back -- but for one at column 0xF8 or more (0x69D7). The four
#: cells: two, and two 0x20 further on.
UNDER, UNDER_AT, UNDER_LAST_COL = 19, 30, 0xF8
UNDER_CELLS = (0, 1, MAP_COLUMNS, MAP_COLUMNS + 1)
#: 0x48B6 draws them there: byte 11 at 1, four characters out of 0x91D1 by
#: the pattern (byte 12); otherwise two side by side, which by byte 11
#: (0x48E0). Past row 0xB8 or column 0xF8 not at all (0x48A9).
PAIRS, PAIR_OTHER = {2: 0xA1, 3: 0xBF, 4: 0x58}, 0x60
DRAWN_BELOW, DRAWN_LEFT_OF = 0xB8, 0xF8
#: A slot 0x484A takes for empty, drawing no sprite: type 0, or 0x19.
EMPTY_TYPES = (0, 0x19)
#: Type 5 planted, or when its shot's delay runs out, faces the ship
#: (0xAB60): on the floor 0xF0 with the ship to its right (or level), 0xE4
#: to its left; on the roof 0xFC and 0xD8.
FACING_5 = {True: (0xF0, 0xE4), False: (0xFC, 0xD8)}
#: The boss's pieces of 0xE780 (bytes 3 and 5 their row and column): with
#: 0xE152 at 1 or 5 all eight, at 6 the first alone, keep the 4x4 cells
#: under them in 0xEA00 before they are drawn (0x6936, from 0x45C4), and
#: once the screen is up they go back (0x6A37, 0x6A2C) -- for the pieces
#: still in their slots. With these three the background blasts' cells are
#: kept and put back too (0x68FB, 0x6A03), not zeroed.
PIECE_UNDER = 4
PIECES_KEPT = {1: 8, 5: 8, 6: 1}
#: At a stage's start the distance is set back this far and as many columns
#: are brought in, which fills the screen (0x45F9, 0x460A).
FIRST_FILL = 0x20
#: Where a stage starts unless the player had passed its checkpoint (0x41E7).
STAGE_START = 0x20
#: The scroll's rotating bit starts at one (0x420A); a column comes in when
#: the bit, rotated left once a game frame, lands on bit 0 (0x4683): one game
#: frame in eight.
SCROLL_BIT_START = 0x01
#: 0xE1C0, the scroll's mode: 1 stops it, 2 scrolls every game frame, and
#: anything else is the rotating bit (0x467B).
SCROLL_STOPPED, SCROLL_EVERY_STEP = 1, 2

#: Map characters: 0 is empty; 1 up to this is solid terrain; this and above
#: are scenery a ship flies through, except the walls below (bank 2, 0x9902).
SCENERY = 0x77
#: A sky column's two star characters, one chosen by the Z80's R register
#: (0x4750): the only chance in the column builder.
STARS = (0xF6, 0xF7)

# -- the ship ----------------------------------------------------------------

#: The ship's card as a stage starts it: sixteen bytes at 0x4193 copied to
#: 0xE200. Row 0x4A, column 0x50, both with no fraction.
SHIP_START_Y, SHIP_START_X = 0x4A, 0x50
#: A pad direction moves 0x80 (half a pixel) on each axis it names (bank 2,
#: 0x9B0D), added to itself 3 + (speed steps) times more (0x9B4D): four
#: half-pixels -- two pixels -- a game frame with no SPEED UP.
SHIP_UNIT = 0x80
SHIP_SPEED_BASE = 3
SHIP_SPEED_MAX = 7
#: The ship's box (bank 2, 0x9AAB, 0x9ABB): X in 0x08..0xD8; Y, tested with
#: 0x10 added, in 0x13..0xB5 -- 0x10..0xB5 on stages 2, 6 and 9 onwards.
SHIP_X_MIN, SHIP_X_MAX = 0x08, 0xD8
SHIP_Y_BIAS = 0x10
SHIP_Y_MIN, SHIP_Y_MIN_OPEN, SHIP_Y_MAX = 0x13, 0x10, 0xB5
SHIP_Y_OPEN_STAGES = (2, 6)
SHIP_Y_OPEN_FROM = 9
#: The ship tests the map at its row plus eight (bank 2, 0x98DE); with its
#: column's three low bits under four it tests that cell and the next, and
#: otherwise the next only (0x98E8).
SHIP_PROBE_Y = 8
SHIP_PROBE_HALF = 4
#: The ship's two sprites: (pattern, colour) twice, by what the pad holds on
#: its two low bits -- neither or both, up, down (bank 2, 0x99E5).
SHIP_SPRITES = (
    ((0x00, 0x0F), (0x04, 0x08)),
    ((0x10, 0x0F), (0x14, 0x05)),
    ((0x08, 0x0F), (0x0C, 0x08)),
)

# -- the shot ------------------------------------------------------------------

#: A shot held down fires again after this many game frames (bank 2, 0x9CE2).
AUTOFIRE = 0x0F
#: A normal shot starts at the shooter's row plus 8 and column plus 0x10,
#: the column squared to eight (bank 2, 0x9D5C, 0x9D62), and moves 0x0C00 --
#: twelve pixels -- a game frame (0x9E42), gone once it passes 0xFF.
SHOT_DY, SHOT_DX = 0x08, 0x10
SHOT_SPEED = 0x0C
#: It is drawn as a character in the map, one of four by where the shooter's
#: row falls in its cell, two pixels apart (bank 2, 0x9E0A).
SHOT_CHARACTER = 0xF8
#: Two slots of the nine for each shooter's normal shots (0xE260, 0xE270).
SHOTS_EACH = 2

# -- the stages ------------------------------------------------------------

#: Characters from SCENERY up that still stop a ship or a shot: walls, by
#: stage. **The listing's labels for these are one stage off**; the code is
#: `sub 3 / jr z` then `dec a / jr z`. The ship (bank 2, 0x9906): stage 3 has
#: 0xA1-0xBB, stage 4 0xBA-0xC5. A shot (choca_con_el_mapa_2, 0x9879):
#: stage 3, 0xA1-0xA5.
SHIP_WALLS = {3: range(0xA1, 0xBC), 4: range(0xBA, 0xC6)}
SHOT_WALLS = {3: range(0xA1, 0xA6)}
#: An object against the map (0x9857) and an enemy shot (0x98AC): stage 1's
#: 0xA2 and 0xA5 (0x9912), stage 3's 0xA1-0xA5 (0x9923).
OBJECT_WALLS = {1: (0xA2, 0xA5), 3: range(0xA1, 0xA6)}

# -- the ship's end ------------------------------------------------------------

#: When the ship dies (bank 2, 0x9B7B) it goes through four states, each
#: lasting so many game frames and drawn with two sprites; past the fourth
#: the life is over (0x9B99). Table 0x9BD2, indexed by the state.
EXPLOSION = (
    (0x0A, ((0x64, 0x06), (0x68, 0x09))),
    (0x14, ((0x5C, 0x09), (0x60, 0x0F))),
    (0x0A, ((0x50, 0x09), (0x54, 0x0F))),
    (0x0A, ((0x64, 0x06), (0x68, 0x09))),
)
#: And the two options' slots, 0xE220 and 0xE240, made 0xFF with the ship
#: (0x9B86), are two more sprites of it: at the ship's row and its column
#: plus the first byte, with the pattern and colour after (0x9BBD).
EXPLOSION_PARTS = (
    ((0x00, 0x6C, 0x0F), (0x00, 0x6C, 0x0F)),
    ((0xF8, 0x58, 0x06), (0x08, 0x74, 0x06)),
    ((0xF8, 0x4C, 0x06), (0x08, 0x70, 0x06)),
    ((0x00, 0x6C, 0x0F), (0x00, 0x6C, 0x0F)),
)

# -- the pad ---------------------------------------------------------------------

#: 0xE009's bits, the joystick's order (0x577D).
UP, DOWN, LEFT, RIGHT, FIRE, POWER = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20

#: Lives a game starts with, in BCD, and one goes when a life starts (0x53CC):
#: three ships, and the band shows the two in reserve.
LIVES = 0x03
#: 0x561C: one more ship, up to 99 (BCD), with the sound 0x15 unless the
#: game's ending is on (0xE1D0). 0x55DE: one each time the score's top four
#: digits reach 0xE067, which starts at 0x0010 (0x5570) and goes up 0x10 --
#: a ship every thousand, the score in the units it is kept in.
MAX_LIVES, ONE_MORE_SOUND = 99, 0x15
FIRST_SHIP_AT, SHIP_EVERY, SHIP_AT_TOP = 10, 10, 9999
#: 0x55CF: the score is three BCD bytes. One that carries out of them wraps
#: (the player's score goes on from the six digits left), and 0x55D1 writes
#: nines over the record instead (0xE054-0xE056), and nothing more that time:
#: no ship, no record compared.
SCORE_WRAP, SCORE_TOP = 1000000, 999999

# -- the stars -----------------------------------------------------------------

#: Every other game frame 0x475B rewrites the top row of the two star
#: characters, in all three thirds: the scroll's rotating bit, masked by a
#: pair from 0x4786 picked by the frame counter's bits 1-2. So a star is one
#: pixel that walks across its cell, and each of the two blinks off in turn.
STAR_MASKS = ((0xFF, 0x00), (0xFF, 0xFF), (0x00, 0xFF), (0xFF, 0xFF))

# -- touching the ship ----------------------------------------------------------

#: The ship is touched at its row plus 4 and column plus 1 (0x7357, 0x75B8).
#: The box is lopsided, and the listing's own comment misses why: the first
#: compare runs on BC' (0x0C08, set in the routine) and, after an `exx`, the
#: second on BC -- whatever the caller left there. So a thing touches the ship
#: from TOUCH_ROWS/TOUCH_COLS past the point back to the caller's C and B
#: before it: 0x0C0C for the enemies (0x7469), 0x0202 for their shots (0x7346).
#: Measured: a type 0x1D blows up 0x0B rows above that point.
TOUCH_DY, TOUCH_DX = 4, 1
TOUCH_ROWS, TOUCH_COLS = 0x08, 0x0C
ENEMY_REACH, SHOT_REACH = (0x0C, 0x0C), (0x02, 0x02)
#: A normal shot meets an enemy inside 0x12 rows and 0x20 columns (0x724A),
#: but not once it is past column 0xF0.
HIT_ROWS, HIT_COLS, HIT_OFFSET, HIT_LAST_COLUMN = 0x12, 0x20, 0x10, 0xF0
#: Enemies that take a shot without harm (0x7270).
SHOT_PROOF = (0x0B, 0x1B, 0x1E)

# -- the power meter ---------------------------------------------------------

#: Six cells (0xE130), round: SPEED UP, MISSILE, DOUBLE, LASER, OPTION, the
#: shield. A capsule is five points (0x7580).
METER_CELLS = 6
CAPSULE_POINTS = 5
#: A cell counts as taken, so the button does nothing on it (0xA022), when:
#: speed steps reach 8; the missile, the laser or the options reach 2; the
#: double is on; the shield is on.
TAKEN_AT = 8

# -- the shield ------------------------------------------------------------------

#: Taking the shield sets the ship's state to 3 and gives it ten hits (0xA0CB);
#: under two it is weak (state 2), at none it is gone (state 1) (0x740C).
SHIELD_HITS, SHIELD_WEAK = 0x0A, 2
#: With a shield the ship is touched in a bigger box: around its row and its
#: column plus 12, 0x21 by 0x15 for enemies (0x7420), 0x13 by 0x0B -- 0x19
#: for one drawn with characters -- for their shots (0x7395).
SHIELD_DX = 0x0C
SHIELD_ROWS, SHIELD_COLS = 0x21, 0x15
SHIELD_SHOT_ROWS, SHIELD_SHOT_COLS, SHIELD_SHOT_COLS_CHARS = 0x13, 0x0B, 0x19
#: The shield's sprite is the ship's second, eight pixels to the right (0xA1A5).
SHIELD_SPRITE_DX = 8

# -- breakable walls -----------------------------------------------------------

#: Characters a shot breaks instead of ending on (bank 2, 0x992F), and the
#: sound each group makes: 0x44 on stage 2 and from stage 9 on (while no boss
#: is on screen), 0x61-0x62 on stage 7.
BREAKABLE = {2: (range(0x44, 0x45), 5), 7: (range(0x61, 0x63), 4)}
BREAKABLE_FROM, BREAKABLE_LATE = 9, (range(0x44, 0x45), 5)

# -- the words typed in pause ----------------------------------------------------

#: What LASER and MISSILE (and HYPER) set: 0xE20E and 0xE20F to two (0xA131,
#: 0xA137).
WORD_LASER, WORD_MISSILE = 2, 2

#: The stage with a background engine of its own (0x5FE7).
STAGE_5 = 5

# -- the sprites ---------------------------------------------------------------

#: 0xEC80: 32 sprite entries, sent from 0xE17F's on, 0x1C bytes (seven
#: entries) further each game frame, then every 0x0C (three) (0x47DB); with
#: 0xE200 at 0xFF (the ship blowing up) straight, from the first. 0x415A
#: sets 0xE17F to 0 as each life and stage starts.
SPRITE_ENTRIES, SPRITE_TURN_STEP, SPRITE_TURN_EVERY = 32, 7, 3
#: 0x45EB: the band's scores (0x564D) are written again at the end of one
#: game frame in eight, with the frame counter at 1 modulo 8.
SCORES_EVERY, SCORES_AT = 8, 1

# -- the pictures the rules name ------------------------------------------------
#
# Which characters and sprite patterns the rules draw with. The cartridge's
# are these; content that draws its own hands a `layout.Layout` with its own
# (the free assets do), and the engine asks that.

#: The double: pattern 0x18 in white (0x9D7E).
DOUBLE_PATTERN, DOUBLE_COLOUR = 0x18, 0x0F
#: The laser: characters from 0xFC, one of four by the shooter's row (0x9DCD).
LASER_CHARACTER = 0xFC
#: The missile: pattern 0x1C rolling and 0x20 falling, colour 0x0A blinking
#: with 0x0B (0x9DE0, 0x9EE0).
MISSILE_ROLLING, MISSILE_FALLING, MISSILE_COLOUR = 0x1C, 0x20, 0x0A
#: The drawings an option blinks through, one every two frames (bank 2, 0x9CBA).
OPTION_DRAWINGS = ((0x44, 0x0A), (0x44, 0x09), (0x48, 0x08), (0x48, 0x06))
#: An enemy shot: pattern 0x88 in light red (0x6646).
ENEMY_SHOT = (0x88, 0x09)
#: A walker (type 5) starts drawn 0xE8 on the floor, 0xF8 on the roof (bank 3,
#: 0xA9D4).
WALKER_START = {True: 0xE8, False: 0xF8}
#: The blast an enemy becomes (0x72DF), and a type 0x0D's (0x72E9).
BLAST_PATTERN, BLAST_0D_PATTERN = 0x78, 0xF0
#: A taken prize floats up showing sprite 0xE0 on, 0x04 a step of the chain
#: (0x752D).
FLOAT_PATTERN = 0xE0
#: Drawings of four characters (0x91D1): the bug's eight, there and back
#: (0x5F47); a box opens into 0x37, the ship, or 0x38, a capsule (0x74E8);
#: a marked enemy leaves a capsule or a bomb, its type plus 0x0F (0x5E65).
BUG_DRAWINGS = (4, 5, 6, 7, 8, 7, 6, 5)
SHIP_DRAWING, CAPSULE_DRAWING = 0x37, 0x38
CAPSULE_DRAWINGS = {0x12: 0x21, 0x13: 0x22}

# -- where a stage's end happens -------------------------------------------------
#
# The distances the ends of stages 1-5 key off. The cartridge's are these; a
# stage of the content's own hands its own (`stages.Stages`).

#: Where the red crystal (0x8E77) comes: in stage 1's end (0x6CEF) and stage
#: 4's (0x6E15).
CRYSTAL_AT = {1: 0x165, 4: 0x171}
#: Where the scroll stops for the core once the stage's end has run -- stage 1
#: (0x6D36), stage 2 (0x6D66's), 3 (0x6DA7's), 4 (0x6E15's) -- and where stage
#: 5's runs on to after its flocks (0x6EDF).
BOSS_LIMIT = {1: 0x1C0, 2: 0x1DF, 3: 0x1AF, 4: 0x1C0, 5: 0x1FF}
#: Where stage 4's rush of rocks from the roof starts, in its end (0x6E15).
RUSH_AT = {4: 0x128}

# -- stage 7's eye (boss 3, bank 2, 0x8719) ----------------------------------------

#: The eye's two cells, one above the other (0xEE5B in the map and the one
#: below), where the brain has its socket.
EYE_AT = {7: (10, 27)}
#: Its two characters open, shut and dead (0x87CF's callers).
EYE_OPEN, EYE_SHUT, EYE_DEAD = (0x3E, 0x3F), (0x40, 0x41), (0x5F, 0x60)
#: A type 0x0D leaving is drawing 0xDC (0xAFA8).
LEAVING_0D = 0xDC

#: Stage 5's flock: a piece of a big one is pattern 0xE8, blinking with bit 2
#: (0xBD33, 0xBDB8).
FLOCK_PIECE = 0xE8
