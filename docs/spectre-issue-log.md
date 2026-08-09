# Spectre Rendering — Final Fix

## Problem

64Spectre (SAR2 sprites) rendered inconsistently: front view near-transparent ghost, side/rear views solid dark purple.

## Root Cause (3 compounding issues)

1. **`IsSpectre()` caught SARG sprites** — regular pinkies were mistaken for spectres (`n[3]=='G'` matched SARG attack frames). Fixed: only match `n[3]=='2'` (SAR2).
2. **`_e` PNGs only existed for front rotations** — generator creates eye masks for rotations 1+2A8 only. Side/rear had no `_e` files.
3. **ADDITIVE pipeline trigger depends on `prim.emissive` value, not `_e` content** — `RasterizedDataCollector` promotes TRANSLUCENT→ADDITIVE when `emissive > 0`. The emissive value comes from `TextureMeta::Modify()` which sets `prim.emissive = max(0, emissiveMult)`. Without a textures.json entry, emissive stays at GZDoom's 0.0 → no promotion → pure TRANSLUCENT.

## Render Pipeline

```
DECORATE: 64Spectre → RenderStyle Translucent → A_SetTranslucent(varying)
    ↓
GZDoom:   IsSpectre() → SAR2 only (not SARG)
          → makePrimFlags() → RG_MESH_PRIMITIVE_TRANSLUCENT
          → l_spriteAlpha() → min(actor_alpha, 0.80)  [cap, not floor]
          → primColor.emissive = 0.0  [l_isemis() = false for STYLE_Translucent]
    ↓
RTGL1:    TextureMeta::Modify()
          → prim.emissive = max(0.0f, meta->emissiveMult)  [OVERRIDES GZDoom!]
    ↓
          RasterizedDataCollector::ToPipelineState()
          → if TRANSLUCENT && emissive > 0 → ADDITIVE pipeline
    ↓
          ADDITIVE: sprite RGB adds to background (ghostly wash)
          + emissive texture: _e × emissiveMult (if _e PNG exists)
```

**Key insight:** The ADDITIVE promotion gate is `prim.emissive > 0` (from TextureMeta), NOT whether the `_e` PNG has non-zero pixels. A fully transparent `_e` PNG still works — the emissive value triggers ADDITIVE, and the transparent texture emits nothing visible.

## Solution

### 1. GZDoom engine (`sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp`)

```cpp
// IsSpectre(): only match SAR2, not SARG
if( n[3] == '2' )  // was: n[3] == '2' || n[3] == 'G'
    return true;

// rt_translucent_minalpha: 0.72 → 0.80
```

### 2. Launcher (`tools/launch-retribution-rt.cmd`)

- Removed `+fly`, added `+notarget`

### 3. `_e` PNG strategy

| Rotation | `_e` content | Why |
|---|---|---|
| Front (1, 2A8) | Eye mask from brightmaps (generator) | Red eye glow where visible |
| Side/rear (3A7, 4A6, 5) | Fully transparent PNG | ADDITIVE triggers via emissiveMult, no visible dot |
| Pain H frames (1–5) | H1+H2H8 clone from G-frame eyes; H3H7+H4H6+H5 transparent | Pain state sprites need ADDITIVE too |

**File locations** (all 3 must be kept in sync):
- `rt/mat/` — engine loads from here (`developerMode: false`)
- `rt/mat_dev/` — engine loads from here (`developerMode: true`)
- `Retribution-RT-Materials/rt/mat/` — source of truth (git)

### 4. textures.json — ALL SAR2 rotations with `emissiveMult: 2.0`

All 40 SAR2 sprites (7 living frames A-G × 5 rotations + 5 pain frames H × 5 rotations = 40) have entries in:

| File | Scope |
|---|---|
| `rt/data/textures.json` | Global (1642 entries) |
| `rt/data/scenes/d64rtr_v15_map01/textures.json` | MAP01 gameplay |
| `rt/data/scenes/d64renemyg_map98/textures.json` | Enemy gallery |
| `Retribution-RT-Materials/rt/data/textures_enemy_eyes.json` | Source |
| `Retribution-RT-Materials/rt/data/textures_pinky_eyes.json` | Source (SARG only) |

## 64Spectre DECORATE — sprite usage

```
Spawn:   SAR2 A, B,D                  (walk)
Idle:    SAR2 B, B,B, D, D,D          (breathing opacity pulse)
See:     SAR2 A,A, B,B, C,C, D,D, AABBCCDD  (chase with alpha wave)
Melee:   SAR2 E,F, G                  (bite attack)
Pain:    SAR2 H (×3)                  ← WAS MISSING _e + meta
Death:   SAR2 I,J,K,L,M,N            (despawn fade)
```

All living + pain frames (A–H) need `_e` PNGs + emissiveMult. Death/gib frames (I–N) skipped — they use `A_FadeIn` which handles fading.

## ⚠ Regeneration hazards — RESOLVED (2026-08-08)

The side/rear and H-frame `_e` files used to be hand-made and were destroyed by every
`gen_enemy_eye_emissives.py` run. That whole step is now inside the generator
(`SOFTBLEND_ACTORS`), so a plain re-run reproduces the full 40-file SAR2 set:

- Front A–G: brightmap eye masks cloned from SARG (unchanged)
- Front H (pain): cloned from the same rotation's G-frame mask
- All side/rear rotations: fully transparent `_e`
- Corpse I–N: no `_e`, and emissiveMult explicitly **cleared** (see below)

`rescale_mask()` replaced `Image.resize`: an eye is 4–18 pixels, and NEAREST resampling
of 72x84 → 56x93 misses every one of them and returns an empty mask. That is how
`SAR2H2H8_e.png` went blank the first time this was consolidated.

---

# Round 2 (2026-08-08): the dead spectre glowed, the live one looked baked-lit

Two more defects, both downstream of the same fact: **a spectre is rasterized, and the
rasterizer does not light anything.**

## 1. Dead spectre glowed — `emissiveMult` with no `_e` mask

`SAR2I0`…`SAR2N0` (the six death frames) carried `"emissiveMult": 2` in
`rt/data/textures.json`, but no `SAR2I0_e.png` etc. ever existed. RTGL1's raster shader
falls back to the BASE texture when there is no emissive texture — `RsWorld.inl`:

```glsl
if( emissiveTextureIndex != MATERIAL_NO_TEXTURE ) ldrEmis = baseColor().rgb * emisTex;
else                                              ldrEmis = ldrColor.rgb;   // whole sprite!
ldrEmis *= emissiveMult;
```

So "the eyes glow at 2×" quietly became "**the entire corpse emits at 2× its albedo**"
into `outScreenEmission`. Fixed by clearing emissiveMult on corpse/gib frames — step 4b
of the generator does this for every actor in `SOFTBLEND_ACTORS`.

## 2. Nothing lights a rasterized primitive

`makePrimFlags()` gives a spectre `RG_MESH_PRIMITIVE_TRANSLUCENT`; RTGL1 rasterizes any
translucent primitive (`VulkanDevice.cpp IsRasterized`) instead of tracing it, and
`RsWorld.inl` outputs `vertexColor * texture` with **no lighting term at all**. On top of
that, `forceSpriteUnlitAlbedo` strips the sector lightlevel out of the vertex colour —
correct for a path-traced sprite, but it leaves a rasterized one with nothing to darken
it. Result: full texture brightness in a pitch-dark room.

### The corpse — `rt_spectre_corpse_solid` (default 1)

`IsSpectre()` returns false for SAR2 frames I–N. The corpse becomes an ordinary
alpha-tested sprite at alpha 1.0, clears `MESH_TRANSLUCENT_ALPHA_THRESHOLD`, enters the
BLAS, is path-traced and casts a shadow like every other corpse. DECORATE's Death
sequence ends on `A_SetTranslucent(1.0)`, so a solid corpse is what the actor asks for.

### The living body — solved: `rt_ghost_lightscale` (default 1, engine-side only)

**This is the fix that keeps the see-through look.** It landed after three prior
attempts were tried and rejected — including `rt_illum_volume`, which shipped, looked
wrong in play, and was reverted. That history is preserved below because the reasoning
that killed each one is what points at this one.

The separation of body from eyes happens in **blending**, not in shading. `RsWorld.inl`
writes two colour attachments, and `RasterizerPipelines.cpp` gives them different blend
factors:

| attachment | contents | src factor | dst factor |
|---|---|---|---|
| 0 | `outColor` — the sprite body | `SRC_ALPHA` | `ONE_MINUS_SRC_ALPHA` (or `ONE` if additive) |
| 1 | `outScreenEmission` — the `_e` eye mask | `ONE` | `ONE` |

Attachment 1 **never sees alpha**. So scaling the sprite's vertex alpha dissolves the
body and leaves the eyes at full strength. In a pitch-black room a nightmare imp becomes
a pair of floating eyes, and a spectre — whose `_e` is fully transparent — disappears
outright. That is exactly the requested behaviour, and it needs no shader change, no
RTGL1 rebuild, and no new data.

`GhostLightScale()` in `rt_main.cpp` computes the multiplier for living ghost frames
only (corpses are excluded — they are solid, traced and genuinely lit):

```cpp
const float ll  = clamp( float( rtstate.m_lightlevel ) / 255.f, 0.f, 1.f );
const float lit = sqrt( ll );          // Doom lightlevels read brighter than linear
return 1.f - amount * ( 1.f - lit );   // amount = rt_ghost_lightscale
```

### The idle-vs-active gap — `rt_spectre_alpha` / `rt_nightmareimp_alpha`

`rt_ghost_lightscale` alone left **idle** ghosts still reading as baked-lit while the same
monster looked right once it woke up and charged. It was not a missed code path — the two
states render at different alpha, and the lightscale was correctly scaling a body that was
4× more opaque to begin with. The two monsters had *different* bugs:

**64Spectre** — its DECORATE `Spawn` loop sets alpha once and never lowers it:

```
Spawn:  SAR2 A 0 A_SetTranslucent(1.0, 0)
        SAR2 BD 10 A_Look
        Goto Spawn+1          <- loops HERE, skipping the A_SetTranslucent line
See:    ... A_SetTranslucent(0.75) -> 0.50 -> 0.25 -> 0.20
```

so idle sat at `1.0` and chasing at `0.20`. The old `min(a, rt_translucent_minalpha)` only
clipped the top, landing idle at **0.80**. `rt_spectre_alpha` (default `0.20`, the value the
actor's own active states use) now *forces* one value across every state — which is what
the old comment there already claimed to do but `min()` never did. Chasing spectres are
unchanged. Cost: the `Idle` state's `0.25 → 1.0` alpha pulse is flattened; under PT that
pulse reads as the ghost glowing on and off rather than as a shimmer.

**64NightmareImp** — no idle/active discrepancy at all: it declares a flat `Alpha 0.60` and
never calls `A_SetTranslucent`. Its bug was the **opposite** one — the
`max(a, rt_translucent_minalpha)` *floor* for soft-blend sprites was raising it from the
authored `0.60` to `0.80`, i.e. making it more opaque than the actor asks for. Living
ghosts now bypass that floor entirely. `rt_nightmareimp_alpha` was briefly left at the
authored `0.60` once the floor was gone, then tuned down to **`0.35`** by eye — deliberately
below what DECORATE asks for, on the same reasoning that settled the spectre (see the caveat
below). Still well above the spectre's `0.20`: a nightmare imp is a semi-transparent monster,
not an invisible one.

### ⚠ A living ghost must be TRANSLUCENT, never ALPHA_TESTED

`makePrimFlags()` used to send only `IsSpectre()` sprites down the rasterized
`TRANSLUCENT` path and drop **64NightmareImp into the `ALPHA_TESTED` cutout branch**. That
is wrong for a `RenderStyle Translucent, Alpha 0.60` monster, and it is a trap, because
`RsWorld.inl` ends with:

```glsl
if( alphaTest != 0 ) { if( outColor.a < ALPHA_THRESHOLD ) discard; }   // 0.5
```

`discard` kills the **whole fragment — including `outScreenEmission`**. So below alpha 0.5
the emissive eyes die *with* the body, and the monster vanishes completely rather than
fading to a pair of floating eyes. Everything the alpha work was built on stops applying.

This is also the real reason the old `max(a, rt_translucent_minalpha)` floor existed: 0.80
kept these sprites above the 0.5 threshold. Its job was clearing the discard, not looks.
Dropping the floor to the authored 0.60 left almost no margin — and since
`GhostLightScale()` multiplies on top, any room dimming past ~0.83× would have popped the
imp out entirely. At `rt_nightmareimp_alpha 0.35` it was invisible everywhere.

`IsLivingGhost()` now routes every living soft-blend monster down the spectre's
`TRANSLUCENT` path with `alphaTest = false`. With no threshold to fall off, the body fades
smoothly to nothing while the eyes — on the `ONE/ONE` attachment — are never discarded at
any alpha. Corpses and anything under `rt_ghost_solid` are excluded and stay solid
alpha-tested cutouts.

⚠ **Caveat on `rt_ghost_lightscale`'s signal, recorded because it may resurface.**
`Sector->GetSpriteLight()` is the map-authored sector lightlevel, which in this project is
deliberately decoupled from actual RT brightness — the same decoupling `forceWorldWhiteRgb`
exists to enforce, and the launcher runs `rt_ceiling_lamps 0 / rt_sector_lights 0` so room
brightness comes from emissive textures and placed lights, not lightlevel. A sector can read
`lightlevel 200` while being pitch black under RT. In practice this stopped mattering once
the alpha gap was closed: at 0.20/0.35 the ghosts are faint enough that imperfect light
tracking is not visible. If it ever does resurface, the fix is *not* the fog froxel
(see above) — it would need a real surface-irradiance probe.

`GhostLightScale()` is applied in `l_spriteAlpha()` **after** the alpha selection above and
after the `rt_translucent_minalpha` floor/cap —
those pin how see-through the ghost is at full light; this then fades that whole look out
with the room. Folding it in earlier would let `minalpha` clamp the darkness back off.

⚠ **`m_lightlevel`, not `m_sectorLightLevel`.** These are deliberately separate fields
(see the comment on `push_sectorlight` in `rt_state.h`). `m_sectorLightLevel` is only ever
pushed from `hw_walls.cpp` / `hw_flats.cpp` — on a sprite it is stale, and using it here
would have read as a permanently pitch-black room and erased every ghost everywhere.
`m_lightlevel` is the sprite-only one, set in `hw_sprites.cpp` from
`actor->Sector->GetSpriteLight()`, defaulting to 255.

This is **static sector light only** — the flashlight and muzzle flashes do not brighten
the ghost back up. That is deliberate, and it is precisely what went wrong with the
illumination volume below.

### Rejected: `rt_illum_volume` (shipped 2026-08-08, reverted 2026-08-09)

`RsWorld.inl` has a branch that looks purpose-built for this problem:

```glsl
if( globalUniform.illumVolumeEnable != 0 ) {
    vec3 illum = textureLod( g_illuminationVolume_Sampler, sp, 0.0 ).rgb;
    outColor.rgb *= illum;                                    // body — darkens with the room
} else {
    outColor.rgb *= max( vec3( 1 ), tonemapping.avgLuminance ); // old behaviour — can only brighten
}
// ... computed AFTER the branch above, from baseColor() — never touched by illum:
ldrEmis = ... ;             // eyes (_e mask)
outScreenEmission = ldrEmis;
```

`max(vec3(1), avgLuminance)` is a floor, not a light response — it can raise a dim
sprite up to scene average brightness but can never darken one, which is the entire
mechanism behind "baked-lit in the dark." The `illumVolumeEnable` branch instead samples
`g_illuminationVolume` — the same froxel grid `RtVolumetric.rgen` already fills every
frame (`rt_volume_type` defaults to 1, unmodified by the launcher, so this data was being
computed and thrown away the whole time) — and multiplies only the body. `ldrEmis` is
computed from `baseColor()` *after* this multiply, so the eyes never see it.

**Why it was reverted.** The thing it samples is *not surface irradiance*.
`RtVolumetric.rgen` writes `g_illuminationVolume` from the same froxel pass that feeds
volumetric **fog**: a coarse 3D grid, temporally blended at `mix(prev, cur, 0.05)`
(~20-frame lag), storing **absolute, unnormalized** radiance. Every artifact followed
directly from that:

- a muzzle flash or the flashlight lights up whole froxel **cells**, so the sprite reads
  foggy, fuzzy and haloed — you are literally seeing the fog grid
- the radiance is unnormalized and exceeds 1 under any real light, so the
  additive-blended body **brightens** until it stops looking see-through — "they are not
  transparent when direct light is cast on them"
- the 0.05 temporal blend adds visible lag
- `illumVolumeEnable` is a **global** switch in `RsWorld.inl`, so it hit every particle
  and additive FX in the game, not just the two monsters

Reported in play as "when those happen it's like there is fog around" — correct, and
correctly diagnosed by the user as a workaround rather than a fix.

`rt_illum_volume` now defaults to `0` and the launcher pins it off. The RTGL1 build
changes below were **kept** — they are inert at runtime while the cvar is 0, and they
cost a full DLL rebuild to redo if the path is ever worth re-testing.

**It was compiled out.** `ILLUMINATION_VOLUME` is a build-time constant, `0` upstream, in
two files that must agree (`Volumetric.cpp` has a `static_assert` enforcing it):

- `deps/RTGL/Source/Volumetric.h` → `#define ILLUMINATION_VOLUME_ 0` (gates the C++:
  the illumination image, its descriptor bindings, and the fill/read calls in
  `Volumetric.cpp`)
- `deps/RTGL/Source/Generated/GenerateShaderCommon.py` → `"ILLUMINATION_VOLUME": 0`
  (gates the GLSL side via the generated `ShaderCommonC.h` / `ShaderCommonGLSL.h`,
  regenerated by `GenerateShaders.py -g`, which `tools/build-rtgl.cmd` already runs)

Both flipped to `1`. **A second, separate gap surfaced on the first build**: the two
descriptor-binding slots the feature needs, `BINDING_VOLUMETRIC_ILLUMINATION` /
`_SAMPLER`, were *commented out* in the same dict, right after the live volumetric
bindings — `Volumetric.cpp`'s `#if ILLUMINATION_VOLUME` blocks reference them by name, so
turning on the top-level flag without them is a straight compile failure (`undeclared
identifier`, both in the GLSL shader compile and the C++ compile). Uncommented; slots 3
and 4 were already reserved for them and nothing else claims those numbers. This
confirms the feature was fully authored upstream and deliberately shipped disabled —
consistent with the DLSS-RR discovery earlier in this project (see
`docs/rayreconstruction/`).

The engine side is `rt_illum_volume` →
`RgDrawFrameVolumetricParams::useIlluminationVolume`, gated additionally on
`rt_volume_type != 0` (no point enabling illum sampling when there's no volumetric pass
filling it). Requires a rebuilt `RTGL1.dll` — on the old one this cvar is inert, RTGL1
silently ignores the field.

### Other rejected routes — don't retry

1. **Dimming the vertex colour by sector lightlevel.** Cannot work in principle:
   `RsWorld.inl` builds its emissive out of `baseColor()`, so darkening the body darkens
   the eye mask by exactly the same factor. Body and eyes are inseparable *in that
   channel* — the separation exists one stage later, in the per-attachment blend
   factors, which is what `rt_ghost_lightscale` uses.
2. **`GLASS | ALPHA_TESTED`.** Traced *and* see-through (`IsRasterized()` exempts
   GLASS/WATER/ACID), so it keeps the ghost look — but it is a refractive material on a
   billboard, which is not the look this mod wants. Rejected 2026-08-08; the same
   approach had already been removed once in `56e9c2ae`.
3. **`rt_ghost_solid` — give up transparency, get real lighting.** Works, and is still
   there as a fallback (default `0`), but the solid dark silhouette breaks the original
   look. Rejected by the user 2026-08-08: *"this is sadly a no go, it break the original
   look."*

Corpses are unaffected by any of this: `rt_spectre_corpse_solid` stays on, since a dead
spectre/imp is meant to read as a solid body per its own Death sequence — see above.

### ⚠ Going solid makes every living `_e` load-bearing

`HitInfo.inl` has the **same no-`_e` fallback as the rasterizer**:

```glsl
if( tr.emissiveTexture != MATERIAL_NO_TEXTURE ) emission = <sample _e>;
else                                            emission = h.albedo * tr.emissiveMult;
```

So a traced sprite carrying `emissiveMult` with no `_e` file glows over its whole body —
exactly the bug that made the dead spectre glow, just on the other pipeline. Every living
SAR2 and TRO2 rotation has an `_e` (eyes on the front, fully transparent elsewhere) and
corpse frames carry no `emissiveMult`, so the set is closed. **Re-run the coverage check
after any change to the generator:**

```python
bad = [n for n, e in metas.items()
       if n[:4] in ("SAR2", "TRO2") and e.get("emissiveMult", 0) > 0
       and not (MAT / f"{n}_e.png").exists()]   # must be empty
```

## 3. `patch_global()` had been appending duplicates for months

Its updater was a single-line regex, but most of `rt/data/textures.json` is
pretty-printed across four lines — so every "update" missed and fell through to the
append branch. The file had **231 duplicated textureNames**. Nothing looked broken only
because RTGL1 loads the array with `insert_or_assign` (`TextureMeta.cpp:115`), i.e. LAST
occurrence wins — meaning any entry hand-edited near the top of that file was dead
weight, silently overridden from the bottom. `patch_global()` now parses the JSON and
collapses duplicates last-wins (semantics-preserving: 1643 names before and after, 0
added, 0 removed, only the intended 48 changed).

---

# 64NightmareImp (TRO2) — same bug, same fix

`ACTOR 64NightmareImp` is `RenderStyle Translucent, Alpha 0.60`, so it hits the identical
pipeline split: a rotation WITH a textures.json entry gets promoted to ADDITIVE, a
rotation WITHOUT one stays plain translucent. Brightmaps only ever exist for rotations 1
and 2A8, so the imp was ghostly-additive from the front and a flat solid body from the
side and rear.

- All 55 living sprites (frames A–K × 5 rotations) now carry `emissiveMult: 2.0`.
- Death/gib frames L0–X0 carry a bare entry with no emissiveMult.
- Front rotations 1 and 2A8 of frames A–G keep their existing TROO-cloned eye masks,
  byte-for-byte unchanged.
- **Every other living rotation gets a fully transparent `_e`** — side, rear and the
  pain/missile frames. No eyes are visible from the side or the back, exactly as on the
  spectre. The `_e` exists only so the rotation is on the same pipeline as the front.

An earlier pass derived cyan eye masks from the imp's own art and lit the 3/4 views. That
was rolled back — side/rear are meant to show nothing.

### Eye colour and fireball colour

The nightmare imp is the one monster that isn't red-eyed. Its mask **geometry** is still
the TROO donor clone; only the colour changed, via `EYE_COLOR` in the generator
(`recolor_mask()` recovers each texel's intensity as `max(r,g,b)/255` — exact for a
RED-painted source — and repaints it). Blue-violet `(120,100,255)`, chosen to match its
own art (eyes are a cold blue `(90,140,189)`) and its violet fireball.

Its fireball light was separately wrong: `gen_fx_emissives.py` had `BAL3` pinned to
`ff5533`, so a violet projectile — brightest texels `(88,48,184)`, peak-normalizing to
~`7a42ff` — lit the room orange. Now `9a5cff`, lifted slightly off the raw art so lit
surfaces read violet rather than near-black blue. `BAL2` beside it was already purple,
which is what made the miss visible.

## SARG (regular pinky) — unaffected

- `IsSpectre()` no longer matches SARG
- SARG textures.json: front rotations only (1, 2A8) with `emissiveMult: 2.0`
- SARG `_e` PNGs: eye masks from brightmaps (front only)
- Result: regular pinky uses its original eye-glow path, never enters spectre ADDITIVE

## Commits

| Repo | Branch | Commit |
|---|---|---|
| `doom64-rt` | `rayreconstruction` | `547891f` Spectre: side/rear _e transparent, pain H frames |
| `gzdoom-rt` | `doom64-rt` | `cfdb5002a` Fix IsSpectre(): SARG is regular pinky, not spectre |
| `RTGL` | `doom64-rt` | `d50bbcb` (existing, no changes needed) |