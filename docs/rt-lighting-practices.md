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

## 13. Never derive a direction from a winding convention you have not verified

Wall strip lights were offset 2 units off the surface to avoid being coplanar with it.
The offset used the left normal `(-dy, dx)` while treating sidedef 0 as the front — but
Doom's front sidedef is on the **right**. Every light was placed 2 units *inside* solid
geometry, fully occluded, emitting nothing.

By eye this is indistinguishable from the lights never being uploaded.

Derive the direction from geometry you can test instead: compare against the sector's own
`centerspot` and flip the sign if it points the wrong way. That is correct regardless of
how the mapper drew the line.

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
