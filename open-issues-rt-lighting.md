# Open issues — Retribution RT (2026-08-03)

Living punch list of **what still fails**, what we **tested**, and what **works**.  
Do not treat this as a progress cheer sheet — only unresolved / partially resolved items belong in §1.

**Related:** `AGENTS.md`, `compat-patches.md`, `material-authoring-spec.md`, `gallery-emis-wall-wash-fix-plan.md`, `gallery-emis-wall-wash-diagnostics.md`

**Play path (canonical):** `tools/launch-retribution-rt.cmd` → `sourcecode/gzdoom-rt/build/RelWithDebInfo/`

---

## 1. Unfixed / incomplete

### 1.1 / 1.3 Spawn blink + shadow-cast lights — **CEILING LAMPS 2026-08-03** (needs visual confirm)

| | |
|---|---|
| **Target** | Ceiling **head lights** over MAP01’s first zombies (`SFLATAS` secs 31/33) — **not** wall SMON terminals. |
| **Why wall terminals blinked** | Alcove secs **32/34** are `dLight_Flicker` (65) + green **9802** at the SMON. Dynlight upload (and any sector_flicker/lights) lightstyles those alcoves. |
| **Why `rt_sector_lights 1` looked dead for ceilings** | Booth ceilings have **special 0 / steady lightlevel 200** — sector lights never blink them. Enabling all-sector lights mostly adds steady fill; the only blink still comes from alcove 65 / 9802. |
| **Fix landed** | `RT_UploadCeilingInsetLamps()` under `SFLATAS*`/`SPORT*` (intensity **900**). `rt_dynlight_flicker 0` skips 9802 wall flashers. `rt_sector_flicker 0`. Debug: `rt_ceiling_lamp_debug 1` → cyan markers + console. |
| **Confirm** | Spawn booths: ceiling blobs pulse + cast on zombies; SMON panels quiet. A/B `rt_ceiling_lamps 0` / `rt_dynlight_flicker 1`. |

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

### 1.5 Enemy eyes incomplete coverage — **PARTIAL**

Working for brightmap-validated frames (TROO/TRO2, SARG/SAR2, FATT, CYBR, BSPI, …). **No** eyes for humans (POSS/SPOS/…) or clean HEAD/BOSS/PAIN masks. Auto detect stays **off**.

### 1.6 WashScratch / play tree drift — **PROCESS RISK**

Isolated `build/WashScratch` starts from stock `rt/` and must **re-stage** eyes/world emis each S06. Easy to think eyes/lights are “broken in engine” when only WashScratch is missing overlays. Prefer diagnosing blink/wash on **`launch-retribution-rt.cmd`**.

### 1.7 Phase packaging — **NOT STARTED**

Single overlay pk3 + clean install docs (Phase 5) still pending.

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
- World allowlist emis: SMON/EXIT/CRT/keys/lava/logo (+ ceiling blob `_e` now) — `gen_world_emissives.py`.
- Monster muzzle frames: `lightIntensity` via `gen_fx_emissives.py` (not Lost Soul).
- MAP01 hangy 3D floor fix wad (TEXTMAP + **BEHAVIOR**); night `SPACE` sky pk3 + `rt_sky 25`.
- Gallery halls: texture / emis / enemy / empty + wash-qa / WashScratch tooling.

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
| `rt_ceiling_lamp_intensity` | **900** | Peak intensity (~dynlight hi×40) |
| `rt_ceiling_lamp_radius` | **0.08** | Source radius (meters) |
| `rt_ceiling_lamp_debug` | 0 | Cyan markers + console dump of ceiling lamp uploads |
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
