# Coagulated blood pools (and the poison art)

Blood that reads as a thick fluid with a skin on it: dark plates of clotted
crust, liquid veins running between them in real relief, and liquid that
visibly **moves along** those veins.

Art built by `tools/gen_liquid_art.py` into
`Doom64-Retribution/d64r-liquid-art.wad` — which also carries the poison
replacement, see the end. A/B it with `tools\ab-bloodpool.cmd <arm> [map]`,
default MAP17.

## What was wrong, measured

`rt_draw.cpp:943` tags all four Doom 64 liquids as water and packs a 2-bit
liquid id, but **the only thing that id changed was two colours** —
`rt_blood_tint` (15,2,2) and `rt_blood_crest` (255,115,102). Blood got water's
wave normal, water's roughness, water's Fresnel and water's caustic gain. It was
water painted dark red.

It was also the liquid where the one mechanism that creates variation is
weakest. `getStylizedWaterAlbedo` builds its vein mask as
`luminance / rt_water_veinref`, and off the WAD patches:

| patch | mean RGB | lum p50 | lum max |
|---|---|---|---|
| `D64BLOD2` (blood) | 27, 0.7, 6 | 0.020 | **0.136** |
| `D64NUKG2` | 4.6, 24.7, 8.3 | 0.067 | 0.307 |
| `D64WATR2` | 4, 7.7, 26.4 | 0.029 | 0.188 |

Nukage saturates that mask. Blood sat near 0.20 across most of the surface — so
the surface was close to a constant colour, and the shimmer riding on it was the
only thing moving.

## Four facts about the shader that decided the design

All four were checked in the source, not assumed.

1. **`_h` parallax already worked on these flats.** `HitInfo.inl:478` applies
   `parallaxTexCoords` before sampling albedo and normal, gated only on
   `globalUniform.parallaxMaxDepth` (`rt_heightmap_stren`). Real depth was free.
2. **`_n` was applied and then thrown away.** The primary pass writes the
   normal-mapped normal to the G-buffer, but `getNormal` (`RaygenPrimary.inl:543`)
   takes the water-wave branch whenever `isWater && !hasNormalMap` — and at the
   primary hit `hasNormalMap` is hardcoded `false` (declared line 864, only
   assigned by `getHitInfoWithRayCone_ReflectionRefraction` for a *later*
   bounce). The stylized branch requires `i == 0`, so the wave always won.
   **That is why relief needed a shader change and not just art.**
3. **`sampleHeightMap` reads `.r` only** (`HitInfo.inl:174`), at **LOD 0** — no
   mips. `_h`'s G and B are free, registered with the albedo (parallax shift
   included), and loaded **linear**: `TextureManager.cpp:1142` marks only albedo
   and emissive sRGB. That is where the flow phase lives.
4. **`framebufAlbedo.a` was unused.** Written `0.0` at every store site, read as
   `.rgb` by `Surface.inl`, `CmNoisyCompose`, `CmNrdCompose`, `CmNrdPack`,
   `CmSVGFAtrous` and the `Ef*` passes. It carries the phase from the primary
   pass to the refl/refr pass, which is where the stylized surface is shaded and
   which has no `ShTriangle` and so can never sample a material texture itself.

## The animation had to die first

Each of the 64 frames is a 64×64 composite of **two offset copies of the
`D64BLOD2` patch, the second at 50% alpha**, with the offsets shifting one unit
per frame (TEXTURES lump in `D64RTR_v15.WAD`). That drift is the stock look.

It also means a static `_n`/`_h` can only ever match **one** frame — which is
exactly why `set_water_meta.py` quarantined the frame-01-only overlays for every
liquid family.

So the new TEXTURES lump redefines all 128 names as one unshifted copy of a
single patch. The ANIMDEFS sequence still runs and is simply invisible, and the
surface becomes materially uniform, which is what makes relief legal at all.

Same call as the lava: `gen_lava_material.py` averaged HLAVA1-5 because the
frames light different cracks and read as blinking, and moved the motion into
the shader. Here the motion becomes the pulse.

The wad must load **after** the mod — GZDoom takes the last definition for a
texture. It is wired into `launch-retribution-rt.cmd` next to the other TX_
overrides.

## The art

`screen/bloodtexture_coag.png` cropped to half, made to tile, resampled to
128 px, and declared `128, 128` with `XScale/YScale 2.0` — so one tile is **64
map units** and a cell reads about 8-9 units, a fist-sized clot. Retribution's
own TEXTURES already uses `XScale 2.0` this way (see `AZTEC02C`).

**Tiling is a min-cut, not a cross-fade.** A feathered blend over the wrap seam
ghosts every vein it crosses and leaves a visibly lighter band — that was the
first attempt and it is obvious at 2×2. The seam is instead routed by a
minimum-error boundary cut, which follows the dark cell interiors where the two
sides agree and steps around the bright veins.

**The tile is EXPOSED, and that is not a look decision.** The reference is ~3×
brighter at the top end than the flat it replaces (p99 0.30 against 0.095), and
the shader's mask is `luminance / rt_water_veinref` with veinref pinned at 0.1.
Shipped as drawn, **65% of the surface read as "vein"** — the mask stopped
picking out the network and the relief baked from it was mush. The tool scales
the art so its 98th percentile lands on `VEIN_REF`, giving ~24% coverage.

Exposing the *art* rather than retuning `rt_water_veinref` keeps this off the
other three liquids, which share that cvar and are correctly tuned for it.
Darkening costs nothing to look at: the stylized path uses this texture's
luminance for the mask and takes its colour from `rt_blood_tint`/`_crest`, so
only the shape survives either way — and a darker pool bounces less light, which
is right for something opaque.

## The flow map — and the version that was rejected

**First version: a phase pulse.** Geodesic distance along the veins, baked as a
phase, with a brightness band sliding along it. Rejected on sight, and
correctly: a band of brightness moving along a *static* vein is still just
brightness changing in place. Nothing in the picture moves. The eye reads it as
the bright parts flickering.

What reads as flow is **texture moving** — a detail pattern advected along the
channel so blobs of liquid physically slide down each vein. That is a **flow
map**, the Portal 2 water technique:

```
_h.r = height          plates high, veins low -- the channel is the LOW point
_h.g = direction.x     the vein's TANGENT, texture space, * 0.5 + 0.5
_h.b = direction.y     (length = confidence; cells and junctions bake to ~0)
```

**The bake** (`flow_field` in the tool): a structure tensor of the blurred vein
mask. Its dominant eigenvector is the gradient — *across* the vein — so the
tangent is that rotated 90°. The tensor is orientation-only, so the sign is
chosen to agree with one global downstream direction (`FLOW_DIR`). That is
deliberate: radiating out of source nodes gives the flow a different heading
every few cells, which at pool distance reads as pulsing from points rather than
a pool drifting one way. Coherence (0 isotropic, 1 clean line) goes into the
vector's *length*, so junctions, blobs and veins perpendicular to `FLOW_DIR`
fade to still instead of pointing somewhere random. About 14% of texels carry
flow — the coherent vein runs — and that is where the eye needs it.

**The advection** (`HitInfo.inl`, primary pass — where the texcoords are): read
the direction at the parallax-corrected UV, then sample the water normal map
(`waterNormalTextureIndex`, tileable, already bound — `getLavaHeat` uses it as
a noise field) at `uv - dir * dist * p` for two phases half a cycle apart,
cross-faded with weight `|1 - 2p|`. One phase alone must snap back to zero
every cycle and the snap is visible; two phases with the blend at zero exactly
when either resets never show it. The result crosses to the shading pass in
`framebufAlbedo.a`.

**The modulation** (`getStylizedWaterAlbedo`): `veins * (1 + flow * (2d - 1))`,
so the sliding detail brightens and darkens the vein both ways — blobs of
brighter and darker liquid moving down a static channel.

**A vector, never an angle.** At a junction two runs disagree; an angle puts
0.98 next to 0.02 and bilinear filtering tears a seam. A vector merely shrinks
toward zero and the shader treats short as still (`length > 0.15`). And exactly
0 in the output means "no flow here", so the valid range is nudged off zero
(`* 0.998 + 0.001`).

**Legibility depends on scale.** `rt_blood_flow_scale` sets detail tiles per
64-unit tile; around 6 a blob is a vein-width across, which is what makes it
read as *something in the vein* rather than a texture sliding under it. The
`coarse`/`fine` arms bracket it.

## Cvars

| cvar | default | |
|---|---|---|
| `rt_blood_relief` | `1.0` | how much of the authored `_n` survives vs the water wave. 0 = the old ripple. Rides on `rt_normalmap_stren`; the depth comes from `_h` parallax, which `rt_heightmap_stren` scales |
| `rt_blood_flow` | `0.7` | depth of the flow-map modulation on the vein mask. 0 = still |
| `rt_blood_flow_speed` | `0.15` | cycles per second of the advection. Slow — this is a thick fluid, and fast reads as a scrolling texture |
| `rt_blood_flow_scale` | `6.0` | detail tiles per 64-unit tile. Higher = smaller blobs |
| `rt_blood_flow_dist` | `0.25` | how far the detail travels per cycle, in tile UV (1 = 64 units). With the speed above, ~2.4 units/s |
| `rt_nukage_caustics` | `0.0` | same as `rt_blood_caustics`, for poison |
| `rt_blood_caustics` | `0.0` | how much of `rt_water_caustics` blood projects onto the geometry around it. 0 because it is opaque — see below |
| `rt_blood_flow_debug` | `0` | `NOARCH`. Paint the decoded phase instead of the surface |
| `rt_blood_autogoto` | `0` | `NOARCH`. Put the player on a pool on the first frame |

At `relief = 1` the wave normal **is** the surface normal, so `tilt` and
`shimmer` are identically zero and `rt_water_caustic` would be a silent no-op.
The mask fades it against relief so that is visible in the source rather than
mysterious, and hands the animation to the flow:

```glsl
caustic = veins * ( 1 + causticGain * shimmer * (1 - relief) + flowAmt * (2*detail - 1) )
```

## Getting to a pool

`rt_blood_goto` moves the player onto one; `rt_blood_autogoto 1` does it on the
first frame of the map, and every `ab-bloodpool.cmd` arm sets it. This is the
same instrument as `rt_lava_goto` and exists for the same reason: a pool is a
puddle in a corner and every verdict judged from the spawn point is worthless.

**It moves to the first pool it can stand in, not "the first pool, if it can".**
`rt_lava_goto` keys its move off `found == 1`, so a concave first sector — whose
bounding-box centre falls outside itself — makes it print its findings and move
nobody. MAP17's first blood sector is exactly that, so the lava version's shape
reported success and left the player at the spawn point.

## Which maps

153 blood-floor sectors, none panned or scaled. 14 carry `rotationfloor`, all
multiples of 90°, and **all 14 are on MAP34** — so every play map's blood floors
are world-aligned and the baked phase stays registered with the art.

| Map | Sectors | |
|---|---|---|
| MAP17 | 39 | `D64B1_*`, floor z −144..−104. **The one to test on** |
| MAP32 | 12 | `D64B2_*`, floor z −16 — at your feet |
| MAP08 | 9 | z −256, **in pits**. Do not judge here: a pool 256 units below you looks identical whether it works or not — the MAP07 trap from the poison bubbles |
| MAP18 | 9 | |
| MAP21 | 4 | |
| MAP23 | 3 | |
| MAP24 | 1 | |
| MAP34 | — | the fluid sampler, and the only rotated pools |

## Verifying it is live

Five layers — wad → material files → `textures.json` → uniform → shader — and any
one failing silently looks exactly like "the effect is too subtle".

- **The wad loaded:** `adding …/d64r-liquid-art.wad, 5 lumps` in `rt-console.log`.
- **The stylized branch runs on it:** `ab-bloodpool.cmd flagcheck` → the pools
  paint **magenta**. Green means RTGL sees water but the stylized gate rejected
  it; nothing means the primitive never got `RG_MESH_PRIMITIVE_WATER`, i.e. the
  JSON meta never reached it. *This arm also paints every other surface blue* —
  that is the same diagnostic's caustic probe, not a fault.
- **The frames are frozen:** stand still for ~4 s (64 frames at 2 tics). No
  drift, no jump.
- **Relief:** `noflow` vs `off`. `flat` (`rt_heightmap_stren 0`) separates the
  normal map from the parallax.
- **Flow:** `phase` first. Green blobs sliding along each vein mean the bake
  and the plumbing both work and the rest is tuning; flat blue means the
  direction never reached the shader or the detail never crossed
  `framebufAlbedo.a`. Then `fast` — motion too slow to see and motion that is
  not happening are the same picture.
- **Judge it in motion.** A settled screenshot cannot show a travelling pulse,
  and cannot show whether junctions fade cleanly or tear.

## Two things this fixed on the way

**`set_water_meta.py` only ever wrote the build copy of `textures.json`**, and
`build-gzdoom-rt.cmd` stages `Retribution-RT-Materials\rt` over `build\...\rt`
on every build. So every `--apply` reported success and the next build silently
reverted it. That is how frame 01 of **all eight** liquid families kept
`roughnessDefault` 0.8 while frames 02..64 sat at 0.1. It now writes both.

**Blood is exempt from the frame-01 quarantine**, and must stay exempt: this
family has overlays on every one of its 128 frames by construction, so
quarantining frame 01 would take the overlay off exactly one frame in 64 and
recreate the defect that list exists to stop — and would kill the pulse with it,
since the flow phase lives in `_h`.

## Blood projects no caustics

A caustic is light refracted **through** a fluid and focused on what lies beyond
it. Blood is opaque, so it makes none — and it was throwing the same rippling
swimming-pool light onto its own walls as water, which is the loudest single
thing that says "this is water with red paint on it".

The awkward part is that the projected caustics are **receiver-side**: a shading
point fires one probe ray down and asks "is there water below", and the wall has
no idea which liquid it is standing next to. So `probeWaterBelow` now hands the
liquid id back out (`out uint liquidId`) — free, because it already unpacks
`geometryInstances[instanceId].flags` to answer the water question — and the
caustic is scaled by `stylizedLiquidCaustics[liquidId]`.

`rt_blood_caustics` and `rt_nukage_caustics` default to **0**. They scale
`rt_water_caustics`, they do not replace it; 1 restores the old behaviour, which
is what the `caustics` arm does for blood. Water and sludge stay at 1 and are
unchanged.

## The poison art

`screen/poison_texture.png` replaces `D64N1_*` / `D64N2_*` through the same wad
and the same pipeline — crop, min-cut tile, resample, expose — and **nothing
else**: no relief, no flow. It keeps the stylized wave shimmer the other liquids
have, and loses its projected caustics for the same reason blood did. No
overlays are written for it, so `set_water_meta.py`'s frame-01 quarantine still
applies to the nukage families and must.

The reference is a marbled swirl, far brighter than the flat it replaces (lum
p50 0.18 against a mask reference of 0.1), so the exposure step matters more
here than for blood: unexposed, the whole pool would sit at full crest colour.

## Not done

- **Per-liquid wave / roughness / Fresnel** for nukage and sludge. The
  `stylizedLiquid*` vec4s are shaped to take them.
- Bubbles or clots breaking the plane — the poison-spawner retarget.
