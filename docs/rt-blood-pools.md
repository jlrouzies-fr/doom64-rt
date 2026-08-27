# Coagulated blood pools (and the poison / sludge art)

Blood that reads as a thick fluid with a skin on it: dark plates of clotted
crust, liquid veins running between them in real relief, and liquid that
visibly **moves along** those veins.

Art built by `tools/gen_liquid_art.py` into
`Doom64-Retribution/d64r-liquid-art.wad` — which also carries the poison and
sludge replacements, see the end. A/B it with `tools\ab-bloodpool.cmd <arm> [map]`,
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
the shader. Here the motion becomes the flow map.

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

**The advection** (`HitInfo.inl`, primary pass — where the texcoords are): the
noise (the water normal map — tileable, already bound, `getLavaHeat` uses it as
a field) is sampled in a **vein-aligned frame**: `u = dot(uv, dir) * scale -
time * speed` runs along the channel and scrolls forever; `v = dot(uv, perp) *
scale * aspect` runs across it at `aspect`× the frequency. That stretches the
noise into elongated streaks sliding lengthwise — the shape that reads as
liquid moving. Version two advected round blobs from base UV with a ping-pong
cross-fade, and isotropic blobs at vein scale read as shimmer; no ping-pong is
needed here at all, because scrolling a wrapping texture's own coordinate never
resets. Where the direction varies along a run the frame shears the noise
slightly — fine, liquid shears. The result crosses to the shading pass in
`framebufAlbedo.a`.

**The modulation** (`getStylizedWaterAlbedo`): `veins * (1 + flow * (2d - 1))`,
so the sliding detail brightens and darkens the vein both ways — blobs of
brighter and darker liquid moving down a static channel.

**A vector, never an angle.** At a junction two runs disagree; an angle puts
0.98 next to 0.02 and bilinear filtering tears a seam. A vector merely shrinks
toward zero and the shader treats short as still (`length > 0.15`). And exactly
0 in the output means "no flow here", so the valid range is nudged off zero
(`* 0.998 + 0.001`).

**Legibility depends on shape.** Round detail at vein scale reads as shimmer no
matter how fast it moves; streaks aligned with the channel read as flow even
slowly. `rt_blood_flow_aspect` is that knob (the `blobs` arm is the round
version, kept to show why), and `coarse`/`fine` bracket the streak length.

## Cvars

| cvar | default | |
|---|---|---|
| `rt_blood_relief` | `1.0` | how much of the authored `_n` survives vs the water wave. 0 = the old ripple. Rides on `rt_normalmap_stren`; the depth comes from `_h` parallax, which `rt_heightmap_stren` scales |
| `rt_blood_flow` | `1.0` | depth of the flow-map modulation on the vein mask. 0 = still. The vein mask clamps at 1, so on saturated veins the DARK half of the modulation is what shows: dark blobs of liquid sliding down the channel |
| `rt_blood_flow_speed` | `0.5` | detail tiles scrolled per second along the vein |
| `rt_blood_flow_scale` | `6.0` | detail tiles per 64-unit tile, along the vein. Higher = finer streaks |
| `rt_blood_flow_aspect` | `3.0` | across-vein frequency multiplier: stretches the noise into lengthwise streaks. 1 = round blobs, which read as shimmer |
| `rt_nukage_caustics` | `0.0` | same as `rt_blood_caustics`, for poison |
| `rt_sludge_caustics` | `0.0` | same as `rt_blood_caustics`, for sludge |
| `rt_sludge_relief` | `1.0` | as `rt_blood_relief`, but the height comes from the art's full luminance range, not the vein mask |
| `rt_sludge_refl` | `0.0` | how much of the stylized water MIRROR sludge keeps. 1 = the mirror water gets. **0 = no mirror and no checkerboard split**: full-res surface, glossy specular sheen |
| `rt_blood_refl` | `0.3` | the same knob for BLOOD, added 2026-08-26. **Was 1.0 (the full water mirror) for as long as blood pools existed.** 0 = no mirror and **no checkerboard split** — which matters more on blood than on sludge, because blood carries an authored `_n` at `rt_blood_relief 1` and the split is what makes a high-contrast normal crawl under a moving light. 0.3 is above zero, so the split is still on |
| `rt_nukage_refl` | `0.5` | the same knob for POISON, added 2026-08-26 (was 1.0). The highest of the three on purpose: nukage is the one liquid meant to look thin and chemical rather than congealed, and the only one that still **keeps the water wave** — there is no `rt_nukage_relief` and no authored `_n` for `D64N*`. Half a mirror on a moving surface is the read it is tuned for. No `rt_nukage_rough`: with no authored normal there is nothing for a separate roughness to scatter |
| `rt_blood_rough` | `0.0` | blood surface roughness. `<= 0` = use `rt_water_rough` (0.1, a near-mirror), which is what blood gets today. Raise it alongside `rt_blood_refl 0` — a no-mirror pool at 0.1 is still a wet plastic sheet |
| `rt_liquid_checkerboard` | `1` | **Console only**, not in the Quality menu. 0 forces the no-split path for all four liquids. Archived, unpinned |
| `rt_sludge_rough` | `0.8` | sludge surface roughness. `<= 0` = use `rt_water_rough` (0.1) |
| `rt_sludge_autogoto` | `0` | `NOARCH`. As `rt_blood_autogoto`; CCMD is `rt_sludge_goto` |
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

## Why none of these persist — and why that is the fix (2026-08-25)

Every cvar in the table above is `RT_CVAR_NOARCH`. It is **never written to
`gzdoom-rt2.ini`** and comes back at its compiled default on every launch. That
is deliberate, and it came out of a player report of the animated water wave on
the blood, poison and sludge flats in a released build.

**The wave is global; the relief is the only thing that removes it.**
`getNormal()` swaps `getWaterNormal()` in for *any* water-flagged primitive —
the `hasNormalMap` flag is hardcoded false at the primary hit — and
`stylizedLiquidRelief[liquidId]` mixes it back out afterwards. So on a blood or
sludge bed, `rt_blood_relief` / `rt_sludge_relief` are not a look knob among
others: they are the entire difference between a coagulated pool and water with
red paint on it.

Before this, that difference was held up by one thing — `+exec d64rt-pins.cfg`
on the launcher line. Three ways it came off, all silent:

| how | what the player sees |
|---|---|
| a `0` archived in their `gzdoom-rt2.ini` from any earlier build or session | the ripple, and the pin never gets a chance |
| launching `gzdoom.exe` without the launcher | the ripple, and no pins at all |
| a release built from a **stale exe** — the pin names a cvar it predates | one `"Unknown command"` in the boot spam, then the ripple |

### NOARCH alone was not enough, and that is the load-bearing part

Taking a cvar off the ini stops it being **written**. It does not stop it being
**read**. `FGameConfigFile::ReadCVars` walks every key in the section and applies
it by name — it never looks at `CVAR_ARCHIVE` — so a line left by an older build
kept setting the cvar, and because nothing rewrites that key any more, the stale
line survived every clean exit that would otherwise have refreshed it. A NOARCH
conversion on its own would have protected only fresh installs.

That was not hypothetical: `rt_clouds_volumetric` has been `RT_CVAR_NOARCH` for a
while and a stale archived line for it was **still in this machine's config and
still being applied**. Nobody had noticed.

So `gameconfigfile.cpp` now skips a key whose cvar is not archived. It is safe by
construction — a key can only be in the config because some build archived it,
and auto-created cvars take the branch above it and are given `CVAR_ARCHIVE` —
and it is self-cleaning: `ClearCurrentSection()` + `C_ArchiveCVars()` drop the
orphaned line on the next clean exit. Measured: poisoning the ini with
`rt_blood_relief=0`, `rt_sludge_relief=0`, `rt_water_wavestren=3` and launching
**with no pins at all** still logs `relief …/1.00/1.00` and `wave=0.40@0.20`, and
one clean exit removes all 58 stale keys.

With that in place NOARCH closes every route above. The pins stay, as a
**restatement** of the shipped values rather than an override — `check_pins.py` blesses a NOARCH pinned
to its own default and errors on one pinned to anything else, so the pins file is
now a guard instead of a second source of truth. Keep them in step:

    python tools/check_pins.py rt_blood      # and rt_sludge / rt_water / rt_nukage / rt_liquid

The third is a packaging problem, and `tools/package_release.py` now refuses it:
`check_engine_fresh()` (binaries not older than their own source tree),
`check_pins_lockstep()` (no drift, no orphan pins) and `check_liquid_relief()`
(64 `_n`/`_h`/`_orm` per liquid family actually present in `rt/mat_dev`, which is
the one path the art reaches a release by). They run before anything is copied,
alongside `check_mods_match_launcher()`.

**And every player's log now says what the shader got.** `RT_ReportLiquidConfig()`
prints one line per level load at `RT_DiagPrintLevel()`, so it is in
`rt-console.log` — which the release launcher already writes — without painting
over the game:

    RT liquid: style=1 liquids=1 split=1 wave=0.40@0.20 | relief w/n/s/b 0.00/0.00/1.00/1.00  refl 1.00/1.00/0.00/1.00  flow(blood) 1.00

`relief …/1.00/1.00` is the confirmation. Anything else on the sludge or blood
slot is the bug, and the same line tells you whether it is the cvar or the art.
Note the first two slots are always `0.00`: water and nukage take the wave, and
nukage does so on purpose (see **Not done**).

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
- **Flow:** `phase` first, and know the instrument: the debug paints
  **R = fract(time/4)** (a heartbeat -- if it does not visibly change second to
  second, the time uniform is dead), **G = the advected detail** (blobs sliding
  along the veins = the flow map is live), **B = the speed the shader sees**
  (near-black at shipping 0.5; a test pin of 40 turns the veins cyan). This
  three-channel split exists because "speed never arrived", "time is frozen"
  and "motion too subtle" produced the same picture and cost a session to tell
  apart. Two traps from that session, paid for once:
  * **Validate the mask against the paint before trusting a null result.** Four
    consecutive measurements "proved" the flow frozen; three of them had masks
    that matched dark scenery instead of the debug paint, and the conclusion
    flipped when the mask was checked against an actual frame.
  * **Debug paint rides screen emission through exposure and bloom** --
    absolute channel values are meaningless in a capture; only deltas and
    ratios survive the tonemapper.
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
is what the `caustics` arm does for blood. **Water is now the only liquid that
projects caustics**; nukage, sludge and blood all wear opaque reference art.

## Sludge: a mud bed, not a pool

Sludge got the same art treatment as poison, then two things poison did not:
**relief**, and **its water reflection taken away**. Those are the two halves of
"mud", and either one alone still reads as a liquid.

**The height cannot come from the vein mask.** Blood's does, and that works
because blood's structure *is* the vein network — a near-binary thing, plates
with channels cut through them. Sludge's exposed art puts 90% of its texels
above the mask's clip point, so a mask-derived height is a flat plateau with a
few dents in it. Its structure is in the **full luminance range** instead:
lumps, rims, pits, crust speckle. `height_src="luma"` in `gen_liquid_art.py`
range-stretches the tile's luminance between its 2nd and 98th percentiles and
uses that directly, bright = high — these references are painted with implied
top-light, so luminance *is* the photometric height approximation, and reading
the dark lumps as high instead would turn every raised rim into a trench.

Two knock-ons, both of which cost a round to find:

- **`relief()`'s blur is wrong for a luminance height.** It smooths at radius 2
  twice, which is right for a clipped mask (effectively binary, stepped normals
  otherwise) and destroys exactly the fine crust speckle that is the reason to
  use luminance at all. The first sludge bake came back as soft rolling humps
  with no texture on them. `relief_smooth=1`, one pass.
- **`np.gradient` does not wrap.** Invisible at blood's `relief_strength`
  0.045; a visible ridge down the tile seam at sludge's 0.085.

### The height map is sampled at LOD 0 — keep it low-frequency

Worth knowing for **any** parallax material, not just sludge. The two relief
maps go through completely different machinery:

| | how it is sampled | |
|---|---|---|
| `_n` | `getTextureSampleGrad(normalTexture, uv, dTdx, dTdy)` | ray-cone derivatives → picks a **mip**, filters. Mips *are* generated for PNG overlays (`TextureManager.cpp` sets `useMipmaps` for everything but `vx_`) |
| `_h` | `sampleHeightMap()` = `textureLod(heightTexture, uv, 0)` | **LOD 0, always. No mips, no derivatives** — and `parallaxTexCoords` marches it 10 times plus 4 binary-search steps |

So high-frequency content in the *height* map is sampled unfiltered at full
resolution however far away the surface is. Once a screen pixel covers more than
a texel, each pixel's march lands on uncorrelated texels.

The fix is a split, not a compromise: **the normal map keeps every bit of crust
speckle** (it can be filtered) **and the height map carries only the big lumps
and hollows** (`parallax_smooth=4`). Measure it rather than eyeballing —
`gen_liquid_art.py` prints the RMS of the wrapping laplacian of both:

```
blood    high-freq: normal src 0.0200, PARALLAX map 0.0200
sludge   high-freq: normal src 0.0971, PARALLAX map 0.0056
```

Blood's 0.0200 is the known-stable ceiling. Sludge's normal now carries ~5x that
detail while its parallax map sits ~3.5x *below* it.

**This was NOT the cause of the flashlight bug below, though it was the first
diagnosis.** `rt_heightmap_stren 0` leaves that symptom completely unchanged, so
parallax is ruled out. The split above is still correct engineering — it is just
not that bug. Keep the two straight.

### Unstable shadows under the flashlight — the checkerboard

With the flashlight on a sludge bed, bump-like shadows appeared **while moving**
and vanished when the player stopped. Bisected with `tools\ab-sludge.cmd`:

| arm | result | conclusion |
|---|---|---|
| `flat` (`rt_heightmap_stren 0`) | unchanged | not parallax |
| `nodlss` (`rt_upscale_dlss 0`) | unchanged | not the upscaler |
| `nomaps` (heightmap **and** normalmap 0) | **clean** | the normal map is the *carrier* |
| `softnormal` (`rt_normalmap_stren 0.4`) | halved | it scales with normal AMPLITUDE |
| `denoised` (`rt_debug_show 32`) | clearly visible | it is in the direct diffuse |
| high-frequency shelf on the bake | **unchanged** | it is not the bake's frequency content |

Three diagnoses died on the way — LOD-0 height sampling, missing normal mips,
and the normal map's top octave — and each was a real fact about the engine
that was not this bug. The shelf stays (the budget it enforces is right), but
it did not fix anything.

**The reading that survives all six rows.** Every denoiser path converges to
the true per-pixel signal at rest, so *if the surface is flat at rest, flat is
the correct answer*, and whatever appears in motion is **added by something
that only acts in motion**. The bake cannot be it: a normal map sets amplitude,
which explains `softnormal` scaling without being the source.

What acts only in motion and is unique to this surface? **The stylized branch
checkerboards.** The lit liquid is shaded on odd screen columns only; even
columns carry the mirror ray, and `CmCheckerboard` rebuilds each missing half as
a 4-neighbour average, with the denoiser reprojecting history in that
half-resolution space. Stock water has a smooth wave normal, so RTGL never had
to notice. On a high-contrast authored normal, every mud texel alternates
between "shaded directly" and "averaged from its neighbours" as it crosses
columns while the camera moves — a per-texel contrast pulse that scales with
slope amplitude, survives the denoiser, ignores parallax and the upscaler, lives
in direct diffuse, and freezes into a stable pattern the moment the camera
stops. Blood goes through the same split; at `relief_strength` 0.045 the
neighbour contrast is too small to see.

**The fix: an opaque bed does not split.** `stylizedLiquidRefl[id] == 0` (which
is what `rt_sludge_refl` now ships at) takes the whole surface down a no-split
path: every pixel shades the surface at full resolution, no mirror ray, no
checkerboard resolve (`framebufThroughput.a = -1`), and the wet sheen is the
standard glossy specular off `rt_sludge_rough` — which is the lighter, dedicated
reflection a mud bed wanted in the first place. With no flow the surface is also
marked non-reactive to the upscaler, like any other static opaque surface.

`tools\ab-sludge.cmd split` is the before-picture: `rt_sludge_refl 0.12`, the dim
mirror *with* the checkerboard, i.e. the build that had the bug.

`rt_liquid_checkerboard 0` forces the same no-split path for all four liquids,
water included. It is **console only and deliberately not in the Quality menu**:
what it trades away is the reflection that sells *water*, and a player meeting
it in an options list has no way to know that. Sludge needs nothing from it —
`rt_sludge_refl 0` already takes the mud bed down the full-res path on its own.

Worth being precise about what "no split" costs, because it is less than it
sounds. The checkerboard exists because the G-buffer holds **one surface per
pixel**, and a mirror needs a second one: RTGL's answer is to give each half the
pixels and blend them with `F`. Drop the split and the surface still reflects —
it goes through the standard path, which does direct specular (the flashlight
sheen) and *indirect* specular, where the GI bounce samples the GGX lobe around
the reflection direction. So what is actually traded is a clean deterministic
mirror ray for a denoised stochastic glossy one. At mud's roughness 0.8 that is
the physically right model anyway; at water's 0.1 it is sharper but noisier.

**The reflection is the other half.** With `relief = 1` the wave normal is gone,
so `tilt`, `shimmer` and `stylizedWaterCaustic` all collapse to zero — that part
is free. What survives is the *mirror*: `F`, the remapped Schlick, and the
`reflect()` ray that goes with it. A mirror is what sells water, and on an
opaque bed it is the loudest single thing saying "this is water with brown paint
on it". Two new per-liquid vec4s, shaped exactly like `stylizedLiquidRelief`:

- `stylizedLiquidRefl[id]` scales `F`. Scaling **`F` itself** rather than the
  reflection ray's throughput is deliberate: the checkerboard resolves to
  `F * reflection + (1 - F) * surface`, so light taken off the reflection comes
  straight back to the diffuse surface instead of vanishing, and the bed does
  not go dark as it stops reflecting.
  **Exactly 0 means no mirror ray and no split at all** — see the flashlight
  section above for why that matters beyond the look.
- `stylizedLiquidRough[id]` overrides `stylizedWaterRoughness`, with `<= 0`
  meaning "keep the global" so no other liquid changes. **This does not blur the
  reflection** — the reflection ray is a mirror off `shadeNormal` either way.
  What actually scatters it is the relief normal. The roughness is what the
  denoiser and later bounces see, and it is what stops a rough surface being
  resolved as a sharp one. The two are meant to be used together.

`rt_sludge_crest` was also retuned down from `255,204,115` to `120,78,38`
(and the tint to `9,3,1`) for the reason the art section below gives: the
pale tan was calibrated against the old, dimmer flat and made the bed read
as light sand.

A/B it with `tools\ab-sludge.cmd <arm> [map]`, default MAP12. **Only MAP12 (6
sectors) and MAP34 (the fluid sampler) have sludge floors in the whole game**,
which is why every arm sets `rt_sludge_autogoto 1`. `mirror` is the arm that
answers "was the reflection really the problem"; `norelief` answers "was the
relief".

## The poison and sludge art

`screen/poison_texture.png` replaces `D64N1_*` / `D64N2_*` and
`screen/sludge_texture.png` replaces `D64S1_*` / `D64S2_*`, both through the
same wad and the same pipeline — crop, min-cut tile, resample, expose — and
**nothing else at the time**: no relief, no flow, and both lost their projected
caustics for the same reason blood did.

That sentence is now only true of **poison**. Sludge acquired its own relief in
the same pass that made the mud beds (`rt_sludge_relief`, 64 `_n`/`_h`/`_orm`
per family), which is why `set_water_meta.py`'s frame-01 quarantine exempts
`D64S1_`/`D64S2_` alongside the blood families — for a liquid whose look IS the
relief, losing frame 01's `_n` puts the water ripple back for two tics a cycle.
Poison is not exempt, because poison has no relief to lose.

Both references are far brighter than the flats they replace (poison lum p50
0.18, sludge 0.15, against a mask reference of 0.1), so the exposure step
matters more here than for blood: unexposed, the whole pool would sit at full
crest colour.

(Sludge's relief and reflection are covered above; this section is about the
art step the three share.)

**Their crest colours were calibrated against the old, dimmer art.** After the
poison swap `rt_nukage_crest` had to come down from `153,255,115` to
`50,150,50` and `rt_nukage_tint` from `2,15,4` to `1,5,1`, because the exposed
art drives the vein mask to a ~0.5 mean and the surface sits half-way to crest
everywhere. Sludge had the same problem and got the same correction: `rt_sludge_crest`
`255,204,115` -> `120,78,38`, tint `15,9,2` -> `9,3,1`, which puts the average
surface at an R:G:B of 1 : 0.61 : 0.29 — brown rather than sand. The crest
dominates wherever the mask is high, so the tint is mostly what sets how dark
and how warm the *hollows* go.

## The crest colours also colour the impact splash (2026-08-25)

`rt_water_crest`, `rt_nukage_crest`, `rt_sludge_crest` and `rt_blood_crest` are no longer
only a surface colour: a hitscan into a pool now throws droplets in the same value
(`docs/rt-impact-fx.md` 2.4). Taking the CREST rather than the flat's own average is
deliberate -- the shader repaints the surface from tint to crest, so the source art is not
what the player sees, and a droplet sampled from it would not match the pool it came out of.

Consequence worth knowing before the next retune: **moving a crest now moves two things.**
That is the intent -- they should never disagree -- but a crest chosen purely for how a pool
reads at a distance is also choosing how its splash reads at arm's length.

## Not done

- **Nukage — a decision, not an oversight (2026-08-25).** Poison is the only
  liquid still taking the water wave, the full water reflection and no relief,
  and it ships that way on purpose. `stylizedLiquidRelief[1]` is a hardcoded
  `0.f` in `rt_main.cpp`, there is **no `rt_nukage_relief` cvar**, and
  `rt/mat` holds **0** `_n` for `D64N*` against 64 each for `D64B1/B2/S1/S2`.
  Closing it is not a cvar: it needs 128 authored relief maps from
  `gen_liquid_art.py`, a wired index 1, a pin, and a `D64N1_`/`D64N2_` entry in
  `set_water_meta.py`'s `_RELIEF_FAMILIES`. Roughness and Fresnel already exist
  per liquid (`stylizedLiquidRough` / `stylizedLiquidRefl`) and the relief array
  is already shaped for it, so the wave is the only piece left.

  Until then: **a report of "the wave is on the poison" is the shipped
  behaviour**, and only the same report about BLOOD or SLUDGE is a bug.
- Bubbles or clots breaking the plane — the poison-spawner retarget.
