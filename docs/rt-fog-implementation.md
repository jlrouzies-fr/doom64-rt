# Illuminated fog — the implementation

Companion to **`docs/rt-fog.md`**, which is the *what and why*: what the feature
is, which maps get it, how to tune it, and the reasoning behind each default.
This file is the *how*: every file the fog touches, in the order the data moves
through them, and the four things that will bite anyone changing it.

If you are here to change a number, you want the other file.

---

## 1. The whole chain, in order

Eleven steps, four of them in the engine and five in RTGL1. Nothing is hidden in
between: this list is the entire feature.

| # | where | what happens |
|---|---|---|
| 1 | `gamedata/g_mapinfo.cpp` | `fade` and `fogdensity` are parsed into `level_info_t` |
| 2 | `g_level.cpp` (`FLevelLocals::Init`) | copied onto the level: `fadeto`, `fogdensity` |
| 3 | `rt_main.cpp` `RT_OnLevelLoad()` | **requests** fog: stashes the map name, sets `g_fog_pending` |
| 4 | `rt_main.cpp` `RT_ResolveFogIfPending()` | first rendered frame: applies `RT_FOG_PRESETS` → writes the `rt_fog_*` cvars |
| 5 | `rt_main.cpp` `RT_ResolveFog()` | every frame: cvars + the map's own data → `ResolvedFog` |
| 6 | `rt_main.cpp` frame setup | fills `RgDrawFrameVolumetricParams` |
| 7 | `RTGL/Source/VulkanDevice.cpp` | params → the `globalUniform` fields |
| 8 | `RTGL/.../RtVolumetric.rgen` | one froxel per thread: density ramp, tint, lighting |
| 9 | `RTGL/.../RaygenCommon.h` | the near-field fade, inside the VOLUME light path only |
| 10 | `RTGL/.../CmVolumetricProcess.comp` | integrates along Z → in-scatter + transmittance |
| 11 | `RTGL/.../CmScatterAccum.comp` → `CmPrepareFinal.comp` | per-pixel sample, temporal reprojection, and `hdr = hdr·a + rgb` |

Steps 1, 2, 10 and 11 are stock and were not modified.

---

## 2. Engine side (`rt_main.cpp`)

### The cvars

    rt_fog                 master
    rt_fog_presets         apply RT_FOG_PRESETS at level load
    rt_fog_color           medium tint    (000000 = the map's own `fade`)
    rt_fog_density         density at the camera  (-1 = the map's own `fogdensity`)
    rt_fog_density_mult    MAPINFO fogdensity -> density
    rt_fog_density_far     density at rt_fog_far  (-1 = same as near)
    rt_fog_color_far       tint at rt_fog_far     (000000 = same as near)
    rt_fog_curve           shape of the near->far ramp
    rt_fog_far             the volume's reach, METRES
    rt_fog_ambient         unlit floor
    rt_fog_lightmult       multiplier on scattered light
    rt_fog_light_near      near-field fade radius around a LIGHT, metres
    rt_fog_illum           light the fog from ALL lights
    rt_fog_debug           NOARCH; log what each level resolved

All are `RT_CVAR` (`CVAR_ARCHIVE`) except `rt_fog_debug`, which is
`RT_CVAR_NOARCH` for the reason `rt_sun_leak_debug` is: a debug mode that sticks
in the ini is how a working fix gets believed to be inert for a whole round trip.

Every one of them is pinned in `tools/launch-retribution-rt.cmd`. That is not
decoration — a launcher pin **overrides the compiled default**, so a value left
in the ini by an `ab-fog.cmd` arm would otherwise follow you into normal play.

### `RT_FOG_PRESETS`

```cpp
struct FogPreset
{
    const char* map;
    bool        fog;
    uint32_t    color;        // 0  = the map's own MAPINFO fade
    float       density;      // <0 = derive from its own fogdensity
    float       far_m;        // <0 = keep the launcher's
    float       ambient;      // <0 = keep
    int         illum;        // 1 all-lights, 0 single, -1 keep
    float       density_far;  // <0 = same as density (uniform)
    uint32_t    color_far;    // 0  = same as color
    float       curve;        // <0 = keep
    const char* note;
};
```

Same shape as `RT_MOON_PRESETS` and `RT_CLOUD_PRESETS`, applied at level load,
gated by `rt_fog_presets`, **opt-in**. `g_fog_base_*` captures the launcher's
values on the first application so a map with no row falls back to the global
rather than inheriting the last fogged map's settings — without that the table is
sticky in one direction and the fallback silently becomes "the last preset
visited".

With `rt_fog_presets 0`, `RT_ApplyFogPreset` returns early leaving `g_fog_active`
**true**: the cvars alone decide, on whatever map is loaded. That is the
authoring mode, and it is why every `ab-fog.cmd` arm but `full` and `debug` sets
it.

### `ResolvedFog`

`RT_ResolveFog()` runs every frame and resolves the sentinels:

- `rt_fog_color` 0 → `primaryLevel->fadeto`; still 0 → **no fog** (a listed map
  that says nothing about a colour gets nothing, rather than a guessed white);
- `rt_fog_density` < 0 → `primaryLevel->fogdensity × rt_fog_density_mult`;
  ≤ 0 → no fog;
- `rt_fog_density_far` < 0 → the near value; `rt_fog_color_far` 0 → the near
  colour. Both mean *uniform medium*.

Every frame rather than at load, so `fog 00A0A0` in the console takes effect
immediately instead of at the next level change.

---

## 3. RTGL1 side

### API

Four fields added to `RgDrawFrameVolumetricParams` (`Include/RTGL1/RTGL1.h`),
with no-op defaults in `Source/DrawFrameInfo.h` so every other caller is
unaffected:

```c
RgBool32  illuminateFromAllLights;   // false
RgFloat3D mediaColor;                // { 1, 1, 1 }
RgFloat3D mediaColorFar;             // { 1, 1, 1 }
float     farScattering;             // < 0 means "same as scaterring"
float     densityCurve;              // 1
float     lightNearFade;             // 0
```

### Uniforms

Declared in `Source/Generated/GenerateShaderCommon.py`, which
`tools/build-rtgl.cmd` re-runs (`GenerateShaders.py -g`) to regenerate
`ShaderCommonC.h` and `ShaderCommonGLSL.h`. **Never hand-edit those two.**

    volumeAllLights        (took the _padc1 slot)
    volumeMediaColor       vec4
    volumeMediaColorFar    vec4
    volumeScatteringFar
    volumeDensityCurve
    volumeLightNearFade    (took a _padf1 slot)

std140 layout is by groups of four scalars per 16 bytes, and `viewProjCubemap`
at the end must stay 16-byte aligned or the C and GLSL layouts diverge silently.
Two of the six fields were taken from existing `_pad` slots for exactly that
reason; the vec4s were added as whole groups.

### `RtVolumetric.rgen` — the froxel pass

One thread per cell of a 160×88×64 grid. In order:

1. **The ramp.** `cell.z` is a straight depth fraction, because
   `volume_getCenter` mixes near..far linearly (`VOLUMETRIC_DISTANCE_POW` is 1).
   So

   ```glsl
   ramp    = pow( cell.z / (VOLUMETRIC_SIZE_Z - 1), volumeDensityCurve );
   density = mix( volumeScattering, volumeScatteringFar, ramp );
   tint    = mix( volumeMediaColor, volumeMediaColorFar, ramp );
   ```

   That is the whole cost of separating near fog from distant fog: one `mix()`,
   no second volume and no extra rays.

2. **The lighting**, one of two paths:
   - `ILLUM_VOLUME_ACTIVE` → `processDirectIllumination`, the full NEE/ReSTIR
     direct estimate, so every light in the map scatters;
   - otherwise `traceDirectIllumination_SpecificLight`, the stock single light
     from `LightManager::TryGetVolumetricLight`.

3. **The tint**, applied to the whole in-scattered term — ambient *and* lit, so a
   cyan fog is cyan and so is the haze around a lamp standing in it.

4. **The store**: `vec4( lighting × scattering, scattering + absorbtion )`.

Extinction is left **monochrome**. The transmittance channel is a single float
all the way to `CmPrepareFinal`, so per-channel extinction is a framebuffer
change, not a shader one.

### `RaygenCommon.h` — the near-field fade

In `traceDirectIllumination`, guarded by
`#if LIGHT_SAMPLE_METHOD == LIGHT_SAMPLE_METHOD_VOLUME` so it exists only in the
fog's specialization of that shared function:

```glsl
out_diffuse *= smoothstep( 0.0, volumeLightNearFade,
                           length( light.position - surf.position ) );
```

Keyed off the **light's** distance, not the camera's. See `rt-fog.md` §4 for why
that distinction is the whole point.

---

## 4. The arithmetic, so a density can be predicted instead of guessed

`RtVolumetric.rgen` applies a flat `density × 0.001` per cell, and
`CmVolumetricProcess.comp` sums those along Z with no slice-thickness term, over
64 slices spread evenly across `rt_fog_far`. So for a ramp `d0 → d1` at curve
`k`, optical depth to depth fraction `t` is

    tau(t) = 0.064 · [ d0·t + (d1 − d0)·t^(k+1)/(k+1) ]        T = exp(−tau)

Two consequences worth holding on to:

- useful densities are **tens**, not fractions;
- because the coefficient is per *cell* rather than per metre, **shortening
  `rt_fog_far` makes the same density read thicker**. Reach and strength are not
  independent.

---

## 5. The four traps

**1. `RT_OnLevelLoad` runs before the level exists.** It is called from
`G_InitNew`, which runs *before* `P_SetupLevel`, so `primaryLevel->fadeto` and
`->fogdensity` there still hold the **previous** map's values — and on a first
load, nothing. That is why the fog is only *requested* at load and resolved by
`RT_ResolveFogIfPending()` on the first rendered frame. Any future code that
wants to read map data at level load has the same problem.

**2. The preset table overrides your `+cvar` pin.** It writes the cvars at level
load, i.e. after the command line has been parsed. Identical to the
`RT_CLOUD_PRESETS` trap, with the identical symptom: an arm looks like it does
nothing. `rt_fog_presets 0` is the answer.

**3. Both flags must WRITE `g_illuminationVolume`.** `illumVolumeEnable`
(`rt_illum_volume`, the raster path) and `volumeAllLights` (`rt_fog_illum`) now
gate the same branch. It is tempting to let only the raster flag store the image
— but the estimate is temporally blended at 0.05 against what it stored last
frame, so without the store it reads a stale image forever and never converges.
`ILLUM_VOLUME_ACTIVE` is deliberately used for both the compute *and* the store;
only `RsWorld.inl` reads it.

**4. Two builds at once corrupt the PDB.** RTGL and gzdoom share build state; a
`build-rtgl.cmd` still running when `build-gzdoom-rt.cmd` starts produces a storm
of `C1041: cannot open program database`. Kill `MSBuild` / `mspdbsrv` and rebuild
one at a time. This bit during this work and is also logged in
`moon-and-sky-leaks.md` §7.

---

## 6. Building and verifying

```
tools\build-rtgl.cmd          uniforms + shaders + RTGL1.dll  (must be first)
tools\build-gzdoom-rt.cmd     the engine
```

RTGL first: it regenerates `ShaderCommonC.h`/`ShaderCommonGLSL.h` and the `.spv`,
and the engine build stages against the result.

`build-rtgl.cmd` already fails loudly on a shader compile error and on a locked
`RTGL1.dll` (both used to be silent). Beyond that, three checks that a change is
actually live — this project has lost sessions to changes that were not:

```
strings gzdoom.exe        | grep rt_fog_          the cvar exists in the binary
grep volumeMediaColor rt/shaders/RtVolumetric.rgen.spv    the uniform reached the shader
+rt_fog_debug 1                                   what the level actually resolved
```

And one free in-game check: on MAP26, `ab-fog.cmd ramp` and `ab-fog.cmd full` are
the same numbers by two different routes — the arm's `+cvar`s and the preset
table. If they differ, the table did not apply.

---

## See also

- `docs/rt-fog.md` — what it is, which maps, and every tuning decision
- `compat-patches.md` — the engine/RTGL patch log entry for this work
- `docs/moon-and-sky-leaks.md` — MAP26's moon, and the concurrent-build trap
- `docs/rt-clouds-and-lightning.md` — the per-map opt-in table this copies
