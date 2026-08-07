# MAP02 Blue Room — RT Lighting

**Date:** 2026-08-07
**Status:** Superseded and replaced. The general fix is in; visually confirmed on the
blue room and the red corridor.

For the reusable principles behind this, see [rt-lighting-practices.md](rt-lighting-practices.md).

## Problem

The Retribution MAP02 blue armor room did not match the original game under RT. The
original has a strong blue atmosphere; the RT version was neutral brown/grey with a warm
white ceiling glow. Compare `screen/level2-blueroom.png` against
`screen/level2-currentblueroom.png`.

The give-away is the hazard stripes: yellow-on-black in RT, cyan-on-dark in the original.
Same texture — so the difference was lighting, not a missing texture or a missing lamp.

## Diagnosis

Sectors in the blue armor area use `lightcolor = 20735 = 0x0050FF`. The RT compat path
forces world vertex RGB to white under `rt_mod_compat`, which discards it. That
force-white is itself a necessary workaround: sector colour and lightlevel arrive baked
into vertex colour, and feeding them to the path tracer as albedo double-counts shading —
the cause of the yellow key-door neon wash and the black light-absorbing rooms.

## What was tried first, and why it was rejected

An initial attempt detected Retribution MAP02 by map name, matched the specific
`0x0050FF` colour profile with a hand-tuned RGB window, and applied three eyeballed
constants `(0.35, 0.58, 1.0)` as an albedo tint.

Rejected on review, for reasons that generalize:

- **Wrong channel.** It tinted albedo, not light. The room's emitters, bloom and speculars
  stayed warm white, so the result was blue paint under a white lamp rather than blue
  light. The reference shows blue *emitters*.
- **Wrong scope.** A map-name check plus a tuned colour window fixes one room; colored
  sector light is used across the whole game. (`strstr(name, "map02")` also matches
  `map020`.)
- **Wrong source for the constants.** The sector colour is available as map data; the
  tint did not derive from it.

## What shipped

`RT_SectorHue()` in `rt_main.cpp`: peak-normalize the sector colormap to hue only — the
largest channel becomes exactly 1, so the transform can never brighten or darken, only
remove off-hue channels — then lerp toward white by a strength cvar. Lightlevel stays
discarded, so neither the black rooms nor the neon wash can return through this path.

The hue is applied to:

- ceiling inset lamps (`RT_UploadCeilingInsetLamps`)
- hanging tech lamps, via the lamp actor's own sector
- sector-centre lights (`RT_UploadExportableSectorLights`), replacing a hardcoded
  `RG_PACKED_COLOR_WHITE`
- emissive world surfaces, at full light strength — **this is the one that mattered for
  this room**, because the launcher forces `rt_ceiling_lamps 0` and the ceiling glow is
  texture emissive under `rt_emis_mapboost`, not an analytic sphere
- ordinary world surfaces, as albedo

`rt_sector_tint_albedo` defaults to 1.0: full normalized hue is what matches the original,
confirmed visually on this room.

## The red corridor — a different failure

`screen/level2-corridor.png` vs `screen/level2-currentcorridor.png`. The original is black
with saturated red panels; RT was simply unlit.

That corridor has **no light source at all** under RT — no analytic lamp, no emissive
texture, flashlight off. Hue tint provably cannot help: albedo is a reflectance
multiplier, and zero incident light times red albedo is still black.

Fixed with `rt_sector_emis`: surfaces above `rt_sector_emis_minlight` self-emit, scaled by
their own sector lightlevel and tinted by the sector hue, so the panels glow and light the
room by GI. A sector-centre analytic sphere was tried first and rejected — it read as a red
bulb floating in the corner rather than glowing floor panels.

## Also fixed in this pass

- **Sticky render state.** `m_sectorLightColor` was a plain assignment written only by
  walls/flats, leaking the last sector's hue onto later geometry. Now scoped via
  `push_sectorlight()` (RAII), which also carries `m_sectorLightLevel` — kept separate from
  `m_lightlevel`, which is sprite-only and feeds `localLightsIntensity` for every primitive.
- **Overexposed yellow key-door jambs.** `rt_dynlight_rsoft` lowered 40 → 20. Unrelated to
  the tint work: `RT_SectorHue` is peak-normalized and cannot add luminance.
- **Debug usability.** `rt_dynlight_debug` now reports an xy-stack histogram and the five
  lights nearest the camera; marker spheres moved to `rt_dynlight_debug_marks` because 67
  markers at intensity 400 flooded the scene purple.

## Open

A white `PointLight` sits on the blue-room switch and does not belong there. Confirmed a
GZDoom map/GLDEFS dynlight (`rt_dynlight 0` removes it, `rt_sector_emis 0` does not). Not
yet fixed — use the nearest-light dump to identify its owner class and filter on that
rather than on map position.
