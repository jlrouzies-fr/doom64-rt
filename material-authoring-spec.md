# Material Authoring Spec — gzdoom-rt / RTGL1 (Doom 64: Retribution)

Hard gate for Phase 4. Describes how path-traced materials are defined for this fork.

## Pipeline overview

1. GZDoom uploads each visible texture via `rgProvideOriginalTexture` using **`GetRTName()`** = game texture name (e.g. `SPACEBE`, `SFLATAJ`).
2. RTGL1 looks for **optional overrides** under `rt/mat/` next to the exe (`pOverrideFolderPath = "rt/"`).
3. RTGL1 also reads **JSON material meta** from `rt/data/textures.json` (global) and `rt/data/scenes/<scene>/textures.json` (per map).
4. For Retribution, `<scene>` is **`RT_MapName`**: `<wadstem>_<map>` lowercased, e.g. `d64rtr_v15_map01`.

Albedo always comes from the game (or an albedo override). PBR “look” is layered on top via meta + companion maps.

## Companion maps (`rt/mat/`)

| File | Slot | Format notes |
|---|---|---|
| `TEXNAME.ktx2` / `.png` | Albedo+alpha override (postfix `""`) | Replaces in-game albedo |
| `TEXNAME_orm.ktx2` / `.png` | Occlusion / Roughness / Metallic | **G = roughness, B = metallic** (AO in R; swizzle `NULL_ROUGHNESS_METALLIC`) |
| `TEXNAME_n.ktx2` / `.png` | Normal map | |
| `TEXNAME_e.ktx2` / `.png` | Emissive | RGB glow |
| `TEXNAME_h.ktx2` / `.png` | Height | Optional |

Stock Doom II also ships many `*_remix_normal.ktx2` / `*_remix_roughness.ktx2` (Remix tooling); for Retribution we use the standard `_orm` / `_n` / `_e` suffixes.

**Release builds** load **KTX2 only** unless `rt/RTGL1.json` has `"developerMode": true` (then PNG/TGA allowed). Authoring workflow: PNG + developerMode → later batch to KTX2 via `rt/CreateKTX2.py` + Compressonator.

## JSON meta (`textures.json`)

```json
{
  "version": 0,
  "array": [
    {
      "textureName": "SPACEBE",
      "metallicDefault": 0.75,
      "roughnessDefault": 0.35,
      "emissiveMult": 0.0,
      "isMirror": false,
      "isMirrorIfSmooth": true,
      "isWater": false,
      "isGlass": false,
      "attachedLightIntensity": 0.0,
      "attachedLightColor": [255, 255, 255]
    }
  ]
}
```

Important fields (from RTGL1 `TextureMeta`):

| Field | Role |
|---|---|
| `textureName` | Must match `GetRTName()` |
| `metallicDefault` / `roughnessDefault` | Used when no `_orm` map (or as defaults) |
| `emissiveMult` | Scales emissive (brightmaps / `_e` / additive) |
| `isMirror` / `isMirrorIfSmooth` | Specular mirror behavior |
| `isWater` / `isGlass` / `isAcid` | Special shading |
| `lightIntensity` + `lightColor` / `lightColorHEX` | Analytic light glued to the surface/sprite (JSON keys map to `attachedLight*`) |
| `lightEvenOnDynamic` | Force attached lights on non-quad dynamics (sprite quads already work) |
| `forceOpaque` / `forceAlphaTest` | Alpha policy overrides |

**Lookup order:** scene JSON overrides global JSON for the same `textureName`.

## Enemy eye emissives

Classic GL brightmaps do **not** become RT emission masks — `rt_mod_compat` only sets a whole-primitive emissive float when a brightmap exists.

For **red glowing eyes** on monsters (current policy):

1. Use eye masks from `D64RTR_BRIGHTMAPS.PK3` (`brightmaps/bd64/<SPRITE>B.png`) only — even if unbound in GLDEFS.
2. Write `rt/mat/<SPRITE>_e.png` with **only the eye pixels**, pure red `(255, 10, 0)`.
3. JSON: `"emissiveMult": 2` only. **Do not** set `lightIntensity` on eyes (casts room light / lanterns). **Do not** set `noShadow` on monster sprites (kills enemy shadows).
4. Validate masks: compact, head-band only; skip rear (`*5`) and death frames (`H+`).
5. **Auto red-pixel detect is OFF** (`AUTO_EYES = False`). It false-positived soldiers (armor/blood) and pinky backs.
6. Clones: Nightmare Imp `TRO2*` ← `TROO*`; Spectre `SAR2*` ← `SARG*` when donor `_e` exists.
7. Lost Soul (`SKUL*`): **stock actor** (do not DECORATE-replace). `d64r-lostsoul-rt.pk3` = yellow/orange SKUL sprite replacements + optional `LSGL` offset-glow handler. Fire `_e` with low `emissiveMult` (~0.12); **no** `lightIntensity` on SKUL frames (bleaches fire white under BRIGHT). Offset-light still experimental.
8. Dark gallery (MAP98): `tools/launch-enemy-gallery-rt.cmd` / `review_enemy_gallery_batch.ps1`. Rebuild map/tour: `python tools/build_enemy_gallery.py`.

Generators:

```text
python tools/gen_enemy_eye_emissives.py
python tools/clear_enemy_eye_emissives.py   # wipe enemy _e + meta, then regen
python tools/pack_lostsoul_rt.py            # SKUL sprites + LSGL pk3
```

Ship copies under `Doom64-Retribution/Retribution-RT-Materials/rt/`; runtime copies also land in the engine `build/.../rt/` tree (gitignored).

## Retribution authoring rules

1. **Never edit** `D64RTR_v15.WAD` in place. Ship `Retribution-RT-Materials/` (or a pk3 that overlays `rt/`).
2. Prefer **meta-first** (JSON) for bulk look; add `_e` / `_orm` / `_n` only where it matters.
3. Use `D64RTR_BRIGHTMAPS.PK3` as an emissive hint list (engine `rt_mod_compat` bit 2 already maps brightmaps → emissive at runtime).
4. Heuristics for auto stubs (see `tools/gen_map01_pbr.py`):
   - `SPACE*` / metal → high metal, mid roughness, `isMirrorIfSmooth`
   - `SFLAT*` / floors → high roughness, low metal
   - `LAVA*` / `NUKE*` / tech lights → `emissiveMult` + `_e` tint
   - water/slime → `isMirror` / `isWater` / `isAcid`

## MAP01 proof package

Generated by:

```text
python tools/gen_map01_pbr.py
```

Writes:

- `build/RelWithDebInfo/rt/data/scenes/d64rtr_v15_map01/textures.json`
- `build/RelWithDebInfo/rt/mat/<TEX>_orm.png` (+ `_e.png` when glowing)
- `build/RelWithDebInfo/rt/RTGL1.json` with `developerMode: true`
- Mirror under `Doom64-Retribution/Retribution-RT-Materials/rt/...`

## Test

Launch `tools/launch-retribution-rt.cmd` (MAP01). Expect metal panels more reflective, tech surfaces glowier, floors duller. Sky stays on Doom II `RSKY1` fallback.

## Later (Phase 4+)

- Hand-tune hero textures (lava, switches, monitors)
- Convert PNG → KTX2; turn `developerMode` off for release
- Per-map scene JSON for MAP02+
- Optional normal maps from height/Sobel
