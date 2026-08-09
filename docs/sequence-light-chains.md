# Fake sector lights — survey and playtest list

Animated sector light with nothing in the world casting it: travelling waves
(sequence chains), per-sector blinks, and effects a map's own ACS installs at
load. Found by `tools/scan_light_specials.py`, stripped by
`tools/make_seqlight_fix.py`.

## The mechanism

A `LightSequenceStart` sector (special 2) anchors a chain of alternating
`LightSequenceSpecial1`/`2` sectors (3/4). At map load `DPhased::PhaseHelper`
(`src/playsim/mapthinkers/a_lights.cpp`) walks the chain once through two-sided
linedefs, spawning one thinker per sector, each phase-offset. Every sector then
ramps from its base lightlevel up to 255 and back, forever, so a bright band
travels along the run.

Two details that matter when scoping a fix:

- **The walk is a path, not a flood.** `P_NextSpecialSector` returns the *first*
  matching neighbour and `validcount` blocks revisits, so sectors carrying 3/4
  that the path never reaches get no thinker and never animate. Do not scope a
  fix by "all sectors with special 3/4" — scope it by the resolved chain.
- **One sector can be two places.** Doom sectors need not be contiguous. MAP03's
  stair sectors each span *both* staircases (s35 is `x −352…−224` **and**
  `x 224…352`), which is why both sides pulse in lockstep.

## Why RT makes it worse

`rt_sector_emis` turns sector lightlevel into surface emission above a threshold
that is computed **per map**, not fixed:

    threshold = max(rt_sector_emis_minlight, map median lightlevel + margin)

With the launcher's `minlight 160` and `margin 40` that is **220 on MAP03 and
MAP12, 240 on MAP05** — the 160 floor almost never binds. An earlier version of
this document asserted a flat 160 and mis-triaged chains on the strength of it.

The correct triage differs by family:

- **Sequence chains.** `DPhased` ramps every sector to **255** at the crest of
  the wave, which clears any threshold a Doom map can produce. So *every*
  sequence chain in the game becomes a sourceless emitter as the wave passes,
  whatever its base. The base only decides whether it *also* emits steadily
  between crests — on MAP03 exactly 1 of 63 sequence sectors does.
- **Blink specials.** `DFlicker` and the strobes only ever dim *below* the
  sector's own lightlevel, never above it. There the base is the whole story.

Clearing the special leaves each sector at its base lightlevel — the value it
already showed between waves — so nothing gets darker.

## The whole game: 4 chains in 2 maps

Re-derive with `python tools/scan_light_specials.py 3 12 --chains`.

### DONE — MAP03 chain 156, the twin staircases

10 sectors (`156, 42, 34–41`), base 180, all emitting. Room at `y −620…−1140`,
two mirrored staircases, nine steps each, no ceiling fixture anywhere. Reported
from play, stripped, confirmed loading clean.

### TODO — MAP03 chain 84, corridor into the wide hall

39 sectors, SFLATAQ, base 180, **all emitting**. Runs from `y −1664` south down
a narrow corridor (`x ±80`) which then opens out into a wide hall reaching
`x ±416`, ending near `y −2640`. Floor 80, ceiling 304 throughout.

Same defect class as the stairs and the same map, so this is the likely next
strip. Question for play: in the wide hall the wave spreads outward rather than
running in a line — does that read as deliberate, or as the same sourceless
pulse?

### TODO — MAP03 chain 150, the SDFLTA room

14 sectors around `(−700, −2450)`, base 150, floor 96, ceiling 288,
SDFLTA/SFLATAC.

**Corrected.** This was previously listed as harmless on the grounds that 150 is
below the threshold and RT would never make it a source. That was wrong: the
crest of the wave is 255, well above MAP03's 220, so these sectors *do* flare
into being emitters as the wave passes — they simply go dark again between
crests. Its base being lowest of the three means the pulse has the highest
contrast, not the least.

### TODO — MAP12 chain 196, the 20-wedge ring

20 sectors nested concentrically around `(−1340, −930)`, CASFL27 floor / CASF80
ceiling, floor 96, ceiling 356, base 160 — below MAP12's threshold of 220, so it
does not emit steadily, but like every chain it crests at 255 and flares as the
wave goes round.

The one I would not strip without looking. Twenty wedges arranged in a ring with
a light rotating around them reads like an intentional beacon effect rather than
sloppy lighting. If it stays, it stays on purpose.

## Applying a decision

Flip `enabled=True` on the entry in `tools/make_seqlight_fix.py` — the `CHAINS`
table for a sequence chain, `BLINKS` for a per-sector blink, `SCRIPTED` for an
ACS call — then:

    python tools/make_seqlight_fix.py           # build
    python tools/make_seqlight_fix.py --list    # show all three tables, build nothing

The launcher already loads `d64r-seqlight-fix.wad`. The builder asserts what it
finds everywhere it touches — the 1/2/3/4 family for a chain member, the exact
value for a blink, the exact byte signature for an ACS call — and aborts rather
than patching blind if the map data ever changes.

## The other family: per-sector blinks

69 sectors across 11 maps carry `dLight_Flicker` (MAP01 6, MAP02 13, MAP03 7,
MAP05 10, MAP06 4, MAP16 1, MAP23 9, MAP24 3, MAP25 3, MAP29 9, MAP31 4). These
are per-sector blinks, not travelling waves — one special animates one sector,
so there is no chain to walk and the sector list *is* the effect.

They are judged one at a time, and the test is not "does it animate" but **is
there a fixture in the room the light could be coming from**. A flickering
sector under a hanging lamp, or one holding its own `9802 FlickerLight` thing,
is authored and has a source. A flickering sector whose only "light" is a
texture that merely looks lit is the same sourceless lie as a sequence chain.

`tools/make_seqlight_fix.py` carries these in a second table, `BLINKS`, and
emits them into the same wad.

### DONE — MAP05 sectors 258–262, the light pylons

Five gateways between corridors. Each is a bar 176×80 in plan and 136 tall
whose middle 80 units are the opening and whose two 48-unit ends are enclosed by
one-sided walls, clad floor to ceiling in **SPACECC** — a dark panel of vertical
blue light strips. That is two lit pylons flanking every gate, ten in all.
`dLight_Flicker` on the sector flashed those strips with nothing casting the
light. Base lightlevel 140, below the emission threshold, so RT never made them
a source — the flashing was surface shading alone, which is why it read as fake
rather than as a lamp. Reported from play, stripped.

How they were identified, since "pylon" is not a thing the map format records:
MAP05's 7 `64TechPoleLong` decorations (thing type 1031) were checked first and
ruled out — they stand in non-flickering sectors and GLDEFS gives them a steady
`pointlight LONGLAMP`, not a flicker. The pylons are architecture, not props.

### KEPT — MAP05 sector 122

264×264 room, 208 tall, lightlevel 255, containing a `64LampTechLongHang`
(thing type 1015). The flicker has a real hanging fixture to come from.

### KEPT — MAP05 sectors 155, 162, 164, 295

Thin 64×8×64 slabs faced with SMONDA/SMONAA — computer monitors set into walls.
Each holds its own `9802 FlickerLight` thing at height 32, so the blink was
placed deliberately and has a source. A flickering CRT is not a fake light.

## The third family: effects installed by ACS

The two families above are both visible in the map geometry — a sector carries a
special, and a survey of specials finds it. The third is not. The map carries no
special at all; an `OPEN` script calls `Light_Glow` / `Light_Flicker` /
`Light_Strobe` on a sector *tag* at load, and the effect exists only at runtime.

This blind spot cost a session. `scan_light_specials.py 7` reported MAP07
completely clean — zero sequence sectors, zero blinks — while the map was
visibly flashing in play, and the search went to textures, then to sprites, then
to GLDEFS before landing on `SCRIPTS`. The scanner now reads the ACS source lump
too, so it cannot happen again:

    python tools/scan_light_specials.py 7

The triage is the sequence-chain triage. `Light_Glow` and `Light_Strobe` take an
upper bound that is 255 almost everywhere in this game, and `Light_Flicker`'s
first argument is likewise 255 — which clears any threshold `rt_sector_emis` can
produce, so every one of these turns its tagged sectors into sourceless emitters.

**Where clearing one is not free.** A sector's `lightlevel` in the map data is
the *low* end of an ACS ramp, not its resting value. Where the base is already
255 (most of them), removing the call leaves the room steady bright and nothing
is lost. Where the base is 140, removing the call pins the sector at 140 instead
of letting it rise — that room genuinely gets darker. The scanner prints
`DARKENS if stripped` on exactly those, and it is the one thing to check before
enabling an entry.

### The whole game: 203 calls in 27 maps

Re-derive with `python tools/scan_light_specials.py`. This is a large surface and
almost none of it has been looked at in play. MAP20 alone re-arms the same eight
tags from four different scripts (48 calls); MAP08 has 29, MAP34 17. Only MAP07
has been acted on.

### DONE — MAP07 script 669, all eight calls

Reported from play as a white patch blinking on a wall beside a tech pole
(`screen/fakelightblinklevel7.png`), with the pole itself steady — the pole is a
`64TechPoleLong` carrying a real GLDEFS `pointlight LONGLAMP`, so it was never
the blink. The patch is `Light_Flicker(8, 255, 200)` on sectors 243/245/265/303,
64-tall alcoves clad SMONBA/SPACEBK/SPACEBO; sector 243 contains the pole at
`(−768, −1536)` and 245 the one at `(−1140, −1892)`.

Script 669 is *nothing but* these eight calls, so all eight were stripped on
instruction and the script is now a run of NOPs and its terminator. Five are
free (base 255). Three darken and are called out as such in the table:

| call | sectors | base | on strip |
|---|---|---|---|
| `Light_Flicker(8, 255, 200)` | 243, 245, 265, 303 | 255 (265 is 220) | steady bright |
| `Light_Flicker(28, 255, 220)` | 193, 194, 195 | 255 | steady bright |
| `Light_Strobe(16, 255, 140, 2, 2)` | 218 | 255 | steady bright |
| `Light_Glow(7, 255, 180, 35)` | 224, 257, 262, 348, 354, 423 | 255 | steady bright |
| `Light_Glow(17, 255, 140, 70)` | 236, 426, 427 | 255 | steady bright |
| `Light_Glow(5, 255, 140, 35)` | 94, 351 | 140 | **darkens** |
| `Light_Glow(6, 255, 140, 35)` | 95 | 140 | **darkens** |
| `Light_Glow(39, 255, 140, 70)` | 120, 121 | 140 | **darkens** |

Two to reconsider first if the map reads wrong. Tag 16 is the one entry with an
arguable source — its sector is floored *and* ceilinged in SPORT1, a lamp
texture, so a room flashing under it is not quite the sourceless lie the others
are. And the three glows above are the only changes that can make anything
darker than it was.

## How the ACS patch works

There is no ACS compiler in this tree, so `make_seqlight_fix.py` does not edit
`SCRIPTS` and rebuild. It overwrites each call in the compiled `BEHAVIOR` with an
equal number of `PCD_NOP` bytes, in place. Nothing moves: no script address, no
jump target, no chunk offset, and the lump comes out the same length with the
rest of the map's ACS bit-identical. MAP07 changes exactly 55 contiguous bytes.

Retribution's `BEHAVIOR` lumps are **ACSe** — the byte-coded "little enhanced"
variant, with an `ACS\0` header whose directory is a dummy, the real script table
in an `SPTR` chunk, and one-byte opcodes. Two opcode families carry these calls:

    PUSHnBYTES = 174 + n   (n = 3, 4, 5)   push n one-byte literals
    LSPECn     =   3 + n   (n = 1..5)      call line special, byte operand

so `Light_Flicker(8, 255, 200)` compiles to `177 8 255 200 6 115`, and that exact
six-byte string is what gets matched and zeroed. The builder requires **exactly
one** match inside the script's own address range and aborts otherwise, which is
the whole safety story: if the map is ever recompiled and a call moves or its
arguments change, the build fails rather than NOP-ing some unrelated instruction.
The format marker is checked too, so a map in any other ACS format refuses.

## Load-order trap: maps that are also in the 3D-floor wad

`d64r-seqlight-fix.wad` loads *after* `d64r-3dfloor-rtfix.wad`, so for any map
present in both, **ours wins and ours alone decides what the map contains**.

MAP03 was safe by accident: it has no `special=160` linedefs and is absent from
the combined 3D-floor wad. MAP05 is not — it is one of the 28 maps in that wad
and has one `Sector_Set3dFloor` linedef. Replacing MAP05 without re-stripping
would have silently handed back the 3D floor that hangs RT live upload, undoing
a fix from a different tool with no error anywhere.

The builder therefore runs `strip_3dfloor` over every map it emits and reports
the count. Verified: MAP05 goes 1 → 0.
