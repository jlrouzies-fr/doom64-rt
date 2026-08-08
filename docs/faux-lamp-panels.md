# Faux lamp panels — SFLATC and SPACECE

Lighting two textures as if they were bulb arrays, to lift rooms that read as
too dark under RT. They are not lamps. This is a deliberate invention, and the
implementation is shaped around keeping it separable from the real fixtures.

See also [[solo-bulb-lamps]] — SFLATDE/SFLATCH, a related but distinct system:
those textures show a real lit bulb in the art, so the light there is white and
modest rather than invented and blue-grey. Same tile-lattice placement
mechanism underneath, generalized to serve both.

## Why these two

Neither carries bulbs in the art and the original game lights neither. What they
do is surface rooms that come out too dark — MAP03's twin-stair hall is ceilinged
in SFLATC, which is how this came up.

Usage across the game decides which walk each one joins, and it mirrors the real
bulb pair exactly:

| texture | uses | slots | analogous to | walk |
|---|---|---|---|---|
| SFLATC | 76 in 7 maps | 33 floor, 43 ceiling | SFLATAQ | flat perimeter (`RT_UploadCeilingEdgeLamps`) |
| SPACECE | 61 in 3 maps | 60 sidedef, 1 floor | SPACEAZ | wall strip (`RT_UploadWallStripLights`) |

SFLATC appears in MAP01, 03, 04, 05, 06, 07, 29; SPACECE in MAP03, 05, 07.
Feeding either to the other walk would match almost nothing.

## Cvars

| cvar | default | notes |
|---|---|---|
| `rt_faux_lamps` | `1` | master switch. `0` shows the rooms as authored |
| `rt_faux_lamp_color` | `3C5078` | dark blue-grey, used **raw**, resaturated to survive intensity 500 |
| `rt_faux_lamp_intensity` | `500` | above the real bulbs' 180, raised after playtest found 110 too dark |
| `rt_faux_lamp_max` | `128` | its own budget, see below |

The colour is deliberately *not* hue-normalised. `RT_SectorHue` forces the peak
channel to 1 so a tint can never darken a light; here the darkness is the point,
so `3C5078` emits `(0.24, 0.31, 0.47)` — a 2.0× blue:red channel spread. These
fixtures do not exist, so they should read as ambient fill the room happens to
sit in, not as a lamp the player will go looking for. Brightness is mostly
`rt_faux_lamp_intensity`'s job — but not entirely, see below.

**Colour and intensity are not independent, because the colour is raw.**
Started at `6E7F94` / `110`: a 1.35× channel spread at a modest brightness. In
play it read as plain white, not blue-grey. The cause is the *raw* design
itself — the RGB you set is multiplied directly by intensity to get emitted
radiance, so once a light is bright enough the tonemapper compresses every
channel toward 1.0 (display white), and channels that started close together
end up closer still as they approach that clip point. Some white-hot clipping
right at the socket is normal for any bright point light; the problem was that
a weakly-saturated tint washed out over a much wider radius than a
well-saturated one would. Raising `rt_faux_lamp_intensity` to `500` (playtest:
110 left target rooms still too dark) made this worse on its own, so the colour
was resaturated to `3C5078` (2.0× spread) at the same time, not raised in
isolation. If intensity is pushed higher still, the colour will likely need
another pass — the failure mode to watch for is the same one, tint reading as
white rather than blue-grey.

## Three decisions worth knowing

**Separate light budget.** Faux lights are capped by `rt_faux_lamp_max` and
never share `rt_ceiling_edge_max` / `rt_wall_strip_max`. Edge-lamp demand is
already ~800 segments against a cap of 320, so the cap binds hard and *which*
lights get dropped is the entire behaviour. Adding SFLATC's 76 flats to that
pool would push real bulbs out of the nearest-N set — darkening fixtures that
exist in order to light ones that do not. Both walks collect and trim the two
sets independently, then merge.

(Note: `rt_sector_emis_minlight` 160 is a *floor* on the emission threshold, not
the threshold — rt_main.cpp takes `max(160, map median + 40)`, which is 220 on
MAP03. It does not affect the faux lights, which are analytic and never gated by
it, but the distinction matters wherever that number is quoted.)

**Faux panels ignore the min-light gate.** `rt_wall_strip_minlight` (120) stops
a real strip double-lighting an already-bright room. A faux panel's only job is
to lift a room that is *too dark*, so applying the same gate would reject
precisely the sectors the feature was asked for, and it would look like the
feature does nothing. Real strips still respect it.

**Turning the real lamps off leaves these on.** Both walks used to bail early on
`intensity <= 0 || max <= 0`. That now also checks the faux state, because
"turn the real fixtures down and judge the fake ones alone" is the obvious
comparison to want.

## Placement follows the bulb lattice, not the perimeter

First attempt used the same perimeter walk as the real bulb arrays: a light every
`rt_ceiling_edge_seglen` (64) units around the sector edge. Judged in play, the
lights looked *misplaced* — and they were. The perimeter has no relation to where
the art puts its sockets, so lights landed between bulbs, in the middle of blank
plate, which reads as light coming from nowhere.

Faux flats now bypass the perimeter walk entirely and place on the socket
lattice. Doom flats map 1:1 to world units anchored at the world origin, so a
socket at texture u appears at every world x where `x mod 64 == u`. SFLATC's
sockets are at 7.5, 23.5, 39.5, 55.5 on both axes, so every faux light now sits
inside a painted socket.

`rt_faux_lamp_stride` (default 2) subsamples that lattice. One light per bulb is
unaffordable — at 16-unit spacing a single 512×512 room wants over a thousand —
so the stride takes every Nth socket on each axis. It counts *absolute* lattice
position rather than a per-sector counter, so the chosen bulbs stay aligned
across tile and sector seams instead of jumping at every boundary.

Two supporting details: the sector bounding box is not the sector, so each
candidate is checked with `PointInSector` (an L-shaped room would otherwise get
lights hanging in its neighbour); and light IDs are derived from sector index
plus lattice cell, never from an emit counter, because the nearest-N set changes
as the camera moves and counter-derived IDs would renumber every light each frame
and flush RR temporal history.

**Still on the perimeter walk: SPACECE.** It is a wall texture, and wall texture
coordinates depend on the sidedef's offsets and pegging rather than on world
position, so the same trick needs real UV work. Its lights are therefore still
placed every 64 units at mid-height and will not line up with its 3×3 lattice.
Open item.

## Lit bulbs in the art

`tools/make_bulb_textures.py` builds `d64r-bulb-textures.wad`, which repaints
both textures' sockets as lit bulbs so the light has a visible fixture. It also
writes `SFLATC_e.png` / `SPACECE_e.png` emissive masks into `rt/mat`, joining the
291 `_e` maps already there, so the painted bulbs actually emit rather than just
looking pale.

The socket centres are **detected** from the art, not assumed, and assuming cost
a pass. SPACECE's columns sit at 10.1/31.1/52.1 but its rows at 9.0/30.0/51.0 —
the axes do not share an offset, and one guessed lattice painted every bulb low
in its housing with a dark crescent above. Detection flood-fills the dark blobs
(with wraparound, since a socket may straddle the tile seam) and asserts the
count against the grid expected.

Only `r <= 1.5` is repainted. The radial profile bottoms out at luminance 37 in
the centre against a plate mean of 59 and is back to plate by `r = 2`, where
SPACECE has a bright rim — the lip of the housing. Painting wider would erase
that lip and the bulb would lose its socket.

Note the interpreter: this tool needs Pillow, which on this machine lives only in
Python 3.13, not the default `python` on PATH.

## Verifying

`rt_ceiling_edge_debug 1` and `rt_wall_strip_debug 1` each print a faux tally
alongside the real one — matched surfaces, uploaded, cap, intensity — so a
glance answers whether invented fixtures are crowding real ones.

The build was confirmed to carry the change by reading the cvar names and both
texture literals back out of `gzdoom.exe`. The lattice placement and the repainted
bulbs have **not** been judged in game.

## Deliberately not done: emission

The real bulb arrays also get `emissiveMult` via `tools/set_bulb_emissive.py`,
which makes the fixture *look* like a large glowing panel while a small analytic
light does the shadow casting. SFLATC and SPACECE were left out of that script.

Emission glows across a surface's whole area, so on a texture with no bulbs in
it the result is a uniformly glowing ceiling rather than a grid of lamps —
exactly the "uniformly bright and directionless" failure the emissive work
already ran into. The analytic lights carry the effect instead. If the panels
read as too flat in play, adding them to `BULBS` in that script is the next
lever, and it is a one-line change.
