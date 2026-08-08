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

### The living body — `rt_ghost_solid` (default 1)

Same treatment, extended to the living frames of **both** monsters: not translucent,
alpha forced to 1.0, alpha-tested. Both halves are required — the `TRANSLUCENT` flag
forces rasterization on its own regardless of alpha, and alpha under 0.98 forces it
regardless of the flag.

The result is what "lit like everything else" actually means: in an unlit room the body
goes black and only the `_e` eye mask emits. **The cost is the see-through look** — a
spectre is now a solid dark sprite. `+rt_ghost_solid 0` restores the rasterized ghost,
and with it the baked-lit appearance.

⚠ **Two other routes to the same goal were tried and rejected — don't retry them:**

1. **Dimming the vertex colour by sector lightlevel.** Cannot work in principle:
   `RsWorld.inl` builds its emissive out of `baseColor()`, so darkening the body darkens
   the eye mask by exactly the same factor. Body and eyes are inseparable from there.
2. **`GLASS | ALPHA_TESTED`.** Traced *and* see-through (`IsRasterized()` exempts
   GLASS/WATER/ACID), so it keeps the ghost look — but it is a refractive material on a
   billboard, which is not the look this mod wants. Rejected 2026-08-08; the same
   approach had already been removed once in `56e9c2ae`.

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