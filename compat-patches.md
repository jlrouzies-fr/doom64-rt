# Compatibility / engine patches log

Living changelog of gzdoom-rt (and Retribution) changes for Doom 64: Retribution RT.
See also `doom64-retribution-pathtracing-plan.md` Status section.

---

## Findings

### Steam / Doom II IWAD hardcoding
Softened in `d_iwad.cpp` / `i_system.cpp` (no hard-exit to Steam store; skip fancy launcher when `-iwad`/`-file`).

### Black screen + HUD + music, then crash (2026-08-02)
**Cause:** Stock gzdoom-rt applies Doom II `rt/scenes/map##` by map lump name. Retribution also uses MAP01… → wrong/empty RT world (black) while HUD/audio still run; crash follows.

Enter-fade (`d64_enterfade`) was a red herring — disabling it did not fix.

**Official fix (upstream modcompat branch):**
- `RT_MapName` = `<wadfile>_<map>` so scenes don't collide
- `+rt_mod_compat 3` + `+r_drawvoxels 0`
- Prebuilt: `gzdoom-mod.exe` from `gzdoom-rt-modcompatibility-1.zip`

---

## Applied patches

### A. Steam soft gates
- `src/d_iwad.cpp` — warn instead of Steam URL `exit`
- `src/common/platform/win32/i_system.cpp` — Fallback picker; skip RT launcher with `-iwad`/`-file`

### B. Official modcompat (cherry-picked onto our main)
- `e61961afa` Mod compatibility 1 (`rt_mod_compat`)
- `7de9cb8c3` Separate mapname for non-Doom2 (`RT_MapName`)
- `36ffff538` Brightmap/glow → emissive hack

Rebuilt: `sourcecode/gzdoom-rt/build/RelWithDebInfo/gzdoom.exe`

---

## Launch

1. **Patched fork:** `tools/launch-retribution-rt.cmd`
2. **Stock official mod binary:** `tools/launch-retribution-modcompat.cmd` → `runtime-mod/`

Deps stay under `G:\AI\Doom64-RT\deps\` (`RTGL`, `RTGL-1.6.3`, `modcompatibility`).

---

## Crash: Scene graph rebuild + C0000005 (2026-08-02)

`Scene graph out of date rebuilding` = RTGL1 auto-exporting a new mod map scene (normal once).

Access violation write `@0x24` / `RAX=0` during that rebuild. Dump also loaded:
- `RTSSVkLayer64.dll` (RivaTuner / MSI Afterburner)
- `graphics-hook64.dll` (OBS / Discord capture)

**Mitigations:** close those overlays; use `tools/launch-retribution-diag.cmd` (`-nosound`, `rt_classic 1`, `rt_fluid false`); then retest modcompat / patched launchers.

---

## No HUD / immediate freeze (2026-08-02 follow-up)

Unattended load reaches `MAP01 - Staging Area` then dies. Cause: **no** `rt/scenes/d64rtr_v15_map01` → RTGL1 auto-export (`Scene graph out of date rebuilding`) → AV.

Fixes applied in tooling:
- Seed stub scene from `rtempty` as `d64rtr_v15_map01`
- Force `+rt_autoexport false` on launchers / smoke
- Auto-click IWAD Launch dialog; `queryiwad=false` in `gzdoom-rt2.ini`
- Source patch (pending rebuild): skip Launch dialog when `-iwad`/`-file`/`-rtnolauncher`

Still crashes after MAP01 even with autoexport off — next: Doom II baseline compare, then isolate RT import of stub scene.

---

## Freeze (not crash) — whole-map upload (2026-08-02)

Symptom: black + unresponsive; Task Manager force-close. Process stays “alive”.

**Cause:** With no `rt/scenes/<wad>_map##.gltf`, RT set cullmode=2 **every frame** (“upload everything”). Fine for small Doom II maps with scenes; freezes large UDMF Retribution.

**Fix (patched `rt_main.cpp`, rebuilt):**
- Do not force uncull-all when static scene missing (use normal BSP cull)
- Default `rt_autoexport` false; block autoexport on mod map names (`_` in `RT_MapName`)
- Launch with `rt_classic 1` until real scenes exist

Use `tools/launch-retribution-rt.cmd`.

---

## Freeze narrowed: Retribution MAP01 only (2026-08-02)

`Process.Responding` samples (20s cap):

| Case | Result |
|---|---|
| Retribution menu (no +map) | Responsive |
| Doom II MAP01 | Responsive |
| Retribution MAP02 | Responsive |
| Retribution MAP01 | Freezes ~3–8s (force-close) |

So not “all mods” / not global RT — **MAP01 Staging Area** content + RT path.

### Root cause (isolated)

Not ACS (script 12 terminate still froze). Real MAP01 `TEXTMAP` without `BEHAVIOR` still froze; tiny replacement MAP01 did not.

| Override | 20s Responding |
|---|---|
| Strip all linedef/sector specials | OK |
| Disable only `Sector_Set3dFloor` (special 160) | OK |
| Keep 3D floor, replace control sector 18 `F_SKY1` → `FLAT1` | Still freezes |

**Fix pack:** `Doom64-Retribution/d64r-map01-rtfix.wad` — same MAP01 geometry with the 3D floor linedef special removed. Loaded last via `tools/launch-retribution-rt.cmd`. Side effect: the teleporter-hallway 3D floor event on MAP01 won’t appear until an engine-side RT 3D-floor fix exists.

**Must include `BEHAVIOR` (+ `ZNODES`):** a TEXTMAP-only replacement stripped ACS → every switch that calls script 19 printed `P_StartScript: Unknown script 19`. Fix wad carries original MAP01 `BEHAVIOR`/`ZNODES` with the patched `TEXTMAP` (3D-floor special cleared). Do **not** ship a mis-offset PWAD (lump directory offsets must be absolute from file start — a bad rewrite once made TEXTMAP = nested `PWAD` header → `Unexpected character ASCII 5` / invalid ACS).

---

## Automatic RT opacity / emissive (2026-08-02)

See-through walls under full RT (`rt_classic 0`) were largely soft/garbage PNG alpha + RT always alpha-testing world geometry.

**Engine (`rt_main.cpp`, `rt_mod_compat`):**
- Force opaque alpha on world texture uploads (RGBA PNGs are always `Masked` in GZDoom — that check was a no-op)
- World geometry (`ExportMap`): **never** alpha-test under mod_compat (sprites still do)
- Force vertex color alpha=1 for all world draws
- Brightmaps/glowmaps on **walls and sprites** → RT emissive (not sprites-only)

### Sky-through-walls (real bug, not fence alpha)

With `rt_classic 0`, `RT_CanOmitUploadOfStaticExportable` skipped ExportMap walls/flats assuming baked `rt/scenes`. Retribution has none → geometry never uploaded → sky holes. The “one fixed wall” was a fence made solid by the alpha hack.

**Fix:** `RT_ModMapNeedsLiveGeometryUpload()` (`mapname` contains `_`) → never omit live uploads. Fence alpha restored via “real mask” pixel heuristic (≥8% low-A pixels).

Rebuild: VS18 MSBuild `build\src\zdoom.vcxproj` RelWithDebInfo.

### Sky voids / pink checker (follow-up)

**Cause:** `rt_sky_always` only emulated sky when `Portals` was empty. Any portal (incl. broken sector skyboxes) skipped sky → white/checker outdoor holes. GLDEFS cubic `D64RTSKY` faces also failed under RT.

**Fix:**
- `hw_portal.cpp`: always process portals; drop `Skybox` when `gl_noskyboxes`; if no `Sky` portal drew, emulate raster sky
- `rt_main.cpp`: non-black `skyColorDefault` fallback
- `d64r-rt-sky.pk3`: `ChangeSky` → Doom II `RSKY1` (no GLDEFS cube)

## Retribution night sky (2026-08-03)

**Symptom:** Outdoor sky was bright Doom II clouds / white-black skyboxes; indoor seams got shadow-casting sky wash (`rt_sky` confirmed). MAP01 is meant to be night stars.

**Fix:**
- `d64r-rt-sky.pk3`: `ChangeSky` → Retribution **`SPACE`** (near-black starfield), never `RSKY1`
- Play launcher: `+rt_sky 25` (was 200), `+gl_noskyboxes false`, keep `rt_sky_always`
- `hw_walls.cpp` / `hw_flats.cpp`: while `portalState.inskybox`, push `RtPrim::Ignored` so sector skybox rooms do not upload as white/black RT geometry; raster `SPACE` sky fills outdoor `F_SKY1` instead
- True SPACE* skybox mural projection under RT still deferred

Rebuild: `tools/build-gzdoom-rt.cmd`. User confirmed sky looks good.

---

## Native DLSS Ray Reconstruction (2026-08-02)

Remix RR (-rtxremix + t_remix_rayreconstr) blacks out Retribution. Native path only had A-SVGF.

**RTGL (deps/RTGL):**
- RgStartFrameRenderResolutionParams.rayReconstruction — when set with NVIDIA_DLSS, skip A-SVGF, run noisy compose + NGX DLSS-RR
- CmNoisyCompose.comp writes PreFinal + RR staging (normals/roughness in DiffPing, specular albedo in DiffPong)
- DLSSRR.cpp — NGX Vulkan Ray Reconstruction (shares NGX init with DLSS2; needs 
vngx_dlssd.dll)
- Build: 	ools/build-rtgl.cmd (clones SDK at deps/DLSS, stages DLL + shaders)

**gzdoom-rt:**
- `+rt_rayreconstr 1` (native; not remix). Forces DLSS mode + frameGeneration off
- Launch: `tools/launch-retribution-rt.cmd` (remix RR script disabled)

**Playtest (2026-08-02):** Native RR much less noisy than A-SVGF on Retribution MAP01.

**MVP out of scope:** Frame Gen + RR, specular motion vectors, Remix path fix.

---

## Intermittent noisy PT + blocky HUD (2026-08-03)

**Symptom:** Sometimes clean with DLSS-RR; sometimes salt-and-pepper noise while moving and HUD/text as solid blocks. Texture gallery captures showed RTGL1 Dev **Upscaler = Linear/Nearest** and often **Downscale to pixelized** checked, despite `+rt_upscale_dlss 2 +rt_rayreconstr 1`.

**Cause:** `Devmode::drawInfoOvrd` fields (`enable`, `pixelizedEnable`, `upscaleTechnique`, …) had **no default initializers**. After `make_unique<Devmode>()`, `Override` randomly came up true with garbage Linear/Nearest + pixelized, overriding the game’s DLSS-RR request.

**Fix:** `deps/RTGL/Source/VulkanDevice_Dev.h` — value-init all `drawInfoOvrd` / `cameraOvrd` members (`enable=false`, `pixelizedEnable=false`, DLSS balanced defaults). Rebuild: `tools/build-rtgl.cmd` (staged 2026-08-03).

**Workaround if it returns:** In RTGL1 Dev, uncheck **Override**; Upscaler should follow NVIDIA DLSS from cvars.

---

## Directional white wash mistaken for sky leak (2026-08-03)

**Symptom:** MAP99 gallery — walls stay solid but looking some yaws washes surfaces white / noisy. Felt like sky leak. Also: subtle glow **toward the gallery center from every approach** when walking around the hall.

**A/B (yaw sweep):** `tools/run_gallery_yaw_sweep.ps1` — 8 shots at 45°. Sky on/off and `rt_autoexport_light 0` **did not** remove west-facing outliers. `rt_emis_mapboost 0` **did** — delta ~88 → ~2. Lowering mapboost only masked the bug.

**Root cause:** In `HitInfo.inl`, when an `_e` map is present, path-traced emission used **raw `_e` RGB and ignored `emissiveMult`**. Indirect then multiplied by global `emissionMapBoost` (default 200). Dense / large world emitters (lava, CRT, glow panels) flooded GI whenever many faced the camera — including every inward view toward the gallery center. Raster already applied `emissiveMult`; PT did not.

**Fix (RTGL):** `deps/RTGL/Source/Shaders/HitInfo.inl` — on **INDIR** only, `emission = _e * emissiveMult`. Primary/reflections keep raw `_e` for on-screen glow (`rt_emis_maxscrcolor`). World mats author **low** `emissiveMult` (≈0.005–0.02) via `gen_world_emissives.py`. Launchers restore stock `+rt_emis_mapboost 200`.

**QA:** `tools/test_gallery_emis_qa.cmd` (orbit-inward + center yaw at boost 200). Rebuild: `tools/build-rtgl.cmd`.

**Follow-up (same day, still open):** Playable wall blotches returned after restoring `_e` even with mults cut to ~0.0005 and `lightIntensity` removed. Emis-off nuclear A/B still clears them. Full evidence, stale-SPV/DLL notes, and next experiments: **`gallery-emis-wall-wash-diagnostics.md`**.

---

## `emissiveMult` > 1 was a no-op (2026-08-03)

**Symptom:** Emis gallery monitors/keys cast almost no PT light even with `emissiveMult` 2–4 and tight `_e`. Doubling mult changed nothing.

**Root cause:** `TextureMetaManager::Modify` did `prim.emissive = Utils::Saturate(meta->emissiveMult)`, clamping to **[0, 1]**. So 1.25, 2.1, and 4.2 all became **1.0** in the BLAS instance. INDIR (`_e * mult * mapboost`) could not get stronger than mult=1. Low wash-QA mults (0.004) still worked because they are < 1.

**Fix:** `deps/RTGL/Source/TextureMeta.cpp` — use `std::max(0.f, meta->emissiveMult)` (no upper Saturate). Rebuild: `tools/build-rtgl.cmd`.

**Follow-up:** `ASManager.cpp` still did `emissiveMult = Utils::Saturate(primitive.emissive)` when writing the BLAS instance — so TextureMeta’s >1 values were clamped again to 1.0. Same fix there. Yellow key GI looked red because `_e` used brownish albedo RGB `(87,61,0)`; keys now tint via authored `lightColor` through a luma mask.

**Side effect (MAP01 wash):** once >1 worked, authored SMON/EXIT mults (~4.2 / 2.5) over-drove GI. Dialed walls back to ~1.0 in `gen_world_emissives.py`.

## GZDoom dynamic lights missing in RT (2026-08-03)

**Symptom:** MAP01 spawn blinking lights over the starting zombies were gone in path tracing.

**Clarification (2026-08-03):** The desired blink is the **ceiling head lights** (`SFLATAS` over the first enemies), **not** the wall SMON terminals. MAP01 9802 `PointLightFlicker` things sit in SMON alcoves (wall-side greens).

**Wrong first try:** Restoring `rt_sector_flicker` + amplifying 9802 made wall terminals pulse — rejected.

**Ceiling lamp fix:** `RT_UploadCeilingInsetLamps()` uploads warm-white shadow-casting spheres under `SFLATAS` / `SFLATAQ` / `SFLATAP` / `SPORT*` ceilings with irregular flicker. Cvars: `rt_ceiling_lamps`, `rt_ceiling_lamp_intensity` (**900**), `rt_ceiling_lamp_radius` (0.08), `rt_ceiling_lamp_zofs` (8), `rt_ceiling_lamp_debug`. Play launcher: `+rt_ceiling_lamps 1`, `+rt_sector_flicker 0`, `+rt_dynlight_flicker 0` (skips 9802 wall flashers). Surface `_e` from `gen_world_emissives.py` still provides the bright blob albedo; analytic lights blink/cast.

**Why `rt_sector_lights 1` did not blink the ceilings:** MAP01 booth `SFLATAS` sectors have special **0** and steady lightlevel 200. Sector lights only *blink* where lightlevel animates — the SMON alcoves (`dLight_Flicker` **65**). So enabling all-sector lights adds steady fill; wall blink still came from 9802/alcove specials.

**Dynlights (9802) still uploaded** via `RT_UploadGzDoomDynamicLights()` for map lights elsewhere. Cvars: `rt_dynlight`, `rt_dynlight_intensity`, `rt_dynlight_radius`. Stable `uniqueID` from light pointer. Rebuild: `tools/build-gzdoom-rt.cmd`.

**Do not** restore blink by painting teal/cyan panel `_e` on SMON — that only dirties the screens. SMON `_e` = tight BM + albedo RGB LEDs only.

**Lingering fake wash:** stock also called `RT_UploadExportableSectorLights()` every frame (even with `rt_autoexport 0`), planting a white sphere (intensity 200) at **every sector center**. Gated behind `rt_sector_lights` (**default false**); play launcher sets `+rt_sector_lights 0`. Optional `rt_sector_flicker` remains for flicker/strobe sector centers when wanted — **off** on play launcher so it doesn’t fake wall-terminal blink.

**Debug lights as blobs:** `rt_dynlight_debug 1` uploads magenta marker spheres at each GZDoom dynlight; `rt_dump_dynlights` lists positions. No stock RTGL “all lights as sprites” overlay — closest Dev UI is Light grid / Direct vs Indirect diffuse.

## Horror RT flashlight + battery (2026-08-03)

**Where:** `RT_AddFlashlight()` in `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp`.

**Look:** dimmer default intensity **90**, warm color `rt_flsh_color` **0xFFBE82**, wider cone `rt_flsh_angle` **42**, tip toward ground via `rt_flsh_pitch` **22**.

**Battery** (`rt_flsh_battery` default true): ~30s on (`rt_flsh_on_secs`) → last ~4s dying flicker (`rt_flsh_die_secs`, hard blackouts) → ~5s recharge off (`rt_flsh_off_secs`) → repeat. Jitter via `rt_flsh_jitter`. Engine writes HUD readouts `rt_flsh_charge` (0..1) and `rt_flsh_battstate` (0=off 1=on 2=dying 3=recharge).

**HUD:** `d64r-rt-flashlight.pk3` (`tools/d64r-rt-flashlight/`, pack with `python tools/pack_rt_flashlight.py`) — bottom-left battery bar. Loaded by `tools/launch-retribution-rt.cmd`. Toggle beam with `rt_flsh 1`.

