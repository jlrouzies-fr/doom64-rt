# Fake sector lights — survey and playtest list

Animated sector light with nothing in the world casting it: travelling waves
(sequence chains) and per-sector blinks. Found by
`tools/scan_light_specials.py`, stripped by `tools/make_seqlight_fix.py`.

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

`rt_sector_emis` turns sector lightlevel into surface emission for any sector at
or above `rt_sector_emis_minlight` (160 in the launcher). So an animated sector
at or above 160 *is* the light source under RT — the floor and steps themselves
glow and pulse with no fixture. Below 160 the special only shades the surface,
which reads far less wrong.

That threshold is the triage rule: **base lightlevel ≥ 160 → sourceless pulsing
emitter; below → cosmetic shading only.**

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

14 sectors around `(−700, −2450)`, base **150 — under the threshold**, so RT
never turns these into a source. Floor 96, ceiling 288, SDFLTA/SFLATAC.

Lowest priority: the pulse only shades surfaces here. Worth a look mainly to
decide whether the shading animation alone is still distracting.

### TODO — MAP12 chain 196, the 20-wedge ring

20 sectors nested concentrically around `(−1340, −930)`, CASFL27 floor / CASF80
ceiling, floor 96, ceiling 356, base **160 — exactly on the threshold**, so it
emits, but only just.

The one I would not strip without looking. Twenty wedges arranged in a ring with
a light rotating around them reads like an intentional beacon effect rather than
sloppy lighting. If it stays, it stays on purpose.

## Applying a decision

Flip `enabled=True` on the entry in `tools/make_seqlight_fix.py` — the `CHAINS`
table for a sequence chain, `BLINKS` for a per-sector blink — then:

    python tools/make_seqlight_fix.py           # build
    python tools/make_seqlight_fix.py --list    # show both tables, build nothing

The launcher already loads `d64r-seqlight-fix.wad`. The builder asserts the
special it finds at every sector it touches — the 1/2/3/4 family for a chain
member, the exact value for a blink — and aborts rather than patching blind if
the map data ever changes.

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
