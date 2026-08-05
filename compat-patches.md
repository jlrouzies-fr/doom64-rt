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

**Fix pack:** `d64r-3dfloor-rtfix.wad` — every Retribution map that had `Sector_Set3dFloor` (special 160) stripped (**28 maps / 161 linedefs**, 2026-08-05). Keeps `BEHAVIOR`/`ZNODES`. Loaded via `tools/launch-retribution-rt.cmd`. Regen: `python tools/make_map_3dfloor_rtfix.py`. Side effect: 3D-floor visuals won’t appear until an engine-side RT 3D-floor fix exists. Per-map copies `d64r-mapNN-rtfix.wad` also written for debugging.

**Must include `BEHAVIOR` (+ `ZNODES`):** a TEXTMAP-only replacement stripped ACS → every switch that calls script 19 printed `P_StartScript: Unknown script 19`. Fix wad carries original `BEHAVIOR`/`ZNODES` with the patched `TEXTMAP` (3D-floor special cleared). Do **not** ship a mis-offset PWAD (lump directory offsets must be absolute from file start — a bad rewrite once made TEXTMAP = nested `PWAD` header → `Unexpected character ASCII 5` / invalid ACS).

---

## Automatic RT opacity / emissive (2026-08-02)

See-through walls under full RT (`rt_classic 0`) were largely soft/garbage PNG alpha + RT always alpha-testing world geometry.

**Engine (`rt_main.cpp`, `rt_mod_compat`):**
- Force opaque alpha on world texture uploads (RGBA PNGs are always `Masked` in GZDoom — that check was a no-op)
- World geometry (`ExportMap`): **never** alpha-test under mod_compat (sprites still do)
- Force vertex color alpha=1 for all world draws
- **Force world vertex RGB=white** under `rt_mod_compat` (2026-08-04): sector `lightlevel`/`lightcolor` must not bake into PT albedo — MAP02 yellow key-door sectors looked neon-emissive; lightlevel-0 rooms absorbed flashlight / ceiling lamps. Classic raster still uses `classicLight`. **Follow-up:** doors/lifts are **not** `ExportMap` (movable) so the first pass missed them — white RGB now applies to all non-sprite world prims.
- **Force sprite/weapon unlit albedo** under `rt_mod_compat` (2026-08-05): same lightlevel-0 bake left enemies + HUD weapon as black silhouettes (`screen/level2blackroomsprites.png`) after world was fixed. Keep `uObjectColor` (ThingColor / weapon ObjectColor); ignore `uVertexColor` RGB (sector shading). Alpha unchanged.
- **Invisible pinkies pure-invisible** under `rt_mod_compat` (2026-08-05): Retribution `64Spectre` is `STYLE_Translucent` + `A_SetTranslucent` (not Fuzz/Shadow). Sprite path always forced `ALPHA_TESTED`, so low vertex alpha cut the whole mesh. Soft blends (`Translucent` / additive / classic spectre) now upload as `TRANSLUCENT` instead. Rebuild gzdoom.
- **Pinkies still too ghostly** (2026-08-05): after translucent upload, See-state `A_SetTranslucent(0.20)` is legible in classic HW but nearly clear under PT alpha blend. Floor soft-blend (`STYLEOP_Add` + `InvSrc`) sprite alpha via `rt_translucent_minalpha` (**0.55**). Additive (muzzle/LS) not floored.
- **MAP04 hanging tech lamps dark** (2026-08-05): first room uses `LMP1`/`LMP2` SPAWNCEILING props (ed 1015/1016) with **no** co-located PointLights; ceiling is `SFLATAB` (not `SFLATAS` inset path). `RT_UploadHangingTechLamps()` places warm amber spheres at each LMP actor. Cvars: `rt_hang_lamps`, `rt_hang_lamp_intensity` (**320**), `rt_hang_lamp_radius` (0.09), `rt_hang_lamp_zofs` (10), `rt_hang_lamp_debug`.
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

**Ceiling lamp fix:** `RT_UploadCeilingInsetLamps()` uploads warm-white shadow-casting spheres under `SFLATAS` / `SFLATAQ` / `SFLATAP` / `SPORT*` **ceilings** with irregular flicker. Floor lamp panels cast via texture `_e` × `emissiveMult` (no floor analytic lights — looked bad). Cvars: `rt_ceiling_lamps`, `rt_ceiling_lamp_intensity` (**450**), `rt_ceiling_lamp_radius` (0.10), `rt_ceiling_lamp_zofs` (8), `rt_ceiling_lamp_off` (**0.12**), `rt_ceiling_lamp_fade` (**8**), `rt_ceiling_lamp_debug`. Play launcher: `+rt_ceiling_lamps 1`, `+rt_sector_flicker 0`, `+rt_dynlight_flicker 0`.

**RR / hard blink (2026-08-05):** Under DLSS-RR, A-SVGF is skipped — hard extinguish + removing the light from the upload list each blackout frame destroyed ReSTIR temporal matching and showed as unfiltered-direct sparkle in the final image (ASVGF looked stabler — expected). Fix: always upload a stable `uniqueID`, ease intensity over `rt_ceiling_lamp_fade`, keep a dim floor via `rt_ceiling_lamp_off`. Same lesson as `rt_mzlflsh_fade`. Peak restored to **700** once RR boiling landed.

**RR boiling filter (2026-08-05) — REVERTED:** Screen-space boiling / sample clamps corrupted the noise distribution RR expects and made IQ worse. Do not re-enable.

**RR temporal prefilter (2026-08-05) — FAILED:** Feeding A-SVGF temporal into ComposeNoisy/`DLSS-RR` produced a **faded duplicate / ghost depth-like view** (`screen/rrasvgghost.png`). Likely double reprojection and/or checkerboard vs regular sampling mismatch. **`AccumulateForRR` removed** from RR frame path; cvar **`rt_rr_temporal 0`**. Soft analytic-light fades remain the safe lever. See `rr-noise-investigation.md`.

**Black world / muzzle-only (2026-08-05) — FIXED:** After removing the writer, `CmNoisyCompose` could still read DiffTemporary when `rrTemporalPrefilterEnabled` was set → empty lighting → black PT world; raster fire sprites still drew. Fix: delete temporal branch from `CmNoisyCompose` (always unfiltered); force Dev Override off; rebuild `tools/build-rtgl.cmd`. Do not re-add a Compose temporal reader without a matching every-frame writer.

**Why `rt_sector_lights 1` did not blink the ceilings:** MAP01 booth `SFLATAS` sectors have special **0** and steady lightlevel 200. Sector lights only *blink* where lightlevel animates — the SMON alcoves (`dLight_Flicker` **65**). So enabling all-sector lights adds steady fill; wall blink still came from 9802/alcove specials.

**Dynlights (9800) still uploaded** via `RT_UploadGzDoomDynamicLights()` for map lights elsewhere. Cvars: `rt_dynlight`, `rt_dynlight_intensity`, `rt_dynlight_radius`, **`rt_dynlight_max`** (default **500**), **`rt_dynlight_stack_atten`** (default on — divide by co-located XY count). Retribution key-door jambs stack 3× yellow PointLights; without stack atten + cap they bloom nuclear-white under PT. Rebuild: `tools/build-gzdoom-rt.cmd`.

**Do not** restore blink by painting teal/cyan panel `_e` on SMON — that only dirties the screens. SMON `_e` = tight BM + albedo RGB LEDs only.

**Lingering fake wash:** stock also called `RT_UploadExportableSectorLights()` every frame (even with `rt_autoexport 0`), planting a white sphere (intensity 200) at **every sector center**. Gated behind `rt_sector_lights` (**default false**); play launcher sets `+rt_sector_lights 0`. Optional `rt_sector_flicker` remains for flicker/strobe sector centers when wanted — **off** on play launcher so it doesn’t fake wall-terminal blink.

**Debug lights as blobs:** `rt_dynlight_debug 1` uploads magenta marker spheres at each GZDoom dynlight; `rt_dump_dynlights` lists positions. No stock RTGL “all lights as sprites” overlay — closest Dev UI is Light grid / Direct vs Indirect diffuse.

## Horror RT flashlight + battery (2026-08-03)

**Where:** `RT_AddFlashlight()` in `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp`.

**Look:** dimmer default intensity **90**, warm color `rt_flsh_color` **0xFFBE82**, wider cone `rt_flsh_angle` **42**, tip toward ground via `rt_flsh_pitch` **22**.

**Battery** (`rt_flsh_battery` default true): ~30s on (`rt_flsh_on_secs`) → last ~4s dying flicker (`rt_flsh_die_secs`, hard blackouts) → ~5s recharge off (`rt_flsh_off_secs`) → repeat. Jitter via `rt_flsh_jitter`. Engine writes HUD readouts `rt_flsh_charge` (0..1) and `rt_flsh_battstate` (0=off 1=on 2=dying 3=recharge).

**HUD:** `d64r-rt-flashlight.pk3` — ForceScaled **320×240 KeepRatio** (same as SBARINFO): `BATTERY` + muted cased 5-cell bar in a column **left of HEALTH**, same baselines (y=208/217). No full-bleed stretch (that clipped `ATTER`). Pack: `python tools/pack_rt_flashlight.py`. Toggle `rt_flsh 1` / **F**.

## DLSS-RR residual sparkle + switch ON emis (2026-08-03)

**RR sparkle:** With native DLSS-RR, RTGL calls `Denoiser::ComposeNoisy` and skips A-SVGF `Denoise()`, so stock `CmAntiFirefly` never ran. Residual sparkle after muzzle/dynlights die came from unclamped ReSTIR outliers feeding RR history.

**Fix:** Screen-space neighborhood firefly clamp inside `deps/RTGL/Source/Shaders/CmNoisyCompose.comp` (gated by `rrNoisyAntiFireflyEnabled`). **Default OFF** — always-on clamp hurt temporal stability while moving. A/B: Dev window **DLSS-RR A/B** (sticky override) or `rt_rr_noisy_antifirefly`. Rebuild RTGL via `tools/build-rtgl.cmd`.

**Engine (gzdoom-rt):** `rt_illum_sens_direct/indirect/spec` (indirect default **0.75**). `rt_mzlflsh_fade` (default 5 tics). `rt_rr_noisy_antifirefly` (default false).

**Switches:** `gen_world_emissives.py` allowlists GLDEFS ON frames (`SWXSAB`, `SWXSFB`, …). GLDEFS `BMTX*` brightmaps are **missing** from the pk3 — masks use albedo chroma (green/red/magenta LED only) + upper connected-component filter, albedo RGB kept, `emissiveMult` 0.4, no `lightIntensity`. Idle A frames stay dark.

## RTGL Dev: font scale, settings persist, Materials A/B (2026-08-04)

**Font:** General → **UI font scale** (`FontGlobalScale`, base TTF 15px).

**Persist:** All Dev knobs (Override Present, RR / Denoise live sticky, Materials A/B, camera overrides, etc.) → `rt/devmode_settings.json`. Window layout → `rt/imgui.ini`. Debounced save (~2s after edit) + save on destroy. **Reset Dev settings to defaults** clears Override/sticky/kills (or delete the JSON). Stuck Linear/Nearest after a bad Override persist → use Reset.

**Materials A/B** (live, no Override): strip toggles + **Roughness toward matte** (`mix` authored→1; replaces useless min-floor post ORM clamp). Flags: bit0=N, bit1=emis, bit2=metallic, bit3=H, bit4=roughness. Rebuild: `tools/build-rtgl.cmd` (now always `-gencomm`).

**RR walk noise (2026-08-04):** User A/B confirmed **ORM roughness (G)** (not metallic). Fixed by `tools/fix_orm_roughness.py` (dielectric G≥0.82, metal≥0.55, blur-always) — now **`--all`** (763 maps). Metallic: `tools/fix_orm_metallic_ai.py --all --force` with stricter demotion (painted SPACE → dielectric; **0 kept as metal**, 545 dielectric / 218 mixed). Dev **Roughness toward matte** stay at **0** for play (0.5 only temporary A/B — do not ship as default).

## Spectre rendering: water/glass → TRANSLUCENT raster + minalpha floor (2026-08-05)

**Symptom:** SAR2 / 64Spectre sprites were squares of refractive water/glass, then opaque PT sprites — neither was the desired see-through purple-dark alpha look.

**Root cause (water squares):** `IsSpectre()` grouped with additiveBlend — both used `RG_MESH_PRIMITIVE_TRANSLUCENT` + `alphaTest=false`. FORCE_WATER/GLASS/MIRROR kept the mesh in PT but without alpha test the full quad showed refractive material.

**Fix (`rt_main.cpp`, final):**
- Split `IsSpectre()` from additiveBlend
- Spectres use `RG_MESH_PRIMITIVE_TRANSLUCENT` (rasterized overlay) — sprite texture RGB + alpha blending gives the see-through look
- `l_makeSpectreFlags()` stripped of FORCE_WATER/GLASS/MIRROR; only `RG_MESH_FORCE_IGNORE_REFRACT_AFTER` remains
- `rt_translucent_minalpha` (0.72) finally wired into `l_spriteAlpha()` — floors the vertex alpha so `A_SetTranslucent(0.20)` doesn't render ghostly-clear
- `rt_spectre` / `rt_spectre_invis1` cvars marked **deprecated**
- `IsSpectre()` removed from `forcealpha1` (vertex alpha should be real, not forced 1.0, for raster blending)

**Result:** Sprite-shaped, see-through purple-dark spectres (pinkies semi-transparent, nightmare imps purple-dark). No water/glass. Rebuild: `tools/build-gzdoom-rt.cmd`.

