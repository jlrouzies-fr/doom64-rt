# Light shafts from ordinary lamps, not just the moon

**Status:** implemented, **not yet judged in play.** Ships **on**
(`rt_volume_shafts 1`, compiled default *and* pinned). Targets the **ceiling**
and **solo bulb** fixture families; nothing else offers a shaft yet.

**Why it was worth doing:** beams of light in a dark room *are* the Doom 64 look,
and until now this project could only produce them outdoors, from the moon. Every
grate, doorway, ceiling lamp and monitor bank inside the game was a light with no
visible air around it.

Related: [`docs/moon-and-sky-leaks.md`](moon-and-sky-leaks.md) §5.4 (the medium
and its density) and §5.5 (the phase function, and why lowering asymmetry is the
wrong answer), [`docs/rt-fog.md`](rt-fog.md), [`docs/rt-smoke.md`](rt-smoke.md) —
all four share the same froxel volume.

---

## 1. What was already there

The shafts under the moon are not a special effect. They are `rt_volume_scatter`
being scattered by **one** directional light inside the froxel volume, and the
volumetric pass shadow-tests that light itself:

- `RTGL1/Source/LightManager.cpp:815` — `TryGetVolumetricLight()` picks a
  **single** light per frame and hands its index to the shader. It scans
  `staticLights` only, so a light gzdoom uploads per frame — which is every
  fixture in this game — could never be picked in the first place.
- `RTGL1/Source/VulkanDevice.cpp` — writes `gu->volumeLightSourceIndex`, or
  `LIGHT_INDEX_NONE`.
- `RTGL1/Source/Shaders/RtVolumetric.rgen` —
  `traceDirectIllumination_SpecificLight()` samples exactly that one light and
  calls `traceShadowRay` for it.

## 2. The route that looks right and is not

The original plan proposed reading the per-froxel **all-lights** estimate that
already exists for fog (`g_illuminationVolume`, `rt_fog_illum`) — "cheapest
possible experiment". **That route was rejected after reading the shader**, and
it is worth writing down why, because it will look attractive again:

- It **replaces** the single-light path (`if( allLightsCell ) … else …`), and
  that path is the only place the sun's sky-reach probe lives — i.e. the only
  thing that makes the shafts the game already has. Switching it on deletes them.
  This is the same trap smoke hit and is annotated in the shader as "TRAP 3".
- It shades the medium with `processDirectIllumination`, a **surface**
  integrator, handing it a fake normal equal to `toviewer`. A light directly
  overhead therefore scores `dot ≈ 0` and is multiplied to nothing — and a light
  directly overhead is exactly what a ceiling lamp is. That is the documented bug
  which made smoke lit by the flashlight and by nothing else.
- It is one stochastic sample per froxel and needs a reprojected temporal history
  to be watchable.

So route 2 of the original plan — an explicit small set of lights — was
implemented instead, deterministically rather than stochastically.

## 3. What was built

An explicit per-frame list, chosen engine-side, scattered **on top of** the
single-light term. The moon and a corridor lamp are both in the air at once.

| Layer | File | What it does |
|---|---|---|
| Selection | `rt_light_shafts.cpp` (new) | fixtures *offer* their lights; this culls, sorts nearest-first, dedupes and caps |
| Offer sites | `rt_lights_fixtures.cpp` | ceiling inset lamps; the ceiling perimeter / bulb lattice / faux panels; solo bulbs |
| Transport | `rt_main.cpp` | `RgDrawFrameLightShaftParams`, linked into the `pNext` chain before the smoke params |
| API | `RTGL1.h`, `DrawFrameInfo.h` | new struct + `RG_STRUCTURE_TYPE_DRAW_FRAME_LIGHT_SHAFT_PARAMS`, `RG_MAX_SHAFT_LIGHTS` 32 |
| Uniform | `GenerateShaderCommon.py` | `volumeShaftLights[8]` as `uvec4`, plus 9 scalars taking the old `_pads10` slot |
| Resolve | `VulkanDevice.cpp` | uniqueID → shader light index, **compacted** (a listed fixture may have been culled) |
| Scatter | `RtVolumetric.rgen` | `traceShaftLights()` — walk, radiance cull, capped shadow rays, near fade, phase function |

**It is deterministic, and that is the design.** One stochastically chosen light
per froxel would be cheaper and would then need the reprojected history the
all-lights branch has. Walking a short list with a radiance cull *in front of*
the shadow ray costs a few ALU per candidate and produces no variance at all. In
a typical cell only one or two lamps survive the cull, so the ray budget is
rarely reached.

### Which lights qualify

`rt_volume_shaft_src` is a bitmask: **1** ceiling inset, **2** ceiling
perimeter/bulb lattice/faux panels, **4** solo bulbs. Default 7.

**Bit 1 offers nothing in the shipping config** — `rt_ceiling_lamps` is pinned
`0` because a centre sphere in a big hall reads as a floating blob, which is the
whole reason the perimeter walk exists. It stays in the default mask so turning
the family back on is one cvar rather than two;
`tools/arms/lampshaft-inset.cfg` turns both on together. Do not read its silence
as the feature being broken.

### The dedupe is load-bearing

A Doom 64 lamp pane is ~16 point lights on a 16-unit lattice
(`rt_ceiling_bulb_spacing`) — entirely correct as *lighting*, and as *shafts* it
is one pane taking the whole 16-slot budget to produce a single blob while every
other fixture in the room gets nothing. `rt_volume_shaft_mingap` (96 map units,
nearest wins) is what prevents that; `tools/arms/lampshaft-nogap.cfg` shows the
failure it prevents. The test is **3D** — the walks tile in both axes, and a 2D
gap would merge a light with the one directly above it, which is the mistake
`PANEL_LAMPS`' `min_gap` made.

## 4. Cvars

| cvar | default | what it is |
|---|---|---|
| `rt_volume_shafts` | `1` | master |
| `rt_volume_shaft_src` | `7` | family bitmask (see above) |
| `rt_volume_shaft_max` | `16` | fixtures sent per frame, nearest first (hard cap 32) |
| `rt_volume_shaft_trace` | `3` | **shadow rays per froxel** — the real budget |
| `rt_volume_shaft_mult` | `1` | brightness of the lamp shafts only |
| `rt_volume_shaft_nearfade` | `1.5` | metres; stops a bulb whiting out the froxels touching it |
| `rt_volume_shaft_mincontrib` | `0` | radiance below which a light is skipped before its ray |
| `rt_volume_shaft_asym` | `-2` | phase asymmetry for lamps only; below −1 = share `rt_volume_lassymetry` |
| `rt_volume_shaft_maxdist` | `1024` | map units, camera cull |
| `rt_volume_shaft_mingap` | `96` | map units, dedupe |
| `rt_volume_shaft_minint` | `0` | skip a fixture dimmer than this (blinking lamps) |
| `rt_volume_shaft_debug` | `0` | shader probe, 1/2/3 |
| `rt_volume_shaft_verbose` | `0` | per-family offered-vs-sent console line |

All thirteen are pinned at their compiled defaults in `tools/d64rt-pins.cfg` —
they are `CVAR_ARCHIVE`, so without a pin the last arm run would follow you into
play.

**Two knobs are deliberately split from ones that already exist**, because
sharing them would retune shipped content: `rt_volume_shaft_mult` against
`rt_volume_lintensity` (global to the volume, and what the moon is tuned with),
and `rt_volume_shaft_asym` against `rt_volume_lassymetry` (0.5, tuned on the moon
and on nine fogged maps).

## 5. How to judge it

    .\tools\ab.cmd lampshaft-fat 07      <- RUN THIS ONE FIRST
    .\tools\ab.cmd lampshaft-off 07
    .\tools\ab.cmd lampshaft-on  07

`lampshaft-fat` is the **absurd arm**: `mult 200`, no near fade, no dedupe, all
32 lights, 8 rays per froxel. Interiors should be unmistakably, unpleasantly full
of light. Every subtle arm is worthless until this has been seen to do something,
because "the knob does nothing" is always two hypotheses — too small to see, or
never reached the shader — and only a value far past visible separates them.
If `lampshaft-fat` changes nothing, go to `lampshaft-probe`
(`rt_volume_shaft_debug 3`), which reads the count and nothing else, and stop
tuning.

| arm | question |
|---|---|
| `lampshaft-fat` | is the plumbing live at all |
| `lampshaft-probe` | is the uniform arriving (reads count only) |
| `lampshaft-lit` / `lampshaft-vis` | reach vs occlusion — the pair the final image cannot separate |
| `lampshaft-off` / `lampshaft-on` | the before and the shipping values |
| `lampshaft-inset` / `lampshaft-lattice` / `lampshaft-solo` | one family at a time |
| `lampshaft-nogap` | what the dedupe prevents |
| `lampshaft-nomoon` | lamp shafts with nothing else in the air (`rt_sun 0`) |
| `lampshaft-dense` / `lampshaft-bright` | more medium vs more light — judge separately |
| `lampshaft-iso` | is the forward bias carrying the shaft (expect **dimmer**, not flatter) |
| `lampshaft-near0` | the near fade off, i.e. the physical answer |

Good interior candidates: the MAP07 clad corridors, any room with a ceiling
grate. Judge it in-game — nothing here is measurable from a scanner. A bright
outdoor area will show nothing, and that is correct, not a null result.

## 6. Traps, all previously paid for

- **The medium's density hangs off `rt_volume_far`.** The shader applies
  `rt_volume_scatter` **per froxel cell** over a grid that is 64 slices at any
  reach, so raising the reach for smoke (30 → 60) halved the moon.
  `rt_volume_scatter` is normalised per metre in `rt_main.cpp`; fog is
  deliberately not. `rt_volume_shaft_mult` is a plain multiplier on the lit term
  and uses neither convention.
- **There is no single visibility choke point.** `RtVolumetric.rgen` does **not**
  call `traceDirectIllumination`; a change in the shared lighting path leaves
  shafts untouched and looks inert. `traceShaftLights()` is in the raygen for
  that reason and shadow-tests its own lights.
- **Asymmetry is expected, not a bug.** The phase function has a ~11× forward
  bias at 0.5, so a shaft is strong looking toward the light and weak from the
  side. Lowering it is *dimmer, not flatter* — §5.5 of the moon doc.
- **Positions crossing into RTGL1 are metres**, never map units. The registry
  works in map units (that is what the fixture walks produce and what the gap and
  distance culls are natural in) and passes **uniqueIDs**, not positions, so this
  boundary is not crossed at all — but `rt_volume_shaft_nearfade` *is* metres.
- **Cost is per froxel, not per pixel.** `rt_volume_shaft_trace` is the number
  that matters; `rt_volume_shaft_max` only widens the set the per-cell cull
  chooses from. Measure before raising either.
- **The generated uniform header is not a tracked build dependency.** Nine
  scalars and a `uvec4[8]` were added to `ShGlobalUniform`; `build-rtgl.cmd`
  clears the objects when it changes, and `tools/check_uniform_layout.py` gates
  the C-vs-std140 agreement. Do not bypass either.

## 7. Not done

- Only the ceiling and solo families offer shafts. Flames, switches, lava, the
  9800/9801/9802 map things and the SMON wall panels do not. SMON in particular
  should stay out until asked for — §20 of `rt-lighting-practices.md` is the
  standing warning about turning a dense family on wholesale.
- No per-map table. If shaft density turns out to want per-map control it belongs
  in an `RT_FOG_PRESETS`-style table in `rt_presets.cpp`, not in per-light
  metadata.
- Not judged in play. Nothing in this document claims a look.
