# AGENTS.md — Doom 64 Retribution Path Tracing

## Read first

Living project plan (progress, checkboxes, corrections, next steps):

→ **`doom64-retribution-pathtracing-plan.md`**

Engine hardcoding / patch log:

→ **`compat-patches.md`**

Material / emissive authoring rules:

→ **`material-authoring-spec.md`**

Open lighting bugs / test log (wash, blink, ceiling lamps):

→ **`open-issues-rt-lighting.md`**

Update those when phases complete or facts change. Do not invent parallel trackers.

## Workspace layout

| Path | Role |
|---|---|
| `sourcecode/gzdoom-rt/` | **Primary engine** (patched fork; build required) |
| `gzdoom-rt-1.0.2/` | Stock prebuilt — Doom II RT reference only |
| `Doom64-Retribution/` | Retribution v1.5 (+ `D64RTR_v15.WAD` shell-safe copy) |
| `Doom64-Retribution/Retribution-RT-Materials/` | Authored RT overlays (`rt/mat*`, scene JSON) — **shipped in git** |
| `DoomCE/` | Local Doom 64 CE Full (gitignored) — PBR source only |
| `Doom64-Retribution/Retribution-RT-Materials-CE/` | Converted CE→RT `_n`/`_orm` (gitignored; regenerate) |
| `sourcecode/Duke-RT/` | Material-authoring reference (NRI) |
| `sourcecode/prboom-plus-rt/` | Secondary RTGL1 reference |
| `tools/` | Helper scripts + gallery packs |
| `retribution-asset-inventory.md` | Phase 1 inventory |

## Hard rules

- Engine work is in `sourcecode/gzdoom-rt`. Prebuilt release is not mod-safe (Steam gates + `rt/scenes/map##` name collision).
- Retribution loads as `-file` on DOOM2.WAD. Prefer `D64RTR_v15.WAD` in PowerShell (`[v1.5]` is a wildcard).
- Prefer IWAD `D:\Games\GZDoom\doom2.wad` (Steam size 14604584). Avoid `D:\Games\Doom RT\DOOM2.WAD` (different size).
- Keep RT materials in `Retribution-RT-Materials/` (or a pk3 overlay) — never edit Retribution originals in place.
- Runtime mats the engine reads live under `sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/` (gitignored). After regenerating, sync into that tree **and** `Retribution-RT-Materials/` when committing.
- Log engine patches in `compat-patches.md`. Update plan Status when phases move.
- Phase 3 (`material-authoring-spec.md`) gates bulk Phase 4 authoring.

## Launchers (start here)

| Script | Purpose |
|---|---|
| `tools/launch-retribution-rt.cmd` | MAP01 play — native RT + DLSS-RR. Loads `d64r-lostsoul-rt.pk3`. |
| `tools/launch-enemy-gallery-rt.cmd` | MAP98 dark no-aggro enemy eye review hall. |
| `tools/launch-texture-gallery-rt.cmd` | MAP99 texture PBR gallery (baseline mats). |
| `tools/launch-emis-gallery.cmd` | MAP99 **world-emissives only** (`d64remis.wad` — monitors/EXIT/keys/CRT/lava). |
| `tools/wash-scratch/00-RUN-ORDER.cmd` | **From-scratch wash ladder** (isolated `build/WashScratch`; play build untouched). |
| `tools/launch-texture-gallery-ce-pbr.cmd` | Same MAP99 with DoomCE Substance PBR overlay (A/B). |
| `tools/test_gallery_emis_qa.cmd` | Auto QA: emis hygiene + 8-yaw wash score (pass/fail). |

Important cvars on Retribution launch (do not crank blindly):

- `+rt_upscale_dlss 2 +rt_rayreconstr 1` — preferred denoising path
- `+rt_normalmap_stren 1 +rt_heightmap_stren 1` — **keep near 1**; 10+ makes RR struggle
- Flashlight: `rt_flsh 0` / `1` in console (default **F** via `d64r-rt-flashlight.pk3` KEYCONF). Horror defaults: dim warm beam tipped to ground (`rt_flsh_pitch`), battery cycle (`rt_flsh_battery`) with HUD bar from `d64r-rt-flashlight.pk3`.
- RTGL1 Dev window cursor: open Esc/`~` first so GZDoom releases mouse grab

## Enemy eyes / Lost Soul (Phase 4 — current state)

### Eyes — `tools/gen_enemy_eye_emissives.py`

- **Brightmap-only** masks from `D64RTR_BRIGHTMAPS.PK3` (`bd64/`), validated compact/head.
- **`AUTO_EYES = False`** — auto red-pixel detect painted armor/blood/pinky backs; do not re-enable without QA.
- Clones: `TROO→TRO2`, `SARG→SAR2` for matching frames.
- Skip rear (`*5`) and death/gib (`H+`) frames.
- Meta: `"emissiveMult": 2`, color `(255,10,0)` / `ff0a00`. **No `lightIntensity`** (eyes must not lantern). **No `noShadow`** (that killed enemy shadows).
- Humans (`POSS`/`SPOS`/…) have **no** eye `_e` (no good brightmaps).
- Caco/Baron/Pain/etc. currently **no** eyes (no clean brightmaps) — add carefully later if wanted.
- After regen, engine tree + `Retribution-RT-Materials` are updated; global `rt/data/textures.json` is patched in the **build** tree (gitignored) — re-run generator after a clean build checkout.

Clear all enemy `_e` + strip meta: `python tools/clear_enemy_eye_emissives.py` then regen.

### Lost Soul — `tools/pack_lostsoul_rt.py` → `d64r-lostsoul-rt.pk3`

- **Do not replace** the `64LostSoul` actor (stock BRIGHT/SoulTrans stays).
- Pk3 = yellow/orange **SKUL sprite replacements** + `LSGL` offset-glow actor/EventHandler (experimental; floor light not fully dialed).
- SKUL mat: low `emissiveMult` (~0.12), **`SKUL_LIGHT = 0`** on the fire sprite itself (attached light on the same sprite white-blooms fire).
- Wired into both Retribution and enemy-gallery launchers.
- **Do not** put `SKUL*` back into `gen_fx_emissives.py` PREFIX_RULES (that re-adds `lightIntensity`/`noShadow` and undoes this).

### Monster muzzle flash — `tools/gen_fx_emissives.py`

- Player muzzle = engine `RT_AddMuzzleFlash` from weapon `A_Light1`/`A_Light2` (`rt_mzlflsh*`). Monsters never get that.
- Fire frames: `POSSF*` / `SPOSF*` / `CPOSF*` / `PLAYF*` / `SSWVF*` get attached `lightIntensity` + `ff8c52`.
- Weapon HUD flashes (`PISF`/`SHTF`/…) keep stock-like `lightIntensity` (do not zero — Retribution still uses `A_Light*`, but sprite lights are part of the visible flash).
- **No `noShadow`** on monster body fire frames. Aim frames (`…E`) stay dark.
- After regen, also re-run `gen_enemy_eye_emissives.py` if FX was run (keeps SKUL/eyes clean).
- Empty-hall A/B: `tools/launch-empty-gallery-rt.cmd` / `wash-qa/09-empty-hall.cmd`.

### World glow (lava / monitors / keys) — `tools/gen_world_emissives.py`

- Classic brightmaps = **masks only** (not PT lights). Pipeline: BM/luma mask → `*_e.png` → INDIR GI.
- **INDIR** = `_e × emissiveMult × mapboost`; primary = raw `_e` × `rt_emis_maxscrcolor`.
- Authored mults (play + gallery): SMON ≈1.0 (+ soft panel `_e`), EXIT ≈0.9, keys ≈1.2, lava ≈1.5 (+ `lightIntensity` 140 floors only). Pre-clamp “4.2” was effectively GI≈1.
- **No `lightIntensity` on wall screens/EXIT** (floating point lamps). No liquid falls / `*GLOW` / OUTTEX / SWX auto-emis.
- Keys: luma mask + **tint** (raw yellow albedo is brown → looked red in GI). No green keycard in Retribution.
- SMON: BM mask + albedo RGB LEDs only (no teal panel fill); clone `_n`/`_orm`/`_h` across ANIMDEFS frames.
- MAP01 spawn blink: GZDoom `PointLightFlicker` (9802) beside SMONAA — engine uploads `FDynamicLight` (`rt_dynlight`; play launcher uses intensity **35**).
- Writes **engine** `rt/mat` + `rt/mat_dev` + global/`d64rtr_v15_map01` JSON **and** `Retribution-RT-Materials/`. Play uses the engine tree (`launch-retribution-rt.cmd`); other maps use **global** meta.
- Emis-only QA hall: `tools/launch-emis-gallery.cmd` (`d64remis.wad`).
- RTGL must allow `emissiveMult > 1` (`TextureMeta` + `ASManager` — both had `Saturate`; rebuild `tools/build-rtgl.cmd`).
- Launchers: `+rt_mod_compat 1` + `+rt_emis_mapboost 200` + `+rt_emis_maxscrcolor 3`.
- Discover gaps: `python tools/discover_world_emissives.py`.

### Enemy gallery (debug MAP98)

- Build: `python tools/build_enemy_gallery.py` → `d64renemyg.wad` + mapinfo + tour pk3 (15 booths).
- Capture: `tools/review_enemy_gallery_batch.ps1` (PNG dumps gitignored under `tools/_enemy_gallery/`).
- Scene overlay: `rt/data/scenes/d64renemyg_map98/`.
- Sparse captures rewrite the tour pk3 — rebuild full tour (`COUNT = 15`) before interactive launch if you used `-Indices`.

## Useful local paths

- IWAD: `D:\Games\GZDoom\doom2.wad`
- GPU: NVIDIA GeForce RTX 5090
- Build engine: `tools/build-gzdoom-rt.cmd` → `sourcecode/gzdoom-rt/build/RelWithDebInfo/`
- Build RTGL runtime: `tools/build-rtgl.cmd` (needs `rt/bin/RTGL1.dll` + `nvngx_dlssd.dll`)
- **SDKs / deps policy:** install only under `G:\AI\Doom64-RT\deps\` (or other `G:\AI\…`), never system Program Files.
  - Headers: `deps/RTGL` (`vs-shirokii/RTGL`)
  - Runtime: `deps/RTGL-1.6.3`
- Python for tools: `C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe` (system `python` may lack Pillow)
- Git branch: `rayreconstruction` → `https://github.com/jlrouzies-fr/doom64-rt.git`

## Known pitfalls (do not repeat)

1. **`noShadow: true` on monster sprite metas** → enemies stop casting shadows. Never put it on whole SKUL/SARG/TROO frames.
2. **`lightIntensity` on eyes** → zombies/imps become lanterns. Surface `_e` + `emissiveMult` only.
3. **Auto eye detect** → false positives on soldiers and pinky backs.
4. **Lost Soul same-sprite attached light** → fire bleaches white; keep cast light separate or off. Do not re-add `SKUL*` to `gen_fx_emissives` PREFIX_RULES.
5. **Normal/height strength 10+** → RR/denoiser falls apart; launcher uses `1`.
6. Gallery/tour pk3s locked while gzdoom is running (WinError 32) — kill `gzdoom` before rebuild.
7. Engine `rt/mat/textures.json` is **not** the meta source of truth — use `rt/data/textures.json` (+ scene overlays).
8. **`noShadow` on monster fire frames** → same as eyes: kills enemy shadows. Muzzle meta must omit it.
9. **Intermittent noisy PT + blocky HUD** → RTGL1 Dev `drawInfoOvrd` was uninitialized; random Override forced Linear/Nearest + “Downscale to pixelized”. Fixed in `deps/RTGL` (rebuild via `tools/build-rtgl.cmd`). In Dev window keep **Override unchecked**.
10. **Center-directed / yaw wash from emitters** → was `_e` GI ignoring `emissiveMult` (only global mapboost). Fixed in RTGL HitInfo INDIR. Keep stock mapboost; dial per-tex mult. Also: `mod_compat 1` + allowlist (`gen_world_emissives`).
11. **World `_e` PNG only in `rt/mat/` while `developerMode: true`** → PNGs load from **`rt/mat_dev/`**; `mat/` is KTX2-only. Generators must write both.
12. **EXIT/sign wash white** → `rt_emis_maxscrcolor` 12 clips saturated reds. Play + gallery use **maxscrcolor 3**.
13. **Global meta contamination / silent revert** → stock Doom II emis meta (PLAY @ 4.25 etc.) floods GI via `albedo×mult×mapboost`. Scrub now runs **by default** in `gen_world_emissives.py` (`--no-scrub` debug-only); `check_emis_hygiene.py` gates the **global** JSON (strays + dupes, keep set = overlay JSONs); `restore_pre_wash_gallery_emis.py` is hygiene-gated. Never restore `textures.json` backups without a regen + hygiene PASS.
14. **`OUTTEX*` / `SWX*` full-bright** → skip auto-emis; clear stock meta.
15. **`emissiveMult` > 1 was a no-op** → `TextureMeta` **and** `ASManager` both `Saturate`d to [0,1]. Fixed; rebuild `tools/build-rtgl.cmd`. Without both fixes, doubling meta does nothing.
16. **`lightIntensity` on wall monitors/EXIT** → floating point lamps on the face. Floors (lava) only.
17. **Whole-face tinted `_e`** → primary shows raw `_e` as solid cyan/yellow. Tight BM / luma masks only.
18. **Yellow key GI looks red** → albedo carving is brown; use luma mask + yellow tint.
19. **SMON anim flat↔bump** → clone `_n`/`_orm`/`_h` to ANIMDEFS sibling frames.
20. **Liquid falls / `*GLOW`** → not auto-emitters.
21. **Post-clamp wash on MAP01** → authored wall mults (4.2) suddenly fully scaled GI; dial walls ~1.0.
22. **Missing spawn blink lamps** → need `RT_UploadGzDoomDynamicLights` for 9802; also disable stock per-sector lights (`rt_sector_lights 0`).
23. **Lingering fake fill / wash** → `RT_UploadExportableSectorLights` ran every frame at intensity 200 per sector even with autoexport off. Default **off** now.
24. **`FIRE` fx prefix swallowing world textures** → `gen_fx_emissives.py` gave `FIRELAVA`/`FIRELAV3` `lightIntensity` 700 + `noShadow`. Fixed via `WORLD_TEX_RE` guard; world fire/lava textures belong to the world allowlist only.

## Suggested next work

1. **`open-issues-rt-lighting.md`** — ceiling lamps glow but no blink/cast; wash still open; dynlight A/B on `launch-retribution-rt.cmd`.
2. Continue Phase 4 PBR; optional HEAD/BOSS eye masks.
3. Lost Soul: finish or drop LSGL; Phase 5 overlay pk3.
