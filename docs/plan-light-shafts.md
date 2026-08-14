# Plan — light shafts from ordinary lamps, not just the moon

**Status:** planned, not started.
**Why it is worth doing:** beams of light in a dark room *are* the Doom 64 look, and
right now this project can only produce them outdoors, from the moon. Every grate,
doorway, ceiling lamp and monitor bank inside the game is currently a light with no
visible air around it.

Related: [`docs/moon-and-sky-leaks.md`](moon-and-sky-leaks.md) §5.4 (the medium and its
density), [`docs/rt-fog.md`](rt-fog.md), [`docs/rt-smoke.md`](rt-smoke.md) — all three
share the same froxel volume.

---

## 1. What already exists

The shafts under the moon are not a special effect. They are `rt_volume_scatter` being
scattered by **one** directional light inside the froxel volume, and the volumetric pass
shadow-tests that light itself:

- `RTGL1/Source/LightManager.cpp:815` — `TryGetVolumetricLight()` picks a **single**
  light per frame and hands its index to the shader.
- `RTGL1/Source/VulkanDevice.cpp:608` — writes `gu->volumeLightSourceIndex`, or
  `LIGHT_INDEX_NONE`.
- `RTGL1/Source/Shaders/RtVolumetric.rgen:66` — `traceDirectIllumination_SpecificLight()`
  samples exactly that one light and calls `traceShadowRay` for it.

There is also already a per-froxel **all-lights** estimate in the same shader, added for
fog and for the raster path:

```
illumVolumeEnable   the RASTER path shades translucent primitives from it
volumeAllLights     rt_fog_illum wants more than the single picked light
```

Both write `g_illuminationVolume`. So the expensive half — an all-lights estimate per
froxel — is written every frame when fog illumination is on, and the shaft pass simply
does not read it.

## 2. The shape of the change

Two candidate routes, in increasing cost:

1. **Read what is already written.** Have the volumetric shaft pass consume
   `g_illuminationVolume` instead of only `volumeLightSourceIndex`, gated by a new cvar
   (`rt_volume_alllights`, off by default). Cheapest possible experiment: if the fog path
   already produces a usable estimate, shafts from local lights are close to free.
2. **Pick N lights instead of one.** Extend `TryGetVolumetricLight` to return the k
   nearest/brightest lights to the camera and loop them in
   `traceDirectIllumination_SpecificLight`. More shadow rays per froxel, so it needs a
   budget cvar — `rt_volume_lights_max`, single digits.

Route 1 first. It answers "does this look good at all" without touching light selection.

## 3. Which lights should qualify

Not all of them. A shaft under every 9802 wall monitor would be a mess, and this project
has already learned that lesson once — §20 of `rt-lighting-practices.md`, where SMONAA's
density would have added ~105 flickering lights to one map.

Start with a brightness/radius threshold plus an explicit opt-in family:

- ceiling insets and hanging lamps (`rt_lights_fixtures.cpp` already infers them),
- the `LAMPS` / `PANEL_LAMPS` things from `make_seqlight_fix.py`,
- anything above a radius threshold.

Per-map control belongs in `RT_FOG_PRESETS`-style tables in `rt_presets.cpp`, not in
per-light metadata.

## 4. Traps, all previously paid for

- **The medium's density hangs off `rt_volume_far`.** The shader applies
  `rt_volume_scatter` **per froxel cell** over a grid that is 64 slices at any reach, so
  raising the reach for smoke (30 → 60) halved the moon. `rt_volume_scatter` is normalised
  per metre in `rt_main.cpp`; fog is deliberately not. Any new knob here must say which
  convention it uses.
- **There is no single visibility choke point.** `RtVolumetric.rgen` does **not** call
  `traceDirectIllumination`; a change in the shared lighting path leaves shafts untouched
  and looks inert. Verify in the shader you actually edited.
- **Asymmetry is expected, not a bug.** The phase function has a ~11× forward bias, so a
  shaft is strong looking toward the light and weak from the side.
- **Cost is per froxel, not per pixel.** Shadow rays per cell per light — this is where a
  frame budget goes. Measure before widening the light set.

## 5. How to judge it

A/B arms in `tools/arms/`, following `moon-*.cfg`. MAP13 has the reference shafts already;
good interior candidates are the MAP07 clad corridors and any room with a ceiling grate.
Judge it in-game — nothing here is measurable from a scanner.
