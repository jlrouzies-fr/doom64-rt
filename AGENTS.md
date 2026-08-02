# AGENTS.md — Doom 64 Retribution Path Tracing

## Read first

Living project plan (progress, checkboxes, corrections, next steps):

→ **`doom64-retribution-pathtracing-plan.md`**

Engine hardcoding / patch log:

→ **`compat-patches.md`**

Material / emissive authoring rules:

→ **`material-authoring-spec.md`**

Update those when phases complete or facts change. Do not invent parallel trackers.

## Workspace layout

| Path | Role |
|---|---|
| `sourcecode/gzdoom-rt/` | **Primary engine** (patched fork; build required) |
| `gzdoom-rt-1.0.2/` | Stock prebuilt — Doom II RT reference only |
| `Doom64-Retribution/` | Retribution v1.5 (+ `D64RTR_v15.WAD` shell-safe copy) |
| `Doom64-Retribution/Retribution-RT-Materials/` | Authored RT overlays (`rt/mat*`, scene JSON) — **shipped in git** |
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
| `tools/launch-texture-gallery-rt.cmd` | MAP99 texture PBR gallery. |

Important cvars on Retribution launch (do not crank blindly):

- `+rt_upscale_dlss 2 +rt_rayreconstr 1` — preferred denoising path
- `+rt_normalmap_stren 1 +rt_heightmap_stren 1` — **keep near 1**; 10+ makes RR struggle
- Flashlight: `rt_flsh 0` / `1` in console
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
4. **Lost Soul same-sprite attached light** → fire bleaches white; keep cast light separate or off.
5. **Normal/height strength 10+** → RR/denoiser falls apart; launcher uses `1`.
6. Gallery/tour pk3s locked while gzdoom is running (WinError 32) — kill `gzdoom` before rebuild.
7. Engine `rt/mat/textures.json` is **not** the meta source of truth — use `rt/data/textures.json` (+ scene overlays).

## Suggested next work

1. Continue Phase 4 world/texture PBR (gallery MAP99 + `gen_ai_pbr.py` / ORM).
2. Optional: careful brightmap or hand masks for HEAD/BOSS/PAIN eyes.
3. Lost Soul: finish or drop LSGL offset-light; accept yellow fire compromise under BRIGHT.
4. Phase 5: package materials as a single overlay pk3 + cleaner install docs.
