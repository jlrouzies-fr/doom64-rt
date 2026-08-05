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

## ⚠ Regeneration hazards

After running `gen_enemy_eye_emissives.py`:
- Front A–G `_e` PNGs: regenerated correctly (generator creates them)
- Side/rear A–G `_e` PNGs: NOT regenerated (generator skips — no SARG donor for those rotations)
- H-frame `_e` PNGs: NOT regenerated (generator skips H+ frames as death/gib)
- textures.json entries: SURVIVE regeneration (upsert keeps existing entries)

**To restore after regeneration:**
1. Re-run the side/rear transparent `_e` generator (single-pixel → now fully transparent)
2. Re-run the H-frame `_e` generator

Scripts for regeneration are inline in this doc; see commit history for the exact Python.

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