# Fake sector lights — survey and playtest list

Sector light with nothing in the world casting it: travelling waves (sequence
chains), per-sector blinks, effects a map's own ACS installs at load, and
painted light shafts that never animate at all. The first three are found by
`tools/scan_light_specials.py` and the fourth by
`tools/scan_fake_lightshafts.py`; all of it is repaired by
`tools/make_seqlight_fix.py` into one wad.

Three of the four are *animation* with no source. The fourth is not animated,
and is the only one where the repair has a second half: where the paint was
imitating light from a real window, removing it leaves a real window with
nothing coming through, so the light gets given back for real. See
[The fourth family](#the-fourth-family-painted-light-shafts).

Two later families do not fit that description at all, and are listed here
because they share the wad and the same underlying question — *what in the world
is casting this?*

- **Fifth, `LAMPS`** — the only family that **adds** rather than strips. Where a
  fixture is real in the art and simply was never wired, the repair is a light
  **thing** in the map, which is how Retribution itself does it everywhere.
- **Sixth, `STATIC_ANIMS`** — an ANIMDEFS animation that paints its own lighting,
  frozen to one frame. Currently all disabled; see the family's section for why
  the one attempt was wrong.

## Before any theory: run the scanner

The families below are invisible in the map geometry to varying degrees and the
ACS one is invisible entirely, so a surface that "looks wrongly lit" is not a
texture problem until the survey says so.

    python tools/scan_light_specials.py 13     # sequence + blink + ACS, one map
    python tools/scan_fake_lightshafts.py 13   # painted shafts

Skipping this cost most of a day on MAP13's CTEL alcove — see
[DONE — MAP13 script 669](#done--map13-script-669-the-tag-30-glow). The answer
was one line of scanner output, and the work went to the texture instead.

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
ACS call, `SHAFTS` for a painted light shaft — then:

    python tools/make_seqlight_fix.py           # build
    python tools/make_seqlight_fix.py --list    # show all three tables, build nothing

The launcher already loads `d64r-seqlight-fix.wad`. The builder asserts what it
finds everywhere it touches — the 1/2/3/4 family for a chain member, the exact
value for a blink, the exact byte signature for an ACS call, the exact current
`lightlevel` for a painted shaft — and aborts rather than patching blind if the
map data ever changes. Sector indices are positional, so an edit that inserts one
sector shifts every entry below it; asserting the value we expect to find is what
turns that into a build failure instead of a silently mis-patched room.

A painted shaft also needs its sky pk3 rebuilt if the moon moved:

    python tools/gen_moon_sky.py --azimuth 135 --altitude 25
    python tools/pack_rt_sky.py

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

### DONE — MAP13 script 669, the tag 30 glow

`Light_Glow(30, 255, 200, 35)`, an `OPEN` script, on **16 sectors**:
96, 97, 98, **126**, 144, 162–165, 170–173, 188–190. Bases are 220 and 255, both
at or above the glow's low end, so nothing darkens when it goes.

Sector 126 is the one that was reported: the 64×64 alcove at (864, −1312) whose
floor *and* ceiling are the CTEL telemetry panel. MAP13's emission threshold is
200, so the sector spent its whole cycle above it and both flats self-emitted on
a sine — a panel lighting itself, brightening and dimming, in an otherwise black
room (`screen/level13badlitstartred.png`).

**This one call cost most of a day, and none of it needed to.** It was reported
as "a fake light sequence", correctly, in the first message about it. What
followed was three rounds of work on the *texture* — an `_e` emissive mask, a
`textures.json` attached light, an `rt_eye_panels` engine feature, then flattening
the artwork's own animation — because a hand-written scan of `BEHAVIOR` came back
"no light calls on tag 30" and was believed. That scan searched for a dword equal
to the special number. The encoding is `PUSHnBYTES args… LSPECn special`, which
`acs_call_signature()` in `make_seqlight_fix.py` spells out in six lines, and
which the section below documents.

The scanner in this repo answers it in one line and always did:

    python tools/scan_light_specials.py 13
    Light_Glow(30, 255, 200, 35)  sectors=[96, 97, 98, 126, ...]  base=[220, 255]

**Run the scanner before forming any theory about a surface that looks wrongly
lit.** Not after the texture work, not to confirm a hypothesis — first. The three
families it covers are invisible in the map geometry to varying degrees, and the
ACS one is invisible entirely.

What finally found it was instrumentation rather than reasoning: `rt_tex_probe`
(see `rt-lighting-practices.md` §25) printed the surface's `lightlevel` sweeping
202↔255 at runtime while the patched map data said 180, with `sector_emis`
tracking it 0.013 → 0.350. That is a runtime animation and nothing else, and it
ruled out every texture-side explanation in a single line of output.

### The half the scanners could not see: COMPUTED arguments

**This cost the better part of a day, twice, after the user had correctly named ACS as
the cause in the first message about it.** Read this before writing another scan.

`scan_light_specials.py` and the `Scripted` family both identify a call by its **byte
signature** — `PUSHnBYTES`, the literal arguments, `LSPECn`, the special. That only
exists when the compiler could fold every argument into a byte. A call like

```c
Light_Fade(tag, random(220, 255), tics)
```

pushes its arguments with preceding instructions, so **there is no literal run to
match** and a signature scan cannot see it *at all*. It is not a near miss; it is
structurally invisible. Two such calls on MAP13 survived four separate scans of the
same 1889-byte lump, including one that decoded the 4-byte `LSPECnDIRECT` form — every
one of them keyed on the arguments.

**Scan for the opcode pair instead.** `LSPECn` is `3 + argc`, and the special number is
the byte after it, both present regardless of where the arguments came from:

```python
if blob[i] in (4, 5, 6, 7, 8) and blob[i+1] in LIGHT_SPECIALS:
    argc   = blob[i] - 3
    packed = blob[i-1-argc] == 174 + argc     # literal, the old scan finds it
    #  not packed  ->  COMPUTED, only this scan finds it
```

Game-wide that turns up **147 computed calls** against 488 literal ones.

Two further things made it look impossible, both worth knowing:

- **`rt_dump_lightthinkers` reported 0 thinkers at level load.** `Light_Fade` creates
  its thinker *per call* from the loop, not at load, so a dump at load is silent while
  the effect is running. A thinker census is only evidence at the moment you take it.
- **The repair has to differ.** NOPing a computed-arg call leaves its `argc` values on
  the VM stack, and in a looping script that grows without bound. Overwrite the
  **special number with 0** instead: `LSPECn` still executes and still pops exactly
  `argc` arguments, `P_ExecuteSpecial` gets special 0 and does nothing. One byte per
  call, stack balanced, lump length unchanged.

### DONE — `Light_Fade` in script 669, fourteen maps

The same fixture across the game. Script 669 is type **OPEN** on every one of them, so
it runs at map load, unconditionally, forever.

| map | calls | | map | calls |
|---|---|---|---|---|
| MAP10 | 3 | | MAP21 | 3 |
| MAP12 | **10** | | MAP22 | 1 |
| MAP13 | 2 | | MAP23 | 2 |
| MAP15 | 2 | | MAP24 | 1 |
| MAP17 | 1 | | MAP33 | 2 |
| MAP18 | 2 | | MAP34 | 4 |
| MAP19 | 1 | | | |
| MAP20 | 1 | | **total** | **35** |

On MAP13 these drove tags 29 and 10 — sectors 0, 43, 94, 179, 210, 211, 243 — sweeping
221↔255 continuously and in lockstep. The pillar sides and walls carry tag 29 and the
ground does not, which is exactly why some surfaces in that courtyard pulsed and others
did not.

**Scoped tightly, and the scoping matters more than the strip:**

- **`Light_Stop` is 67 of the 147 computed calls and must never be stripped.** It is
  the opposite operation — it turns an effect *off*. Removing it leaves that effect
  running forever.
- `Light_Fade` / `Light_ChangeToValue` in scripts 2–30 are triggered by gameplay —
  doors, switches, events — not installed at load. Those are authored moments.
- Other argument counts inside 669 are a different call shape and are not assumed to be
  the same fixture without looking at one.

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

## The fourth family: painted light shafts

The first three families all *animate*, which is what made them findable — a
survey of specials or of ACS calls turns them up. This one does not move at all,
carries no special and no script, and every scanner above reports the map clean.

A map author cut wedge-shaped sectors out of a room's floorplan, gave them a
higher `lightlevel` than the room, and left everything else identical: same
floor height, same ceiling height, same floor flat, same ceiling flat. In the
software renderer that reads as light slanting in through a window. It is the
light drawn on by hand.

Under RT it stops being a drawing. `rt_sector_emis` makes any sector at or above
the per-map threshold a **surface emitter**, so a wedge at 255 inside a room at
170 does not merely look brighter — it radiates, throws GI onto the pillars
beside it, and (because the wedge spans the room's full height) emits from the
**ceiling as well as the floor**.

    python tools/scan_fake_lightshafts.py 13

The signature the scanner looks for is exactly "identical but brighter":
`S.lightlevel − N.lightlevel >= 48` across a two-sided line, with floor height,
ceiling height and both flats equal, and no special on `S`. A real fixture
almost never looks like this — a lamp recess changes the ceiling height, a light
panel changes the flat. When nothing changes but the number, the brightness is
not describing anything that is there. Sky-ceilinged sectors are skipped: those
are open to a sky that is a genuine RT light, so bright is correct.

### The family is wider than shafts — and the scanner only finds shafts

`scan_fake_lightshafts.py` requires the bright sector to **match its neighbour's floor
and ceiling flats**, because that is what makes a painted shaft a shaft. A wall alcove or
a door recess never matches, so the scanner reports nothing while the defect is plainly
on screen.

When a surface looks self-lit and both `scan_light_specials.py` and
`scan_fake_lightshafts.py` come back clean, widen the test by hand — **above the map's
emission threshold, and brighter than every neighbour**:

```python
if lv[i] > threshold and lv[i] - max(lv[n] for n in adj[i]) >= 30: ...
```

On MAP13 that turns up 38 candidates where the two scanners find 4.

The triage is the one the MAP05 pylons got: **is there anything in the room the light
could be coming from?** The screenshots answer it directly in both cases below — the wall
immediately around each element is black while the element is lit, and no real fixture
lights a recess without lighting its own wall.

### DONE — MAP13, the C921 wall alcoves and the HDOR10 door recesses

Reported as `screen/fakelitlevel13wallelement.png` and
`screen/fakelittexturearounddoorlevel13.png`.

| sectors | element | from | to |
|---|---|---|---|
| 162, 170–173 | C921 alcove (C92 relief, pentagram at its foot), L170 halls | 255 | 170 |
| 163–165, 188–190 | the same alcove in the L180 halls | 255 | 180 |
| 35 | HDOR10 door recess (HDOR10A mirrored ×4, the star panel) | 220 | 180 |
| 32 | the second door of that design | 220 | 200 |

The alcoves are 64×16 / 16×64 recesses, so at 255 the recess *and its own jambs* emitted
while the C53 wall around stayed dark — "the texture inside the alcove, and the side of
the alcove itself". The door recess is 80×272 and took the door, its jambs and the lintel
with it as one pale slab.

Both were split by host-room brightness rather than done as one entry: the same fixture
must not end up lit in one corridor and dark in the next.

**The torches at the door are real and stay.** They are things, they light the C22 demon
panels, and none of this touches them — that is the whole point of separating "the fixture
is real" from "the sector is painted".

### DONE — MAP13, four fans in two halls

Reported from play as `screen/level13fakeoutside light streaks.png`: bands
across floor and ceiling of a large dark hall, reading as moonlight through a
window, with no moon anywhere.

| sectors | host room | fans | from | to |
|---|---|---|---|---|
| 136, 137 | 75 (L170) | 5 wedges each, west hall | 255 | 170 |
| 134, 135 | 14 (L180) | 5 wedges each, north colonnade | 255 | 180 |

Two sectors per hall, and **each one is the whole fan** — Doom sectors need not
be contiguous, so sector 136 is all five of its wedges at once, the same trick as
MAP03's twin staircases. MAP13's threshold is 200, so 255 emits and the host
rooms at 170/180 do not: the contrast in the screenshot is the whole mechanism.

The west fans splay east out of two **real** `F_SKY1` window slots in the west
wall (sectors 54/55, 15 units deep at `x −2063…−2048`, `z 40…160`). The north
fans splay south off a colonnade open to the sky. That is what makes this family
different from the other three: the paint was imitating something that could
actually exist.

### The other half of the repair — an actual moon

Dropping the wedges alone would leave both halls with real windows and nothing
coming through them. So the light is given back for real:

- **The disc you see.** `MOONSKY`, built by `tools/gen_moon_sky.py` and packed by
  `tools/pack_rt_sky.py` into `d64r-rt-sky.pk3`. It is the WAD's own `SPACE`
  starfield tiled to **1024 wide** with one moon painted in. The width is not
  cosmetic: `hw_skydome.cpp` uses `xscale = texw < 1024 ? floor(1024/texw) : 1`,
  so the 256-wide `SPACE` wraps **four times** around the horizon — painting a
  moon into it at 256 would put four moons in the sky. At 1024 (four copies of
  `SPACE`, so the starfield is pixel-identical to before) it wraps once.
- **The light you feel.** `rt_sun`, RTGL1's analytic directional light, pinned in
  the launcher at intensity 90, altitude 25°, azimuth 135°, colour `B4C8FF`.

They are two halves of one thing and must be aimed alike. RT's sky is a
rasterised cubemap sampled on ray miss and is **not** importance-sampled, so the
painted disc casts nothing usable at 1 spp — it is scenery. `rt_sun` casts the
shafts but draws nothing. Move one, move the other.

**Why 135°.** `rt_sun_b` is the moon's own compass bearing (the code negates it
to get the travel direction). The west windows need light travelling `+x`; the
north colonnade needs it travelling `−y`. North-west is the only bearing that
gives both, at a 45° rake each. Due west (`ab-moon.cmd west`) serves the west
hall alone at full rake and abandons the colonnade — the two fans were painted
implying two different suns, which is itself a tell that neither was real.

### Aiming it from the console — the `moon` CCMD

    moon                    print the current aim
    moon <az> [alt] [int]   swing both halves together

The disc is **geometry**, not paint: `RT_DrawMoonQuad` (`hw_skyportal.cpp`) draws
a quad after the dome along the `rt_sun` direction, so it sits at the light's own
bearing by construction and the two cannot drift apart. Nothing to calibrate.

Full detail, including the two failure modes that got there — the sky dome's 60°
altitude ceiling and the `(doom_x, doom_z, doom_y)` vertex order — is in
`docs/moon-and-sky-leaks.md`.

| cvar | default | what it is |
|---|---|---|
| `rt_moon_geo` | `1` | draw the disc as geometry (0 = no disc) |
| `rt_moon_geo_size` | `12` | apparent diameter in degrees |
| `rt_moon_presets` | `1` | apply the per-map aim table below |

### Per-map aim — `RT_MOON_PRESETS`

One moon, many maps, and each map's windows face wherever its author pointed
them — so a bearing that lights one level rakes uselessly across the next.
`RT_MOON_PRESETS` in `rt_main.cpp` is a small table applied at `RT_OnLevelLoad`:

| map | azimuth | altitude | why |
|---|---|---|---|
| MAP13 | **90** | 25 | Due north, settled in play. The painted shafts implied *two* suns — the west hall wants light travelling `+x`, the north colonnade `−y` — and 135 was the geometric compromise. 90 reads better: it rakes hard through the colonnade and still catches the west windows obliquely. |

Maps with no entry fall back to the launcher's `rt_sun_a/b`, **captured on the
first level load** — without that snapshot the fallback would quietly become
"whatever the last map with a preset set", and the table would be sticky in one
direction only.

The table is engine-side rather than in the sky pk3 for a hard reason:
**ZScript cannot set these cvars.** `_CVar.SetFloat` throws *"Attempt to change
CVAR outside of menu code"* for anything without `CVAR_MOD`, and every `RT_CVAR`
is `CVAR_GLOBALCONFIG|CVAR_ARCHIVE`. A `WorldLoaded` handler was the obvious
place for this and it does not work.

Adding a map is a console round trip, no rebuild needed to *find* the answer:

1. `rt_moon_presets 0` (so the table stops overriding you), or just play a map
   that has no entry.
2. `moon <az> [alt]` until it looks right.
3. Bare `moon` — it prints the ready-to-paste row for the current map.
4. Paste into `RT_MOON_PRESETS` with a note saying *which windows* it serves, and
   rebuild.

`intensity` is `-1.f` in a row that only wants to turn the moon and not rebalance
the level's brightness, which is most of them.

**The disc can no longer be aimed apart from its light.** It is a quad placed at
`dir × R`, with `dir` built from the same `rt_sun_a/rt_sun_b` the light uses, so
there is no offset, no sign to settle and no calibration to pin. The painted moon
this replaced needed four cvars and a sky rotation and still could not go above
60° — see `docs/moon-and-sky-leaks.md` §8/§9.

Intensity, altitude and bearing are also pre-set as arms of `tools/ab-moon.cmd`
(`off | dim | moon | bright | noon | west`), including a deliberately
over-lit `noon` arm whose only job is to make the shaft geometry unmistakable
when you cannot tell a bad azimuth from a light that is merely too dim to see.

`rt_sun` is a **global** cvar, so the moon is up on every map, not only MAP13.
That is coherent — the sky is a starfield everywhere — but it is also the one
change here with reach beyond the reported room. Fully enclosed maps get nothing
(a directional light is occluded by geometry like any other), but any map with a
geometric **sky leak** will now show a hard-edged directional wash where it
previously showed only the diffuse `rt_sky` bleed. MAP01 had exactly such a leak
(§1.2 of `open-issues-rt-lighting.md`, mitigated by dropping to a night sky at
`rt_sky 25`); it is the first place to look if a room outside MAP13 reads wrong.

### The rest of the game — 149 shafts in 15 maps, unexamined

    python tools/scan_fake_lightshafts.py

| map | emitting | map | emitting | map | emitting |
|---|---|---|---|---|---|
| MAP01 | 12 | MAP12 | 10 | MAP20 | 9 |
| MAP02 | 37 | MAP13 | **4 — done** | MAP21 | 9 |
| MAP05 | 1 | MAP15 | 10 | MAP22 | 10 |
| MAP08 | 8 | MAP16 | 10 | MAP24 | 1 |
| MAP10 | 10 | MAP18 | 11 | MAP34 | 7 |

None of these have been looked at in play, and the count is **not** a to-do
list. The geometric test is deliberately loose, and a bright sector that happens
to match its neighbour's flats can still be perfectly well motivated — a bay
under a lamp fixture, a floor around a glowing pool. Judge them the way the
blinks are judged: **is there something in the room the light could be coming
from**, and if the answer is a window, the repair is a moon, not a deletion.

## The fifth family: fixtures that need a light ADDED

Everything above removes light. This one gives it. Where the artwork draws a lit
fixture that the original game never wired, the mechanism is a **light thing in
the map** — `LAMPS` in `make_seqlight_fix.py`.

That is not an invention; it is what Retribution does throughout. **MAP02 lights
its red corridor elements with 48 `PointLight` (9800) and 35 `PointLightFlicker`
(9802) things**, the red ones at `arg0=255, arg3=32`, with nothing whatsoever on
the texture.

Texture metadata cannot substitute, and a full day was spent proving it the hard
way on C23 and CTEL:

| attempt | result |
|---|---|
| `_e` mask + `emissiveMult` | glows, illuminates nothing — RTGL1 emissive is not a light source |
| `lightIntensity` on a **wall** | nothing at all: the light lands at the quad centre with no normal offset, i.e. buried in the wall and fully occluded |
| `lightIntensity` on a **flat** | unreliable — needs the prim to pass a strict quad test that a BSP-split subsector often fails |
| `lightEvenOnDynamic` | did not rescue the flat case either |

**Thing types and arguments.** 9800 `PointLight`, 9801 `PointLightPulse`, 9802
`PointLightFlicker`. `arg0..2` = RGB, `arg3` = radius, `arg4` = secondary radius.
For **Pulse** the period comes from the thing's **`angle`** — `specialf1/TICRATE`
seconds, sine-cycling `arg3`↔`arg4` (`a_dynlight.cpp` `Activate`), so `angle=140`
is a 4-second cycle.

Keep the dim end **above `rt_dynlight_minradius`** (16 in the launcher) or the
light is culled at the bottom of the cycle and the fixture blinks off instead of
dimming.

### DONE — MAP13 sector 126, the CTEL alcove

Two 9801 things at the alcove centre (864, −1312), one 16 above the floor panel
and one 16 under the ceiling panel so each reads as coming off its own fixture:
red `255/0/0`, radius 144 ↔ 60, `angle=140`. Paired with the tag-30 ACS strip and
the 255 → 180 shaft fix above; with the surface no longer lighting itself, these
carry the whole fixture.

## The sixth family: animations that paint their own lighting

Some Doom 64 fixtures animate by repainting their lit elements brighter and
darker frame by frame — the light is *in the artwork*. Under a path tracer that
is baked lighting one level below a painted shaft, and no amount of real lighting
corrects it, because the surface is lighting itself.

`STATIC_ANIMS` freezes such an animation to one dim frame via a generated
`ANIMDEFS` lump. **Every entry is currently disabled, and the one attempt was a
mistake worth keeping visible.**

CTEL (`CTEL1`..`CTEL8`, 4 tics each) looked like exactly this case. Measured per
gem cluster, it is two behaviours at once:

| | behaviour | verdict |
|---|---|---|
| 8 rim clusters, 4 px each | same luminance set cyclically shifted one frame each; total **891 in every frame** | a chase turning around the panel — **motion, keep** |
| 1 centre blob, 13 px | `44 → 1166`, no rotation; **by itself the tile's entire 2.20× envelope** | painted fade — remove |

Freezing the animation killed both. The fade was removed at the source instead —
`tools/make_ctel_static_center.py` holds the *centre blob* at its darkest across
all eight frames and leaves every other pixel alone, shipping replacement lumps
in `d64r-ctel-fix.wad` (`TX_` namespace, like `make_bulb_textures.py`). The ring
keeps turning; the panel stops pulsing.

Two rules fall out of that:

- **Measure per cluster before freezing anything.** "The animation pulses" and
  "one element of the animation pulses" call for completely different repairs.
- A single-frame ANIMDEFS animation **aborts startup** — `animations.cpp:480`,
  *"Animation needs at least 2 frames"*, thrown inside `Texman.Init`. Emit the
  same pic twice.

## The seventh family: sectors painted a different COLOUR

The painted-light problem has two halves, and only one of them is brightness.

Lightlevel is dropped and re-derived by RT, which is why a painted shaft shows up as
self-emission. **Colour is not dropped** — `rt_sector_tint_albedo` carries the Doom 64
sector colormap into albedo at full strength *on purpose*, so a red corridor stays red.
The consequence is that a sector painted unlike its room puts a **hard-edged colour
change across a continuous floor**, at the sector boundary, with no gradient and nothing
casting it.

`TINTS` copies every colour field — `lightcolor` plus `color1`..`color5`, all six
together, or the floor and the walls end up disagreeing — from a donor sector, normally
the room the element sits in.

**Never run this over a colour globally.** Doom 64's per-sector colour is real art
direction and most of it is deliberate: MAP13 has 15 sectors sharing the door's warm
salmon and only the two door recesses are wrong — the rest are rooms that are simply
warm.

### DONE — MAP13, the door floor and the courtyard pillars

| sectors | what | from | to |
|---|---|---|---|
| 32, 35 | HDOR10 door recesses, painted warm salmon `(254,146,118)` inside halls at cold blue `(89,164,255)` | donor 15 | the hall's blue |
| 47–52, 61–69, 93 | the H119 courtyard pillars, warm yellow `(254,225,109)` inside a 2944×2944 courtyard at `(146,194,254)` | donor 46 | the courtyard's blue |

The door was reported as *"that door floor texture still has a harsh split of colour —
is it the texture colour that was changed to simulate light in front of the door?"* Yes,
exactly that: the floor texture is `CASFL27` on both sides of the line, and the torches
flanking the door are real lights that already warm that floor themselves, so the paint
was both hard-edged and double-counted.

The pillars are the more instructive case. **Their lightlevel is 200, which is not above
MAP13's threshold**, so they never self-emitted and no amount of brightness work would
ever have touched them. H119 itself is dull mottled brown-purple stone — the gold-brass
look was *entirely* the sector colour, pillars lit warm by nothing in a night courtyard
whose only real light is a cool moon.

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
