# RT Lighting & Colour — Practices for Doom 64 Retribution

**Date:** 2026-08-07
**Audience:** agents and contributors touching `rt_main.cpp`, `rt_state.h`, or the
hwrenderer scene files.

Derived from the MAP02 blue-room / red-corridor work. Read this before "restoring"
any original-game lighting behaviour in the RT renderer — the traps below were all
hit for real, and several cost a full investigation each.

---

## 1. Original sector data is baked shading, not lighting

Doom 64 stores room atmosphere as a per-sector **colormap** (`lightcolor`, e.g. MAP02's
blue armor room is `0x0050FF`) plus a **lightlevel**. Neither is a light. There is no
position and no falloff, and GZDoom folds both into the vertex colour before RT ever
sees them.

Handing that to a path tracer as albedo **double-counts shading**: RTGL1 computes its
own lighting, then you multiply by the old renderer's output on top. That is the
documented cause of both:

- the **yellow key-door neon wash** (baked bright colour read as albedo), and
- the **black, light-absorbing rooms** (`lightlevel 0` → albedo 0, so no amount of RT
  light can recover the surface).

`rt_mod_compat`'s force-white in `rt_main.cpp` exists to work around exactly this.

**Rule:** discard the baked shading, keep the art intent, re-express the intent as a
physical parameter. `lightlevel` is baked shading. `lightcolor` is art intent.

## 2. Split hue from intensity

The two arrive multiplied together, which is why the original workaround had to throw
away both. Separate them:

- Keep **hue**: peak-normalize the colormap so the largest channel is exactly 1
  (`RT_SectorHue` in `rt_main.cpp`), then lerp toward white by a strength cvar.
- Keep **lightlevel discarded** for albedo purposes.

Peak-normalizing matters for a non-obvious reason: it makes the transform **incapable
of brightening or darkening**. It can only remove off-hue channels. That property is
what lets you rule the tint out as a cause of any overexposure complaint without
running an A/B — which is exactly what happened with the yellow door.

## 3. Put colour where it physically belongs

Albedo tint says *"the walls are painted blue."* You get blue diffuse and blue GI
bounce, but **white lamps, white bloom, white speculars**. It reads as blue paint under
a white lamp — muddy, and not what the original looks like.

Light colour says *"the lamps are blue,"* and then the path tracer does the rest for
free: emitters, bloom, speculars, and GI all inherit the tint physically.

Apply the hue to the light side first, and treat albedo tint as the fallback for
sectors with no light source at all.

## 4. Match the emitter's shape to what the original depicts

Getting the colour right is not enough; the *form* of the light has to match.

The MAP02 red corridor is lit purely by sector lightlevel — there is no light actor
anywhere in it. Two candidate fixes were tried:

- **Sector-centre analytic sphere** (`rt_sector_lights`): produced a visible red point
  light floating in the corner. Rejected — the original shows glowing floor panels, not
  a bulb.
- **Surface self-emission** (`rt_sector_emis`): the bright surfaces emit, scaled by
  their own lightlevel, and light the room by GI. This is the right shape.

Ask what the original image is *depicting* — a fixture, a glowing panel, an ambient
wash — and pick the RT construct with that shape.

**And put it where the art draws the emitter, which is a question about the TEXTURE TILE,
not about the surface.** A wall texture repeats, so the unit of "one fixture" is one
64×64 tile, not one sidedef: a 128-tall band is *two* stacked panels with *two* screens.
Placing one light at the middle of the band puts it on the seam between them, lighting
bare panelling — `screen/pointlightinthemiddlebad.png`. Within the tile, the emitter's
position is the `_e` mask's lit centroid, and it is not necessarily the middle: SMONAA,
SMONCA and SMONDA all draw their screens at 0.46–0.54 of the tile, so "centre" looks like
the rule, but SMONBA's readout block sits at **0.688** — and the panels Retribution itself
wired sit at 0.625–0.688 to match. Derive the position from the mask; do not centre it.

## 5. Albedo cannot rescue an unlit room

Albedo is a reflectance multiplier. **Zero incident light × any albedo is still black.**

When a room looks wrong, first establish whether it has any light source at all. If it
does not, no amount of tint work will help, and you are solving the wrong problem. The
blue room had emissive texture light to tint; the red corridor had nothing, and needed
a light *created*.

## 6. No map-name or texture-name special cases

The first attempt at the blue room used `strstr(mapname, "map02")` plus a hand-tuned RGB
window matching one sector colour, with three eyeballed tint constants. That fixes one
room and leaves the general defect everywhere else — and colored sector light is Doom
64's signature, used in dozens of rooms.

The data you need is already in the map (`sector.Colormap.LightColor`). Derive from it.
A rule that reads map data generalizes; a rule that matches a name does not.

Corollary: `strstr` for map names is also just wrong — it matches `map020`.

## 7. Scope RT render state with RAII

`rtstate.m_sectorLightColor` was originally a plain assignment written only by
walls/flats. It stayed set after the flat finished and leaked the last sector's hue onto
any later world geometry that did not set it.

Use the `push_*` / `detail::AutoPop` idiom already established by `push_type` and
`push_uniqueid` (see `push_sectorlight` in `rt_state.h`). It restores the previous value
on scope exit, so a leak is structurally impossible.

Also: do not overload existing state for a new purpose. `m_lightlevel` is sprite-only and
feeds `RgMeshInfo::localLightsIntensity` for *every* primitive; writing world lightlevel
into it would silently change local-light response on all map geometry. A separate
`m_sectorLightLevel` was added instead.

## 8. Check what the launcher actually forces

`tools/launch-retribution-rt.cmd` overrides most `rt_*` cvars on every launch. During
this work, tinting the analytic ceiling lamps would have done **nothing visible**,
because the launcher forces `rt_ceiling_lamps 0` and `rt_sector_lights 0` — the MAP02
ceiling glow is texture emissive under `rt_emis_mapboost`, not an analytic sphere.

Read the launcher before concluding where a light comes from. A renderer-side reading
alone is not enough.

## 9. Console-typed cvars persist and poison later runs

Every `RT_CVAR` is `CVAR_ARCHIVE`. A value typed into the console is saved to the ini and
silently applies to every future launch. This has cost this project multiple sessions
(see the `rt_upscale_fsr2` root cause in the RR docs).

- Force every knob you care about explicitly in the launcher.
- Pass A/B arms through the launcher's `--` passthrough, never by typing into the console.
- Use `RT_CVAR_NOARCH` for anything that is purely an investigation knob.

## 10. Instrument to discriminate, not to confirm

Two lessons from the yellow-door hunt:

- **Toggling a knob and seeing no change is ambiguous.** `rt_dynlight_stack_atten` looked
  inert in both positions — which is equally consistent with "it works and nothing is
  stacked" and "the bucketing is broken." The fix was a histogram printing
  `max stack`, which answers the question directly. Prefer an instrument that reports the
  intermediate value over a toggle that reports only the outcome.
- **A debug visualization must not destroy what you are localizing.** `rt_dynlight_debug`
  drew 67 magenta markers at intensity 400 and turned the whole scene purple, hiding the
  very light being hunted. Console statistics and marker spheres are now separate
  (`rt_dynlight_debug` vs `rt_dynlight_debug_marks`).

  **That separation was not enough, and this recurred on 2026-08-08.** The flat bulb lamps
  copied the same 400-intensity marker and emitted up to 320 of them, turning a whole MAP02
  room cyan. A marker *is* a real uploaded light, so N markers light the scene N times over
  — the danger scales with **count**, and a per-marker toggle does not bound it.

  All marker spheres now share `rt_light_mark_intensity` (25) and `rt_light_mark_max` (24
  nearest per path). When a debug aid is itself made of the thing being measured, the
  budget has to be on the aggregate.

## 11. Verify a change is live before believing a null result

Before concluding "the tint is too weak" or "that setting does nothing", force the value
to an absurd extreme and confirm the pixels move. This repo has a standing history of
silent-plumbing failures where a correct diagnosis was discarded because the change never
reached the renderer.

---

## Source style notes

- `RT_CVAR` descriptions carry the **reasoning**, not just the units: the failure the
  default prevents, what was measured, and the date when it was a session finding. Follow
  that — several of these descriptions are the only record of a root cause.
- Comments explain the trap, not the syntax. Prefer "why this is not the obvious thing"
  over restating the code.
- `FVector3` uses `.X/.Y/.Z`, and MSVC's strict narrowing rules require float literals
  (`1.0f`, not `1.0`) in braced initializers.
- Local lambdas in the draw path use the `l_` prefix (`l_isemis`, `l_spriteAlpha`,
  `l_worldemissive`).
- New per-primitive state goes in `FRtState` with a `push_*` accessor, never a bare
  public field written from the scene code.

## Cvar map for this area

| Cvar | Default | Purpose |
| --- | --- | --- |
| `rt_sector_tint_albedo` | 1.0 | Sector colormap hue applied to surface albedo. 1.0 matches the original game. Clamped to [0,1]. |
| `rt_sector_tint_lights` | 0.85 | Same hue applied to light/emitter colour — ceiling lamps, hanging lamps, sector lights, emissive surfaces. |
| `rt_sector_emis` | 0.35 | Bright surfaces self-emit, scaled by sector lightlevel. Restores rooms the original lit purely with lightlevel. |
| `rt_sector_emis_minlight` | 160 | Absolute *floor* only. Effective threshold is `max(this, map median + margin)`. |
| `rt_sector_emis_margin` | 40 | How far above the map's own median a sector must be to self-emit. This is what prevents the whole-image flood. |
| `rt_sector_emis_saturation` | 0.80 | The COLOUR gate: a lightlevel-qualifying surface self-emits only if its sector's colormap tint is at least this saturated. Stops a plain bright wall reading as a light. Was 0.58 (measured on MAP04 sector 68, tint 255,231,145 = 0.431, against MAP02's red panels) until 2026-08-28, when three maps in a row needed a preset row raising it to 0.80 — so 0.80 became the default and **MAP02 keeps 0.58** as the only row. |
| `rt_sector_emis_presets` | 1 | Apply the **per-map** saturation table `RT_EMIS_PRESETS` (`rt_presets.cpp`) at level load. One row today: **MAP02 at 0.58**, the only map with a gate *below* the global, because its red corridor panels are what the feature exists for. A map with no row keeps the launcher's value; 0 turns the table off, which is what an A/B of the global has to pass. Like every preset table it writes the cvar AFTER the command line is parsed, so on a listed map it **overrides the pin**. |
| `rt_wall_strips` | true | Analytic lights on wall-mounted bulb arrays: `SPACEAZ`, `SFLATAQ`, `SFLATAS`, `SFLATAP`. Not `SPACEAR` — see §20. |
| `rt_wall_strip_intensity` | 500 | High because a strip light is flush against the wall it lights (see §19). |
| `rt_wall_strip_minlight` | 120 | Was 140, tuned on MAP03's 180s. MAP02 has fixtures at exactly 120. |
| `rt_ceiling_edge_lamps` | true | Lights around the perimeter of lamp **flats** — ceilings *and* floors (§23), for halls `rt_ceiling_lamps` skips. |
| `rt_ceiling_edge_intensity` | 500 | Same occlusion reasoning as wall strips. |
| `rt_ceiling_edge_max` | 320 | Raised from 160 when floors were added — both planes share the cap. |
| `rt_ceiling_edge_debug_marks` | false | Cyan markers, vs the wall strips' magenta, so both paths can be shown at once. |
| `rt_dynlight_minradius` | 16 | Drops raster-era helper `PointLight`s (r=12) while keeping real fixtures (r>=32). |
| `rt_dynlight_rsoft` | 20 | Inverse-square roll-off above this map radius. Lowered from 40; fixed the overexposed yellow key-door jambs. |
| `rt_dynlight_debug` | false | Console stats: upload count + xy-stack histogram + nearest-light dump. |
| `rt_dynlight_debug_marks` | false | Magenta marker spheres, separated so they cannot flood the scene. |

## 12. Emissive surfaces are not light sources in RTGL1

This is the single most important fact in this document.

`HitInfo.inl` computes `emission = h.albedo * tr.emissiveMult` (or the `_e` map), and
`RtRaygenIndirect.inl` applies `emissionMapBoost` — but **only inside `traceBounce()`**.
Emission is collected when an indirect bounce ray happens to land on the surface. It
never reaches `processDirectIllumination`, which is what samples uploaded lights and
traces shadow rays.

Consequences, none of which are tunable away:

- An emissive surface **cannot cast a pool of light and cannot cast a shadow.**
- At 1 spp indirect it contributes weak, noisy, diffuse fill — which reads as "flat".
- Raising `rt_sector_emis` or `rt_emis_mapboost` increases noise and flatness, not
  directional light.

Use emission for **colour and glow**. Use `rgUploadLight` for anything that must
actually light the room. The MAP02 blue room needed colour, so emission was right; the
MAP03 corridor needed cast light, so it needed real lights.

Note also that `RgLightPolygonalEXT` exists in `RTGL1.h` with a working encoder, but
`LightManager.cpp` compiles it out behind `#if TRIANGLE_LIGHTS` and calls
`debug::Error("Polygonal / triangle lights are not supported")`. **Checking the public
header is not enough — check the implementation.** Uploading one crashes the game.
Spherical lights with a wide radius and tight spacing are the working substitute for a
strip.

**And the bounce that collects emission was, until 2026-08-24, both unlit and ~2π
too bright.** The indirect path was two bounces hardcoded and unrolled; under the
live `rt_shadowrays 2` its second vertex sampled no analytic lights at all, and it
multiplied by `1/pdf` with no BRDF or cosine — `E[π/z] = 2π` over — which is why
emissive fill read as saturated, dotted and "very red". Depth is now `rt_gi_bounces`
and the overweight is behind `rt_gi_bounce_legacy` (ships **on**, so nothing moved
yet). Before tuning any `_e` or `rt_emis_mapboost` against how GI *looks*, read
`docs/rt-gi-bounces.md` — the number you are tuning against may be the 2π.

## 13. Never derive a direction from a winding convention you have not verified

Wall strip lights were offset 2 units off the surface to avoid being coplanar with it.
The offset used the left normal `(-dy, dx)` while treating sidedef 0 as the front — but
Doom's front sidedef is on the **right**. Every light was placed 2 units *inside* solid
geometry, fully occluded, emitting nothing.

By eye this is indistinguishable from the lights never being uploaded.

Derive the direction from geometry you can test instead: compare against the sector's own
`centerspot` and flip the sign if it points the wrong way. That is correct regardless of
how the mapper drew the line.

**But see §32 — the centroid version of that test is itself a trap, and the honest fix is
to measure the convention rather than to route around it.**

## 14. Debug output must be aggregated, not truncated

Two failures of the same kind, both of which cost a round trip:

- A "12 nearest sidedefs" dump was swamped by a handful of repeated wall panels, so the
  rarer fixture textures never appeared at all. Aggregating by distinct texture name —
  with use count, which parts they appear as, lightlevel range, and whether the current
  matcher accepts them — showed the whole picture in six lines.
- A bare "0 lights uploaded" cannot distinguish "no fixtures in this map" from "fixtures
  found, all rejected". Print a **rejection tally** broken down by cause, and put the
  cheap gate (texture match) before the expensive one (lightlevel) so the counts mean
  something.

Related: when a fixture-driven feature only half works, the question is always "which
surfaces did the matcher miss", and only a deduplicated inventory answers it.

## 15. Sidedefs are not the only place fixtures live

Doom 64 puts light strips on wall textures **and** on thin sector steps whose flats carry
the lamp texture. A feature that walks `primaryLevel->lines` sees only the first kind.
`RT_UploadCeilingInsetLamps` covers the second (`SFLATAS`/`SFLATAQ`/`SFLATAP`/`SPORT*`),
and the launcher disables it by default — so before writing new code to find a missing
fixture, check whether an existing path already covers it and is merely switched off.

## 16. Absolute lightlevel thresholds do not transfer between maps

`rt_sector_emis` originally emitted from any sector above a fixed lightlevel of 160. That
was correct on MAP02, whose dark corridor has bright panels, and catastrophic on MAP03,
whose *ordinary* rooms sit at 180–200 — every wall, floor and ceiling in the level became
an emitter. With `rt_emis_mapboost` at 200, a plain 180-lightlevel wall emits
`albedo * 0.074 * 200 = albedo * 14.8`. The whole image goes uniformly bright and
directionless: the "fake, not ray traced" look.

180 means "glowing panel" in a dark corridor and "ordinary lit room" on a bright deck. No
global constant can mean both.

The fix is to judge each sector against **its own map's distribution**:
`threshold = max(absolute_floor, map_median_lightlevel + margin)`, computed once per map
(`RT_UpdateSectorEmisThreshold`). Self-tuning, no per-room authoring, and it degrades
sensibly on maps of any overall brightness.

Generalise this: any heuristic keyed on a raw map value should be expressed relative to
that map's own statistics, not to a number tuned on the first map you happened to test.

## 17. Confirm texture identity from source data, not from derived art

`SPACEAI1` was the leading suspect for the MAP03 ceiling strip for several iterations: it
was the nearest texture, it was the only one with a `top` part reaching ceiling height,
and its `_orm`/`_n` maps showed a horizontal band that looked plausibly like a fixture.

It is `SPACEAI` composited with a mirrored copy of itself — plain panelling. The WAD's
`TEXTURES` lump says so in four lines:

```
Texture SPACEAI1, 64, 128
{
	Patch SPACEAI, 0, 0
	Patch SPACEAI, 0, 64 { FlipY }
}
```

Authored PBR side-maps (`rt/mat/*_h.png`, `_n`, `_orm`) are interpretations and can
mislead — a rivet row reads much like a bulb row at 64×64. Extract the actual patch from
the WAD, and read `TEXTURES` for composites. A texture named `FOO1` frequently does not
exist as a lump at all.

Note also that `docs/texture-status.md` records use counts: `SPACEBE` has 12,556 uses,
which alone rules it out as a light fixture.

## 18. Read the existing cvar descriptions — they encode prior root causes

The MAP03 ceiling strips were dark for a reason already written down in this codebase, in
the description of `rt_ceiling_lamp_maxspan`:

> "Large SFLATAQ halls only have edge texture blobs — a center sphere looks like a fake
> mid-ceiling light (MAP02)"

That single line explains the whole symptom: large lamp ceilings are *skipped* to avoid a
bogus centre light, so their bulbs cast nothing. It would have saved several iterations of
hunting for a wall texture that never existed.

A guard that skips a case is not the same as that case being handled. When a fixture is
unlit, check whether some existing path is deliberately excluding it.

The answer was `RT_UploadCeilingEdgeLamps()`: trace the sector **perimeter** instead of
its centre, which suits both a long corridor edge and a small square ceiling panel, and
lives on its own cvar so the centre-sphere path can stay off.

## 19. Lights flush against geometry need far more intensity than free-hanging ones

Wall strips read as *completely unlit* at intensity 120 and 250, and only appeared at 500
— while ceiling lamps hanging in open air look right at 700. A light sitting against the
surface it illuminates has most of its sphere occluded, so the same nominal intensity buys
a fraction of the visible contribution.

Do not conclude "the feature is broken" from a dim result before comparing against an
existing light of known-good intensity in a *similar geometric situation*.

## 20. A fixture rule can be right by proximity on the map you tested

`rt_wall_strips` originally matched `SPACEAR`, and on MAP03 it looked completely correct:
lights appeared, in the right places, along the right trim. It was wrong anyway.

`SPACEAR` is a plain trim panel. The actual bulbs are a separate family of **lamp arrays** —
`SPACEAZ` (4×4 bulbs), `SFLATAQ` (4×4), `SFLATAS` (2×2 large), `SFLATAP`. `SPACEAR` happens
to be the panel on the same thin step that a bulb flat caps, so:

| | `SPACEAR` sidedefs | adjacent to a bulb flat |
| --- | --- | --- |
| MAP03 | 57 | **54 (95%)** |
| MAP02 | 41 | **4 (10%)** |

On MAP03 the light landed a few units from a real fixture and read as correct. On MAP02 the
same rule lights blank wall and misses every lamp in the level.

This is more dangerous than a rule that visibly fails, because the confirming screenshot is
genuinely convincing. Two defences:

- **Confirm the fixture from the pixels, not from the result.** `SPACEAR` has no visible
  bulbs at all — extracting it from the WAD next to `SPACEAZ` settles it in seconds. §17 said
  to check source data over derived art; this extends it: check source data over a
  *good-looking outcome* too.
- **Measure the rule's precision on a second map before believing it.** "How often is this
  texture actually next to the thing I care about" is a query over map data, and 95% vs 10%
  is the entire finding.

Corollary: `SFLAT*` names are not only flats. Doom 64 hangs them on sidedefs — MAP02 carries
`SFLATAQ` as `bottom` 26 times and `middle` 4 times — so the sidedef walk and the flat walk
(`RT_UploadCeilingInsetLamps` / `RT_UploadCeilingEdgeLamps`) each see part of the same
fixture family. Neither is redundant.

## 21. A `middle` texture on a two-sided line does not span the sector

The band code gave `middle` the whole `thisSec` floor→ceiling range, which put MAP02's
lights at mid-room height, floating in front of the fixture rather than on it. The band a
middle texture actually covers is the line's **opening**: `max(floors) … min(ceilings)`.

Only `top` and `bottom` had been special-cased, because MAP03 — the map the feature was
built on — uses the fixture exclusively as `bottom`. The untested part was the wrong part.

## 22. Truncated debug output regresses; make truncation impossible to miss

§14 already recorded that a truncated dump hides rare fixtures. The replacement aggregated
by texture name — and then printed `std::min(24, sorted.size())` rows, sorted nearest-first,
with **no notice that it had truncated**. It reported "30 distinct" and listed 24.

The six it dropped were the farthest, which is exactly where a fixture across the room sits.
An hour went into candidates from the visible 24 while the answer may never have printed.

If output can be capped, the cap must announce itself (`... N more not shown`). A count in
the header that disagrees with the number of rows below it is not a notice — nobody
subtracts.

## 23. A fixture that turns a corner spans two code paths

Doom 64 runs one continuous bulb band along a wall and then across the flat it meets. To
the map it is a single fixture. To this renderer it is two: sidedef textures go through
`RT_UploadWallStripLights`, sector flats through `RT_UploadCeilingEdgeLamps`. A band that
turns a corner lights up on one side of the corner and stops dead on the other.

Two separate bugs produced that symptom at once, and they are easy to confuse:

- `RT_UploadCeilingEdgeLamps` read only `sector_t::ceiling`. Bulb **floors** — 19 sectors
  on MAP02, 46 on MAP03 — were never even looked at. The name of the function is the whole
  explanation, which is why it survived: nobody re-reads a function that is doing exactly
  what it says.
- The flat path had **no marker visualization** while the wall path did. So even the
  ceilings it *was* lighting looked absent in the debug view.

Note `zOfs` has to flip sign with the plane — down from a ceiling, up from a floor.
Sharing one sign buries every floor lamp under the floor where it is fully occluded, which
looks identical to it never being uploaded (§13 again).

**Rule:** when a fixture is unlit on one face and lit on another, ask which *walk* owns each
face before touching either one's matcher. And give paired debug visualizations parity —
one path with markers and one without does not show you "half the lights are missing", it
shows you a half-instrumented renderer.

## 24. Run the existing survey before writing your own, and treat a user's diagnosis as evidence

MAP13's CTEL alcove pulsed bright/dark in a black room. It was reported, in the first
message about it, as *"a fake light sequence"* and then explicitly as *"that lighting ACS
script or whatever it is"*. Both were correct.

What happened instead: a hand-written scan of `BEHAVIOR` came back "no light calls on tag
30", that null was believed, and three rounds of texture work followed — an `_e` emissive
mask, a `textures.json` attached light, a whole `rt_eye_panels` engine feature, then
flattening the artwork's own animation. All of it reverted. The scan was broken: it searched
for a dword equal to the special number, when the encoding is `PUSHnBYTES args… LSPECn
special` — documented in `acs_call_signature()` in `make_seqlight_fix.py`, in six lines, in
this repo.

And the correct scanner already existed, was already documented in
`sequence-light-chains.md`, and answers it in one line:

    python tools/scan_light_specials.py 13
    Light_Glow(30, 255, 200, 35)  sectors=[96, 97, 98, 126, ...]  base=[220, 255]

**Rules:**

- Before theorising about a wrongly-lit surface, run `scan_light_specials.py <map>` and
  `scan_fake_lightshafts.py <map>`. First, not as confirmation afterwards.
- Before hand-rolling a parser for a project format, grep for the encoder. A repo that
  *writes* the format contains the definition of the format.
- A negative result from a tool you just wrote is worth much less than a positive claim
  from the person watching the screen. When the two disagree, distrust the new tool.
- Say which one you ran. "There is no ACS on that tag" was reported as a fact when it was
  the output of an unvalidated five-line loop.

## 25. `rt_tex_probe` — ask the running game, per surface

A string cvar (unarchived, so it is off again next launch). Set it to a texture-name prefix
and every world surface drawn with a matching texture reports once a second:

    +rt_tex_probe CTEL

    rt_tex_probe CTEL5  file=d64r-ctel-fix.wad  lump=11067  lightlevel=215
                        sector_emis=0.095  color=0xFF66E0FF  drawn=1

Four independent facts, each of which had been *guessed at* repeatedly:

| field | answers |
|---|---|
| `file=` | which file the texture actually came from — i.e. whether a replacement wad is winning the load order **at all** |
| the frame name | which animation frame is on screen; names cycling = the animation runs |
| `lightlevel=` | the lightlevel in use **at runtime**, which is not necessarily the map data |
| `sector_emis=` | whether the engine is making this surface self-emit, independent of any texture work |

That fourth line is what finally cracked MAP13: `lightlevel` swept 202↔255 while the patched
map data said 180, with `sector_emis` tracking it 0.013 → 0.350. A runtime animation and
nothing else — which eliminated every texture-side explanation at once, after a day of not
being able to.

**Rule:** when two rounds have gone by without the screen changing, stop proposing fixes and
add the instrument. It is cheaper than the third round. This is §10 and §11 again — the
lesson keeps being re-learned because the instrument feels like a detour when you are sure
you are one edit away.

## 26. A dynlight thing's radius is not its brightness — past `rsoft` it is the inverse

For GZDoom light things (9800/9801/9802), `arg3`/`arg4` are map **radii**, and the engine
turns them into RT intensity as:

    intensity = hi * rt_dynlight_intensity * blink        capped at rt_dynlight_max
    if radius > rt_dynlight_rsoft:  intensity *= (rsoft / radius)^2

With the launcher's `intensity 40 / max 500 / rsoft 20 / minradius 16`, the cap bites at
once (16 × 40 = 640 > 500), so above `rsoft` the only term still varying is an **inverse
square in radius**. Two consequences, both counter-intuitive:

- **A bigger radius makes the light dimmer.**
- The roll-off tracks the *current* radius, so a pulsing light also runs **backwards** —
  dimmest at the crest of its cycle.

Measured on MAP13's CTEL alcove:

| `arg3/arg4` | trough → crest | |
|---|---|---|
| 144 / 60 | 56 → **10** | dim *and* inverted — shipped by mistake |
| 48 / 20 | 288 → 87 | inverted |
| 32 / 24 | 133 → 195 | inverted mid-cycle |
| **20 / 17** | **120 → 500** | correct, 4.2× rise |

"Make it 3× brighter" was implemented as 48 → 144 and made the crest **~9× dimmer**.

**Rules:**

- Keep both radii inside `minradius <= r <= rsoft` (16…20 here). Below `minradius` the
  light is culled outright at the bottom of its cycle and the fixture blinks *off*; above
  `rsoft` the roll-off inverts it.
- That band admits no crest dimmer than the 500 cap. A fixture that needs to be subtler is
  a job for `rt_dynlight_intensity` or `rt_dynlight_minradius`, not for the thing's args.
- Before tuning any light-thing value, read the conversion in `RT_UploadDynLights` rather
  than assuming radius behaves like radius. This is §18 again — the cvar descriptions and
  the code encode prior root causes.

## 27. A scan that keys on values cannot see values it does not have

The single most expensive lesson of the MAP13 work, and it generalises well past ACS.

`acs_call_signature()` identifies a light call by matching `PUSHnBYTES`, the **literal
arguments**, `LSPECn`, the special. That is exact and safe — and it is *blind* to any
call whose arguments are computed, because there is no literal run in the lump to match.
`Light_Fade(tag, random(220,255), tics)` is not a near miss for that scan; it is
invisible to it.

Two such calls drove seven MAP13 sectors in a continuous 221↔255 sweep. They survived
**four** scans of the same 1889-byte lump — including one that decoded the alternative
4-byte `LSPECnDIRECT` encoding — because every scan keyed on the arguments. Game-wide
the class is 147 calls against 488 literal ones, i.e. a quarter of all light calls in
the game were structurally unfindable.

The fix is to key on the part that is always present. For ACS that is the **opcode
pair**: `LSPECn` is `3 + argc` and the special is the next byte, whatever the arguments
were computed from.

**Rules:**

- When a scan returns "none" for something the evidence says exists, ask *what the scan
  keys on* and whether the thing you are hunting is required to have it. A null from a
  matcher is only as strong as its key.
- Prefer keying on structure (opcodes, types, positions) over content (values, names).
  Content is optional; structure is not.
- Say which scan produced a null and what it matched on. "There is no ACS on that tag"
  was reported as fact three times; it was true only of one encoding.

## 27b. `scan_light_specials.py` under-reports ACS — cross-check the compiled lump

Two independent blind spots, both found the hard way, and they compound:

1. **It misses computed arguments** (§27) — a quarter of the game's light calls.
2. **It disagrees with the compiled `BEHAVIOR`.** On MAP11 it reports
   `acs light calls=0` while an opcode scan of that map's `BEHAVIOR` finds **five**
   (four literal `Light_Fade` plus one computed `Light_ChangeToValue`).

So a clean result from it is not evidence that a map has no ACS light. Until it is
fixed, scan the compiled lump directly:

```python
if blob[i] in (4,5,6,7,8) and blob[i+1] in LIGHT_SPECIALS: ...   # LSPECn = 3+argc
```

**And read the script TYPE before stripping anything.** MAP11's four calls live in
script 671, whose type is **12 — the lightning script**, run on each strike. That is the
storm map's authored weather, not a fake light. The type byte is in the `SPTR` chunk:
`struct.unpack_from("<HBBI", sptr, i)` → `(number, type, argc, address)`. Type 1 is
`OPEN` (installed at load, the suspicious one); 12 is `LIGHTNING`; 0 is a normal
triggered script.

## 28. Census instruments are evidence only at the instant you take them

`rt_dump_lightthinkers` reported **0 light thinkers running** on MAP13 while seven
sectors were visibly sweeping. That looked like proof no light effect existed. It was
not: `Light_Fade` creates its thinker **per call** from a looping script, so a census
taken at level load is silent while the effect runs continuously.

`rt_lightlevel_watch` — which samples *every frame* and reports change rather than
presence — found it immediately.

**Rule:** for anything periodic, prefer an instrument that observes over time to one
that counts once. If you must count once, say when you counted, and treat "none right
now" as much weaker than "none ever".

## 29. When the user names a cause, that is data — not a hypothesis to be talked down

On MAP13 the user identified the cause as ACS **in the first message about it**, then
again explicitly (*"you did not remove that lighting ACS script or whatever it is"*),
and a third time (*"AGAIN I SAID IT ACS"*). Each time it was contradicted on the
strength of a scan that could not have seen the thing. The intervening work — an
emissive mask, a `textures.json` attached light, an `rt_eye_panels` engine feature, a
frozen ANIMDEFS animation, a map light thing, three rounds of radius tuning — was all
reverted.

The person watching the screen has information the map file does not contain: what the
effect *looks* like, and how it behaves over time. That is exactly the information a
static scan lacks.

**Rules:**

- A user's stated cause outranks a null from a tool written in the last ten minutes.
  When they disagree, distrust the tool first.
- If a scan contradicts a report, the next step is to test the scan, not to argue the
  report.
- Do not answer a repeated report by re-explaining the previous elimination. Build the
  instrument instead — §25 and §28 both exist because that was learned late.

## 30. `whatsthat` — identify a reported surface from the game, not from the screenshot

Point at a surface in play and type `whatsthat`:

```
whatsthat: sector 150  lightlevel 255  tag 0  middle texture 'C53'
           threshold 220 -> ABOVE: this surface SELF-EMITS
           brightest neighbour: sector 0 at 180  (delta +75)
```

Sector index, lightlevel, tag, the texture on the **exact** surface hit (floor / ceiling /
top / middle / bottom), whether it is above the map's `rt_sector_emis` threshold, and the
frame test printed — brightest neighbour and delta.

It exists because the alternative was costing a round trip each time. Identifying a
reported surface meant rendering candidate textures and picking the one that looked like
the screenshot. That got `C921` and `HDOR10` right, and `C52` and `C53` wrong. **A
screenshot does not carry a sector index; the running game does.**

Note the MAP12 cage came back as `C53` — deliberately excluded from texture matching as
common wall cladding (597 sectors game-wide). No amount of texture matching could have
found it; it needed the geometry.

**Rule:** when a report names a place rather than a thing ("the cage", "the panel by the
door"), get the sector from the game before forming any theory about it.

## 31. A fixture INSIDE the sector makes the paint redundant, not warranted

The survey reports the nearest light-bearing thing, and it is tempting to read a small
distance as "the paint is reinforcing something real, leave it alone". That reading was
wrong every time it was applied:

| case | fixture | verdict |
|---|---|---|
| MAP11 H66 face panel | 133u | fake — its own frame stayed dark |
| MAP12 C53 rust panels | 45u | fake — the wall they are bolted to stayed dark |
| MAP12 cages (150/151) | **0u**, a `64BigFire` *inside* | fake — see below |
| MAP13 door recess | 97u | fake |

The cages are the clearest. Under RT that fire is a **real light** —
`RT_UploadFlameLights` gives it intensity, flicker and falloff. So a painted 255 on the
sector containing it is not the fixture's light; it is a **second copy** of that light,
flat and sourceless, laid on top of the real one. Removing it leaves the cage lit by its
own fire, which is the entire point of the port (§1: the original sector data is baked
shading, not lighting).

**Rules:**

- Fixture distance is a weak signal and it has pointed the wrong way four times out of
  four. The strong signal is the **host**: what does this element sit inside, and is that
  darker?
- A fixture *inside* the element is evidence the paint is **redundant**, because RT will
  light it for real. It is not evidence the paint is earned.
- The one thing fixture proximity is good for is deciding what to look at first, never
  what to skip.

## 32. "Geometry you can test" has to actually be inside the shape

§13 says: do not trust a winding convention, compare against the sector's own centre and
flip the sign. `PANEL_LAMPS` (SMONBA wall monitors) followed that advice literally,
using the mean of the sector's vertices as the centre, and it put **25 of 38 lights
inside solid geometry** — the exact failure §13 exists to prevent.

The reason is simple and applies to any polygon: **a centroid is not necessarily inside
the shape.** For an L-shaped room, a ring corridor, or MAP07's sprawling sector 305, the
vertex mean lands in the middle of the wall — so "point the normal toward the centre"
points it into the wall.

Worse, the same centroid was in the *verifier*, so tool and check shared the defect and
would have agreed with each other. What broke the tie was a **control**: run the check
against fixtures known to be correct — the mod's own 159 authored monitor lights. Had
those come back "in solid" too, the verifier was the thing at fault.

The actual fix was to measure the convention §13 warned against assuming. Retribution's
169 authored monitor lights answer it directly: `sidefront` sits on the **right** of
`v1→v2` in 157 of them. That is a fact about this data, not an assumption, and it has no
dependence on sector shape.

**Rules:**

- A centroid is a valid interior point only for a convex shape. For point-in-polygon use
  a **ray cast**, which is correct for non-convex shapes, holes and islands alike.
- §13's principle is right — prefer testable geometry to an assumed convention — but
  "testable" means the test has to be *sound*. A cheap proxy for the real question is not
  a test; it is a second assumption wearing a test's clothes.
- **When a convention is unavoidable, measure it against authored content.** A mod that
  already ships hundreds of the fixture is a labelled dataset for exactly this.
- **Give every verifier a control on known-good data.** A checker that has never been
  shown a case it must pass, and a case it must fail, is not evidence. This is §10
  ("instrument to discriminate") applied to the instrument itself.

## 33. "It casts no shadow" is usually the pipeline, not the caster

`screen/moon_shadow_limit.png`: 21 `64MarineBot`s in `TITLEMAP` casting no moon
shadow while the buildings around them did. The question asked was whether the
moon has a **limit on how many shadows it can cast**. It does not — `rt_shadowrays`
maps to RTGL1's `maxBounceShadows`, which gates shadow rays by *bounce depth*
("if illumination bounce index is in `[0, maxBounceShadows)`"), never by caster
count, and shadow rays test the whole TLAS at a fixed cost per ray.

Four caster-side explanations were checked and all four were wrong:

| checked | result |
|---|---|
| meta `noShadow` → `WORLD_1`, which `rayCullMaskWorld_Shadow` excludes | 441 textures carry it; `PLAY`/`POSS`/`SPOS`/`SARG`/`TROO` are **243 entries with zero** |
| the shadow cull mask | `getShadowCullMask()` returns `WORLD_0` + first-person-viewer; an opaque sprite is in `WORLD_0` |
| rasterized-not-traced (the MAP01 fence bug, `rt_force_mask_opaque`) | `64MarineBot` is `: ZombieMan` with no `RenderStyle` and no `Alpha` |
| the actor | **the user's own observation ended it**: the same sprites shadow in play when an enemy shoots |

**The answer was `rt_shadow_samples`.** Direct visibility is *one binary ray per
pixel*, so a pixel is fully lit or fully black. A thin, distant, **moving** caster
covers a fraction of a pixel, so every pixel along its umbra is a coin flip with
no temporal history to reuse — and a coin flip is exactly what a denoiser
averages to nothing. A muzzle flash escapes this because it is bright and close,
so its shadow is *most* of the light at those pixels and survives anything. The
static buildings escape it because their history is stable.

**Rules:**

- **"No shadow" has two distinct causes and the image cannot tell them apart:**
  the ray was never blocked, or it was blocked and the result was drowned in fill
  light or smeared by the denoiser. `rt_debug_visibility 1` exists for exactly
  this (added after four A/B ladders failed to separate them) — black where the
  shadow ray was blocked, no radiance involved. **Reach for it before building
  arms**; it would have answered this in one run instead of six.
- **A user's "it works over there" is the strongest evidence in the room.** The
  muzzle-flash observation eliminated every caster-side theory at once and
  redirected the search to the light. §29.
- **Contrast, not correctness.** A shadow is only visible in proportion to how
  much of the local light it blocks. Before suspecting geometry, ask what *else*
  is lighting that surface.
- **A print-only debug cvar changes nothing on screen.** `rt_prim_debug` was
  reported as "no difference"; its answer was in the console, unread. Say which
  output an instrument writes to when handing one over.

## 34. The MAP01 fence: BOTH the light count and the source radius, measured in a lab

`screen/noVisibleShadowFence.png`: the `SPACECM` cage on MAP01 casts nothing under its
lamp pane, while a flashlight and a muzzle flash cast crisply through the same grating.

Settled 2026-08-14 in **MAP93, the shadow lab** (`tools/build_shadow_lab.py`,
`tools/shadow-lab.ps1`): the same fixture — one SFLATAS pane inside a `SPACECM` cage —
alone in a dark room with **no other light of any kind**, captured unattended. Every
earlier attempt was run in MAP01's real room, which carries 283 analytic lights plus a
moon, wall strips, dynlights and a level of emissive GI, and could not isolate anything.

**Both levers are necessary and neither is sufficient:**

| lights on the pane | source radius | result |
|---|---|---|
| 1 | 0.35 m = 11.2 map units (shipped) | nothing |
| 1 | **0.02 m = 0.64 units** | **crisp diamond shadows on floor, both walls and ceiling** |
| 4 | 0.02 | a trace on the ceiling only |
| 16 | 0.02 | nothing |
| 16 | 0.06 | nothing |

So a legible grating shadow needs **one compact light per fixture**. Four already washes
it out, which rules out "one light per painted bulb" as a design: an SFLATAS pane draws
2×2 bulbs per 64-unit tile, so even a single tile is four.

**I previously wrote in this section that source size was falsified. That was wrong**, and
the way it was wrong is the lesson. The test that "falsified" it moved radius *inside*
MAP01, where 271 other lights were untouched, and it also concentrated flux into a few very
bright emitters, which added noise. A confounded experiment produced a confident negative
that then steered two more rounds. The 2026-08-08 finding (`60e19bb`, `aacb140`) was right
all along.

**Why radius matters so much here.** RTGL1 samples a sphere light at a random point on its
surface (`Light.h:278-291`), so the radius *is* the penumbra generator. A grating cell is
16 units; an 11.2-unit source blurs the cell's own width away, while a 0.64-unit one draws
it sharply. Brightness does not change with radius — radiance is `intensity/(π r²)` and the
sphere subtends `≈ π r²/d²`, so the product is `intensity/d²`.

**Rules:**

- **Isolate the fixture in a purpose-built map before tuning it.** Three ladders and six
  days went into a room where no single knob could be seen. The lab answered it in eight
  captures, and its light count is derived from the cage size and printed in the frame, so
  an arm that fails to apply announces itself.
- **A confounded experiment yields a false negative just as easily as a false positive**,
  and a negative is far more expensive because nothing contradicts it later.
- **`whatsthat` reports the surface the ray HIT.** It returned `SPACEAF` for the cage and
  that was written down as fact; `SPACEAF` has *zero* transparent pixels. The grating is
  `SPACECM` (64×64, 56.2 % transparent). Confirm a texture from its pixels (§17) before
  building on the name — the lab caught this in one frame, because a cage built from an
  opaque texture is a sealed box and renders the room black.

## 34a. `rt_debug_visibility 1` was not showing you visibility — the instrument itself was the bug

The whole method in §33 rests on one claim: that `rt_debug_visibility` separates *"the ray
was never blocked"* from *"it was blocked and the result was drowned or smeared"*. On
2026-08-14 that claim turned out to be false in exactly the rooms it was being used in.

`RtRaygenDirect.rgen:93-104` writes the visibility term into the **unfiltered DIRECT**
buffer — the direct *diffuse* channel and nothing else — and returns. But
`CmPrepareFinal.comp:43-84` builds the final pixel as denoised direct **+ indirect +
volumetrics + auto-exposure + screen emissive × `emissionMaxScreenColor`**, and only
substitutes the raw direct buffer when `DEBUG_SHOW_FLAG_UNFILTERED_DIFFUSE` is ticked in
the Dev window. Without that tick you are looking at the normal image with one summand
scaled by visibility.

Under a Doom 64 lamp pane, that summand is a **minority of the pixel**: the painted glow
is only one of several shadowless contributors (`rt_ceiling_bulb_emis`, `rt_sector_emis`
and indirect GI), all of it
emissive and none of it able to shadow. So the view came out looking like the ordinary
scene with a few lights dimmed — reported verbatim as *"it just seems to disable some
lights but not much"* — and it could not have shown an umbra it did find, let alone prove
one absent.

**Two conclusions were built on that reading and both are now void:** the 2026-08-08
*"`rt_debug_visibility 1` showed that NOTHING casts a shadow from the bulb bands"*, which
eliminated "blocked but drowned" and sent the hunt into source size for six days; and the
`sprshadow-probe` decision table, which asks you to read black-vs-no-black off the same
view.

Fixed in `deps/RTGL/Source/VulkanDevice.cpp` (`FillUniform`): mode **1** now sets
`DEBUG_SHOW_FLAG_UNFILTERED_DIFFUSE` itself, so it shows the raw buffer, bypassing the
denoiser, with no box to remember. Mode **2** deliberately still composites — it exists to
locate an umbra *against* normal shading. Needs `tools/build-rtgl.cmd`.

**Rules:**

- **An instrument that only works when paired with a setting somewhere else is not an
  instrument.** The cvar description did say "judge in the Dev 'Unfiltered diffuse direct'
  view"; two investigations still read it composited. If a debug view has a precondition,
  make the view enforce it rather than documenting it.
- **Validate the instrument on a case where you know the answer before trusting it on one
  where you do not.** §32 already says every verifier needs a control — a case it must pass
  and a case it must fail. This one had never been shown either. Point it at a wall lit by
  a single close lamp with a body in front: if that does not go black, the view is lying.
- **A debug view that composites is showing you a RATIO, not a term.** Ask what fraction of
  the final pixel the thing you are debugging actually contributes. When the answer is
  16 %, no amount of staring will resolve it.

## 34c. A per-pixel debug view cannot isolate one occluder while N lights compete

`screen/redDebugShadow.png` — `rt_debug_visibility 2` in the MAP01 cage room with every
authored emissive fill peeled off — comes back with **nearly every surface tinted**, which
looks like "everything is shadowed" and localises nothing.

The console explains it in one line:

    uploaded=283 of 275 wanted (cap 1024, within 3072u)
      from 16 lamp ceiling(s) + 4 lamp floor(s) + 12 bulb lattice(s) | faux 4 | solo 4

283 lights, against a cap of 1024 — nothing is being trimmed, so that is the real number
competing for every pixel. ReSTIR shades **one** light per pixel, and `g_debugVisibility`
records the shadow ray for *that* light. With 283 candidates most pixels choose something a
wall, a pillar or the cage occludes, so the view reports "shadowed" almost everywhere and
says nothing whatever about the fence.

**The view is not wrong; the question is wrong.** "Was the light this pixel chose blocked"
only becomes "does this occluder cast" when there is essentially one light to choose.

And the same number invalidates every count experiment on this problem. The knobs each
reach a different fraction of those 283:

| knob | reaches |
|---|---|
| `rt_ceiling_bulb_spacing` | the **12** bulb-lattice panes |
| `rt_ceiling_edge_seglen` | the **8** perimeter-walk panes |
| `rt_faux_lamp_max` / `rt_solo_lamp_max` | faux + solo, on **separate budgets** no arm ever set |
| `rt_ceiling_edge_max` | the main list only — *not* faux or solo |

That is why the 2026-08-14 key/fill test returned null: it re-spaced 12 panes and left the
other ~271 lights exactly as they were. `ab-onelamp` had the same defect in reverse — it
capped the main list to 1, called that "one lamp", and uploaded 9.

**Rules:**

- **Before reading any per-pixel light debug view, print the light count.** If it is not
  ~1, the view is answering a different question than the one you are asking.
- **When a population is assembled from several sources with separate budgets, no single
  knob thins it.** Find the total first — the debug line existed and said 283 — then check
  which fraction your knob actually reaches before running the experiment, not after.
- **An isolation arm has to turn off *everything*, and prove it did.** State the expected
  console line in the arm's own echo, so an arm that failed to apply announces itself
  instead of returning a confident null.

## 34b. A knob can go inert under you when placement changes, and every ladder that used it silently becomes void

The 2026-08-08 fence work built seven ladders that thinned the lamp count with
`rt_ceiling_edge_seglen`. On **2026-08-10** the bulb lattice (`open-issues` §1.6g) moved
`SFLATAS`/`SFLATAQ` off the perimeter walk, and seglen stopped reaching them — the count
knob became `rt_ceiling_bulb_spacing`, which no arm had ever set. Nothing errored. The
ladders still ran, still printed counts, and still produced results; those results were
about a code path the fixtures no longer take. `ab-bulb-density`, `ab-bulb-softness`,
`ab-bulb-keyfill` and `ab-lamp-placement` were re-pointed on 2026-08-14.

Worse, the surviving conclusion was a *negative* — "count was eliminated" — and a stale
negative is invisible.

**Rules:**

- **When you change where a feature places things, grep for every tool that tuned the old
  placement** and re-point or retire it in the same commit. A cvar that no longer reaches
  the code is worse than one that was deleted, because it still accepts a value.
- **Date a null.** "Count does not matter" was true of the perimeter walk on 2026-08-08 and
  says nothing about the lattice. §28's rule about census instruments applies to A/B arms
  too: an experiment is evidence about the code that existed when it ran.
- **Write the conclusion into `docs/`, not only into commit messages and tool headers.**
  The whole 08-08 investigation — root cause believed confirmed, fix never shipped — lived
  only in five commit messages and seven `.cmd` headers, so it was re-derived from scratch
  on 08-14 and its central claim was only then found to be false. Had it been written down,
  the falsifying test would have been the first thing tried rather than the last.

## Pending visual confirmation

`RT_UploadCeilingEdgeLamps` (MAP03 ceiling strips) and the map-relative
`rt_sector_emis` threshold are built and wired into the launcher but **not yet confirmed
by eye**. Check on MAP03, and on MAP01's spawn ceiling bulb panel, which the perimeter
walk should also cover.

The re-aimed `rt_wall_strips` matcher (§20) is likewise unconfirmed. On MAP02 it should now
find 30 wall-mounted bulb arrays (26 `SFLATAQ` bottoms, 4 middles) where it previously found
none; on MAP03, 4 `SPACEAZ` bottoms where it previously lit 57 `SPACEAR` trim panels. **MAP03
will look different** — the lights move from the trim onto the bulbs, and there are far fewer
of them. Judge it against the fixtures, not against the previous screenshot.

## Resolved this session

The white dynamic light on the MAP02 blue-room switch is fixed. It was a bare stock
`PointLight` map thing (white, map radius 12) placed to keep the switch readable under the
raster renderer. Real fixtures nearby are r>=32 (`64BlueArmor` 32, `64TechPoleShort` 48),
so `rt_dynlight_minradius` (default 16) separates helper lights from fixtures by radius —
no class list, no position match. It is applied after `curDynIds.insert` so skipping a
light does not register as a light disappearing and flush RR temporal history.
