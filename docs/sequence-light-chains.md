# Sequence light chains — survey and playtest list

Travelling waves of sector light with nothing in the world casting them. Found
by `tools/scan_light_specials.py`, stripped by `tools/make_seqlight_fix.py`.

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

Flip `enabled=True` on the chain in the `CHAINS` table in
`tools/make_seqlight_fix.py`, then:

    python tools/make_seqlight_fix.py

The launcher already loads `d64r-seqlight-fix.wad`. The builder asserts that
every sector it touches still carries a 2/3/4 special and aborts rather than
patching blind if the map data ever changes.

## Not this problem: the blink family

69 sectors across 11 maps carry `dLight_Flicker` (MAP01 6, MAP02 13, MAP03 7,
MAP05 10, MAP06 4, MAP16 1, MAP23 9, MAP24 3, MAP25 3, MAP29 9, MAP31 4). These
are per-sector blinks, not travelling waves, and are usually authored under a
real lamp texture. Different judgement call, left alone.
