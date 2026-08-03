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

### Monster muzzle flashes

Player weapons light the room via engine `RT_AddMuzzleFlash` (`rt_mzlflsh*`) keyed off `A_Light1`/`A_Light2` extralight. Monsters never call those.

Author brief cast light on **fire frames only** (`POSSF*`, `SPOSF*`, `CPOSF*`, `PLAYF*`, `SSWVF*`):

- `lightIntensity` ~480–720, `lightColorHEX` `ff8c52` (matches `rt_mzlflsh_color`)
- Modest `emissiveMult` (~0.35–0.4)
- **Do not** set `noShadow` (kills enemy shadows)
- Aim frames (`…E`) stay without attached light

```text
python tools/gen_fx_emissives.py
python tools/gen_enemy_eye_emissives.py   # restore SKUL/eyes after FX regen
```

Generators:

```text
python tools/gen_enemy_eye_emissives.py
python tools/clear_enemy_eye_emissives.py   # wipe enemy _e + meta, then regen
python tools/pack_lostsoul_rt.py            # SKUL sprites + LSGL pk3
python tools/gen_fx_emissives.py            # FX + monster muzzle frames
python tools/gen_world_emissives.py         # lava / SMON blink / falls / exits
```

## World texture emissives

Keep stock `rt_emis_mapboost` (~200). On-screen glow is raw `_e` × `rt_emis_maxscrcolor`;
**indirect GI** is `_e` × `emissiveMult` × mapboost (HitInfo INDIR fix in RTGL).

### Hard lessons (2026-08-03)

| Pitfall | Reality |
|---|---|
| Classic brightmaps | **Not** PT lights — only “draw texel full-bright” in raster. We reuse them as **masks** for `_e`. |
| `lightIntensity` on walls | Analytic point/spot on face center → **floating lamp orbs** on monitors/EXIT. Use only on **floors** (lava/nukage). |
| Whole-face tinted `_e` | Primary path shows raw `_e` → solid cyan/yellow panels. Keep **tight** BM / luma masks. |
| `emissiveMult` > 1 “does nothing” | Was clamped twice: `TextureMeta` **and** `ASManager` used `Saturate` → **[0,1]**. Fixed — mult > 1 now scales INDIR GI. Rebuild `tools/build-rtgl.cmd`. After fix, dial walls ~**1.0** (old 4.2 washed MAP01). |
| MAP01 spawn blink gone | GZDoom **9802** PointLightFlicker must be uploaded to RT (`rt_dynlight`). Do not fake with teal panel `_e` on SMON. |
| Yellow key casts red | Albedo carving is brown `(87,61,0)`. Keys need **luma mask + authored tint**, not raw albedo RGB. |
| Liquid falls | Not lamps — do not auto-emit `BFALL*`/`SFALL*`/`WFALL*`. |
| `OUTTEX*` / `SWX*` | Skip — classic BM + stock mult ≈ full-bright walls. |
| `*GLOW` by name | Not auto-authored (glow-for-glow). |
| No green keycard | Retribution only has `SKEYFLRD` / `YL` / `BL`. |
| SMON anim flat↔bump | Clone donor `_n`/`_orm`/`_h` onto ANIMDEFS sibling frames. |
| `rt_emis_maxscrcolor 12` | Bleaches saturated EXIT/keys white — launchers use **3**. |
| `rt_mod_compat` bit 2 | Auto brightmap→emis — keep gallery/play at **mod_compat 1**. |

### Play vs gallery (same pipeline)

Normal Retribution maps use the **same** engine DLL + global `rt/data/textures.json` + `rt/mat_dev/*_e.png` (developerMode). Scene overlay `d64rtr_v15_map01` is also upserted; other `d64rtr_v15_map##` fall back to **global** meta (first `textureName` wins — always rewrite in place).

Launch: `tools/launch-retribution-rt.cmd` (MAP01). Emis QA hall: `tools/launch-emis-gallery.cmd` (`d64remis.wad`, 52 emitters only).

Current authored scale (INDIR): SMON ≈ **1.0** (BM + albedo RGB LEDs only — no teal panel fill), EXIT ≈ **0.9**, keys ≈ **1.2**, lava ≈ **1.5** + `lightIntensity` 140.

After the Saturate→clamp fix, older mults (SMON 4.2…) suddenly fully scaled GI and washed MAP01 — dial walls back near **1.0** (what GI effectively was while clamped).

MAP01 spawn blink lamps are GZDoom **PointLightFlicker** (thing 9802, green) beside SMONAA. Engine uploads `FDynamicLight` into RT (`rt_dynlight`; play launcher `rt_dynlight_intensity 35`). Do **not** fake these with wall `lightIntensity` or teal panel `_e`.

Auto-author with `tools/gen_world_emissives.py`:

1. `D64RTR_BRIGHTMAPS.PK3` GLDEFS `brightmap texture` → `_e` mask (SMON, SEXIT, C22/C23, …).
2. Name heuristics + ANIMDEFS: `HLAVA*` / `D64LAVA*` / CRT / CFACE / SMON / SEXIT / D64LOGO / `SKEYFL*`. Clone SMON PBR companions across frames. **Not** falls / `*GLOW` / OUTTEX / SWX.
3. Resolve albedo via PNG lump or ZDoom `TEXTURES` composite.
4. JSON: `emissiveMult` for GI; `lightIntensity` **only** for floor lava/nukage. Wall cast = `_e` GI only. Writes engine `mat`+`mat_dev` **and** `Retribution-RT-Materials/`.

Find gaps:

```text
python tools/discover_world_emissives.py   # → tools/_emissive_candidates.md
```

QA: `tools/launch-emis-gallery.cmd` · `tools/test_gallery_emis_qa.cmd`
## DoomCE PBR → RT (gallery A/B)

Doom 64 CE Full ships GZDoom `material` maps (Substance): `normal` / `roughness` / `metallic` / `ao`. Those do **not** load in RTGL1 as-is.

```text
python tools/convert_ce_pbr_to_rt.py          # → Retribution-RT-Materials-CE/rt/mat/*_{n,orm}.png
python tools/sync_gallery_pbr_set.py ce       # overlay into engine rt/mat (keeps *_e)
python tools/sync_gallery_pbr_set.py baseline # restore authored/gallery stubs
```

Launchers: `tools/launch-texture-gallery-ce-pbr.cmd` vs `tools/launch-texture-gallery-rt.cmd` (same MAP99 hall).

Ship copies under `Doom64-Retribution/Retribution-RT-Materials/rt/`; runtime copies also land in the engine `build/.../rt/` tree (gitignored).

## Retribution authoring rules

1. **Never edit** `D64RTR_v15.WAD` in place. Ship `Retribution-RT-Materials/` (or a pk3 that overlays `rt/`).
2. Prefer **meta-first** (JSON) for bulk look; add `_e` / `_orm` / `_n` only where it matters.
3. Use `D64RTR_BRIGHTMAPS.PK3` as an emissive **mask source** via `gen_world_emissives.py` / eye tools. Do **not** lower global `rt_emis_mapboost` to hide bad GI — dial world `emissiveMult` instead (INDIR-only scale when `_e` exists).
4. Heuristics for auto stubs (see `tools/gen_map01_pbr.py`):
   - `SPACE*` / metal → high metal, mid roughness, `isMirrorIfSmooth`
   - `SFLAT*` / floors → high roughness, low metal
   - `LAVA*` / `NUKE*` → `_e` + `emissiveMult` ≈3.6 + `lightIntensity` (floors)
   - Monitors / EXIT / keys → tight `_e` + mult ≈2–4; **no** wall `lightIntensity`
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
