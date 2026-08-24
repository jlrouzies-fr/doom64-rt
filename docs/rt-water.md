# RT water — stylized Doom 64 water + projected caustics

Everything about how water is rendered in this fork: the surface shader, the
caustics it throws onto the geometry around it, every cvar, and — at the end —
the four traps that cost most of a session, because each of them will recur on
other features.

Engine patch-log entries: `compat-patches.md` (§ *Stylized Doom 64 water*,
§ *Water tag was inert*, § *Projected water caustics*). This file is the
canonical description; those entries are the dated changelog.

---

## 1. What the water is

`D64W2_01` (MAP10/11/34) and `D64W1_01` (MAP08/14/15/16/22/23/30/34) are the
Doom 64 water flats. Two facts drive the whole design:

- **They are opaque FLOOR flats.** There is no sector underneath them. Anything
  that refracts through the surface has nothing to show.
- **They are nearly black.** Measured in *linear* space, the flat's median texel
  luminance is `0.0024`, p95 `0.0113`, p99 `0.0161`, max `0.0327`. Under a path
  tracer the raw flat reads as a hole in the floor, not as water.

RTGL's built-in water path is physical: refract into the media, Beer-Lambert
absorb, mirror the rest. That reads far too real next to Doom 64's art *and* is
structurally wrong here — the refraction half of its checkerboard split has
nothing under it. Hence a stylized path.

> For reference: **Doom II RT does not use the water shader on its water.** Its
> global meta marks `FWATER1`–`4` as `isMirror` with metallic 1 / roughness 0 —
> a plain mirror, no media, no caustics. That is why it is trouble-free there,
> and why copying it cannot give a deep blue body with caustics.

---

## 2. The surface — `rt_water_style`

In `RaygenPrimary.inl`, `RAYGEN_REFL_REFR_SHADER`. Same entry point as stock
water (`GEOM_INST_FLAG_MEDIA_TYPE_WATER`), but the checkerboard split is spent
differently:

| checkerboard half | stock physical | stylized |
|---|---|---|
| odd | refraction into the media | **keep the lit water surface** in the G-buffer |
| even | mirror reflection | mirror reflection, Fresnel remapped |
| resolve (`CmCheckerboard`) | `F·refl + (1−F)·refracted` | `F·refl + (1−F)·lit surface` |

The surface half rewrites only the shading inputs and returns early: albedo,
normal (the animated wave normal), a low metallic/roughness, throughput
(`(1−F)·2`, alpha 1 = split), and the screen-emission sheen. Position, depth,
motion and the visibility buffer stay exactly as the primary pass wrote them —
they already describe this surface — so the direct and indirect passes, which
run *after* refl/refr, light the water plane like any other opaque surface and
the denoisers see an ordinary primary hit.

**Colour is rebuilt from the flat, not invented** (`getStylizedWaterAlbedo`):
the texture's own luminance is the caustic vein mask, normalised by
`rt_water_veinref`, brightened by the wave-normal tilt (`rt_water_caustic`), and
mixed from a deep blue body (`rt_water_tint_*`) toward a pale-cyan crest.
`rt_water_glow` adds a small **screen-space** sheen on the veins so the pattern
still reads in near-black rooms — on-screen emission only, it casts no light and
cannot wash GI.

### Reflection strength is deliberately not physical

Water's F0 is ~0.02, so a correct Schlick term reflects sprites and geometry
perfectly *at a strength nobody can see* — looking down at a pool you get a 2%
reflection. The shader keeps the **shape** of the Schlick curve (weak head-on,
strong at grazing) and remaps its range onto
`[rt_water_reflmin, rt_water_reflmax]`.

---

## 3. The caustics — `rt_water_caustics`

Caustics cast **by** the water **onto** the walls and floors around it.

**A 1-spp path tracer cannot find these, at any sample count.** A caustic is a
light→specular→diffuse→eye path: the segment from a diffuse wall toward a light
passes through the specular water surface, and the probability that a random
diffuse bounce hits the water *and* refracts into a light is effectively zero.
This is the classic unidirectional-path-tracer limitation, not an RTGL defect.

So they are **projected**. In `RaygenPrimary.inl` (primary pass), every shading
point fires one probe ray; if it lands on water, an animated caustic field is
folded into that point's albedo.

### Design decisions, and why

**Applied to ALBEDO, in the primary pass — not to the direct lighting term.**
Doom 64 interiors are lit mostly by *indirect* light (sector emissives, sky
fill), and the indirect term is written by `RtRaygenIndirectFinal.comp`, a
compute shader with no TLAS that cannot fire the probe. Modulating only direct
lighting computed the effect perfectly and showed nothing — multiplying a
near-zero direct contribution changes nothing. Albedo scales direct and indirect
alike.

*Side benefit:* albedo is not denoised, so the filaments stay crisp and
temporally stable. Real traced caustics would live in the lighting signal at
1 spp and A-SVGF would smear exactly the thin filaments that make them read as
caustics.

**Multiplicative, never additive.** Caustics are focused light, not a light
source. A pitch-black room must stay black; an additive term would make water
glow in the dark and wash the GI — the failure already logged for world
emissives in `compat-patches.md`.

**The probe is slanted**, `normalize(-up + normal * rt_water_caustic_slant)`. A
pool almost always has a ledge or walkway around it, so a wall set back behind
that ledge probes straight down onto the *ledge* and never sees the water. The
tilt lets a wall look down-and-out over the ledge — which is also where the
light physically comes from. Floors (`normal == up`) and ceilings still probe
straight down: the normal term only shortens or cancels the vertical component,
it never tips those cases sideways.

**The pattern is sampled at the WATER hit point, not at the receiver.** The
probe resolves the exact hit position from `getOnlyCurPositions()` plus the
payload barycentrics. Sampling the receiver projected onto the horizontal plane
gave a vertical wall identical UVs at every height — infinite vertical smearing.
Sampling the water point also gives correct foreshortening and a distance to
fade by.

**Two separate falloffs**, because they are not the same distance:

- along the probe (`rt_water_caustic_dist`) — light spreads, so a wall at the
  pool edge gets a crisp pattern and one set back gets little;
- with **height** above the water (`rt_water_caustic_rise`) — real caustics climb
  only a little way up a wall. The probe needs a long *sideways* reach to clear
  a ledge, so one shared range ran the pattern up the full height of every wall.

**Walls get their own gain** (`rt_water_caustic_wall`), blended on
`verticality = 1 − |dot(normal, up)|`. The same pattern is genuinely fainter on
a wall — grazing angle, and the light has spread further — so a single gain
tuned on the pool bottom leaves walls invisible, while raising it brightens the
floor just as much.

**Sprites do not receive caustics.** `RG_MESH_PRIMITIVE_NO_WATER_CAUSTICS` →
`GEOM_INST_FLAG_NO_WATER_CAUSTICS`, set in `rt_main.cpp` for sprites, the
first-person weapon and viewer, particles, decals, sky and UI. A caustic is
light thrown *across a surface*; a camera-facing billboard has no surface for it
to lie on, so the pattern just tints the enemy and swims as the camera turns.
Those pixels also skip the probe ray entirely, so it is slightly cheaper.

### What these caustics are NOT

**They are not traced.** The only ray-traced part is the probe: *is there water
below, and where*. The pattern itself is two scrolling samples of the
`WaterNormal` texture, combined where they cancel. It has **no** relationship to
the light positions, to the wave normals actually visible on the surface, or to
refraction. It is a caustic-*looking* field with physically-motivated placement
and falloff.

A genuinely light-driven version is feasible without going to photon mapping:
the probe already lands on a known water point, and `getWaterNormal()` already
computes the animated wave normal there. Refract the direction toward the chosen
light through that normal and weight by how well the beam converges on the
receiver, plus a curvature focusing term. That would agree with the visible
ripples and respond to lights moving. Deliberately **not** done — see the
denoiser note above; keep any such version in albedo.

---

## 4. Tagging — which surfaces are water

RTGL only runs its water path on primitives carrying `RG_MESH_PRIMITIVE_WATER`.
This fork sets it **engine-side**, in `rt_main.cpp` `l_waterflag()`, by texture
name **prefix** match (`D64W1_`, `D64W2_`, plus exact `D64WATR1`/`D64WATR2`).
It prints one unmuted line per distinct frame name per session:

    RT water: tagging "D64W2_37" as RG_MESH_PRIMITIVE_WATER (rt_water_style 1)

Why engine-side rather than `isWater` in `rt/data/textures.json`:

- that file lives under `build/` (gitignored) and is rewritten wholesale by the
  PBR tooling, so the tag needed re-applying by hand after every regen;
- RTGL's own diagnostics are gated behind **both** `-rtdebug` and its private
  `g_printSeverity`, so a meta that silently failed to apply and one that
  applied and did nothing produce byte-identical evidence.

`tools/set_water_meta.py` still maintains the JSON route (harmless, and correct
if it is ever wanted) and, more importantly, quarantines the frame-01-only
material overlays — see trap 2 below.

---

## 5. Cvars

All pinned explicitly in `tools/launch-retribution-rt.cmd`.

### Surface

| cvar | default | meaning |
|---|---|---|
| `rt_water_style` | 1 | stylized water; 0 = stock RTGL physical water |
| `rt_water_tint_r/g/b` | 1 / 1 / 15 | deep blue body colour |
| `rt_water_caustic` | 1.5 | how hard wave crests brighten the flat's own veins |
| `rt_water_veinref` | 0.1 | linear luminance that saturates the vein mask |
| `rt_water_reflmin` | 0.1 | reflection looking straight **down** (physical = 0.02) |
| `rt_water_reflmax` | 0.75 | reflection at **grazing**; 1 = true mirror |
| `rt_water_rough` | 0.1 | roughness written for the surface half |
| `rt_water_glow` | 0.04 | unlit screen-space sheen on the veins; casts no light |
| `rt_water_wavestren` | 0.4 | wave normal strength (**also** the partial-invisibility warp) |
| `rt_water_wavespeed` | 0.2 | wave scroll speed (also partial-invisibility) |
| `rt_water_areascale` | 0.35 | world area one tile of the wave normal covers |

`rt_water_wavestren` / `rt_water_wavespeed` were hardcoded (3.0 / 0.05, "for
partial_invisibility"). At 0.05 the wave field scrolled one cycle every few
minutes — the caustics could not shimmer at all.

### Projected caustics

| cvar | default | meaning |
|---|---|---|
| `rt_water_caustics` | 1.2 | base gain (this is what floors get). 0 = off, **and no probe ray is traced** — the perf switch |
| `rt_water_caustic_wall` | 4.0 | extra gain on vertical receivers only |
| `rt_water_caustic_scale` | 0.8 | field frequency, **UV per metre** |
| `rt_water_caustic_speed` | 0.35 | field scroll speed |
| `rt_water_caustic_dist` | 512 | probe reach, **map units** (slant range, not pure height) |
| `rt_water_caustic_rise` | 64 | how far above the water caustics reach, map units |
| `rt_water_caustic_slant` | 0.6 | probe tilt along the surface normal; 0 = straight down |

### Diagnostic

`rt_water_debug` — **NOARCH**, so it cannot stick in the ini.

- `1` — water **surface**: magenta where the stylized branch runs, green where
  RTGL flagged it water but the gate rejected it; plus the caustic probe on
  everything else.
- `2` — caustic probe only. The water surface is left showing its own probe
  result, which is the test for whether the probe can see water *at all*.
- Probe colours: **black** = hit nothing, **blue** = hit non-water geometry,
  **green** = hit water (brightness is the caustic field).

---

## 6. Files

| file | role |
|---|---|
| `deps/RTGL/Source/Shaders/RaygenPrimary.inl` | `getStylizedWaterAlbedo`, `probeWaterBelow`, `getWaterCaustic`, the stylized refl/refr branch, caustics folded into primary albedo |
| `deps/RTGL/Source/GeomInfoManager.cpp` | `RG_MESH_PRIMITIVE_NO_WATER_CAUSTICS` → geom flag; water probe at **WARNING** severity |
| `deps/RTGL/Source/Generated/GenerateShaderCommon.py` | uniform fields; `GEOM_INST_FLAG_NO_WATER_CAUSTICS` (took `RESERVED_0`) |
| `deps/RTGL/Include/RTGL1/RTGL1.h`, `Source/DrawFrameInfo.h`, `Source/VulkanDevice.cpp` | `RgDrawFrameReflectRefractParams` plumbing |
| `sourcecode/gzdoom-rt/.../rt_main.cpp` | all cvars, `l_waterflag()`, `l_nocausticsflag()` |
| `tools/set_water_meta.py` | JSON meta route + frame-01 overlay quarantine |
| `tools/ab-water.cmd` | arms `stock` / `styl` / `flat` / `mirror` / `noglow` / `nocaus` / `debug` |

Rebuild: `tools/build-rtgl.cmd` **and** `tools/build-gzdoom-rt.cmd` — new
uniform fields change the generated `ShaderCommonC.h`, so the engine must be
rebuilt too, not only the shaders.

---

## 7. The four traps

Each of these produced a *wrong-looking result with no error*, and each
generalises well beyond water.

### 1. `D64W2_01` is one frame of a 64-frame animation

`ANIMDEFS` defines `D64W1_01`/`D64W2_01` as 64-frame sequences at 2 tics per
frame. The map's sector names frame 1, but GZDoom swaps the frame every 2 tics,
so the name reaching RTGL is almost never the one in the map data.

Matching the exact name tagged the water for **2 tics out of ~128** — it became
water for one frame per ~3.7 s cycle and reverted. Reported as "the water
regularly flashes bright". A periodic flicker is much harder to read as "the
match is wrong" than a clean null would have been.

> **Rule:** anything keyed on a Doom 64 texture name must check `ANIMDEFS` and
> prefix-match. This applies to emissive meta, `rt_faux_lamps`, `rt_solo_lamps`
> and `rt/mat` overlays, not just water. RTGL says so itself in
> `GeomInfoManager`: *"can't use texture / mesh name, as texture can be just 1
> frame of animation sequence"*.

### 2. Material overlays generated for frame 01 only

The PBR tooling had produced `_n` / `_orm` / `_h` for `D64W1_01` and `D64W2_01`
— the names the maps reference — and nothing for frames 02–64. Once per cycle
the surface gained a normal map *and* a heightmap (parallax shifts the UVs),
then snapped back two tics later: the reflections and waves visibly jumped.

> **Rule:** a per-texture asset generated for an animated flat must cover every
> frame or none. `tools/set_water_meta.py --apply` quarantines the 24 offending
> files; `--revert` restores them.

### 3. Water is not in `rayCullMaskWorld`

`ASManager.cpp`:

```cpp
if( filter & FT::PT_REFRACT ) {
    // completely rewrite mask, ignoring INSTANCE_MASK_WORLD_*
    instance.mask = INSTANCE_MASK_REFRACT;
}
```

Water is refractive, so its TLAS instance mask is **only** `INSTANCE_MASK_REFRACT`
(bit 5) — every `INSTANCE_MASK_WORLD_*` bit is stripped. A probe ray using
`rayCullMaskWorld` is not merely unlikely to find water, it is **incapable** of
intersecting it. Four rounds of fixes (winding, reach, slant, direct-vs-indirect)
all produced identical output because none of them could ever have mattered.

> **Rule:** a result that does not move when you change the thing you believe
> causes it means you are not looking at the cause. RTGL's own
> `getReflectionRefractionCullMask` ORs in `INSTANCE_MASK_REFRACT` — the answer
> was in a function already read.

### 4. Silent failures in the build path

Three, all found while working on this, all now guarded:

- `copy /Y` of `RTGL1.dll` fails when gzdoom holds the file, `>nul` swallowed
  it, and `build-rtgl.cmd` still printed **BUILD_OK** — fresh shaders playtested
  against a stale DLL. Now error-checked.
- `GenerateShaders.py` exits 0 even when glslang **rejects a shader**. The
  script now greps its log for `error:` and aborts.
- `debug::Error` inside RTGL reaches `RT_Print`, which pops a modal Win32
  `MessageBoxA` whose default action is `exit(-1)`. An ERROR-severity probe
  **kills the game** at the first matching primitive. Use `debug::Warning`
  (goes through `Printf`); `debug::Error` only reaches the log via `DPrintf`,
  i.e. developer mode. For anything that must be visible, print from the gzdoom
  side with `Printf`.

Also worth knowing: RTGL builds from two agents at once collide on
`deps/RTGL/BuildCMake` and fail with `C1041: cannot open program database`.
Stagger them.
