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
| `rt_sector_emis_minlight` | 160 | Lightlevel floor for self-emission, so ordinary mid-lit walls stay inert. |
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

## Known open item

**MAP03 upper wall light strips still cast no light.** The floor-level bulb trim
(`SPACEAR`/`SPACEAR1`) is handled by `RT_UploadWallStripLights` and works — 57 matched
sidedefs, 98 lights, no rejections. The strips higher on the wall are *not* sidedef
textures: within 256u the only other names present are `SPACEAI1` (flat normal map,
metallic band in ORM — panelling), `SPACEAC` (ribbed panel), `SWXSFB`, `SPACEBE` and
`SMONAA`, none of which is a bulb fixture.

Most likely they are thin sector steps whose **flats** carry the lamp texture, which
`RT_UploadCeilingInsetLamps` already handles — and which the launcher force-disables with
`rt_ceiling_lamps 0`. Test that before writing new code:

```
.\tools\launch-retribution-rt.cmd 3 -- +rt_ceiling_lamps 1 +rt_ceiling_lamp_intensity 400
```

`rt_ceiling_lamp_maxspan 128` skips large sectors, so a long corridor shelf may still be
excluded.

## Resolved this session

The white dynamic light on the MAP02 blue-room switch is fixed. It was a bare stock
`PointLight` map thing (white, map radius 12) placed to keep the switch readable under the
raster renderer. Real fixtures nearby are r>=32 (`64BlueArmor` 32, `64TechPoleShort` 48),
so `rt_dynlight_minradius` (default 16) separates helper lights from fixtures by radius —
no class list, no position match. It is applied after `curDynIds.insert` so skipping a
light does not register as a light disappearing and flush RR temporal history.
