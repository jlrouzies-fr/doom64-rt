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

**Fix pack:** `d64r-3dfloor-rtfix.wad` — every Retribution map that had `Sector_Set3dFloor` (special 160) stripped (**44 maps / 209 linedefs**, 2026-08-13; was 28/161 while the scan was `MAP\d\d`-only). Keeps `BEHAVIOR`/`ZNODES`. Loaded via `tools/launch-retribution-rt.cmd`. Regen: `python tools/make_map_3dfloor_rtfix.py`. Side effect: 3D-floor visuals won’t appear until an engine-side RT 3D-floor fix exists. Per-map copies `d64r-<mapname>-rtfix.wad` also written for debugging.

**The extra campaigns were never covered (2026-08-13).** `list_map_names()` matched
`MAP\d{2}`, so the five bonus episodes — whose lumps are `FUN00`, `ABS01`–`ABS06`,
`OUT01`–`OUT10`, `RDM01`–`RDM08`, `REC01`–`REC09`, `RTR01`–`RTR10` — kept their 3D
floors and froze on New Game exactly like MAP01 used to: black screen, "Not
Responding", process alive. Reported as **Bonus Fun Maps and Absolution Levels crash
while Outcast and Redemption work**; that split is content, not category — a map only
freezes if its 3D floor is heavy enough, so OUT01/RDM01 have 160s and survive.
Map markers are now detected structurally (a zero-length lump followed by
`TEXTMAP`/`THINGS`), which also picks up any future map whatever its name.

Two things that will mislead you here:

- **`+map FUN00` does NOT reproduce it.** Both maps boot and render fine when warped
  to directly; the freeze only appears on the TITLEMAP → level transition the New Game
  menu takes. Test the menu route or you will conclude the maps are fine.
- **The log stops after `Can't find a file, no static scene will be present`** and
  that same line is the last one on a *healthy* level load too, so it is not a marker.
  The only reliable tell is `MainWindowTitle` going to "(Not Responding)".

**Must include `BEHAVIOR` (+ `ZNODES`):** a TEXTMAP-only replacement stripped ACS → every switch that calls script 19 printed `P_StartScript: Unknown script 19`. Fix wad carries original `BEHAVIOR`/`ZNODES` with the patched `TEXTMAP` (3D-floor special cleared). Do **not** ship a mis-offset PWAD (lump directory offsets must be absolute from file start — a bad rewrite once made TEXTMAP = nested `PWAD` header → `Unexpected character ASCII 5` / invalid ACS).

---

## Automatic RT opacity / emissive (2026-08-02)

See-through walls under full RT (`rt_classic 0`) were largely soft/garbage PNG alpha + RT always alpha-testing world geometry.

**Engine (`rt_main.cpp`, `rt_mod_compat`):**
- Force opaque alpha on world texture uploads (RGBA PNGs are always `Masked` in GZDoom — that check was a no-op)
- World geometry (`ExportMap`): **never** alpha-test under mod_compat (sprites still do)
- Force vertex color alpha=1 for all world draws
- **Force world vertex RGB=white** under `rt_mod_compat` (2026-08-04): sector `lightlevel`/`lightcolor` must not bake into PT albedo — MAP02 yellow key-door sectors looked neon-emissive; lightlevel-0 rooms absorbed flashlight / ceiling lamps. Classic raster still uses `classicLight`. **Follow-up:** doors/lifts are **not** `ExportMap` (movable) so the first pass missed them — white RGB now applies to all non-sprite world prims.
- **Restore MAP02 blue armor-room filter** (2026-08-07): `FRtState` carries the active `FColormap.LightColor` from flats, walls, and 3D-light wall slices. `rt_main.cpp` applies a bounded blue surface tint only when the map name contains `map02` and the original color matches the room's `0x0050FF` profile (low red, medium green, high blue). Other maps and non-blue MAP02 sectors remain white under `rt_mod_compat`; no point light is created.
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

Remix RR (-rtxremix + 
t_remix_rayreconstr) blacks out Retribution. Native path only had A-SVGF.

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

**RR temporal prefilter (2026-08-05) — FAILED:** Feeding A-SVGF temporal into ComposeNoisy/`DLSS-RR` produced a **faded duplicate / ghost depth-like view** (`screen/rrasvgghost.png`). Likely double reprojection and/or checkerboard vs regular sampling mismatch. **`AccumulateForRR` removed** from RR frame path; cvar **`rt_rr_temporal 0`**. Soft analytic-light fades remain the safe lever. See `docs/rayreconstruction/rr-noise-investigation.md`.

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

**Persistent charge + sound cues (2026-08-10):** the cycle was phase-based (`s_phaseStart`/`s_phaseLen` measured from the moment the light came on), so **toggling the flashlight off and on restarted the on-phase at full charge** — a free refill, once per keypress. Replaced by a single persistent accumulator `s_charge` (0..1) advanced by real elapsed game tics (`dt`, clamped to 1s so a load or pause can't dump a cycle): drains at `1/rt_flsh_on_secs` while lit, refills at `1/rt_flsh_off_secs` during the forced post-burnout recharge, and **trickles up at `rt_flsh_idle_recharge` × that rate (default 0.25 → ~20s from empty to full while off, vs 5s forced) while switched off**. Dying flicker is now a charge threshold (`rt_flsh_die_secs / rt_flsh_on_secs`), not a phase tail; cycle durations are re-rolled when the cell reaches full, not on each keypress. Burnout still forces the light off until fully recharged, whatever the switch says.

New readout `rt_flsh_flicker` — a counter bumped every time the beam *starts* a fade-out (mid-cycle blink, dying gutter, burnout). The pk3's `WorldTick` watches it plus `rt_flsh_battstate` and plays `d64rt/flashlight/{out,flicker,on}` (`CHANF_UI`); mute/tune with `d64rt_flsh_sound` / `d64rt_flsh_sound_vol` (CVARINFO, client-side). The three cues are **synthesized**, not sampled — `python tools/gen_flashlight_sounds.py` writes `D64FLK{O,R,N}.wav` (22050 Hz mono, deterministic seed) into `tools/d64r-rt-flashlight/`, then re-pack. RR untouched: the light-cut edge detector still keys off the emitted scale, and `fadeValley()` ramps are unchanged.

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
- `rt_translucent_minalpha` (0.80) wired into `l_spriteAlpha()` — spectres use **cap** (`min(a, minalpha)`) so states that don't call `A_SetTranslucent` (pain/hit) also render semi-transparent; other soft-blend sprites use **floor** (`max(a, minalpha)`) so they don't render ghostly-clear
- `IsSpectre()` name check: **`SAR2*` only** (2026-08-05 fix). SARG = regular pinky demon, not spectre — the original `n[3]=='G'` guard was incorrect (attack frames are already covered by SAR2's own G frames)
- `rt_spectre` / `rt_spectre_invis1` cvars marked **deprecated**
- `IsSpectre()` removed from `forcealpha1` (vertex alpha should be real, not forced 1.0, for raster blending)

**Result:** Sprite-shaped, see-through purple-dark spectres (pinkies semi-transparent, nightmare imps purple-dark). No water/glass. Rebuild: `tools/build-gzdoom-rt.cmd`.

## Spectre emissive: uniform ADDITIVE ghost via textures.json (2026-08-05)

**Symptom:** After TRANSLUCENT fix, SAR2 front view was ghostly-wash (ADDITIVE pipeline from eye `_e` PNGs) but side/rear were solid translucent purple (no `_e` PNGs → emissive=0 → no ADDITIVE promotion). Pain state (SAR2 H frames) also broke — no `_e` PNGs, no textures.json entries.

**Root cause:** `RasterizedDataCollector` promotes TRANSLUCENT→ADDITIVE when `prim.emissive > 0`. The emissive value comes from `TextureMeta::Modify()` which sets `prim.emissive = max(0, emissiveMult)`. Without textures.json entries for side/rear + pain frames, emissive stayed at GZDoom's 0.0. The ADDITIVE gate checks the emissive VALUE, not `_e` PNG content.

**Fix (runtime data, no rebuild):**
- ALL 40 SAR2 sprites (A–G × 5 rotations + H × 5 rotations) have `emissiveMult: 2.0` in every textures.json layer (global + MAP01 overlay + enemy gallery + source files)
- Side/rear `_e` PNGs: **fully transparent** — ADDITIVE pipeline triggers via emissiveMult, visible emission is zero (no red dot)
- Pain H-frame `_e` PNGs: front (H1, H2H8) cloned from G-frame eye masks; side/rear transparent
- Launcher: removed `+fly`, added `+notarget`

See `spectre-issue-log.md` for full architecture and regeneration instructions.

## DLSS-RR disocclusion mask — transient-light ghosting fix (2026-08-06)

**Symptom:** Barrel explosions, muzzle flashes, and occluded glows lingered for seconds under DLSS-RR — RR's temporal history had no way to know the light was transient.

**Fix (GaetanRouzies/Claude Fable, merged upstream):**

**RTGL (`deps/RTGL`):**
- `CmNoisyCompose.comp` — tile-based (16×16) luminance comparison: motion-reproject per-tile mean of lighting-only luminance vs previous frame. On sharp change, writes sentinel 10000.0 to fbRrDisocclusion → RR drops history.
- `DLSSRR.cpp` — wires `pInDisocclusionMask`; `pInSpecularHitDistance=nullptr` (FB_DEPTH_WORLD was primary-hit distance, not reflection ray length — wrong guide corrupts specular reprojection).
- `Denoiser.cpp` — barriers for `FB_IMAGE_INDEX_RR_DISOCCLUSION` + `FB_IMAGE_INDEX_RR_LUM_HISTORY`.
- `BRDF.h` — `envBRDFApprox2()` column-major GLSL port (Ray Tracing Gems ch.32). Corrected RR guides: diffuseAlbedo = ro_d × mod; specularAlbedo = envBRDF × mod.
- Rebuild: `tools/build-rtgl.cmd` (2026-08-06).

**gzdoom-rt (`sourcecode/gzdoom-rt`):**
- `rt_main.cpp` — cvars: `rt_rr_disocc` (on), `rt_rr_disocc_ratio` (3.0), `rt_rr_disocc_mindelta` (0.01), `rt_rr_disocc_show` (debug).
- Rebuild: `tools/build-gzdoom-rt.cmd` (2026-08-06).

**Follow-up (2026-08-06, same day):** the mask above produced zero visible
effect — see `docs/rayreconstruction/flashlight-linger-issue.md` for the (superseded) investigation
and `docs/rayreconstruction/flashlight-linger-fix-plan.md` for the corrected diagnosis. Landed
instead: pulse `RgDrawFrameInfo.resetHistory` (already-wired, previously
unused → `DLSSRR.cpp` `evalParams.InReset`) on an abrupt transient-light edge,
gzdoom-rt only, no RTGL rebuild.

- `rt_main.cpp` — new cvars `rt_rr_reset_on_lightcut` (on, flashlight edge),
  `rt_rr_reset_delta` (0.5), `rt_rr_reset_on_dynlight` (on, any GZDoom dynlight
  appearing/disappearing — barrel/rocket explosions, pickups; muzzle flash
  intentionally excluded, too frequent, has its own `rt_mzlflsh_fade`),
  `rt_rr_reset_min_ms` (250, rate limit), `rt_rr_reset_hold` / `rt_rr_reset_now`
  (diagnostics). `RT_AddFlashlight` and `RT_UploadGzDoomDynamicLights` both set
  a shared `g_rt_lightcut` flag (declared near `FlashlightLightId`, not beside
  `g_resetposteffects`, for inline-method lookup reasons); `RT_OnLevelLoad`
  sets it unconditionally. Consumed once per frame in
  `RTFrameBuffer::RT_DrawFrame`.

## DLSS-RR was compiled out of RTGL1.dll (2026-08-06)

**Symptom:** every DLSS-RR cvar and experiment above produced *zero* difference,
and the image showed raw ~1-spp noise. Diagnosed as: there was no denoiser at
all. `deps/RTGL/CMakeLists.txt` gated the DLSS block on
`if (RG_WITH_NATIVE_DLSS AND DEFINED ENV{DLSS_SDK_PATH})`, but the SDK path had
been passed as a CMake *variable* (`-DDLSS_SDK_PATH=...`), for which
`DEFINED ENV{...}` is false. So `RG_USE_NATIVE_DLSS2` was never defined,
`nvsdk_ngx_d.lib` never linked, and `DLSSRR.cpp` compiled to its empty `#else`
stub — `nvDlssRr` permanently null. No build error, no link error, and no
runtime log either (the `"DLSSRR: ..."` strings live inside the compiled-out
branch, so even `-rtdebug` printed nothing). Meanwhile gzdoom still *requested*
RR (`nvDlss` survives on DLSS3-FG availability alone), and
`VulkanDevice.cpp:798` skips A-SVGF whenever RR is requested — so both denoisers
were off.

**Fix:**
- `deps/RTGL` `f133bda` — accept `DLSS_SDK_PATH` from env **or** `-D`;
  `FATAL_ERROR` if the path is set but `nvsdk_ngx.h` is missing; loud
  `message(WARNING)` if `RG_WITH_NATIVE_DLSS=ON` with no path. Note CMake had
  cached the poisoned value (`DLSS_SDK_PATH:UNINITIALIZED=...`), so every
  rebuild silently reused it — clear the cache when changing this.
- `sourcecode/gzdoom-rt` `d19782c36` — `rt_rr_status` CCMD printing the whole RR
  decision chain (request, upscale mode, Remix flag, DLSS2/DLSS3-FG availability
  + RTGL failure reasons, resulting flag). This is what surfaced the bug; use it
  first whenever RR behaves unexpectedly.

To check a DLL for these symbols on this box, use PowerShell
(`[Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($p))`) — there is no
`strings` binary, and `strings` under bash silently returns nothing, which looks
exactly like a real negative.

## DLSS-RR: pulse lights fired a history flush every frame (2026-08-07)

**Symptom:** with RR genuinely running, the image was stable (lingering fixed)
but noisier than A-SVGF.

**Cause:** `RT_UploadGzDoomDynamicLights` recorded a light's stable ID into the
frame-over-frame presence set *after* the brightness cutoffs
(`m_currentRadius <= 0.01f`, scaled `intensity <= 0.01f`, black colour). A
Pulse/Flicker light dipping under one for a few tics left the set and re-entered
it, which reads as a scene-lighting cut and fires `InReset` — up to every frame.
Invisible to the earlier `rt_dynlight_debug` check because that prints the
*count*, and one ID leaving as another enters keeps the count flat while
`curDynIds != s_prevDynIds` is still true.

**Fix (`sourcecode/gzdoom-rt` `bbe1d1b85`, gzdoom-rt only, no RTGL rebuild):**
record presence right after the *static* eligibility checks, so it means "this
`FDynamicLight` exists and is active". Genuine appear/disappear events
(explosion flashes, pickups) still fire. Adds `rt_rr_reset_debug` — per-flush
cause logging, throttled dynlight `+N/-M` deltas, and a once-a-second
fired/suppressed tally.

**Related trap:** every `RT_CVAR` is `CVAR_ARCHIVE` (`rt_main.cpp:84`), so a
diagnostic left at `1` in one console session persists in the ini and silently
poisons every later A/B test — `rt_rr_reset_hold 1` did exactly this for a whole
session. `tools/launch-retribution-rt.cmd` now forces
`rt_rr_reset_hold/_now/_debug` to 0 on launch.

**In-game (2026-08-07):** confirmed genuinely more stable, no more light
linger. Did **not** explain noise reported at MAP02 spawn — that's a different
light system entirely, see next entry.

## DLSS-RR: ceiling-lamp intensity swing too abrupt for ReSTIR (2026-08-07)

**Symptom:** persistent salt/noise localized right at 4 lights blinking near
MAP02 spawn, unaffected by `rt_dynlight 0`, `rt_sector_lights`, or
`rt_emis_maxscrcolor 0` — none of which gate this code path.

**Cause:** `rt_ceiling_lamps` (`rt_main.cpp:4089+`) is a third, independent
synthetic-light system — analytic lights placed under ceiling textures named
`SFLATAS`/`SFLATAQ`/`SFLATAP`/`SPORT*` (MAP02 SFLATAQ corridors explicitly
named in a comment), each blinking on its own per-sector phase. The light
swings ~33x in intensity (`rt_ceiling_lamp_intensity` 700 down to
`peak * rt_ceiling_lamp_off * 0.25` ≈ 21) but is deliberately *never removed*
from the ReSTIR/RR list (avoids the history-reset noise a hard on/off would
cause). At the old default `rt_ceiling_lamp_fade` = 8 tics (~0.2s), that swing
is too fast for ReSTIR's temporal reservoir reuse to track, producing salt
concentrated at the lamp every cycle.

**Fix (`sourcecode/gzdoom-rt` `5b36421d3`, gzdoom-rt only, no RTGL rebuild):**
`rt_ceiling_lamp_fade` default raised 8 → 40 tics (~1.1s), spreading the same
swing thin enough for ReSTIR to track smoothly. Also updated in
`tools/launch-retribution-rt.cmd`, which was pinning the old value explicitly.
Sibling system `rt_hang_lamps` (`rt_main.cpp:4307+`) uses a hard on/off, not
this swing — not touched, but worth checking if similar localized noise shows
up at hanging lamps on other maps.

**Caveat (2026-08-07):** the in-game observations that motivated this ran with
DLSS-RR **off** — see the next entry. The lamp swing is a real defect and the
fix targets ReSTIR (upstream of both denoisers), so it stands, but its effect
under RR specifically has never been measured.

## RTGL Dev UI silently overrode rt_rayreconstr, persistently (2026-08-07)

**Symptom:** `rt_rayreconstr 0` vs `1` did nothing. DLSS-RR was off through an
entire multi-session investigation *into DLSS-RR*; every "RR is stable / noisy /
fixed" observation actually measured A-SVGF.

**Cause:** `rt/devmode_settings.json` persisted `ovrd_enable`,
`rayReconstruction` and `rayReconstructionSticky` across launches. In
`VulkanDevice_Dev.cpp`, `Dev_Override` applies the sticky RR value **even when
the Override master switch is off**:

```cpp
else if( devmode->rayReconstructionSticky )
{
    resolution.rayReconstruction = devmode->rayReconstruction;  // stomps rt_rayreconstr
}
```

Sticky is set by either Dev-UI RR checkbox and cleared only by the "Follow game
(rt_rayreconstr)" button. Touching that checkbox once disabled the cvar in every
subsequent launch. The live "works without Override" behaviour is intentional;
persisting it across launches is the bug.

`ovrd_enable = true` compounded it by force-replacing `emissionMapBoost`,
`emissionMaxScreenColor`, `normalMapStrength`, `heightMapDepth`,
`maxBounceShadows`, ev100 range, and the upscale/resolution/frame-gen params
every frame — so console cvars mapping to any of those were silently reverted.

**Why it stayed hidden:** `rt_rr_status` reports `g_rr_dbg_rrRequested`
(`rt_main.cpp:3290`), gzdoom's request, computed *before* the DLL's
`Dev_Override` runs. It printed `RR REQUESTED = YES` while RTGL forced RR off.

**Fix (`deps/RTGL`, needs `tools/build-rtgl.cmd`):**
- `ApplyDevmodeSettings` no longer restores `drawInfoOvrd.enable`,
  `rayReconstructionSticky`, `rrTemporalPrefilterSticky`, `illumSensSticky` —
  forced `false` on load. Override values still persist; only the switches that
  make them apply reset each launch.
- Edge-triggered `debug::Warning` when the applied RR value disagrees with the
  game's request (visible with `-rtdebug`).
- `rt_rr_status` now says outright that it reports a request, not applied state.

**Lesson (same shape as the `CVAR_ARCHIVE` trap above):** any diagnostic or
override that outlives the session which enabled it will eventually be mistaken
for normal behaviour. Persist the *value*, never the *switch*. And never treat a
"requested" readout as confirmation — instrument the applied state.

## Stale rt_upscale_fsr2 silently disabled DLSS-RR (2026-08-07)

**Symptom:** `rt_rayreconstr 0` vs `1` did nothing, even after fixing the Dev-UI
override above. DLSS-RR never ran.

**Cause:** `rt_upscale_dlss` and `rt_upscale_fsr2` both write
`RgStartFrameRenderResolutionParams::upscaleTechnique` in
`RT_UpscaleCvarsToRtgl`, and the FSR switch runs **second**:

```cpp
switch( nvDlss ) { case 2: pDst->upscaleTechnique = NVIDIA_DLSS; ... }
switch( amdFsr ) { case 2: pDst->upscaleTechnique = AMD_FSR2; ... }  // clobbers
```

`rayReconstruction` was set afterwards regardless, because that check only
tested `nvDlss != 0` and never rechecked that DLSS survived. gzdoom thus sent
RTGL `upscaler = FSR2` **and** `rayReconstruction = 1`;
`RenderResolutionHelper::Setup` resolves that contradiction by silently
clearing RR (it requires DLSS) and running A-SVGF.

Trigger: `rt_upscale_fsr2=2` persisted in
`Documents/My Games/GZDoom/gzdoom-rt2.ini` (default `0`). Every `RT_CVAR` is
`CVAR_ARCHIVE` and the launcher never reset it — the third instance of a
persisted archived cvar invalidating an entire run of tests.

**Fix (`sourcecode/gzdoom-rt` `23e12994b`):** upscalers made mutually exclusive
(DLSS wins when both are set, since RR requires it, with a one-time console
warning naming both cvars); `rayReconstruction` gated on the technique that
actually survived both switches; launcher forces `+rt_upscale_fsr2 0`.

**Three layers of silence had to be removed before this was observable** — each
is a fix in its own right:

| Layer | Effect |
|---|---|
| `RgInstanceCreateInfo::allowedMessages = 0` without `-rtdebug` | muted RTGL **WARNING and ERROR**; this is how "RR compiled out of the DLL" hid |
| `RT_Print` → `DPrintf( DMSG_WARNING, ... )` | second gate, needs gzdoom `developer >= 2` |
| nothing reported the *applied* state | `rt_rr_status` only ever showed the request |

Now: `WARNING\|ERROR` always allowed, warnings use `Printf`, and RTGL logs both
the incoming `Setup()` params and the resolved denoiser path (`RTGL 3e524bb`).

**Verified in-game:** `rt_rayreconstr 1` → `Denoiser path: DLSS-RR (ComposeNoisy
-> nvDlssRr->Apply)`; `rt_rayreconstr 0` → `Denoiser path: A-SVGF (Denoise)`.
First confirmation that DLSS-RR actually runs, and confirmation that root cause
\#1's CMake fix is good at runtime (`nvDlssRr` non-null).

**Lesson:** when two settings write one field, the second silently wins. Make
such pairs mutually exclusive and loud, and validate derived flags against the
value that actually survived — not against the input that motivated them.
- Rebuild: `tools/build-gzdoom-rt.cmd` (2026-08-06). No `deps/RTGL` changes.
## DLSS-RR tuning A/Bs with RR verified running (2026-08-07)

First experiments ever run with DLSS-RR confirmed active (see previous entry).
Both are recorded because both are **negative results** worth not repeating.

**RR preset D vs E** (`deps/RTGL` `0c73464`). `DLSSRR.cpp` pinned Preset E on all
five quality slots. A/B'd D (default transformer) against E (latest): **D was
clearly worse — visibly noisy even with a static camera**, where E converges
cleanly. E retained. Only D and E are usable at all; A/B/C were removed in SDK
310.4.0 and F..O silently revert to default. The five literals were collapsed to
one `RR_PRESET` constant and the live preset is now logged, so `rt_upscale_dlss`
can no longer change preset alongside resolution and confound an image A/B.

Incidentally the first *positive control* of the whole investigation: the change
visibly altered RR output, independently confirming settings reach NGX.

**Neighbourhood firefly clamp** (`deps/RTGL` `f2822e2`, `gzdoom-rt` `2a81d65d3`).
The RR path applies no prefilter whatsoever — `ComposeNoisy` hands raw 1-spp
radiance to NGX and `AccumulateForRR` is never called — while A-SVGF gets
anti-firefly plus a variance-driven à-trous. Remix runs an equivalent clamp, and
an `RTGL1.h` comment showed one existed here once and was replaced by the
now-inert temporal prefilter. Added back, deliberately conservative: a pixel is
scaled down only if it out-shines the *brightest* of its 4 spatial neighbours by
`rt_rr_firefly`, with uniform RGB scale so chroma is preserved and no blur added.

**Result: marginal noise reduction at best, and it ADDED a visible trail behind
the weapon sprite.** Mechanism is the instructive part — suppressing outliers
removes the local contrast RR uses to detect change, so RR over-trusts history
and ghosts. It trades noise for ghosting rather than fixing anything. Kept as a
documented knob, **off by default** (`rt_rr_firefly 0`), with the 12 neighbour
fetches guarded out of the default path.

Two implementation notes for anyone touching this shader:
- Neighbours are taken in **regular** pixel space then mapped through
  `getCheckerboardPix`. Stepping in checkerboard coords does *not* give spatial
  neighbours — the two halves interleave into alternating columns.
- The uniform fields reuse existing `_pad` slots, so the std140 layout is
  byte-identical. A C++↔GLSL layout mismatch is exactly the kind of silent
  corruption this investigation spent days chasing.

**Conclusion of the whole RR noise investigation:** see
`docs/rayreconstruction/rr-noise-investigation.md` §10. Short version — with a 1-spp input, anything
that buys stability pays in blur or lag; A-SVGF is the better denoiser for this
content, and that is now a choice rather than an accident.

---

## Stylized Doom 64 water (2026-08-10)

**Problem.** `D64W2_01` (MAP10/11/34) and `D64W1_01` (MAP08/14/15/16/22/23/30/34)
had no water treatment at all: they were plain rough materials, and the flat is
nearly black (mean luminance 8/255, brightest texel 48/255) so under path
tracing the water read as a hole in the floor rather than water. Handing them to
RTGL's existing water path is not the answer either — that path is physical
(refract into the media, Beer-Lambert absorb, mirror the rest) and reads far too
real next to Doom 64's art. It is also structurally wrong for these maps: both
are **opaque FLOOR flats**, there is no sector under them, so the refraction half
of the checkerboard split has nothing to show.

**Fix — a stylized branch in the refl/refr raygen** (`rt_water_style`, on by
default). Same entry point as stock water (`GEOM_INST_FLAG_MEDIA_TYPE_WATER`),
but the split is spent differently:

| | stock physical | stylized |
|---|---|---|
| odd checkerboard half | refraction into the media | **keep the lit water surface** in the G-buffer |
| even half | mirror reflection | mirror reflection (Fresnel clamped) |
| resolve | `F·refl + (1−F)·refracted` | `F·refl + (1−F)·lit surface` |

The surface half rewrites only the shading inputs and returns early —
`framebufAlbedo`, `framebufNormal` (the animated wave normal), a low
`framebufMetallicRoughness`, `framebufThroughput` (`(1−F)·2`, alpha 1 = split)
and the screen-emission sheen. Position, depth, motion and the visibility buffer
stay as the primary pass wrote them, because they already describe this exact
surface — so the direct/indirect passes (which run *after* refl/refr) light the
water plane like any other opaque surface, and the denoisers see a normal
primary hit.

The colour is rebuilt from the flat itself rather than invented:
`getStylizedWaterAlbedo()` takes the texture's own luminance as the caustic vein
mask (normalized by `rt_water_veinref`), brightens it with the wave-normal tilt
(`rt_water_caustic`), and mixes a deep blue body (`rt_water_tint_*`) toward a
pale-cyan crest. `rt_water_glow` adds a small **screen-space** sheen on the veins
so the pattern still reads in near-black rooms — it is on-screen emission only
and casts no light, so it cannot wash GI (see the emissive wash log above).

**Files:**
- `deps/RTGL/Source/Shaders/RaygenPrimary.inl` — `getStylizedWaterAlbedo()` + the
  `stylizedWater` branch in `RAYGEN_REFL_REFR_SHADER`. Gated to `i == 0` and a
  vacuum→water crossing; everything else keeps stock behaviour.
- `deps/RTGL/Source/Generated/GenerateShaderCommon.py` — 8 scalars + one vec4,
  two full groups so `viewProjCubemap` stays 16-byte aligned.
- `deps/RTGL/Include/RTGL1/RTGL1.h`, `Source/DrawFrameInfo.h`,
  `Source/VulkanDevice.cpp` — `RgDrawFrameReflectRefractParams` plumbing.
- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp` — `rt_water_style`,
  `rt_water_tint_r/g/b`, `rt_water_caustic`, `rt_water_reflmax`, `rt_water_rough`,
  `rt_water_glow`, `rt_water_veinref`. Also **un-hardcoded** `waterWaveSpeed`
  (was `0.05f`, "for partial_invisibility") and `waterTextureAreaScale` (was
  `1.0f`) as `rt_water_wavespeed` / `rt_water_areascale`. At 0.05 the wave field
  scrolls one texture cycle every few minutes — the caustics would not have
  shimmered at all. Both still also drive the partial-invisibility warp.
- `rt_main.cpp` `l_waterflag()` — **the flats are tagged engine-side**, by
  full texture-name match, ORed straight into `RgMeshPrimitiveInfo::flags`.
  It prints one unmuted `RT water: tagging "<name>"` line per distinct water
  texture per session.

  This started as the JSON route (`isWater` in `rt/data/textures.json`, via
  `tools/set_water_meta.py`) and that route could not be made to work or even to
  falsify: no water flag ever reached the shader, and RTGL's own diagnostics are
  gated behind **both** `-rtdebug` and its private `g_printSeverity`, so "the
  meta silently failed to apply" and "the meta applied and did nothing" produce
  byte-identical evidence. Tagging in the engine also survives the PBR tooling,
  which rewrites the gitignored `rt/data/textures.json` wholesale — the JSON tag
  had to be re-applied by hand after every regen. `set_water_meta.py` is kept
  (harmless, and still correct if the JSON route is ever wanted) but is no
  longer required.
- `tools/launch-retribution-rt.cmd` — all water cvars pinned explicitly.
- `tools/ab-water.cmd` — arms `stock` / `styl` / `flat` / `mirror` / `noglow` /
  `debug`, default MAP10. Every arm sets every water cvar, so nothing leaks via
  the ini. The `debug` arm paints water magenta (stylized branch running) or
  green (RTGL sees water, stylized gate rejected), and turns on `rt_prim_debug`.

Rebuild: `tools/build-rtgl.cmd` **and** `tools/build-gzdoom-rt.cmd` (new uniform
fields mean the generated `ShaderCommonC.h` changes, so the engine must be
rebuilt too, not just the shaders).

### Water tag was inert: D64W2_01 is one frame of a 64-frame animation (2026-08-10)

The stylized water above looked completely dead for several test runs, then
"flashed bright" on a regular cycle. Cause: **`D64W2_01` is not a texture.**
`ANIMDEFS` defines `texture D64W1_01` / `D64W2_01` as 64-frame sequences at 2
tics per frame, and `TEXTURES` defines all 128 composites. The map's sector
names frame 1, but GZDoom swaps the frame every 2 tics, so the name that
reaches RTGL is almost never `D64W2_01`.

Both tagging routes matched the exact name, so the surface was water for **2
tics out of ~128** — one frame per ~3.7s cycle. The shader was working the
whole time; it was switching off again immediately. RTGL's own
`GeomInfoManager` carries the warning: *"can't use texture / mesh name, as
texture can be just 1 frame of animation sequence"*.

**Rule for anything keyed on a Doom 64 texture name** (emissive meta, faux/solo
lamps, material overlays, this): check `ANIMDEFS` first and prefix-match the
sequence. An exact-name match on an animated flat produces a periodic flicker,
not a clean null — which is far harder to read as "the match is wrong".

Two instrumentation traps found on the way, both worth remembering:

- `RT_Print` in `rt_main.cpp` turns any RTGL **ERROR** into a modal
  `MessageBoxA` whose default action is `exit(-1)`. An ERROR-severity probe
  therefore kills the game at the first matching primitive. Use **WARNING**,
  which goes through `Printf`; `DPrintf( DMSG_ERROR, ... )` does not reach the
  log at all unless developer mode is on.
- RTGL's `debug::Info` is gated behind **both** `-rtdebug` and its private
  `g_printSeverity`, so "the meta silently failed" and "the meta applied and did
  nothing" produce byte-identical evidence. Any check that has to distinguish
  those needs a gzdoom-side `Printf`, not an RTGL message.

### Reflection strength is deliberately not physical

Water's F0 is ~0.02, so a correct Schlick term makes the reflection invisible
from anything but a grazing angle — the first version reflected sprites and
geometry perfectly, at a strength nobody could see. The shader keeps the SHAPE
of the Schlick curve and remaps its range onto `[rt_water_reflmin,
rt_water_reflmax]` (0.35 → 0.75 by default): visible looking straight down,
strong at the horizon. `tools/ab-water.cmd mirror` pushes it to 0.8 → 1.0 and
also drops `rt_water_wavestren` to 1.2, since the wave normal at 3.0 shatters
the reflected image.

### The other periodic jump: material overlays on frame 01 only (2026-08-10)

After the prefix fix stopped the water flashing in and out, the reflections and
waves still **jumped on a regular beat**. Same root cause family, different
mechanism: the PBR tooling had generated `_n` / `_orm` / `_h` for `D64W1_01` and
`D64W2_01` — the names the maps reference — and nothing for frames 02..64. So
once per animation cycle the surface gained an authored normal map and a
heightmap (parallax shifts the UVs), then snapped back two tics later.

A 64-frame sequence has to be materially uniform. `tools/set_water_meta.py
--apply` now also quarantines those 24 files (live build tree + repo tree, both
`mat` and `mat_dev`) into `mat_quarantine_water/`; `--revert` puts them back.
They are unwanted anyway — the stylized path builds its own wave normal in
`getWaterNormal` and writes roughness/metallic explicitly.

**Generalisation:** any per-texture asset generated for an animated flat must
cover every frame or none. `D64WATR1/2` are left alone: they are separate
192x192 warp textures, not members of either sequence.

### Tuned defaults (2026-08-10)

`rt_water_wavespeed 0.2`, `rt_water_wavestren 0.4`, `rt_water_veinref 0.1`,
`rt_water_reflmin 0.1`. Note `rt_water_wavestren` also drives the
partial-invisibility warp; it was 3.0, which shattered the reflected image into
sparkle.

## Projected water caustics (2026-08-10)

Caustics cast **by** the water **onto** the walls and floors around it. A 1-spp
path tracer will never find these: a caustic is a specular-to-diffuse path, and
the chance of a random diffuse bounce landing on the water surface and then
scattering into a light is effectively zero, so no amount of denoiser tuning
makes them appear.

So they are projected. In `RtRaygenDirect.rgen`, each shading point fires **one
probe ray straight down** (`isOverWater`), offset along the surface normal so a
point on a wall probes the floor in front of it rather than grazing the wall's
own base. If the hit's geometry instance carries
`GEOM_INST_FLAG_MEDIA_TYPE_WATER` within `rt_water_caustic_dist`, the point's
direct lighting is modulated by an animated caustic field sampled from the same
`WaterNormal_n` texture the surface waves use, so the two agree.

Two deliberate choices:

- **Multiplicative on direct lighting, never additive.** Caustics are focused
  light, not a light source. An additive term would make water light a
  pitch-black room and wash GI — the exact failure logged for world emissives
  above.
- **Applied to the noisy direct term**, before the denoisers, so it is present
  in the DLSS-RR albedo guides. A post-denoise multiply is absent from the
  guides RR demodulates by, which is what makes such terms shimmer.

The field is two wave layers scrolling against each other, with the filaments
where they **converge** (`pow(1 - length(n0+n1), 8)`) — convergence is what
focuses light, so this gives thin bright lines over a dark field rather than a
plain texture lookup.

Cvars: `rt_water_caustics` (gain, 0 = off **and no probe ray traced** — this is
the perf switch, it costs one ray per pixel), `rt_water_caustic_scale`,
`rt_water_caustic_speed`, `rt_water_caustic_dist` (192 map units).
A/B: `tools/ab-water.cmd nocaus`.

### build-rtgl.cmd staged a stale DLL silently

While building the above: `copy /Y` of `RTGL1.dll` fails when gzdoom is running
(file locked), the failure is swallowed by `>nul`, and the script still prints
BUILD_OK — so fresh shaders get playtested against an old DLL. The copy is now
error-checked and the script aborts with a message naming the cause.

## Illuminated fog — two RTGL1 froxel changes (2026-08-11)

Nine Retribution maps ask for fog in their own MAPINFO (`fade` + `fogdensity`;
MAP26 is cyan `00 56 56` at 200). Both keys belong to the rasterizer's fog and
the RT path read neither, so no map showed any. Rebuilt as a participating
**medium** in RTGL1's froxel volume rather than as a distance lerp, so the
level's own lights scatter through it. Full write-up: `docs/rt-fog.md`.

Two things RTGL1 could not express, both in `RtVolumetric.rgen`:

- **`volumeMediaColor`** — the pass had no coloured medium at all. The only
  colour was `volumeAmbient`, the *unlit* term, so a cyan fog still had white
  haze around every lamp standing in it. Now a scattering albedo multiplying the
  whole in-scattered term. `{1,1,1}` is the identity every unfogged map passes.
  Extinction stays monochrome — the transmittance channel is one float all the
  way to `CmPrepareFinal`, so per-channel would be a framebuffer change.
- **`volumeAllLights`** — the pass scatters exactly **one** light, whatever
  `LightManager::TryGetVolumetricLight` picks: a `RG_LIGHT_ADDITIONAL_VOLUMETRIC`
  light if any exists (nothing in this game sets that flag) and otherwise the
  sun. On MAP26, whose moon is deliberately off, that is *nothing* — the fog
  collapsed to flat ambient, i.e. back to the rasterizer fog it was meant to
  improve on. Now runs the full per-froxel direct estimate.

The all-lights branch already existed (`ILLUMINATION_VOLUME`) but was gated on
`illumVolumeEnable` = `rt_illum_volume`, which **also** switches how
`RsWorld.inl` shades every rasterized translucent primitive in the game — so
asking for lit fog would have meant accepting that. Split: `illumVolumeEnable`
decides who *reads* `g_illuminationVolume`, `volumeAllLights` decides whether it
is *computed*. Both write it, because the 0.05 temporal blend reads back what it
stored last frame and never converges otherwise.

Engine side (`rt_main.cpp`): `rt_fog_*`, `RT_FOG_PRESETS` (opt-in, MAP26 only),
the `fog` CCMD. **Resolution is deferred to the first rendered frame** —
`RT_OnLevelLoad` runs from `G_InitNew`, i.e. *before* `P_SetupLevel`, so
`primaryLevel->fadeto` / `->fogdensity` there are still the previous map's.
MAP26's `RT_MOON_PRESETS` row also drops the moon's light to 0: a directional
light rakes a froxel volume from one bearing and the fog reads as a lit slab.

### The flashlight in fog (same day)

Lit fog made the flashlight a switch that blinds you. Not a bug: a light in a
medium lights the froxels around it by inverse square, and the flashlight is at
~0 m, so the cells right in front of the camera flood. It is what a headlight in
fog does, and it is unplayable first-person.

`rt_fog_light_near` (2 m) fades in-scattering within that distance **of a light**
— keyed off the light's position, not the camera's, so glare from a light you are
*holding* goes while the beam's shaft further down the corridor, which is the
entire point of lit fog, survives. Muzzle flashes get it for free. Directional
lights never trigger it (`sampleLight` puts their position far away).

One clause in `traceDirectIllumination` under
`#if LIGHT_SAMPLE_METHOD == LIGHT_SAMPLE_METHOD_VOLUME`, so surfaces still
receive the light physically. `tools/ab-fog.cmd flshraw` is the whiteout, kept so
the fade can be seen working rather than trusted.

## Localised volumetric smoke — one RTGL1 froxel change (2026-08-11)

The fog above is one density for the whole level and the froxel grid is
camera-fitted, so there was no way to say *there is smoke here*. This adds a list
of world-space spheres whose density is **added** to that medium per froxel:
muzzle smoke that the muzzle flash which made it lights from inside. Full
write-up: `docs/rt-smoke.md`.

**`RgDrawFrameSmokeParams`, a NEW pNext struct.** Not six more fields on
`RgDrawFrameVolumetricParams`, on purpose — the fog is shipped and tuned against
a measured transmittance ladder, and a struct that does not change size cannot
break a caller that knows nothing about smoke. Puffs ride in the global uniform
(`smokePuffs[32]` + `smokeAlbedoDensity[32]`, 1 KB) rather than a storage buffer:
a `LightManager` clone would mean a new descriptor set in
`RayTracingPipeline.cpp` for no gain at 32.

**The shared code is one block in `RtVolumetric.rgen`**, with all the maths in a
new `Source/Shaders/Smoke.h`. `CmVolumetricProcess.comp` needed **no change** —
it is a front-to-back prefix sum over whatever the raygen wrote, so a puff gets
correct occlusion and transmittance for free.

The property that had to hold: with `smokeCount` 0 the loop does not execute and
the medium arithmetic collapses algebraically to the fog's two lines. The
derivation is written out in `Smoke.h`; `tools/ab-smoke.cmd fogsafe` is the
check, and must be pixel-identical to `ab-fog.cmd ramp`.

### Both trap fixes are per froxel, not per frame

Two values the fog depends on had to differ inside smoke, and the obvious
implementation of each would have retuned MAP26 every time the player fired.
Since the smoke density at a cell is known before the lighting block runs, both
are chosen per cell and fog cells keep the fog's values bit for bit.

- **The near-light fade.** `rt_fog_light_near` (2 m) exists so a carried light
  does not white out the screen, and the entry above notes muzzle flashes get it
  "for free". They needed it for fog filling the screen; a muzzle flash is at
  ~0 m from its own *smoke*, so at 2 m the puff is fully faded and the effect is
  gone. `traceDirectIllumination` now reads a file-scope `g_volumeLightNearFade`
  (sentinel −1 = the uniform, since GLSL requires a constant initializer) which
  `RtVolumetric.rgen` sets per cell. `rt_smoke_light_near` ships at 0.
- **The 0.05 temporal blend.** Right for fog, far too slow for a 2–3 frame muzzle
  flash: the smoke would light up ~0.7 s after the flash and linger as long
  again. `rt_smoke_illum_blend` is 0.4 inside a puff, the literal 0.05 elsewhere.

Engine side (`rt_main.cpp`): `rt_smoke_*`, a CPU puff simulation modelled on
`RT_UploadFlameLights` (maptime-driven, so pause freezes it; nearest-first to a
budget). The sim is on the CPU because it is the only side that can see the
level — a puff pools under a low ceiling via `PointInSector`/`ceilingplane`,
which a GPU sim could only guess at from the depth buffer. It uses a **private
xorshift**, not `M_Random`: the gameplay RNG is part of the simulation and
consuming it from the renderer would desync demos and netgames invisibly.

`rt_smoke_density` is optical depth per **metre**, not per cell — the slice
thickness is paid engine-side — so unlike `rt_fog_density` it does not change
meaning when the volume's reach does. `rt_mzlflsh` is now pinned in the launcher:
it gates the smoke spawn as well as the flash, and was `CVAR_ARCHIVE` and
unpinned, so an ini value could have disabled smoke with no `rt_smoke_*` cvar
saying so.

### What the first playtest found (same day)

Three bugs, and the second is the one worth remembering.

**No smoke at all — the density arrived 1000x too thin.** `rt_smoke_density` is
optical depth per metre and the shader applies a flat `0.001` per cell, so the
conversion is `k * sliceThickness / 0.001`. The first version sent `k * slice`,
dropping the division: tau across an entire puff came to 0.002, transmittance
0.998. Mathematically invisible, which is exactly how it looked.

**Firing deleted the moon's light shafts.** Two independent causes, both from
smoke taking over settings that were not its own:

- The smoke-only branch tested `!fog.on` alone. `rt_volume_type` defaults to 1,
  so on any unfogged map firing set the global medium's density to **0** and its
  reach from 30 m to 14 — and the shafts *are* that medium being scattered. The
  predicate is now `!fog.on && rt_volume_type == 0`: smoke may only take the
  volume over when nothing else is in it. **Smoke adds, it does not replace** —
  which the shader always did, via the density-weighted blend, and which the
  engine side had quietly broken.
- `illuminateFromAllLights` was set per FRAME whenever a puff existed. That flag
  switches the whole volume off `traceDirectIllumination_SpecificLight`, and that
  function is the only place the sun's sky-probe test lives (`sunRequireSky`,
  `traceSunReachesSky`) — i.e. the only thing that makes a shaft. Smoke now
  carries its own `allLights` in `RgDrawFrameSmokeParams`, read **per froxel**,
  so a cell outside a puff keeps the single-light path and its shafts. The
  `g_illuminationVolume` store follows the same per-cell predicate, or a cell
  that computed the estimate without storing it would read a stale image forever.

That makes three per-froxel decisions where the naive version was per-frame, all
for the same underlying reason: this volume has other tenants.

**A puff was smaller than a froxel.** With the global medium owning the reach, a
slice is `rt_volume_far / 64` = 0.47 m, so the 0.18 m default radius was 0.77 of
a cell across its whole diameter — it fitted inside one froxel. Default is now
0.35. The froxel grid, not the puff count, is this feature's resolution limit.

### The smoke was never reaching the GPU — a stale object file (2026-08-12)

Localised smoke rendered nothing for a full debugging session. The cause was not
in the smoke code, the API, the pNext chain, std140 offsets or the shader.

**`GlobalUniform.obj` was hours out of date.** `GenerateShaders.py -g` rewrites
`Source/Generated/ShaderCommonC.h`, which defines `ShGlobalUniform`. CMake and
MSBuild do not know that every `.cpp` depends on that generated header, so a
translation unit nobody edited keeps its stale object. `GlobalUniform.cpp` is the
one that matters: it allocates the uniform buffer with `sizeof(ShGlobalUniform)`.
When the struct grew from 1984 to 3024 bytes for smoke, that object still
allocated **1984** — so the buffer was 1040 bytes short while the rest of the
library wrote and read the full struct.

The symptom is the worst kind. Every field below 1984 bytes worked perfectly;
every field above it silently read **zero**. No validation error, no crash,
nothing in any log, and the shader looked like it was ignoring its input.

How it was finally caught, after the API and the layout had been cleared:

- a probe ladder in the shader — a flag read (worked), the count (worked), the
  arrays (blank) — which localised the failure to the array reads;
- a **swap experiment**: exchanging the two arrays' positions in the struct moved
  the failure with the OFFSET, not with the field name (1564 read fine, 2076 read
  zero), proving it was an address problem rather than a data problem;
- object-file timestamps: `ShaderCommonC.h` and `VulkanDevice.obj` at 21:46,
  `GlobalUniform.obj` at 13:38.

`tools/build-rtgl.cmd` now keeps a stamp copy of the generated header and
**deletes `BuildCMake/RayTracedGL1.dir` whenever it changes**, so no object can
outlive the struct layout it was compiled against. The `rt_smoke F/layout` line
(one-shot, needs `-rtdebug`) prints `sizeof` and the C offsets beside the SPIR-V
ones as a canary for the same trap recurring.

### tools/launch-retribution-rt.cmd exceeds cmd.exe's 8191-character limit

Found while chasing the above, and it affects **every A/B tool in this project**.

The assembled command line is 8192 characters — cmd.exe truncates at 8191. The
`%EXTRA%` passthrough (`-- +cvar value`) sits at the very end, so it is **always
cut off**: no `ab-*.cmd` arm has been applying its cvars. Three diagnostic runs
were lost to this before it was noticed, each reporting the default value of the
cvar the arm claimed to set.

The launcher's own trailing pins are cut too: `+rt_water_debug`,
`+rt_normalmap_stren` and `+rt_heightmap_stren` never reach the game.

Workaround used for the smoke work: invoke `gzdoom.exe` directly with a short
argument list. The real fix is to move the pin block into a generated `.cfg` and
`+exec` it, which is not yet done.

**Correction (2026-08-12).** The claim above that no `ab-*.cmd` arm had ever
applied its cvars is wrong. Before the smoke pins the command line was 7516
characters, leaving 675 for an arm — enough, and the arms worked. Adding 500
characters of `rt_smoke_*` pins cut the headroom to 175 and is what broke them.
The failure mode is growth, not a standing defect.

Fixed properly rather than trimmed: the ~325 static pins moved to
`tools/d64rt-pins.cfg`, applied with `+exec` before `+map`. The command line is
now **885 characters** with 7306 of headroom. A/B arms are config files too —
`tools/arms/*.cfg`, run with `.\tools\ab.cmd <arm> [map] [-- +cvar ...]`, exec'd
after the pins so an arm still wins. Verified end to end: `ab.cmd smoke-probeuni`
reports `DEBUGMODE=4` and paints the screen blue (98.5% blue-dominant), the exact
arm that silently failed three times as a command-line string.

## A second blink floor, for RandomFlicker only (2026-08-12)

**`rt_dynlight_rndflicker_floor`, default 0.3, in `rt_lights_sector.cpp`
(`RT_UploadGzDoomDynamicLights`) and `rt_cvars.inc`.**

The SMONBA readout panels are meant to read as a screen full of TV static:
strong, and flickering hard. Neither was reachable, for two separate reasons,
and the first is the interesting one.

**`rt_dynlight_blink_floor` is global to every flicker/pulse light.** It sits at
0.8 because 199 SMON panels blink at once and anything livelier reads as a
strobing wall (pitfall 28). That single number therefore also forbids any *one*
fixture family from swinging harder — and no map-thing value can escape it,
because the blink term is `floor + (1-floor)*t` with `t` normalised over the
fixture's own radius range. Widening `arg3`/`arg4` changes the fixture's
brightness, never its swing.

The escape hatch is that Retribution uses **9800 (989), 9801 (14) and 9802 (205)
but not a single 9804**. So `RandomFlickerLight` is an empty class in this game,
and giving it its own floor cannot move an existing fixture. That was checked
across all 39 map lumps before the split was written, not assumed.

The two GZDoom types also differ in kind, which matters here (`a_dynlight.cpp`
`Tick`):

| type | behaviour | `angle` (`specialf1`) means |
|---|---|---|
| 9802 `FlickerLight` | **binary** — radius is `arg3` *or* `arg4`, re-rolled every tic | duty cycle out of 360 |
| 9804 `RandomFlickerLight` | **continuous** — a random radius across the range, held | tics to hold each value |

A binary toggle at 1.25x is machinery; a continuous random signal at 3.3x,
re-rolled every 2 tics, is static. Only 9804 can express the second.

**The brightness ceiling is not where you would guess.** Intensity is
`hi * rt_dynlight_intensity * flicker_scale * blink`, then rolled off by
`(rsoft/hi)^2` once `hi` exceeds `rt_dynlight_rsoft`. Those pull opposite ways,
so the product **peaks exactly at `hi == rsoft`** — 20 here, giving 200. `hi=21`
already gives 190, and the `hi=32` the first SMONBA pass shipped gives 125. The
fix was to move the panels *down* from 32 to 20 to make them brighter, which is
the same "radius is not brightness" trap as pitfall 26, one level along.

Shipped: 48 SMONBA panels as 9804, `arg3/arg4` 16/20, `angle` 2, white, at
`rndflicker_floor` 0.3 → **60..200 at a 3.3x swing**, against SMONAA's steady
133..167. Pinned in `tools/d64rt-pins.cfg`; arms `ab-smon.cmd
static|statichard|staticcalm|staticoff`, which vary only this cvar and so leave
every 9802 monitor identical between them.

## RTGL1: `sunSplit` — the directional light shaded outside ReSTIR (2026-08-13)

**Symptom.** Sprites cast no moon shadow (`screen/moon_shadow_limit.png`, 21
`64MarineBot`s in TITLEMAP) while the same sprites shadow perfectly from a muzzle
flash. Not a caster problem: no `noShadow` meta, correct `WORLD_0` shadow mask,
opaque alpha-tested primitives, and no caster limit exists (`maxBounceShadows`
gates bounce depth, not object count).

**Cause.** `RaygenCommon.h` merged the directional light's reservoir into the
regular-lights reservoir stochastically, so one light wins per pixel. A weak,
huge light loses that draw on most pixels, so its shadows come back sparse and
the denoiser flattens them.

**Change**, all gated on the new uniform and OFF by default:

| file | change |
|---|---|
| `Source/Generated/GenerateShaderCommon.py` | `_pads8` → `sunSplit` (float where a uint was, so std140 is unchanged; `check_uniform_layout.py` passes, 183 fields / 8192 bytes) |
| `Source/Shaders/RaygenCommon.h` | exclude the sun from the merge in DIRECT **and** INITIAL; new `calcSunOnlyReservoir()`; deterministic sun term in `processDirectIllumination`, with the `validCount == 0` early-out moved so a moon-only room is not returned black |
| `Include/RTGL1/RTGL1.h`, `Source/DrawFrameInfo.h` | `RgDrawFrameSkyParams::sunSplit`, default 0 |
| `Source/VulkanDevice.cpp` | `gu->sunSplit` |
| gzdoom `rt_cvars.inc`, `rt_main.cpp` | `rt_sun_split` (default false) → `.sunSplit` |

Unbiased: the sun is removed from the candidate set rather than double-counted,
and the single-candidate reservoir is built exactly as the stochastic path built
it, so sunlit brightness is unchanged and only the noise differs. Indirect and
volumetric keep the stock path. A/B: `.\tools\ab.cmd title-nosplit|title-split`.
Full write-up: `docs/moon-and-sky-leaks.md` §5.2.

## RTGL1: `RG_MESH_PRIMITIVE_SHADOW_ONLY` — sprite shadow proxies (2026-08-13)

**Symptom.** A sprite is a camera-facing quad with no thickness: a light lying in
its plane projects it to a line (no shadow at all), and the shadow's shape
changes as the player rotates, because the quad turns to face the viewer.
Voxelising the actors is a documented dead end (`docs/rt-voxel-models.md` §6).

**Change.** A new primitive class that is in the acceleration structure and
blocks shadow rays while being invisible to every other ray — the complement of
`RG_MESH_PRIMITIVE_NO_SHADOW`:

| file | change |
|---|---|
| `Include/RTGL1/RTGL1.h` | `RG_MESH_PRIMITIVE_SHADOW_ONLY = 1 << 22` |
| `Source/VertexCollectorFilterType.h/.cpp` | new `PV_SHADOW_ONLY` primary-visibility class (bit 11, previously unused; BLASes are per-primitive here so no bucket growth) |
| `Source/ASManager.cpp` | that class → `INSTANCE_MASK_RESERVED_0`, with **no** `rayCullMaskWorld` test — the mask's absence from it is exactly what hides the geometry |
| `Source/VulkanDevice.cpp` | `rayCullMaskWorld_Shadow = WORLD_0 \| RESERVED_0` |
| gzdoom `rt_draw.cpp` | after the sprite upload, submit `rt_sprite_shadow_planes` copies at fixed world yaws; same verts, different transform (the billboard is already factored into rotation + pivot); IDs at `actor + 0x4000000000000000 + k` so they cannot collide with a pointer-derived ID |
| gzdoom `rt_cvars.inc` | `rt_sprite_shadow` (off), `_planes` (2), `_hidecaster` (on), `_dist` (40 m) |

Translucent sprites are skipped (rasterized, so not in the AS and casting nothing
today). Default off. A/B: `.\tools\ab.cmd sprshadow-off|sprshadow-on`. Full
write-up: `docs/moon-and-sky-leaks.md` §5.3.

## `rt_volume_far` was a hidden density knob, and it dimmed the moon (2026-08-13)

**Symptom.** After the smoke work the moon's volumetric shafts went weak on
MAP01 — barely visible in front of the ceiling opening, but plainly there
standing under it looking up at the moon. No `rt_sun_*` value had changed.

**Cause.** `RtVolumetric.rgen` multiplies its scattering coefficient **per
froxel cell**, and `CmVolumetricProcess.comp` prefix-sums cells with no
slice-thickness weighting. The grid is 64 slices whatever the reach, so
`rt_volume_far` sets metres-per-cell — and the pin raised it `30 → 60` to double
smoke's render distance (commit `11417f2`). A shaft crossing a given room then
passed through half as many cells: **half the in-scattered light**. Smoke was
immune because it converts its own per-metre density to per-cell before upload
(`rt_main.cpp`, the `sliceM` block), which is precisely why the moon was the only
thing that changed. The view asymmetry is the Henyey–Greenstein phase function at
`rt_volume_lassymetry 0.5` — ~11× more scattering into the eye along the beam
than across it — so only the weaker of the two views fell under threshold.

**Change** (engine only; no RTGL1 rebuild):

| file | change |
|---|---|
| gzdoom `rt_main.cpp` | `volume_dens = rt_volume_scatter * ( reach / 30 )`, feeding `.scaterring` and `.farScattering` in the **unfogged** branches only. `rt_volume_scatter` is now a per-metre density and `rt_volume_far` a pure reach/resolution knob |
| gzdoom `rt_main.cpp` | `.farScattering` also states `0` in the `smoke_owns` case — near 0 with a non-zero far was a ramp from clear air into haze, the opposite of what zero base density is for |
| gzdoom `rt_cvars.inc` | `rt_volume_far` / `rt_volume_scatter` help rewritten to say which is which |
| `tools/arms/moon-*.cfg` | seven arms, `moon-before` reproducing the regression exactly on the fixed build |

**Fog is deliberately untouched.** `RT_FOG_PRESETS` is tuned in the per-cell
units `rt-fog.md` §6 documents, across nine maps; normalising it would retune all
of them for a MAP01 report. `ab-smoke.cmd fogsafe` is the check that it did not
move. Full write-up: `docs/moon-and-sky-leaks.md` §5.4.

## Doom 64 menu graphics — RT's `rt/wad` was overriding the mod (2026-08-13)

**Symptom.** On the main menu, `New Game` and `Options` were in the Doom 64 face
while `Load` / `Save` / `Quit` were plain Doom 1/2 lettering, and the RT options
header read `GRAPHICS` in that same plain face.

**Cause.** Not a font fallback — all five main-menu entries are `PatchItem`s, so
no font is consulted. `GetCmdLineFiles` (`d_main.cpp:1963`) adds every `-file`
PWAD and then appends `rt/wad` **unconditionally, last**, so nothing loaded with
`-file` can ever override an `rt/wad` lump. RT ships its own
`graphics/M_LOADG|M_SAVEG|M_QUITG.png` in the plain face and they beat
Retribution's D64 patches; it ships **no** `M_NGAME`, `M_OPTION` or `M_SKULL1`,
which is exactly why those kept the D64 look. `M_DISOPT` / `M_DISP` (both reading
`GRAPHICS`) are RT's own — Doom 64 never had that word, so there was no mod art
to lose the fight.

**Change** (no engine or RTGL1 rebuild; art only):

| file | change |
|---|---|
| `tools/extract_d64_menu_gfx.py` | new — copies `M_LOADG` / `M_SAVEG` / `M_QUITG` out of `D64RTR_v15.WAD` **byte for byte** into `rt-wad-overlay/graphics/` |
| `tools/gen_d64_menu_title.py` | new — renders a title from the mod's `DBIGFONT` for words the mod has no art for; writes `M_DISOPT` / `M_DISP` as `Graphics` |
| `tools/sync-rt-wad.py` | walks subdirectories (was top-level only) and creates destination dirs, so `graphics/` mirrors into both `rt/wad` trees |

**Retribution's menu patches are font renders, not drawn art.** `DBIGFONT`
(FON2) at zero tracking, cropped to the ink, with the font's grey ramp remapped
to the menu's reds, reproduces `M_NGAME` / `M_NEWG` / `M_LOADG` / `M_SAVEG` /
`M_OPTION` / `M_OPTTTL` / `M_QUITG` at **0 mismatching pixels** — that is what
`gen_d64_menu_title.py --verify` asserts, and it is why a synthesised `Graphics`
is indistinguishable from shipped art. The casing matters: the font is small-caps,
so the words are `"Options"` / `"Load Game"`, not `"OPTIONS"`. Two traps paid for:
the ramp needed palette indices **1 and 10** as well as 2–9 (they appear only in
`m`/`d`/`v` and in `Q`'s descender, so `Options` alone verified clean while the
two-word lumps were 4–8 px out), and the height must come from the ink, not a
constant — `Quit Game` is 14 rows where every other patch is 13.

**Do not put menu art in a `-file` pk3.** It cannot win. The tracked master is
`rt-wad-overlay/`, mirrored by `tools/sync-rt-wad.py`; both real `rt/wad` trees
are gitignored, so edits made directly in them are invisible to git and are lost
on the next build refresh.

---

## `rt_verbose` — the renderer stops talking over the game (2026-08-13)

**Reference: `docs/rt-verbose.md`** — what it covers, what it deliberately does
not, and which print level a new message should take. This entry is the
changelog; that file is the one to read before adding a `Printf`.

**Symptom:** every level load, and every press of the flashlight key, painted a
line of text across the picture — `Can't find a file, no static scene will be
present: ...`, `Denoiser path: A-SVGF (Denoise) ...`, `ReSTIR: initialSamples=32
...`, `D64RtSkyFix: MAP01 sky -> MOONSKY`, `RT_BOOT: ...`, `"rt_flsh" = "true"`.
Fine while developing, not shippable.

**The lever is the print LEVEL, not the call site.** `PRINT_NONOTIFY` (1024, an
*flag* on the print level) makes `PrintString` skip the notify overlay while
still writing the console buffer, `I_PrintStr` and the logfile
(`c_console.cpp`). So a message can be silenced on screen and lose nothing —
`~` and `rt-console.log` still have every line. That is why the new default is
quiet: there is no diagnostic cost to pay for it.

`rt_verbose` (bool, default **false**) selects between the two, through
`RT_DiagPrintLevel()` in `rt_internal.h` (and a private mirror,
`RT_BootPrintLevel()`, in `d_main.cpp`, which must not include that header).

| Source of noise | How it was silenced |
|---|---|
| **Everything RTGL1 prints** | one line: the `RG_MESSAGE_SEVERITY_WARNING` branch of `RT_Print` (`rt_main.cpp`) |
| `RT_BOOT:` timings ×4 | `d_main.cpp` |
| upscale/RR decision, `RT_Title:` | `rt_main.cpp`, `rt_titles.cpp` |
| `RT water:` / `RT lava:` tagging, lava-with-no-light | `rt_draw.cpp`, `rt_lights_fx.cpp` |
| `D64RtSkyFix:`, `D64LavaFx:` | `Console.PrintfEx(DiagLevel(), ...)` in the pk3 ZScript; `DiagLevel()` reads `rt_verbose` via `CVar.FindCVar` |
| `"rt_flsh" = "true"` on every keypress | new **`CCMD(rt_flsh_toggle)`** (`rt_weapon.cpp`); KEYCONF alias moved off `toggle rt_flsh` |

Four things worth knowing before extending this:

- **A toggle *message* does not help.** `CCMD(toggle)` in `c_cvars.cpp` reports
  unconditionally, and `SetToggleMessages` only swaps one on-screen line for
  another (`Printf(PRINT_NOTIFY, ...)`). The key had to stop calling `toggle`.
- **`PRINT_LOG` is the wrong flag.** It writes the logfile *only* — the message
  disappears from the in-game console too. `PRINT_HIGH | PRINT_NONOTIFY` is the
  one that keeps the console.
- **Do not silence a CCMD's reply.** `whatsthat`, `moon`, `clouds`, `fog`,
  `smoke`, `thunder`, `rt_dump_*` answer a question the user typed and must
  print where it was asked. Everything already behind a `*_debug` cvar is left
  loud for the same reason: turning that cvar on *is* the request.
- **`con_notifylines 0` is not the answer.** It would take pickups and level
  names with it. Game messages are untouched by any of this.

---

## Light shafts from ordinary lamps (2026-08-14)

Beams of light in a dark room are the Doom 64 look, and until now this renderer
could only produce them **outdoors**. RTGL1's froxel pass scatters exactly ONE
light per frame — `LightManager::TryGetVolumetricLight` picks it, and it scans
`staticLights` only, so a fixture gzdoom uploads per frame could never be picked
at all. Every ceiling lamp, grate and doorway inside a level was a light with no
visible air around it.

Full write-up, cvars and A/B ladder: **`docs/plan-light-shafts.md`**.

**RTGL1 (`deps/RTGL`)**

- `Include/RTGL1/RTGL1.h` — new `RgDrawFrameLightShaftParams` (pNext on
  `RgDrawFrameInfo`), `RG_STRUCTURE_TYPE_DRAW_FRAME_LIGHT_SHAFT_PARAMS = 37`,
  `RG_MAX_SHAFT_LIGHTS 32`. A **separate struct**, not fields on
  `RgDrawFrameVolumetricParams`, for the reason `RgDrawFrameSmokeParams` is one:
  the fog is shipped and tuned on nine maps, and a struct that does not change
  size cannot break it. `count 0` is the stock volume.
- `Source/DrawFrameInfo.h` — trait, `CheckMembers` assert, link root, defaults.
- `Source/Generated/GenerateShaderCommon.py` — `VOLUME_SHAFT_LIGHT_MAX 32`;
  `volumeShaftLights` as `uvec4[8]` plus nine scalars **replacing the `_pads10`
  slot**. Nine, not five: the scalar run from `smokeCount` must stay a multiple
  of four or C and std140 disagree from the first vec4 array onward.
  `tools/check_uniform_layout.py` is the gate and `build-rtgl.cmd` refuses to
  build when it complains — 196 fields, 8368 bytes.
- `Source/VulkanDevice.cpp` — resolves uniqueIDs to shader light indices via
  `LightManager::GetLightIndexForShaders`, **compacting** as it goes: a fixture
  the engine listed may have been culled before its light was uploaded, and a
  `LIGHT_INDEX_NONE` hole mid-array would spend the shader's nearest-first budget
  on nothing.
- `Source/Shaders/RtVolumetric.rgen` — `traceShaftLights()`, added to the
  single-light term and gated on `!allLightsCell` so it cannot double-count
  inside smoke or on a fogged map.

**gzdoom-rt**

- New `rt_light_shafts.cpp` (registered in `src/CMakeLists.txt`) — the fixture
  walks *offer* lights; this culls, sorts nearest-first, dedupes and caps.
- `rt_lights_fixtures.cpp` — offer sites at the ceiling-inset upload and at the
  merged ceiling-edge/lattice/faux/solo upload; `Cand` gained a `shaftSrc` field
  so the family survives the merge.
- `rt_main.cpp` — `RT_ShaftLightsBegin()` before the fixture walks,
  `RT_ShaftLightsSelect()` where the params are built; chain is now
  volumetric → shaft → smoke → sky.
- 13 cvars in `rt_cvars.inc`, all pinned at their compiled defaults in
  `tools/d64rt-pins.cfg`. 15 arms in `tools/arms/lampshaft-*.cfg`.

**Three things worth knowing before extending this:**

- **`rt_fog_illum` is not the answer, though it looks like it.** The all-lights
  froxel estimate already exists and was the original plan's cheap route. It
  *replaces* the single-light path — which is the only place the sun's sky-reach
  probe lives, i.e. the only thing that makes the shafts the game already has —
  and it shades the medium through a **surface** integrator with a fake normal
  equal to `toviewer`, so a light directly overhead scores `dot ≈ 0` and is
  multiplied to nothing. A ceiling lamp is exactly a light directly overhead.
- **Deterministic, not stochastic, and on purpose.** One randomly chosen light
  per froxel would be cheaper and would then need the reprojected temporal
  history the all-lights branch has. A short list with a radiance cull in front
  of the shadow ray has no variance at all, and in a typical cell only one or two
  lamps survive the cull.
- **The dedupe is load-bearing.** A lamp pane is ~16 point lights on a 16-unit
  lattice; without `rt_volume_shaft_mingap` one pane takes the whole 16-slot
  budget and yields a single blob while the rest of the room gets nothing. The
  test is 3D — the walks tile in both axes, and a 2D gap would merge a light with
  the one above it, which is the mistake `PANEL_LAMPS`' `min_gap` made.
