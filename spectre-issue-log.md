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
- **Result:** Side/rear remained bright (albedo fallback at emissiveMult 2). Did not match front.
	- **Rolled back.**

### Attempt 7 (2026-08-05 — current fix): Generate `_e` PNGs for side/rear + uniform emissiveMult

**GZDoom fix:**
- `IsSpectre()`: removed `n[3]=='G'` check — only matches `SAR2` (spectre), not `SARG` (regular pinky)
- `rt_translucent_minalpha` changed from 0.72 → 0.80
- Launcher: removed `+fly`, added `+notarget`

**`_e` PNGs for side/rear rotations:**
- Front rotations (1, 2A8): keep existing eye-mask `_e` PNGs from brightmaps
- Side/rear rotations (3A7, 4A6, 5): generated new `_e` PNGs with a small (~3px radius) red emissive patch at the head position on each rotation's sprite. The patch uses the same red color (ff0a00) and has similar total emissive area to the front eye masks.
- Saved to `rt/mat/`, `rt/mat_dev/`, `Retribution-RT-Materials/rt/mat/`

**textures.json:**
- ALL 35 SAR2 living rotations (A-G × 5 angles) now have `emissiveMult: 2.0` in:
  - Global `textures.json`
  - `d64rtr_v15_map01` scene overlay (MAP01 gameplay)
  - `d64renemyg_map98` scene overlay (enemy gallery)
  - `textures_enemy_eyes.json` (source)
  - `textures_pinky_eyes.json` (source)

**Expected result:**
- Uniform ADDITIVE pipeline for all SAR2 rotations (emissive = 2.0 from TextureMeta)
- Front: red eye glow from eye-mask `_e`
- Side/rear: small red head-side patch from generated `_e`
- All rotations: consistent ghostly ADDITIVE render (not solid TRANSLUCENT)
- Regular SARG pinkies: unaffected (not caught by IsSpectre, front-only eye `_e`)

## Data Files Involved

| File | Role |
|---|---|
| `sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json` | Global runtime meta (1642 entries) |
| `sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/scenes/d64rtr_v15_map01/textures.json` | MAP01 scene overlay (914 entries) |
| `sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/scenes/d64renemyg_map98/textures.json` | Enemy gallery overlay (164 entries) |
| `Doom64-Retribution/Retribution-RT-Materials/rt/data/textures_enemy_eyes.json` | Source for eye emissive metadata |
| `Doom64-Retribution/Retribution-RT-Materials/rt/data/textures_pinky_eyes.json` | Source for pinky eye metadata |
| `rt/mat/SAR2*_e.png` + `rt/mat_dev/` + `OMAT/` | Per-rotation emissive textures |
| `tools/gen_enemy_eye_emissives.py` | Generator — side/rear `_e` PNGs are hand-generated, not from generator |

**⚠ Regeneration hazard:** `gen_enemy_eye_emissives.py` does NOT generate side/rear `_e` PNGs (Clone step line 515 skips non-existing SARG donor rotations + rear views). After rerunning the generator, side/rear `_e` PNGs must be regenerated via the head-patch script. Also the generator's `upsert_json` keeps all entries (doesn't remove side/rear), so textures.json survives regeneration — only the `_e` PNGs need restoring.

## Architecture Summary

```
GZDoom: IsSpectre() → SAR2 only (not SARG)
       → RG_MESH_PRIMITIVE_TRANSLUCENT
       → alpha = min(actor_alpha, 0.80)
       → emissive = 0.0 (l_isemis=false for Translucent style)

RTGL1: TextureMeta → emissive = max(0, emissiveMult) = 2.0  [overrides 0.0]
       → RasterizedDataCollector: TRANSLUCENT + emissive(2.0) > 0 → ADDITIVE
       → _e PNG lookup:
         - Front: eye-mask pixels emit at 2.0×
         - Side/rear: head-patch pixels emit at 2.0×
       → All rotations: ADDITIVE ghostly wash with small red emissive accent
```