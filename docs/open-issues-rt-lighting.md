# Open issues — Retribution RT (2026-08-03)

Living punch list of **what still fails**, what we **tested**, and what **works**.  
Do not treat this as a progress cheer sheet — only unresolved / partially resolved items belong in §1.

**Related:** `AGENTS.md`, `compat-patches.md`, `material-authoring-spec.md`, `gallery-emis-wall-wash-fix-plan.md`, `gallery-emis-wall-wash-diagnostics.md`, **`rr-noise-investigation.md`** (DLSS-RR salt / PBR)

**Play path (canonical):** `tools/launch-retribution-rt.cmd` → `sourcecode/gzdoom-rt/build/RelWithDebInfo/`

---

## 1. Unfixed / incomplete

### 1.0 MAP04 first room wash — **DYNMAXRADIUS 2026-08-05** (needs rebuild + test)

| | |
|---|---|
| **Symptom** | `screen/level4lightingfirstroom.png` — flat bright yellow-brown wash, room 4× brighter than original. Ceiling at nearly white (brightness 244) vs original (brightness 38). Center of room brightness 93 vs original 23. |
| **Cause** | 4× type 9800 static PointLights at room corners (r=88, arg1=200 red). These are **decorative ceiling fixtures** (software colormap indicators, not real light sources). Since they're not FlickerLight (sector special=None), `rt_dynlight_flicker 0` does NOT skip them. Each gets ~103 intensity after rsoft rolloff, totaling ~412 in a small room = yellow-brown flood. Sector light 160 and `volumeLightMultiplier 3` are minor contributors — the dynlights dominate. |
| **Fix** | Engine: skip dynlights with radius > 40 on MAP04 only (checks `_map04` in map name). The 4 corner r=88 ceiling fixtures are decorative software-colormap markers. MAP01 spawn blink (r=24) and other maps are unaffected. No rebuild needed after engine patch. |
| **Confirm** | `tools/launch-retribution-rt.cmd 4` — first room dark with warm hanging-lamp pools. `tools/launch-retribution-rt.cmd 1` — MAP01 blink still works. |

### 1.1 / 1.3 Spawn blink + shadow-cast lights — **CEILING LAMPS 2026-08-03** (needs visual confirm)

| | |
|---|---|
| **Target** | Ceiling **head lights** over MAP01’s first zombies (`SFLATAS` secs 31/33) — **not** wall SMON terminals. |
| **Why wall terminals blinked** | Alcove secs **32/34** are `dLight_Flicker` (65) + green **9802** at the SMON. Dynlight upload (and any sector_flicker/lights) lightstyles those alcoves. |
| **Why `rt_sector_lights 1` looked dead for ceilings** | Booth ceilings have **special 0 / steady lightlevel 200** — sector lights never blink them. Enabling all-sector lights mostly adds steady fill; the only blink still comes from alcove 65 / 9802. |
| **Fix landed** | `RT_UploadCeilingInsetLamps()` under `SFLATAS*`/`SPORT*`. `rt_dynlight_flicker 0` skips 9802 wall flashers. `rt_sector_flicker 0`. Debug: `rt_ceiling_lamp_debug 1` → cyan markers + console. |
| **RR noise (2026-08-05)** | See **`rr-noise-investigation.md`**. Soft lamp fade landed; boiling + `rt_rr_temporal` both **failed** (worse / ghost). Follow-on: black world when Compose still read empty temporal buffers — **fixed** (ComposeNoisy raw-only). PBR suspected amp — do not strip. |

### 1.2 MAP01 directional wash / sky leak — **MITIGATED** (night sky 2026-08-03)

| | |
|---|---|
| **Symptom** | Inch forward ~2%: warm fill on left wall/floor, **casts shadows**, no lamp in view. |
| **Confirmed cause** | **`rt_sky`** through an aperture (not emis GI / dynlights). Amplified by bright `RSKY1` @ `rt_sky 200`. |
| **Fix landed** | `d64r-rt-sky.pk3` → **`SPACE`** night flat (not RSKY1); play launcher `+rt_sky 25`; sector skybox rooms **Ignored** under RT (`hw_walls`/`hw_flats` when `portalState.inskybox`) + `rt_sky_always` fills outdoor sky; `gl_noskyboxes false`. User: sky looks good. Residual geometric seams may still need hunting at very high sky intensity. |

### 1.3 Map PointLightFlicker (9802) / wall SMON — gated off

9802s by wall terminals are **not** the desired spawn blink. Play launcher sets `rt_dynlight_flicker 0` so those Flicker lights are not uploaded; ceiling lamps handle §1.1.

### 1.4 Lost Soul LSGL offset floor light — **UNFINISHED / OPTIONAL**

Yellow SKUL sprites via `d64r-lostsoul-rt.pk3` ship; same-sprite attached light abandoned (white bloom). LSGL EventHandler experimental — not dialed. Accept yellow fire under BRIGHT or finish/drop LSGL.

### 1.6 MAP02 yellow door + dark absorb room — **ENGINE FIX 2026-08-04** (needs confirm)

| | |
|---|---|
| **Yellow door** | `SDOOR6` on sectors with `lightcolor` yellow + high `lightlevel` — not RT `_e`. Sector tint baked into vertex color → neon wash. |
| **Dark room** | Secs **35/40**: `SFLATAQ` ceil + `SPACECN` walls, `lightlevel` 0/10. Lamp blobs `_e` with `emissiveMult=0` (primary only); walls got **black** vertex color → flashlight/ceiling lamps absorbed. |
| **Fix** | `rt_main.cpp`: under `rt_mod_compat`, world prims upload **white RGB**. First pass only hit `ExportMap`; **doors are movable → not ExportMap** — extended to all non-sprite world (2026-08-04 eve). Rebuild gzdoom. |
| **Confirm** | `launch-retribution-rt.cmd 2`: yellow/red **key doors** not neon. Dark room: walls lit by flashlight/ceiling lamps. |
| **Sprites** | World fix left enemies + weapon black (`level2blackroomsprites.png`) — sprite path still multiplied sector lightlevel into albedo. **2026-08-05:** `ExportInstance` / FirstPerson keep `uObjectColor`, drop `uVertexColor` RGB. Rebuild gzdoom. |

### 1.6b MAP02 freeze at red-key approach — **FIX WAD 2026-08-05** (needs confirm)

| | |
|---|---|
| **Symptom** | Window freezes (audio still plays) when entering the red-key door approach on MAP02. |
| **Cause** | Same as MAP01: `Sector_Set3dFloor` (special **160**) — two linedefs, control sectors tag 1/2 with `F_SKY1`. RT live-upload hang when that geometry is in play. |
| **Fix** | Combined `d64r-3dfloor-rtfix.wad` strips special 160 on **all 28 maps** that had it (161 linedefs). Keeps `BEHAVIOR`/`ZNODES`. Regen: `python tools/make_map_3dfloor_rtfix.py`. |
| **Confirm** | `tools\launch-retribution-rt.cmd 2`, walk to red-key door room — should stay responsive. Outdoor 3D-floor prop may be missing until engine fix. |

### 1.6e MAP02 fake mid-ceiling blink blobs — **ENGINE FIX 2026-08-05** (needs confirm)

| | |
|---|---|
| **Symptom** | `screen/level2fakeceilinglights.png` — blinking white patches in empty mid-ceiling (circled); real fixtures are only edge inset blobs. |
| **Cause** | `RT_UploadCeilingInsetLamps` placed one analytic sphere at every `SFLATAQ`/`SFLATAS` **sector center**. Fine for MAP01 ~96×96 booths; large halls get a fake center lamp. |
| **Fix** | `rt_ceiling_lamp_maxspan` **128** — skip analytics if sector AABB width or height exceeds span. Texture `_e` still lights the real edge blobs. |
| **Confirm** | Mid-ceiling white blinks gone; edge inset lamps remain. A/B: `rt_ceiling_lamp_maxspan 0` restores old behavior. |

| | |
|---|---|
| **Symptom** | `screen/level2floorelementnocastlight.png` — raised `SFLATAQ` floor panels glow but cast nothing. |
| **Cause** | `_e` with `emissiveMult=0` (was ceiling-analytic-only). Floor analytic spheres looked bad — removed. |
| **Fix** | `gen_world_emissives.py`: `SFLATAS`/`SFLATAQ`/`SFLATAP`/`SPORT*` `emissiveMult` **1.0** so INDIR GI casts from blob `_e`. No floor analytic lights. |
| **Confirm** | Dark room panels light nearby walls via texture GI only. |

### 1.6c MAP02 yellow door jamb lamps nuclear — **ENGINE FIX 2026-08-05** (needs confirm)

| | |
|---|---|
| **Symptom** | `screen/yellowdoor.png` — doorframe side strips bloom pure white / wash the hall. |
| **Cause** | Retribution stacks **3× PointLight (9800)** per jamb corner (heights 24/64/104), RGB yellow, radius 32. PT uploaded each at `radius × rt_dynlight_intensity` (~1280) and **added** them → ~3840/strip. |
| **Fix** | `rt_dynlight_stack_atten 1` divides by co-located XY count; `rt_dynlight_max 500` hard-caps. Rebuild gzdoom. |
| **Confirm** | `launch-retribution-rt.cmd 2` at yellow key door — soft yellow jamb glow, not white blowout. A/B: `rt_dynlight_stack_atten 0`. |
---

Working for brightmap-validated frames (TROO/TRO2, SARG/SAR2, FATT, CYBR, BSPI, …). **No** eyes for humans (POSS/SPOS/…) or clean HEAD/BOSS/PAIN masks. Auto detect stays **off**.

### 1.6 WashScratch / play tree drift — **PROCESS RISK**

Isolated `build/WashScratch` starts from stock `rt/` and must **re-stage** eyes/world emis each S06. Easy to think eyes/lights are “broken in engine” when only WashScratch is missing overlays. Prefer diagnosing blink/wash on **`launch-retribution-rt.cmd`**.

### 1.7 Phase packaging — **NOT STARTED**

Single overlay pk3 + clean install docs (Phase 5) still pending.

### 1.8 DLSS-RR residual sparkle / salt — **OPEN detail in `rr-noise-investigation.md`**

Short status: debug match = unfiltered diffuse direct; ceiling lamps confirmed amplifier; soft fades landed; boiling **reverted**; `rt_rr_temporal` **failed** (ghost) then left a **black world** when Compose still sampled empty DiffTemporary after `AccumulateForRR` was removed — ComposeNoisy is now **raw unfiltered only**. Full-tree PBR suspected — **do not strip**. Detail → **`rr-noise-investigation.md`**.

---

## 2. What was tested (high-signal)

| Test | Result | Takeaway |
|---|---|---|
| `rt_emis_mapboost 0` (gallery) | Wash gone | Wash is emissive-GI × mapboost path |
| `rt_sky 0` / yaw sweep | Wash remains | Not sky hole (after gallery winding fix) |
| Nuclear strip all emis meta + quarantine `*_e` | Wash gone | Needs some emission path to appear |
| HitInfo INDIR `_e` kill variant (wash-qa 04) | Wash remained (earlier ladder) | Not only `_e` sample path; albedo×mult else-path / contaminants mattered |
| Prefix scrub only | Insufficient | PLAY@4.25 etc. flooded GI |
| Fullscrub keep allowlist | Partial; wash still reported later | Contaminants + sector lights + mult>1 after clamp all layered |
| `emissiveMult` >1 with Saturate clamp | Mult ignored (effective 1) | Fixed TextureMeta + ASManager; then authored 4.2 washed MAP01 → dialed ~1.0 |
| SMON teal panel glass `_e` | Screens look bad | Reverted; BM LEDs + albedo RGB only |
| `lightIntensity` on wall monitors | Floating orbs | Forbidden for walls; floors (lava) only |
| Sector lights always on (`RT_UploadExportableSectorLights`) | Suspected fake fill | Gated `rt_sector_lights` **false** |
| WashScratch S01→S06 | S06 still had wash; eyes missing until staged | Ladder useful; eyes must be staged into WashScratch |
| Ceiling blob `_e` only | Glow yes; blink/shadow **no** | Confirms need dynlight (or attached light) for cast/blink |
| Global scrub + hygiene gate + QA (2026-08-03) | Orbit delta 0.2 / yaw delta 0.6 @ boost 200 (was ~88) | Gallery wash gone on verified-clean meta; see §1.2 |

---

## 3. What currently works (do not regress)

- Retribution loads on patched `gzdoom-rt` (`RT_MapName`, Steam soft gates).
- Native RT + DLSS-RR launchers; keep normal/height strength ≈ **1**.
- Enemy eyes: brightmap `_e`, `emissiveMult≈2`, red, **no** eye `lightIntensity`, **no** `noShadow` — regen: `gen_enemy_eye_emissives.py`.
- World allowlist emis: SMON/EXIT/CRT/keys/lava/logo + switch ON frames (`SWX*B` / GLDEFS) muted green — `gen_world_emissives.py`.
- Monster muzzle frames: `lightIntensity` via `gen_fx_emissives.py` (not Lost Soul).
- MAP01 hangy 3D floor fix wad (TEXTMAP + **BEHAVIOR**); night `SPACE` sky pk3 + `rt_sky 25`.
- Gallery halls: texture / emis / enemy / empty + wash-qa / WashScratch tooling.
- RR path firefly clamp in `CmNoisyCompose` + muzzle soft fade (`rt_mzlflsh_fade`).

---

## 4. Engine / cvar knobs that matter now

| Cvar | Play launcher | Role |
|---|---|---|
| `rt_emis_mapboost` | 200 | INDIR emission scale |
| `rt_emis_maxscrcolor` | 3 | Primary `_e` clamp (12 bleached EXIT) |
| `rt_mod_compat` | 1 | Bit2 brightmap→emis **off** |
| `rt_sector_lights` | **0** | All-sector fake fill — keep off |
| `rt_sector_flicker` | **0** | Off on play — was lighting wall SMON alcoves, not ceiling lamps |
| `rt_ceiling_lamps` | **1** | Blink+cast under `SFLATAS`/`SPORT*` ceilings (spawn head lights) |
| `rt_ceiling_lamp_intensity` | **700** | Peak intensity (soft fade + temporal prefilter) |
| `rt_ceiling_lamp_radius` | **0.10** | Source radius (meters) |
| `rt_ceiling_lamp_off` | **0.12** | Dim floor while “off” — keep light in ReSTIR/RR list |
| `rt_ceiling_lamp_fade` | **8** | Tics to ease on↔off (0 = instant) |
| `rt_ceiling_lamp_debug` | 0 | Cyan markers + console dump of ceiling lamp uploads |
| `rt_hang_lamps` | **1** | Warm cast lights at `LMP1`/`LMP2` hanging tech lamps (MAP04…) |
| `rt_hang_lamp_intensity` | **320** | Per-lamp intensity (dense halls — below ceiling 700) |
| `rt_hang_lamp_radius` | **0.09** | Source radius (meters) |
| `rt_hang_lamp_zofs` | **10** | Drop below SPAWNCEILING origin (map units) |
| `rt_hang_lamp_debug` | 0 | Yellow markers + console dump |
| `rt_translucent_minalpha` | **0.55** | Floor PT alpha for translucent sprites (64Spectre) |
| `rt_dynlight` | 1 | Upload GZDoom FDynamicLight (non-flicker by default) |
| `rt_dynlight_flicker` | **0** | Skip 9802 Flicker lights (wall SMON alcoves) |
| `rt_dynlight_intensity` | **40** | Peak scale for remaining dynlights |
| `rt_dynlight_debug` | 0 | Magenta marker spheres at uploaded GZDoom dynlights |
| `rt_sky` | **25** | Night sky intensity |
| `rt_flsh` | **0** | Toggle horror flashlight (`rt_flsh 1` in console) |
| `rt_flsh_intensity` | **90** | Dim warm beam |
| `rt_flsh_pitch` | **22** | Degrees tip toward ground |
| `rt_flsh_angle` | **42** | Cone width |
| `rt_flsh_color` | ffbe82 | Warm horror tint |
| `rt_flsh_battery` | **1** | On → dying flicker → recharge cycle |
| `rt_flsh_on_secs` / `die` / `off` | 30 / 4 / 5 | Battery phase lengths |
| `rt_flsh_charge` | (readout) | 0..1 for HUD bar |
| `rt_flsh_battstate` | (readout) | 0 off / 1 on / 2 dying / 3 recharge |
| `rt_illum_sens_direct` | **1** | Lighting-change sensitivity (direct) |
| `rt_illum_sens_indirect` | **0.75** | Lighting-change sensitivity (indirect) |
| `rt_illum_sens_spec` | **1** | Lighting-change sensitivity (specular) |
| `rt_mzlflsh_fade` | **5** | Soft fade-out tics after extralight ends (0 = hard cut) |
| `rt_rr_temporal` | **0** | Ghost + black-world hazard — keep off; Compose ignores temporal |

**Console:** `rt_dump_dynlights` — list active FDynamicLight positions / RGB / radius.

### Debug: show light sources?

| Tool | What it shows | Blobs? |
|---|---|---|
| `rt_dynlight_debug 1` | Extra **magenta** RT spheres at every uploaded GZDoom dynlight | **Yes** (engine-side; rebuild required) |
| `rt_dump_dynlights` | Console list of GZDoom lights | No |
| RTGL Dev → **Debug show → Light grid** | Light-grid debug buffer | Grid, not per-light markers |
| RTGL Dev → Diffuse direct / Diffuse indirect | Separates analytic vs GI wash | No |
| Stock “draw all lights as world sprites” | **Does not exist** in RTGL / gzdoom-rt | — |

Open Esc/`~` first so GZDoom releases mouse grab before clicking the RTGL Dev window.

---

## 5. Suggested order to close remaining light bugs

1. **MAP01 spawn A/B on play launcher:** `rt_ceiling_lamp_debug 1` — cyan markers should sit under `SFLATAS` over the zombies; wall SMON should stay quiet (`rt_dynlight_flicker 0`).
2. If no cyan markers: ceiling texture name mismatch — dump names from debug.
3. If markers but weak cast: raise `rt_ceiling_lamp_intensity` / lower `rt_ceiling_lamp_zofs`.
4. A/B: `rt_dynlight_flicker 1` should restore the old wall-terminal blink (wrong target).
5. WashScratch drift: prefer diagnosing on **`launch-retribution-rt.cmd`**.
6. Sky leak mitigated via night `SPACE` + `rt_sky 25`; optional later: find residual geometric aperture if wash returns at higher sky.

---

## 6. Session snapshot (authoring counts)

As of last regen on play tree:

- Enemy eye/fire metas: **143** (`textures_enemy_eyes.json`)
- World emis allowlist: **62** (`textures_world_emis.json`) including **10** `ceiling-blobs` sources
- Ceiling `_e` present: `SFLATAS`, `SPORT1`, … under `rt/mat_dev/`
- Global `rt/data/textures.json`: **669 emis entries = authored keep set exactly** (hygiene-gated; was ~670 incl. 42× PLAY @ 4.25 stock contaminants)
- Follow-up: `FIRELAV*`/`FIREWAL*` world textures now **non-emissive** (fx FIRE prefix leak fixed). If Retribution maps use them, author via world allowlist (lava policy) — check with `discover_world_emissives.py`.

---

*Update this file when an item moves to fixed or a test changes the conclusion. Prefer short factual rows over narrative.*
