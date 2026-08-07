# Gallery wall blotch / emissive GI wash — diagnostic brief

**Status:** Open / circling (2026-08-03). Surface emission is confirmed; dialing `emissiveMult` does not visibly fix the playable symptom. Hand this file to another model for fresh analysis.

**Related docs:** `compat-patches.md` (HitInfo INDIR note), `material-authoring-spec.md`, `AGENTS.md`, `tools/gen_world_emissives.py`.

---

## 1. Symptom (player-facing)

- Map: texture gallery **MAP99** (`d64rtexg.wad`), launcher `tools/launch-texture-gallery-rt.cmd`.
- Pose: near end / along **STONE2** shell wall, often ~30–40° yaw off the wall normal; also appears with forward/back motion.
- Look: soft **circular / blotchy** light patches on dark stone with **no local lamp**. Feels like a glow “around” the player.
- Reference shot: `screen/wallturned.png` (right-half wall mean luma ~47; blotches obvious).
- Automations that teleport-and-settle often miss it (RR / temporal). Manual free-roam reproduces reliably.
- Stock cvars of interest: `rt_emis_mapboost 200`, `rt_sky 80`, `rt_rayreconstr 1`, `rt_upscale_dlss 2`, `rt_flsh 0`, `rt_mod_compat 1`.

---

## 2. What is proven

| Test | Result | Implication |
|---|---|---|
| `rt_emis_mapboost 0` (with emitters present) | Blotches **gone** | Path uses **indirect surface emission × mapboost** |
| `rt_sky 0` / `rt_autoexport_light 0` (earlier yaw A/B) | Blotches **remain** | Not primarily sky / sector autoexport |
| Nuclear “emis off” (no world `_e`, strip **all** `emissiveMult` / light fields from global `textures.json`, quarantine all `*_e.png`, `rt_emis_additive_dflt 0`) | Blotches **gone** | Needs **some** surface-emission path |
| Remove only authored world `_e` (69 allowlist) but leave global meta | Blotches **remain** | Not only `textures_world_emis` / allowlist `_e` |
| Then also strip high global booth meta (OUTTEX/SWX @ **1.25**) | Still reported **remain** (then nuclear fixed) | Intermediate state messy; nuclear is the clean “off” |
| Restore world `_e` + low `emissiveMult` (0.004→0.01, later 0.0004→0.001) + no `lightIntensity` | Blotches **back** (“same issue”) | Either mult not applied on GI path, or another emission path still huge |
| Emis-off launcher | `tools/launch-texture-gallery-emis-off.cmd` | Good “known dark” baseline |

**Conclusion so far:** The wash is **emissive GI** (mapboost path), not sky and not a light attached to the player. Emis-off proves that; mult dialing has **not** behaved as the HitInfo fix predicts.

---

## 3. Intended engine mechanism (and the suspected break)

### HitInfo emission (`deps/RTGL/Source/Shaders/HitInfo.inl`)

Authored intent (compat patch 2026-08-03):

- With `_e` map:
  - **Primary / reflection:** raw `_e` (on-screen glow via `rt_emis_maxscrcolor`).
  - **INDIR:** `_e * emissiveMult`, then `emissionMapBoost` in `RtRaygenIndirect.inl`.
- Without `_e`: `albedo * emissiveMult` (all paths).

```glsl
// Simplified from HitInfo.inl
if (tr.emissiveTexture != MATERIAL_NO_TEXTURE) {
    emission = sample(_e);
#if defined(HITINFO_INL_INDIR)
    emission *= tr.emissiveMult;
#endif
} else {
    emission = h.albedo * tr.emissiveMult;
}
```

`RtRaygenIndirect.inl` then does `emis *= globalUniform.emissionMapBoost` (`rt_emis_mapboost`, default **200**).

### Why “lower mult” should work — but playtests disagree

If INDIR really multiplies by `emissiveMult`, then:

- `GI ≈ _e * mult * 200`
- mult `0.0005` → ~`0.1 × _e` (should be calm)
- mult `1.25` with **no** `_e` → `albedo * 1.25 * 200` (catastrophic)

We found stock/global lines like `OUTTEX01` with `"emissiveMult":1.25` while authored world overlay wanted ~`0.004`. RTGL `TextureMetaManager` keeps the **first** `textureName` and **ignores duplicates**. Early `patch_global_inline` sometimes **appended** a second low-mult line → ignored. That was fixed to rewrite in place + scrub stock world lines (`gen_world_emissives.py`).

Even after low mults in **scene** `d64rtexg_map99/textures.json` (verified ~0.0004–0.001, no `lightIntensity`), user still sees the wash. That strongly suggests either:

1. **INDIR multiply by `emissiveMult` is not what the running shaders do**, or
2. **Instance `emissiveMult` arriving in the shader is ~1 / wrong**, or
3. **Another buffer / RR path** still paints blotches that vanish when `_e` files disappear (correlation with emis-off).

---

## 4. Build / deploy smell (important for next model)

Timestamps observed same day:

| Artifact | Time (local) | Note |
|---|---|---|
| `HitInfo.inl` patched | ~10:52 | Source fix present |
| `RtRaygenIndirectInit.rgen.spv` (Build + staged) | ~10:55 | Size **128448** (newer) |
| `RTGL1.dll` in engine `rt/bin` | ~07:29 | **Older than HitInfo patch** |
| Older copies | e.g. `runtime-mod/rt/shaders/…`, `gzdoom-rt-1.0.2/…` | Size **128364** (older) |

- Shaders are loaded as **`.spv` next to the game**, not only baked into the DLL.
- Launcher cwd: `sourcecode/gzdoom-rt/build/RelWithDebInfo/` → should use `rt/shaders/*.spv`.
- `tools/build-rtgl.cmd` reported BUILD_OK but **DLL mtime did not advance**; shader gen often says “Everything is up-to-date” and may miss `.inl` invalidation depending on cache.
- **Open question:** Is the running process definitely using the 10:55 SPVs with the INDIR `emissiveMult` multiply? Force-clean regen + confirm hash at runtime.

Include path: `RaygenCommon.h` defines `HITINFO_INL_INDIR` around `#include "HitInfo.inl"`.

---

## 5. Material / meta pipeline (Retribution)

| Piece | Role |
|---|---|
| `rt/mat/<TEX>_e.png` | Emissive mask (engine tree under RelWithDebInfo) |
| `Retribution-RT-Materials/rt/mat/` | Shipped copy of mats |
| `rt/data/textures.json` | Global meta (commenty JSON; **first name wins**) |
| `rt/data/scenes/d64rtexg_map99/textures.json` | Scene overlay (wins over global if present) |
| `textures_world_emis.json` | Allowlist overlay from `gen_world_emissives.py` |
| `tools/sanitize_gallery_emissives.py` | Keep allowlist; strip other scene emis; don’t delete sprite `_e` |
| `tools/clear_world_emissives.py` | Temp strip world allowlist `_e` + meta |
| Nuclear A/B | Quarantine **all** `_e` → `rt/mat_e_quarantine/`; blank emis fields in global |

**GZDoom upload:** world prims start with `.emissive = 0` unless additive (`rt_emis_additive_dflt`). `TextureMetaManager::Modify` sets `prim.emissive = Saturate(meta->emissiveMult)`. `ASManager` copies that into geom `emissiveMult`.

**`rt_mod_compat`:** bit1 (`& 2`) = auto brightmap→emissive. Gallery uses **`1`** (bit0 only) — brightmap auto-emis should be off. Additive still can set emis via `l_isemis()`.

---

## 6. Dead ends / red herrings

- End-wall **BIGDOOR2** baked lamps → changed shell to **STONE2** (fixed a different red-strip issue).
- “Sky leak” / floor sky in iso gallery → wrong pillar winding; separate.
- Flashlight / player lantern → `rt_flsh 0`; blotches are on the wall, not muzzle.
- Only-motion RR flash → real lighting term also exists when looking at wall (`wallturned.png`).
- Assuming “low mult in JSON” implies low GI without verifying **which meta entry is first** and **which SPV is loaded**.

---

## 7. Open questions (for a smarter pass)

1. **Does INDIR HitInfo in the live SPV actually execute `emission *= tr.emissiveMult`?**  
   Force delete `GenerateShaders` cache + Indirect SPVs, rebuild, hash-check staged vs Build, then retest with mult 0 vs 0.01 (mult 0 with `_e` present should kill GI if multiply works).

2. **What is `tr.emissiveMult` for a hot booth (e.g. SEXIT / SMONAA) at runtime?**  
   If it’s 1.0 despite JSON 0.0005, meta name mismatch or Modify not applied.

3. **With `_e` present and `emissiveMult` forced 0 in scene+global, do blotches remain?**  
   - Remain → emission path ignores mult (old shader / wrong define) or non-HitInfo path.  
   - Gone → mult works; previous JSON wasn’t what the GPU saw.

4. **Does RR (`rt_rayreconstr`) only amplify, or invent blotches from noisy emis?**  
   A/B RR off **after** confirming emission is small.

5. **Primary raw `_e` → reflection / other buffers → wall?**  
   Unlikely to be killed by mapboost alone, but worth tracing who writes emission into indirect reservoirs.

6. **Alternative product fix if mult cannot be trusted:**  
   On INDIR, ignore `_e` entirely (`emission = 0`) and drive GI only from attached lights / explicit lightIntensity — keep raw `_e` for primary screen glow. That matches “emis-off walls clean” while preserving look-at-CRT glow.

---

## 8. Suggested next experiments (ordered)

1. **Hard shader verify**
   - Delete `deps/RTGL/Source/Shaders/Build/GenerateShadersCache.txt` and Indirect `*.spv`.
   - `tools/build-rtgl.cmd`; confirm staged Indirect SPV hash/mtime.
   - Temporarily change INDIR branch to `emission = vec3(0.0);` (keep primary raw `_e`), rebuild shaders only, play gallery: walls should match emis-off; CRT still glows when stared at.

2. **Mult 0 with `_e` kept**
   - Keep `_e.png`, set all world allowlist `emissiveMult: 0` in scene + global (in-place patch).
   - If walls clean → mult path works; raise mult slowly.
   - If walls still blotchy → multiply not applied or other path.

3. **Class isolation**
   - Enable only SMON `_e`, then only CRT, then only lava — iso hall already pointed at SMON as hottest class (`tools/run_emis_iso_qa.ps1`).

4. **Instrument**
   - Devview / unfiltered indirect if available (`DEBUG_SHOW_FLAG_*` in RTGL).
   - Log `TextureMeta::Access` hits for `SEXIT` / `SMONAA` on map load.

---

## 9. Commands / paths cheat sheet

```text
Engine cwd:     sourcecode/gzdoom-rt/build/RelWithDebInfo/
Shaders:        .../rt/shaders/RtRaygenIndirect*.spv
DLL:            .../rt/bin/RTGL1.dll
HitInfo source: deps/RTGL/Source/Shaders/HitInfo.inl
Indirect apply: deps/RTGL/Source/Shaders/RtRaygenIndirect.inl  (emissionMapBoost)
Meta global:    .../rt/data/textures.json
Meta gallery:   .../rt/data/scenes/d64rtexg_map99/textures.json
World generator: tools/gen_world_emissives.py
Emis-off launch: tools/launch-texture-gallery-emis-off.cmd
Normal launch:   tools/launch-texture-gallery-rt.cmd
Rebuild RTGL:    tools/build-rtgl.cmd
```

Console A/B while in the wall pose:

```text
rt_emis_mapboost 0     // should kill blotches if emission GI
rt_sky 0
rt_rayreconstr 0
rt_emis_additive_dflt 0
```

---

## 10. One-paragraph summary for another model

We have a soft blotchy wash on dark gallery walls that disappears when all surface emissives are removed or when `rt_emis_mapboost` is 0, so it is indirect emissive GI, not sky or a player light. We patched RTGL `HitInfo.inl` so INDIR uses `_e * emissiveMult` before mapboost, and authored very low mults, but the wash returns whenever `_e` maps are present—as if mult were ignored or always ~1. Suspects: stale/wrong Indirect SPV at runtime, TextureMeta first-entry / name mismatch leaving mult=1, or a need to zero `_e` on the INDIR path entirely and keep raw `_e` for primary only. Please verify the live shader path and propose a minimal fix that keeps on-screen CRT/lava glow without wall wash at stock mapboost 200.
