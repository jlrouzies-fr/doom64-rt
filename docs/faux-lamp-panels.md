# Faux lamp panels — SFLATC and SPACECE

Lighting two textures as if they were bulb arrays, to lift rooms that read as
too dark under RT. They are not lamps. This is a deliberate invention, and the
implementation is shaped around keeping it separable from the real fixtures.

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
| `rt_faux_lamp_color` | `6E7F94` | dark blue-grey, used **raw** |
| `rt_faux_lamp_intensity` | `110` | below the real bulbs' 180, on purpose |
| `rt_faux_lamp_max` | `128` | its own budget, see below |

The colour is deliberately *not* hue-normalised. `RT_SectorHue` forces the peak
channel to 1 so a tint can never darken a light; here the darkness is the point,
so `6E7F94` emits `(0.43, 0.50, 0.58)` — roughly half power and cool. These
fixtures do not exist, so they should read as ambient fill the room happens to
sit in, not as a lamp the player will go looking for. Brightness is
`rt_faux_lamp_intensity`'s job, not the colour's.

## Three decisions worth knowing

**Separate light budget.** Faux lights are capped by `rt_faux_lamp_max` and
never share `rt_ceiling_edge_max` / `rt_wall_strip_max`. Edge-lamp demand is
already ~800 segments against a cap of 320, so the cap binds hard and *which*
lights get dropped is the entire behaviour. Adding SFLATC's 76 flats to that
pool would push real bulbs out of the nearest-N set — darkening fixtures that
exist in order to light ones that do not. Both walks collect and trim the two
sets independently, then merge.

**Faux panels ignore the min-light gate.** `rt_wall_strip_minlight` (120) stops
a real strip double-lighting an already-bright room. A faux panel's only job is
to lift a room that is *too dark*, so applying the same gate would reject
precisely the sectors the feature was asked for, and it would look like the
feature does nothing. Real strips still respect it.

**Turning the real lamps off leaves these on.** Both walks used to bail early on
`intensity <= 0 || max <= 0`. That now also checks the faux state, because
"turn the real fixtures down and judge the fake ones alone" is the obvious
comparison to want.

## Verifying

`rt_ceiling_edge_debug 1` and `rt_wall_strip_debug 1` each print a faux tally
alongside the real one — matched surfaces, uploaded, cap, intensity — so a
glance answers whether invented fixtures are crowding real ones.

The build was confirmed to carry the change by reading the cvar names and both
texture literals back out of `gzdoom.exe`. It has **not** been judged in game
yet; that is the open item.

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
