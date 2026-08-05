# Spectre Rendering Investigation

## Overview

The 64Spectre (SAR2 sprite) in Retribution needs a consistent see-through ghostly look from all viewing angles. Currently the front view renders differently from side/rear views, and the root cause has been traced to RTGL1's emissive pipeline interaction.

## Observed Behavior

| View | Appearance | Pipeline |
|---|---|---|
| **Front** (SAR2*1, SAR2*2A8) | Near fully transparent / washed-out ghostly | ADDITIVE (TRANSLUCENT + eye emissive > 0) |
| **Side/Rear** (SAR2*3A7, SAR2*4A6, SAR2*5) | Solid dark purple | TRANSLUCENT only (no emissive) |

The front sprites have eye emissive `_e` PNGs (generated from brightmap masks). RTGL1 promotes any TRANSLUCENT mesh with `emissive > 0` to **ADDITIVE pipeline** — rendering additively against the background (washed-out ghost look). Side/rear sprites have no eye emissive textures → emissive = 0 → pure TRANSLUCENT alpha blend at 0.80 opacity.

## Render Pipeline Architecture

```
GZDoom → rt_main.cpp:IsSpectre()                 [SAR2/SARG name check]
       → makePrimFlags() → RG_MESH_PRIMITIVE_TRANSLUCENT
       → l_spriteAlpha() → min(actor_alpha, 0.80)
       → primColor.emissive = l_isemis() ? 0.15 : 0.0

RTGL1  → TextureMeta::Modify()
       → prim.emissive = std::max(0.0f, meta->emissiveMult)  [OVERRIDES GZDoom!]
       
       → RasterizedDataCollector::ToPipelineState()
       → if TRANSLUCENT && emissive > 0 → ADDITIVE flag
```

**Key finding:** `TextureMeta.cpp:282` overwrites the emissive value that GZDoom sets. Any texture with an entry in `rt/data/textures.json` gets its `emissiveMult` applied regardless of GZDoom's value.

## What's Been Tried

### Attempt 1: Alpha cap → fixed (GZDoom side)
Changed `a = std::min(actor_alpha, 0.80)` → `a = 0.80` for spectres.
- **Result:** No change to side/rear. Front already had cap working.
- **Why failed:** Alpha wasn't the issue — it's the ADDITIVE vs TRANSLUCENT pipeline difference.

### Attempt 2: Render-style based detection
Changed `IsSpectre()` to match all alpha-blend (non-additive) ExportInstances.
- **Result:** ALL sprites became semi-transparent, broke regular monsters.
- **Rolled back.**

### Attempt 3: Zero emissive in GZDoom for spectres
Set `.emissive = IsSpectre() ? 0.f : ...` in mesh primitive.
- **Result:** No change.
- **Why failed:** TextureMeta at `TextureMeta.cpp:282` overrides GZDoom's emissive. SAR2 front entries already had `emissiveMult: 2` in `textures.json`.

### Attempt 4: Remove all SAR2/SARG emissiveMult from textures.json
- **Result:** Broke regular pinkies (SARG lost eye glow), spectre eyes disappeared.
- **Rolled back.**

### Attempt 5: Add emissiveMult: 2 to ALL SAR2/SARG rotations
- **Result:** Regular pinkies (SARG) also turned additive/transparent.
- **Why failed:** SARG sprites should not be in ADDITIVE pipeline — they're not spectres.

### Attempt 6 (current): SAR2 only, all rotations
- SAR2 spectre sprites: `emissiveMult: 2` on ALL rotations (including side/rear)
- SARG regular pinkies: restored to original (front-only emissiveMult)
- **Expected:** All SAR2 sprites get ADDITIVE pipeline uniformly. No change for SARG.
- **Status:** Pending user test

## Data Files Involved

| File | Role |
|---|---|
| `sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json` | Runtime texture metadata (read by RTGL1) |
| `Doom64-Retribution/Retribution-RT-Materials/rt/data/textures_enemy_eyes.json` | Source for eye emissive metadata |
| `tools/gen_enemy_eye_emissives.py` | Generator that builds textures.json entries |

**Important:** Changes to `build/.../rt/data/textures.json` are runtime-only and get overwritten on regeneration. Source changes should go into `Retribution-RT-Materials/` and then re-generated.

## Open Questions

1. Does having `emissiveMult: 2` without an actual `_e` PNG texture cause RTGL1 to fall back to `albedo × emissiveMult` as emission? (Lines `HitInfo.inl:582` and `RsWorld.inl:111` suggest yes.)
2. Is the ADDITIVE pipeline what the user wants for spectres (ghostly look), or should it be pure alpha-blend but with a different alpha value?
3. Should the eye emissive `_e` PNGs be generated for side/rear rotations too, so they match the front exactly?
4. The `emissiveMult` override in TextureMeta.cpp makes GZDoom-side emissive control useless — any fix in GZDoom code is silently overwritten.