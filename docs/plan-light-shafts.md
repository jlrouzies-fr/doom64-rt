# Light shafts from ordinary lamps, not just the moon

**Status:** implemented; reach fixed twice from play reports (§4a, §4b), look not yet settled. Ships **on**
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
| Scatter | `RtVolumetric.rgen` | `traceShaftLights()` — **two passes**: find the brightest candidate at this froxel, then trace only those within `relcull` of it (§4a) |

**It is deterministic, and that is the design.** One stochastically chosen light
per froxel would be cheaper and would then need the reprojected history the
all-lights branch has. Evaluating a short list with a radiance cull *in front of*
the shadow ray costs a few ALU per candidate and produces no variance at all. In
a typical cell only one or two lamps clear the bar, so the ray budget is rarely
reached.

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
| `rt_volume_shaft_bands` | `4` | split the slot budget across distance bands (1 = old nearest-first) |
| `rt_volume_shaft_max` | `32` | fixtures sent per frame (hard cap 64) |
| `rt_volume_shaft_trace` | `4` | **shadow rays per froxel** — the real budget |
| `rt_volume_shaft_mult` | `10` | brightness of the lamp shafts only — **judged in play** |
| `rt_volume_shaft_nearfade` | `1.5` | metres; stops a bulb whiting out the froxels touching it |
| `rt_volume_shaft_falloff` | `0.5` | how much of the inverse square is handed back (0 physical, 2 sun-like) — **judged in play** |
| `rt_volume_shaft_relcull` | `0.05` | skip a light below this fraction of the brightest **at that froxel** |
| `rt_volume_shaft_mincontrib` | `0` | absolute radiance below which a light is skipped before its ray |
| `rt_volume_shaft_asym` | `-2` | phase asymmetry for lamps only; below −1 = share `rt_volume_lassymetry` |
| `rt_volume_shaft_maxdist` | `1920` | map units (60 m = `rt_volume_far`), camera cull |
| `rt_volume_shaft_mingap` | `96` | map units, dedupe |
| `rt_volume_shaft_minint` | `0` | skip a fixture dimmer than this (blinking lamps) |
| `rt_volume_shaft_debug` | `0` | shader probe, 1/2/3 |
| `rt_volume_shaft_verbose` | `0` | per-family offered-vs-sent console line |

All sixteen are pinned at their compiled defaults in `tools/d64rt-pins.cfg` —
they are `CVAR_ARCHIVE`, so without a pin the last arm run would follow you into
play.

**Two knobs are deliberately split from ones that already exist**, because
sharing them would retune shipped content: `rt_volume_shaft_mult` against
`rt_volume_lintensity` (global to the volume, and what the moon is tuned with),
and `rt_volume_shaft_asym` against `rt_volume_lassymetry` (0.5, tuned on the moon
and on nine fogged maps).

**`rt_volume_shaft_mult` is 10, and the size of it is not a mistake.** A lamp is a
small sphere and its scattering is a solid angle, so what reaches a froxel a few
metres away is a tiny fraction of what the moon — a directional light with no
distance term at all — delivers everywhere. The two are simply not in the same
units, which is exactly why this knob is separate from `rt_volume_lintensity`
rather than folded into it. Both values were settled from play on 2026-08-14.

**When a shipping value moves, every arm defined as a MULTIPLE of it has to move
too.** `lampshaft-bright` was `mult 4` against a shipping 1 and `lampshaft-fat`
was 200; at a shipping 10 those would have become a *dimming* arm and a merely
20× one, i.e. an inversion and a no-op, with their own comments still claiming
otherwise. They are now 40 and 2000.

## 4a. "It works but it doesn't display very far" (2026-08-14, from play)

Reported after the first build: a shaft is there under the lamp you are standing
by, and a few metres away it is gone. **Two independent causes, both real**, and
neither is brightness.

**1. A lamp is inverse-square; the moon is not.** `sampleSphereLight` sets
`dw = calcSolidAngleForSphere(radius, d)`, so a lamp's scattering falls as
`1/d²` — **36× dimmer at 6 m than at 1 m**. The shafts this renderer already had
come from the *sun*, and a directional light has no distance term at all. That
difference, not the intensity, is why one reads across a whole level and a lamp's
reads as a puddle around the bulb. `rt_volume_shaft_falloff` hands the exponent
back: `radiance *= pow(max(d,1), k)` — `0` physical, `1` is `1/d`, `2` sun-like.
**Shipping 0.5**, which is where play landed: 0 read as a puddle around the bulb
and 1 as fog with no shape to it, so the answer is between them and nearer the
physical end. Ladder: `lampshaft-phys` → shipping → `lampshaft-flat`.

**2. The per-froxel ray budget was spent in list order — and the list is sorted
by distance to the CAMERA.** With `mincontrib 0` the cull never fired, so the
first `rt_volume_shaft_trace` (3) entries consumed *every* froxel's budget. A
froxel ten metres down a corridor was tested against the three lamps behind the
player and never against its own, which was therefore **absent, not dim**,
however bright it was. `traceShaftLights()` is now two passes: pass 1 finds the
brightest candidate at that froxel (ALU only, no rays), pass 2 traces only those
within `rt_volume_shaft_relcull` of it. `lampshaft-listorder` keeps the old
behaviour runnable.

The general lesson, and it is the one this file already had in §2: **"nearest
first" has to mean nearest to the thing being shaded.** A camera-sorted list is
the right thing to *send* — it decides which fixtures exist this frame — and the
wrong thing to *spend a per-cell budget with*. The two orderings look identical
in a small room and diverge exactly where the report said they did.

Distinguishing them, if this comes back: raise `rt_volume_shaft_trace` to 16. If
distant shafts appear, it is selection order; if they stay absent but brighten,
it is the falloff.

## 4b. "They still don't render far enough" (2026-08-14, second report)

The falloff in §4a was real and was not the whole story. The remaining limit was
never in the shader at all — it was in **which fixtures get sent**.

`rt_volume_shaft_max` was 16, handed out **nearest-first** with a 3 m dedupe.
Sixteen points at 3 m spacing fill a disc of radius **≈7 m** around the camera —
and a Doom 64 lamp room offers *hundreds* of candidates: the bulb lattice places
one every 16 units (`rt_ceiling_bulb_spacing`), faux panels every 32
(`rt_faux_lamp_stride 2`), the perimeter walk every 64
(`rt_ceiling_edge_seglen`). So every slot went to the ceiling directly overhead,
and a lamp ten metres down the corridor **was never sent**. Not dim — *absent*,
with no shader knob able to touch it.

The fix is `rt_volume_shaft_bands`: the budget is split across distance bands,
each getting its own share, leftovers rolling forward, and a final sweep handing
anything unspent back to the nearest candidates so an empty corridor loses
nothing. With it: `max` 16 → 32, cap 32 → 64, `maxdist` 1024 → 1920 (60 m, the
froxel volume's own reach — past it there is no medium to scatter in).

**Why two rounds went past this.** The symptom — "works near a lamp, dies a few
metres away" — is what a falloff problem looks like, and the falloff *was* also
wrong, so fixing it produced a real improvement and confirmed the wrong theory.
The verbose line said `sent 16 of 300 offered`, which reads as a healthy cap
doing its job. It now prints **`reach a..b m`** — the near and far distance of
the set actually sent — and that single field would have ended this in one
launch. `lampshaft-noband` keeps the old behaviour runnable;
`lampshaft-wide` (8 bands, 64 lights, 60 m) is the upper bound of the machinery.

**The lesson, which is the same one as §4a in a different place:** a per-frame
*budget* and a per-cell *budget* need different orderings, and neither is served
by "nearest to the camera". Sorting a list is not covering a space.

## 4c. Dust motes

`rt_dust_*`, implemented in `rt_light_shafts.cpp`'s sibling `rt_dust.cpp`. A
beam is only a beam because something is in it; the froxel medium supplies the
smooth half of that, and dust supplies the sparkle — specks bright inside the
beam and invisible outside it, so the shaft draws itself and the dark stays dark.

**They are real traced geometry, lit by the scene.** No emission, no rasterized
overlay, no hand-applied tint:

- **Emissive dust is fireflies.** A mote carrying its own light glows in a
  pitch-black room, which is the opposite of the effect.
- **Rasterized dust is fullbright.** RTGL1 keeps a `TRANSLUCENT` primitive out of
  the acceleration structure and does not shade it — the trap the spark batch
  lives with deliberately and debris was moved off. Dust is opaque, alpha 1, no
  flags, which is RTGL1's rule for *entering* the AS. Its vertex colour is an
  **albedo the path tracer shades**, not a final pixel.
- Which also means a mote is correctly **shadowed** — a speck in the shadow of
  the grating that makes the shaft goes dark, for free.

**No pool, no state, no spawning.** Dust is a property of the room, not an event.
The motes live on a hashed lattice fixed in *world* space and the frame draws the
cells near the camera, so the whole system is a pure function of (camera, time).
Density is uniform and exact, motes do not drift or pop as the player moves,
walking away and back shows the same dust, and no budget can quietly run out.

**Size is angular, and it has to be.** A real mote is tens of microns; even a
generous 8 mm speck at 10 m subtends about a fifth of a pixel, which under an
upscaler is not a dim speck but a shimmering one. A mote is drawn at whichever is
larger of its world size and a fixed **angular** size — a constant few pixels at
any distance. `dust-honest` turns that off so the shimmer it prevents can be
seen.

### The shaft gate — dust is *for* the shafts

Traced lighting alone does not make dust a shaft effect, and this was reported
from play: a room's ambient and its bounced GI reach everywhere, so every mote in
the level picks up something and the field reads as an even haze of specks rather
than as air made visible by a beam. Asked for as *"mostly visible under shafts,
barely when not"*.

`rt_dust_shaft_floor` (0.08) is the albedo a mote keeps where there is no beam —
`1` is the ungated behaviour, `0` is beams only. What it interpolates against is
a per-mote weight computed on the CPU from the very list that decides where
shafts are (`RT_ShaftLightsSelected`), plus the moon. Two things keep that honest
rather than a fudge:

- **It is proximity × phase, never a radiance.** How much light actually arrives
  is the tracer's answer; computing it here as well would count it twice. The
  proximity term is deliberately *not* inverse-square — that is the light's own
  falloff and the tracer has already applied it. `rt_dust_shaft_radius` (2.5 m)
  is the half-weight distance, and it is a look knob with no physical answer.
- **Visibility is still the tracer's.** A mote near a lamp but behind a wall gets
  a high weight and no light, so it is still black. The CPU never has to answer
  the question it could not answer cheaply.

The phase term is the same Schlick/HG function `RtVolumetric.rgen` scatters with,
normalised so isotropic is 1 and sharing `rt_volume_shaft_asym`. That is what
makes the dust feel *volumetric* rather than merely locally lit: at the shipping
0.5 it swings ~0.17–5.8, so a mote between you and the lamp flares and one lit
from behind you does not — the same reason a shaft reads strongly looking into it
and weakly from the side.

**The moon needs a gate of its own** (`rt_dust_moon`). It is the strongest shaft
in the game and a mote in one should blaze, but a directional light has no
position, so proximity says nothing about it and the phase term *alone* would
brighten every mote in the level whenever the player faces its bearing —
including in a sealed room the moon cannot reach. So it counts only for a mote
whose sector has a **sky ceiling**: cheap, exact for the case that matters, and
wrong only under an overhang, where the tracer finds the mote shadowed and blacks
it anyway.

`rt_dust_clip` (on) skips motes outside every sector or buried in a floor or
ceiling. Not a look change — such a mote is lit by nothing and already invisible
— but the quads are never *built*, so the same `rt_dust_max` buys more dust where
dust can be seen. It also supplies the sector the moon gate needs, so the two
share one lookup.

Ladder: `dust-ungated` (floor 1) → shipping 0.08 → `dust-only` (floor 0);
`dust-beamwide` / `dust-beamtight` bracket the radius; `dust-nomoon` and
`dust-noclip` isolate the two gates above.

Two consequences worth knowing before tuning:

- **`rt_dust_density` and `rt_dust_max` are not independent.** The cell spacing is
  the coarser of what the density asks for and what the cap allows, so raising
  density alone does nothing once the cap binds. That is what makes `rt_dust_max`
  a real hard bound rather than a cull applied after the work is done — and why
  raising `rt_dust_far` costs nothing, it just thins. `rt_dust_debug` prints the
  spacing that actually resulted, which is the only way to tell which is in
  charge.
- **A mote cannot be faded out.** Below RTGL1's 0.98 alpha threshold the whole
  batch is demoted to the rasterized overlay and goes fullbright, so distance is
  handled by **shrinking**, exactly as debris is.

Arms: `dust-fat` (**run first** — the absurd arm; a mote is small enough that
"I can't see any" has two causes that look identical), `dust-off`/`on`,
`dust-heavy`, `dust-still` (freezes the field — the real test is whether the
lattice is *visible*, which would be a bug in the hashing, not a value to tune),
`dust-honest`, `dust-noshaft`, and the gate ladder above.

**The diagnostics ship off.** `rt_volume_shaft_verbose` and `rt_dust_debug` are
0 in the pins *and* in every arm — they were on in the first pass of arms and
that is console noise during play. Turn one on for a run by appending it:
`.\tools\ab.cmd dust-on 07 -- +rt_dust_debug 1`.

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
| `lampshaft-phys` / `lampshaft-flat` | the falloff ladder: honest inverse square vs no falloff at all |
| `lampshaft-listorder` | the ray-budget bug, kept runnable (`relcull 0`) |
| `lampshaft-noband` / `lampshaft-wide` | the selection bug kept runnable, and the upper bound of the machinery |
| `dust-fat` | **run first for dust** — is anything being drawn at all |
| `dust-off` / `dust-on` / `dust-heavy` / `dust-still` / `dust-honest` / `dust-noshaft` | the dust ladder (§4c) |
| `dust-ungated` / `dust-only` | the shaft gate: dust everywhere vs dust in beams only |
| `dust-beamwide` / `dust-beamtight` | how wide a beam counts as a beam — a look knob with no physical answer |
| `dust-nomoon` / `dust-noclip` | the moon gate and the solid-geometry clip, isolated |
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

- Dust is global and has no per-map control. If a level wants dustier air than
  its neighbour, that belongs in an `RT_FOG_PRESETS`-style table in
  `rt_presets.cpp`.
- Only the ceiling and solo families offer shafts. Flames, switches, lava, the
  9800/9801/9802 map things and the SMON wall panels do not. SMON in particular
  should stay out until asked for — §20 of `rt-lighting-practices.md` is the
  standing warning about turning a dense family on wholesale.
- No per-map table. If shaft density turns out to want per-map control it belongs
  in an `RT_FOG_PRESETS`-style table in `rt_presets.cpp`, not in per-light
  metadata.
- Not judged in play. Nothing in this document claims a look.
