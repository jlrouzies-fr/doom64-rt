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
