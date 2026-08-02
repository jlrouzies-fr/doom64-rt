# Doom 64: Retribution â€” Path Tracing Implementation Plan (Windows)

**Goal:** Add real-time path tracing (global illumination, reflections, refractions, emissive lighting) to *Doom 64: Retribution* by building on the existing `gzdoom-rt` ("GZDoom: Ray Traced") fork, which already implements path tracing for GZDoom via the RTGL1 library.

**Target platform:** Windows 10/11, NVIDIA RTX GPU (RT cores required).

**Reference projects:**
- [vs-shirokii/gzdoom-rt](https://github.com/vs-shirokii/gzdoom-rt) â€” path tracing renderer already built into a GZDoom fork. **This is our base engine.**
- [sultim-t/prboom-plus-rt](https://github.com/sultim-t/prboom-plus-rt) â€” same author's RTGL1 integration for PrBoom+, useful as a secondary reference for RTGL1 usage patterns.
- [postmemetic/Duke-RT](https://github.com/postmemetic/Duke-RT) â€” reference for material-authoring workflow (PBR overlays on classic-era textures) and NRI-based RT abstraction (not directly reusable since gzdoom-rt uses RTGL1, but useful for material pipeline ideas).
- [Doom 64: Retribution (ModDB)](https://www.moddb.com/mods/doom-64-retribution) â€” GZDoom total-conversion mod containing the actual Doom 64 content (maps in UDMF, monsters, weapons, sector lighting) that we will load into gzdoom-rt.

**Core insight driving this plan:** We are *not* writing a renderer from scratch. `gzdoom-rt` already has a working RTGL1-based path tracer for vanilla/Boom-format GZDoom content. The work is (1) getting Retribution's assets/maps to load and render correctly inside gzdoom-rt, and (2) authoring RT material data (PBR/emissive/reflective definitions) so the path tracer knows how to treat Doom 64's specific textures, sprites, and light sources.

---

## Status (living â€” update this)

| Field | Value |
|---|---|
| **Last updated** | 2026-08-02 |
| **Current phase** | **Phase 3→4** — MAP01 PBR stubs; Phase 6 RR MVP playtested |
| **Blocked on** | — |
| **Next action** | Continue Phase 4 materials; keep native RR as default launch (`tools/launch-retribution-rt.cmd`) |

### Progress

| Phase | Status |
|---|---|
| 0 Prerequisites / vanilla RT validate | **Done** |
| 1 Acquire / inventory Retribution | **Done** |
| 2 Baseline compatibility | **Mostly done** â€” hang/sky/live-upload fixes; residual sky-holes OK for now |
| 2.5 Engine fork (Steam / scene collision) | **Done** â€” built `sourcecode/gzdoom-rt/build/RelWithDebInfo/gzdoom.exe` |
| 3 Material / lighting authoring spec | **Done** â€” `material-authoring-spec.md` |
| 4 Author RT content for Retribution | **Started** â€” MAP01 auto stubs via `tools/gen_map01_pbr.py` |
| 5 Integration / load order / launcher | Not started |
| 6 Performance tuning | **Started** — native DLSS-RR preferred over A-SVGF (user: much less noisy) |
| 7 Polish | Not started |
| 8 Distribution | Not started |

### Workspace (this machine)

| Path | Notes |
|---|---|
| `G:\AI\Doom64-RT\gzdoom-rt-1.0.2\` | Stock prebuilt (Doom II RT only; scene collision with Retribution) |
| `G:\AI\Doom64-RT\sourcecode\gzdoom-rt\` | **Primary engine** â€” patched fork; build â†’ `build/RelWithDebInfo/` |
| `G:\AI\Doom64-RT\Doom64-Retribution\` | Retribution v1.5 (`D64RTR[v1.5].WAD` + `D64RTR_v15.WAD` copy for shells) |
| `G:\AI\Doom64-RT\compat-patches.md` | Engine hardcoding findings + applied patches |
| `G:\AI\Doom64-RT\sourcecode\Duke-RT\` | Material-authoring reference |
| `G:\AI\Doom64-RT\sourcecode\prboom-plus-rt\` | RTGL1 secondary reference |
| `G:\AI\Doom64-RT\tools\inventory_retribution.py` | Phase 1 inventory script |
| `G:\AI\Doom64-RT\retribution-asset-inventory.md` | Inventory report |
| `G:\AI\Doom64-RT\AGENTS.md` | Short agent briefing; plan is source of truth |
| Preferred IWAD | `D:\Games\GZDoom\doom2.wad` (**14604584** Steam size). Avoid `D:\Games\Doom RT\DOOM2.WAD` (14943400) for stock RT. |
| GPU | NVIDIA GeForce RTX 5090 |
| Build tools | VS 2022 Build Tools + MSBuild present; CMake/Git OK; system Vulkan SDK optional (bundled ZVulkan) |

### Corrections vs original plan assumptions

- Retribution main file is **`D64RTR[v1.5].WAD`**, not a pk3. Brightmaps are a separate `D64RTR_BRIGHTMAPS.PK3`.
- As of v1.5 it is **not an IWAD**. Load: `-iwad DOOM2.WAD -file D64RTR[â€¦].WAD [brightmaps]`.
- **Stock gzdoom-rt is not mod-friendly:** Steam DOOM2 size/launcher gates + `rt/scenes/map##` keyed only by map name â†’ Retribution MAP01 pulls Doom II light scenes (crash/corruption risk). **Source fork required** (Phase 2.5).
- Inventory: **35 UDMF maps**, **DECORATE only** (no ZSCRIPT), `GLDEFS`/`ANIMDEFS`/`TEXTURES`, **1187 TX_** textures, 1387 sprites.
- PowerShell: `[v1.5]` in paths is a wildcard â€” use `D64RTR_v15.WAD` copy or `-LiteralPath`.

### Phase 2 / 2.5 launch (after rebuild)

```powershell
cd G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo
# First time: copy rt\, libsndfile-1.dll, openal32.dll, zmusic.dll from gzdoom-rt-1.0.2
.\gzdoom.exe -iwad "D:\Games\GZDoom\doom2.wad" -file "G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD" "G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
```

Until rebuild finishes, stock prebuilt can limp with Steam-sized IWAD + `-rtdoom2` + (workaround) moving `rt\scenes\map*` aside â€” not a real fix.

---

## 0. Prerequisites & Environment Setup

- [x] Windows 10/11, NVIDIA RTX GPU (20-series or newer) with current Game Ready / Studio drivers â€” **RTX 5090 confirmed**
- [ ] Visual Studio 2022 (Desktop C++ workload) â€” **deferred** (prebuilt used; `cl` not on PATH yet)
- [x] CMake â‰¥ 3.20 â€” present
- [x] Git (with submodule support) â€” present
- [ ] Vulkan SDK (latest) â€” **deferred** (`VULKAN_SDK` not set; only needed for source builds)
- [x] ~20 GB free disk space (engine build + WAD assets + intermediate shader caches) â€” assumed OK given downloads present

### 0.1 Baseline engine (sanity check before touching Retribution)

**Done via prebuilt release** (source clone exists under `sourcecode/gzdoom-rt` for later).

Original source-build path (if needed later):

```powershell
git clone --recursive https://github.com/vs-shirokii/gzdoom-rt.git
cd gzdoom-rt
auto-setup-windows.cmd
```

- Prebuilt package already includes `gzdoom.exe`, `rt/`, `libsndfile-1.dll`, `openal32.dll`, `zmusic.dll`.
- [x] **Validation:** Run with vanilla DOOM2.WAD â€” **user confirmed Doom II RT works** (2026-08-02).

**Cursor task:** Automate into `setup.ps1` â€” optional; skipped while prebuilt path is sufficient.

---

## 1. Acquire and Inspect Doom 64: Retribution

- [x] Download Doom 64: Retribution from ModDB â€” present at `Doom64-Retribution/`
- [x] Confirm package layout â€” main content is **`D64RTR[v1.5].WAD`** (PWAD); brightmaps in `D64RTR_BRIGHTMAPS.PK3`
- [x] Inventory (scripted; SLADE optional for deep dives):
  - Map format: **UDMF** (`TEXTMAP` + `BEHAVIOR` + `ZNODES`) for MAP00â€“MAP34 (35 maps)
  - Textures: **TX_** namespace (~1187), plus large `TEXTURES` lump; classic F_/P_ namespaces almost unused
  - Scripts/defs: **DECORATE** (no ZSCRIPT), MAPINFO, SNDINFO, **GLDEFS**, ANIMDEFS, MODELDEF not listed as top lump, LOADACS, MENUDEF, SBARINFO, TERRAIN, etc.
  - Sprites: ~1387 in S_/SS_
  - Brightmaps PK3: `brightmaps/` + GLDEFS

**Cursor task:** [x] Inventory script â†’ `tools/inventory_retribution.py` â†’ `retribution-asset-inventory.md`

---

## 2. Baseline Compatibility Pass (No RT Yet / or RT as-is)

Before bulk RT material authoring, confirm Retribution *runs* under gzdoom-rt. Prefer noting rasterized vs RT behavior; triage content/engine issues first.

- [ ] Launch with the Phase 2 command in **Status** above
- [ ] Note whether RT is on by default; if problems look RT-specific, find disable cvar / menu toggle and retest rasterized
- [ ] Play 2â€“3 maps checking for:
  - Script errors in console (DECORATE/MAPINFO/ACS vs gzdoom-rt GZDoom version)
  - Missing textures (checkerboard)
  - Broken dynamic lights, 3D floors, or crashes

**Cursor task:** Triage and fix incompatibilities; document every patch in `compat-patches.md`.

**Exit criterion:** Retribution playable, maps load, no missing assets (RT materials can still be vanilla/untuned).

---

## 3. Understand gzdoom-rt's Material & Lighting Authoring System

`gzdoom-rt` extends GZDoom with data read by RTGL1. Study bundled Doom II RT content and the prebuilt `rt/` tree.

- [ ] Study `sourcecode/gzdoom-rt/wadsrc_lights/` (and related wadsrc_*)
- [ ] Study `gzdoom-rt-1.0.2/rt/mat/`, `rt/data/`, `rt/wad/`, config examples (`RTGL1.json-example`)
- [ ] Check `sourcecode/gzdoom-rt/docs/` and Duke-RT `MATERIAL-OVERLAY-AUTHORING.md` / `LIGHTOVR-AUTHORING.md` for workflow ideas (different backend â€” adapt carefully)
- [ ] Identify lump/file types for: emissive surfaces, material props (roughness/metalness/normals), light entities, sky/env lighting

**Cursor task:** Produce `material-authoring-spec.md`. **Hard gate before Phase 4.**

---

## 4. Author Path Tracing Content for Doom 64: Retribution

Bulk creative/technical work â€” Doom 64 look into RTGL1 materials. Use inventory TX_ names (lava, nukage, water, switches, etc.) and brightmaps as emissive hints.

### 4.1 Emissive texture pass
- [ ] Identify glow textures (panels, lava/nukage, torches, energy, eyes, exits, teleporters)
- [ ] Author emissive entries per Phase 3 spec
- [ ] Tune intensity/color vs N64 / Retribution mood

### 4.2 Sector/dynamic lighting reconciliation
- [ ] Verify UDMF sector light colors feed the path tracer
- [ ] Verify scripted/animated lights (flicker/strobe) vs denoiser artifacts

### 4.3 Material properties (reflective/metallic)
- [ ] Identify reflective candidates (metal, wet/slime, marble); keep conservative
- [ ] Author roughness/metalness; normal maps optional (Phase 6 stretch)

### 4.4 Sky and outdoor lighting
- [ ] Verify sky as RT light source where outdoor areas exist

**Cursor task:** Batch-authoring helper scaffolding stubs from inventory + spec.

---

## 5. Integration & Load Order

- [ ] Package Phase 4 work as overlay pk3 (e.g. `Retribution-RT-Materials.pk3`) â€” never edit Retribution in place
- [ ] Load order: `DOOM2.WAD` â†’ `D64RTR[v1.5].WAD` â†’ `D64RTR_BRIGHTMAPS.PK3` (optional) â†’ `Retribution-RT-Materials.pk3` last
- [ ] Launch script / ini profile for one-click RT play

**Cursor task:** Launch script + install README section.

---

## 6. Performance Tuning

- [ ] Profile frame time (RTGL1 overlay / Nsight / PIX) on RTX 5090 and note mid-range targets if distributing
- [ ] Hotspots: monster-dense fights, complex geometry
- [ ] Tune rays / bounces / denoiser via `rt/` configs
- [ ] Verify DLSS/FSR if exposed

**Cursor task:** Performance report on representative maps.

---

## 7. Polish Pass

- [ ] Playtest episodes vs rasterized baseline
- [ ] Fix light leaks, bad emissive bleed, wrong brightness
- [ ] Particles, decals, muzzle flashes vs RT pipeline
- [ ] Save/load, menus, multiplayer if relevant

---

## 8. Distribution

- [ ] Install README: DOOM2 IWAD (owned), gzdoom-rt, Retribution files, RT overlay, launch steps
- [ ] Package for testers
- [ ] Licensing: gzdoom-rt GPL-3.0; Retribution ModDB terms; no redistributing commercial IWADs

---

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| gzdoom-rt GZDoom version behind Retribution â†’ script errors | Medium | Phase 2 catch; patch DECORATE/MAPINFO; log in `compat-patches.md` |
| RTGL1 material system missing features (e.g. normals) | Medium | Scope normals as stretch; emissive + roughness first |
| Performance in monster-dense fights | Medium-High | Phase 6 + upscaling; cap bounces |
| Path-traced look fights Doom 64 moody lighting | Medium | Reference N64 / Retribution during Phase 4 tuning |
| Upstream gzdoom-rt lightly maintained | Low-Medium | Budget engine debug time; track upstream issues |

---

## Suggested Milestones for Cursor Sessions

1. ~~**Session 1:** Phase 0 â€” validate vanilla gzdoom-rt~~ **Done**
2. ~~**Session 2:** Phase 1 â€” inventory Retribution~~ **Done**
3. **Session 3â€“4 (current):** Phase 2 â€” Retribution in gzdoom-rt, compat fixes
4. **Session 5:** Phase 3 â€” material-authoring spec
5. **Session 6â€“9:** Phase 4 â€” emissive/material data
6. **Session 10:** Phase 5 â€” overlay pk3, launcher
7. **Session 11:** Phase 6 â€” performance
8. **Session 12:** Phase 7â€“8 â€” polish and packaging

---

## Notes for Cursor

- **This plan file is the progress tracker.** Update Status / checkboxes when work completes. `AGENTS.md` is a short pointer only.
- Treat Phase 3's `material-authoring-spec.md` as a hard gate before bulk Phase 4.
- Keep RT content in a separate overlay `.pk3`.
- Log every engine-level patch in `compat-patches.md`.
