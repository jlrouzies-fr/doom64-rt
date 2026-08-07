# DLSS-RR session handoff — 2026-08-06

## TL;DR

**Root cause #1 (fixed): `RTGL1.dll` was built with DLSS Ray Reconstruction
compiled out.** Not a shader bug, not a framebuffer bug, not a denoiser-tuning
problem. Fixed, rebuilt, confirmed via `rt_rr_status`: `DLSS2 available = YES`,
`RR REQUESTED = YES`. RR is now genuinely running.

**Root cause #2 (found, explains all "zero difference" results this
session): `rt_rr_reset_hold` is `CVAR_ARCHIVE`.** It got set to `1` during an
early diagnostic *before* the DLL fix, saved to the ini, and silently
persisted across every relaunch since — including the "everything is very
noisy" report right after the DLL fix landed. That single stuck cvar explains
why `rt_rayreconstr 0` vs `1` looked identical too (both were forced into
per-frame full history discard). **Any test run before this was found is
unreliable and needs redoing** — see "Now confirmed" below for what has
actually been validated with a clean cvar state.

**Root cause #3 (fixed, `bbe1d1b85`): the dynlight appear/disappear diff
counted brightness dips as disappearances.** Pulse/Flicker lights crossing the
`0.01f` radius/intensity cutoffs left and re-entered the tracked set, firing
`InReset` as often as every frame. Fixed — presence is now recorded before the
brightness cutoffs. **In-game: image confirmed genuinely more stable** (incl.
MAP01), no more light linger. This cause did **not**, however, explain the
noise reported at MAP02 spawn — see #4.

**Root cause #4 (fixed, `5b36421d3`): ceiling inset lamps (a third,
independent synthetic-light system, `rt_ceiling_lamps`) swing ~33x in
intensity every cycle, too fast for ReSTIR's temporal reservoir reuse to
track.** Not gated by `rt_dynlight`/`rt_sector_lights` — that's why the
MAP02-spawn "4 blinking lights" ignored every dynlight cvar tested. Fix:
`rt_ceiling_lamp_fade` default raised 8 → 40 tics. **Awaiting in-game
re-check** (should reduce, not necessarily eliminate, localized salt at those
lamps — see NEXT ACTION).

**Root cause #6 (THE blocker, fixed + VERIFIED 2026-08-07): a stale
`rt_upscale_fsr2=2` in the ini overwrote the DLSS upscaler selection, and RTGL
silently drops Ray Reconstruction whenever the upscaler isn't DLSS.** Fixing #5
was *not* enough — `rt_rayreconstr` still did nothing until this. **DLSS-RR is
now confirmed running**, by logging from inside RTGL, and `rt_rayreconstr`
`0`/`1` demonstrably switches denoiser paths. Three independent layers of muted
diagnostics had to be removed before the bug was even observable. See root
cause #6 below — this is the one to read.

**Root cause #5 (fixed 2026-08-07): RTGL's Dev UI was silently
overriding `rt_rayreconstr`, and the override persisted across launches.** RR
was **off** for essentially every test in this document. Everything reported as
"RR is stable / RR is noisy / RR fixed the linger" was measuring **A-SVGF**.
Real, but not the blocker — see #6.
`rt_rr_status` could not detect this — it reads gzdoom's request, upstream of
the override. See "Root cause #5" below for the mechanism and what it
invalidates.

**Ruled out this session — one of these is now RETRACTED:**
- ~~`rt_emis_maxscrcolor` (proposals item 1, unguided screen emission)~~
  **Retracted.** `ovrd_enable = true` was persisted in
  `rt/devmode_settings.json`, and `Dev_Override` forces
  `emissionMaxScreenColor` from the Dev value every frame
  (`VulkanDevice_Dev.cpp:1897`). Typing `rt_emis_maxscrcolor 0` did nothing.
  **Item 1 is still an open suspect and needs re-testing.**
- Stale NGX DLL (proposals item 5) — **still valid**, this one was a direct
  file inspection: `nvngx_dlssd.dll` is 310.7.0, Preset E supported. Not
  affected by any cvar or override.

Every earlier "no effect" symptom in this doc follows from causes #1 and #2,
including all six failed experiments recorded in `flashlight-linger-issue.md`
(which predate the DLL fix) and this session's own `rt_rayreconstr` A/B
(which was contaminated by the stuck `reset_hold`).

---

## The bug

`deps/RTGL/CMakeLists.txt` gated the whole DLSS block on:

```cmake
if (RG_WITH_NATIVE_DLSS AND DEFINED ENV{DLSS_SDK_PATH})
```

At some point RTGL was configured with `-DDLSS_SDK_PATH=...` — a CMake
*variable*, not an *environment* variable. `DEFINED ENV{...}` is false for that,
so the block was skipped:

- `RG_USE_NATIVE_DLSS2` never defined
- `nvsdk_ngx_d.lib` never linked
- `DLSSRR.cpp` compiled to its empty `#else` stub (`DLSSRR.cpp:470`,
  `MakeInstance` → `return {}`) ⇒ **`nvDlssRr` permanently null**

CMake then cached the `-D` value (`DLSS_SDK_PATH:UNINITIALIZED=...`), so every
later rebuild silently reused the poisoned cache.

### Why it was invisible

- No build error. No link error.
- No runtime diagnostic either — the `"DLSSRR: ..."` log strings live *inside*
  the compiled-out branch, so even `-rtdebug` printed nothing.
- gzdoom still requested `rayReconstruction = 1`, because `nvDlss` survives on
  DLSS3-FG availability alone (`rt_main.cpp:3152`:
  `rt_available_dlss2 || rt_available_dlss3fg`).
- `VulkanDevice.cpp:798` skips A-SVGF whenever RR is requested and the
  `nvDlssRr` object exists — it never checks that RR *works*.

Net: **no denoiser at all**, which is exactly the "raw 1-spp noise" seen.

### Symptom → explanation map

| Observed | Cause |
|---|---|
| `rt_rr_reset_hold 0` vs `1` — zero difference | `InReset` never reaches NGX |
| `rt_rr_disocc 0` — zero difference | mask feeds a `pInDisocclusionMask` nobody consumes |
| `rt_rr_reset_on_lightcut/on_dynlight 0` — zero difference | same; RR absent |
| Dev-menu RR toggle does nothing | there is no RR to toggle |
| No `DLSSRR:` line even with `-rtdebug` | strings not in the binary |
| `DLSS2 available = NO`, no reason string | `nvDlss2` null; that branch never sets a reason |
| Image = pre-guide-fix noise | A-SVGF skipped *and* RR absent ⇒ no denoiser |
| Ghosting "better" | nothing was temporally accumulating |

---

## Fixes committed

| repo | commit | what |
|---|---|---|
| `deps/RTGL` | `f133bda` | Accept `DLSS_SDK_PATH` from env **or** `-D`; `FATAL_ERROR` if path set but `nvsdk_ngx.h` missing; loud `message(WARNING)` if `RG_WITH_NATIVE_DLSS=ON` with no path. Verified all three cases. |
| `sourcecode/gzdoom-rt` | `d19782c36` | `rt_rr_status` CCMD — prints the full RR decision chain (request, upscale mode, Remix flag, DLSS2/DLSS3-FG availability + RTGL failure reasons, resulting requested flag). This is what surfaced the bug. |
| `sourcecode/gzdoom-rt` | `0a42122f5` | Transient-light history flush (see below). |
| `sourcecode/gzdoom-rt` | `bbe1d1b85` | Root cause #3: record dynlight presence before the brightness cutoffs so pulse dips stop firing `InReset`; add `rt_rr_reset_debug`. |
| `sourcecode/gzdoom-rt` | `5b36421d3` | Root cause #4: `rt_ceiling_lamp_fade` default 8 → 40 tics — gentler intensity swing for ReSTIR/RR reservoirs. |
| `deps/RTGL` | (this session) | Root cause #5: don't restore `ovrd_enable` / sticky flags from `devmode_settings.json`; warn when a Dev override contradicts the game's RR request. |
| `sourcecode/gzdoom-rt` | (this session) | `rt_rr_status` now states it reports a *request*, not the applied state. |
| `Doom64-RT` (top) | `01aefc6`, `0d146f3` | Docs + launcher cvars. |

### Verification that the DLL is now correct

| check | before | after |
|---|---|---|
| `RG_USE_NATIVE_DLSS2` in `RayTracedGL1.vcxproj` | 0 | 8 |
| `nvsdk_ngx` linked | 0 | 4 |
| `DLSSRR` literals in DLL | 0 | 12 |
| `NVSDK_NGX` | 0 | 32 |
| DLL size | 2,461,184 | 2,526,720 |

Deployed artifacts (`sourcecode/gzdoom-rt/build/RelWithDebInfo/`):
`gzdoom.exe` 21:10, `rt/bin/RTGL1.dll` 21:20, `rt/shaders/*.spv` 21:18.
**Everything is built and staged. No rebuild needed to test.**

> Note: to scan a DLL for strings on this box, use PowerShell
> (`[Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($p))`) — there is
> **no `strings` binary**; `strings` in bash silently returns nothing and looks
> like a real negative result.

---

## Now confirmed (this session, post-DLL-fix)

> **RETRACTED 2026-08-07 — see root cause #5.** The first and last bullets below
> are wrong. `rt_rr_status` reports gzdoom's *request*, which RTGL's Dev UI was
> silently overriding; RR was **off** for these tests and A-SVGF produced the
> "more stable" image. Kept verbatim as a record of how the wrong conclusion was
> reached.

- ~~`rt_rr_status`: `DLSS2 available = YES`, `RR REQUESTED = YES`. RR is real.~~
  **False** — proves only that gzdoom asked, not that RTGL complied.
- `rt_rr_reset_hold` is `CVAR_ARCHIVE` (persists in the ini across launches —
  every `RT_CVAR` does, see `rt_main.cpp:84`: `CVAR_GLOBALCONFIG | CVAR_ARCHIVE`
  unless the name starts with `_`). It was left at `1` from an earlier
  diagnostic and caused the "very noisy" report even though RR was working.
  **Before any further A/B testing, explicitly check/set every `rt_rr_*`
  cvar** (`rt_rr_status`, plus `rt_rr_reset_hold`, `rt_rr_reset_now`,
  `rt_rr_disocc_show`) rather than assuming defaults — a past console session
  can leave any of them stuck.
- RR toggling works via the **Dev GUI**; console `rt_rayreconstr` does **not**
  — now explained by root cause #5. The Dev GUI was the only working control
  precisely *because* it set the sticky flag that killed the cvar.
- ~~With RR genuinely active … **lingering is fixed**, RR reads as "more
  stable"~~ **False (root cause #5).** RR was off. The stable, linger-free
  image was **A-SVGF**. The "noisier than A-SVGF" comparison was RR-off vs
  RR-off — it measured nothing about RR.

## Root cause #3 (found in code and fixed, 2026-08-07): dynlight set churn

`sourcecode/gzdoom-rt` `bbe1d1b85`. The working theory below was confirmed by
reading the code: `RT_UploadGzDoomDynamicLights` recorded a light's `stableId`
into `curDynIds` **after** the brightness cutoffs —
`m_currentRadius <= 0.01f`, post-scaling `intensity <= 0.01f`, and
`cr+cg+cb <= 0`. Any Pulse/Flicker light dipping below one of those for a few
tics therefore *left* the set and re-entered it, which reads as a scene-lighting
cut and fires `InReset`. With several such lights on a map that can fire every
frame — i.e. permanent full-history discard, which is exactly the observed
"stable but noisier than A-SVGF".

This is the same failure mode as stuck `rt_rr_reset_hold` (root cause #2),
reached by a different route, which is why the image looked identical in both
states. And it was invisible to the earlier `rt_dynlight_debug` check for the
reason predicted below: that prints the *count*, and one ID leaving as another
enters leaves the count flat while `curDynIds != s_prevDynIds` is still true.

**Fix:** record presence right after the *static* eligibility checks
(`IsActive` / subtractive / uninitialized / flicker-disabled), before any
brightness cutoff. Presence now means "this `FDynamicLight` exists and is
active", which is what actually corresponds to a lighting cut. Explosion
flashes and pickups still fire correctly (those are genuinely new/destroyed
lights).

**Also added: `rt_rr_reset_debug`** (default off) — logs every flush with its
cause (`flashlight` / `dynlight` / `levelload`), a throttled dynlight set-delta
line (`+N/-M`, one line per 15 changes so an every-frame trigger can't drown the
console), and a once-a-second `fired / suppressed-by-rate-limit` tally. An
over-firing trigger is now directly observable instead of inferred.

Built and staged: `build/RelWithDebInfo/gzdoom.exe` (2026-08-07 05:27). No
`RTGL1.dll` change, so no RTGL rebuild needed.

**Launcher hardening** (same date): `tools\launch-retribution-rt.cmd` now
forces `rt_rr_reset_hold 0`, `rt_rr_reset_now 0`, `rt_rr_reset_debug 0` on every
launch. Every `RT_CVAR` is `CVAR_ARCHIVE`, so root cause #2 (a diagnostic left
at `1` persisting silently in the ini) can no longer contaminate a test run
started from the launcher.

## In-game verification (2026-08-07 play session)

- **Confirmed:** image is genuinely more stable than the pre-DLL-fix baseline,
  including on MAP01 (which was noisy even under the 2026-08-05 guide fix, but
  had the linger bug). No more light linger. Root causes #1–#3 are real
  improvements, not just theory.
- **`rt_emis_maxscrcolor 0` test: negative.** It only dims the emissive
  *texture* itself; it does not touch the separately-blinking lights sitting
  on top of that texture. Proposal item 1 (screen-emission unguided into RR
  color) is **not** the cause of the MAP02-spawn noise — still plausible for
  *other* noise, just not this specific symptom. Ruled out for this case only.
- **`rt_dynlight 0` test: negative.** The 4 blinking lights at MAP02 spawn kept
  blinking with dynlights fully disabled — they are not GZDoom dynlights, so
  every `rt_dynlight_*`/`rt_rr_reset_on_dynlight` cvar was structurally unable
  to affect them. This sent the investigation to a **third, separate light
  system** — see root cause #4.
- **NGX DLL version: cleared.** `rt/bin/nvngx_dlssd.dll` is 310.7.0, well past
  the 310.2.1 Preset-E requirement — no silent CNN fallback (proposals doc §0
  item 5). Was flagged "verify first" and had never actually been checked
  because RR wasn't running until this week.

## Root cause #4 (found and fixed, 2026-08-07): ceiling-lamp intensity swing

`rt_main.cpp:4089-4250`, `RT_UploadCeilingInsetLamps` (name approximate — see
`rt_ceiling_lamps` cvar block). A **third, independent** synthetic-light path,
gated by ceiling texture name (`SFLATAS`/`SFLATAQ`/`SFLATAP`/`SPORT*`) —
comment at line 4142 names MAP02 SFLATAQ corridors explicitly. Not gated by
`rt_dynlight` or `rt_sector_lights`, which is why neither affected it.

Each qualifying sector blinks on a per-sector phase
(`maptime*4 + sectorIndex*23) % 256`) between full intensity
(`rt_ceiling_lamp_intensity`, default 700) and a dim floor
(`peak * rt_ceiling_lamp_off * 0.25`, ≈21 at defaults) — a ~33x swing. The
light is deliberately *never removed* from the ReSTIR/RR list (existing
comment: "hard delete was the RR noise source"), so it never trips the
history-reset path from root cause #3. But the swing itself, eased over only
`rt_ceiling_lamp_fade` = 8 tics (≈0.2s) at the old default, is too abrupt for
ReSTIR's temporal reservoir reuse to track — producing salt/noise localized
right at the lamp. This matches the reported symptom exactly (noise
concentrated on 4 independently-phased lights at MAP02 spawn, unaffected by
any dynlight/sector-light cvar).

**Fix (`sourcecode/gzdoom-rt` `5b36421d3`):** raised the `rt_ceiling_lamp_fade`
default 8 → 40 tics (~1.1s), spreading the same swing thin enough for ReSTIR to
track smoothly. Also updated in `tools\launch-retribution-rt.cmd`, which was
pinning the old value of 8 explicitly (would have overridden the new default).
User-confirmed direction: "more gentle on the denoiser, should be default."

Built and staged: `build/RelWithDebInfo/gzdoom.exe`. No RTGL rebuild needed.

## Root cause #5 (fixed, 2026-08-07): Dev UI override killed `rt_rayreconstr`

**RR was off for essentially every test recorded in this document.** The
"more stable, no linger" image everyone was judging was **A-SVGF**.

`rt/devmode_settings.json` persisted three fields across launches:

```
ovrd_enable             = true    ← Override master switch
rayReconstruction       = true
rayReconstructionSticky = true
```

`VulkanDevice_Dev.cpp`, `Dev_Override(RgStartFrameInfo&, ...)`, the branch
taken when the Override checkbox is **unchecked**:

```cpp
else if( devmode->rayReconstructionSticky )
{
    resolution.rayReconstruction = devmode->rayReconstruction;  // stomps rt_rayreconstr
}
```

`rayReconstructionSticky` is set `true` by *either* RR checkbox in the Dev UI
and cleared only by the "Follow game (rt_rayreconstr)" button. It was
serialized to JSON and restored on load. So touching that checkbox once, in any
session, permanently disabled `rt_rayreconstr` in every later launch —
regardless of the Override switch. The UI advertises "works without Override",
so the live behaviour is intentional; **persisting it across launches is the
bug.**

**Why nothing caught it:** `rt_rr_status` prints `g_rr_dbg_rrRequested`
(`rt_main.cpp:3290`) — gzdoom's request, produced *before* `Dev_Override` runs
inside the DLL. It reported `RR REQUESTED = YES` while RTGL forced RR off. An
intention was read as a fact, and that single misreading is what let a wrong
conclusion survive multiple sessions.

**Second blast radius — `ovrd_enable = true`.** It also gates
`Dev_Override(illumination, tonemapping, textures)`, which force-replaces
`emissionMapBoost`, **`emissionMaxScreenColor`**, `normalMapStrength`,
`heightMapDepth`, `maxBounceShadows`, ev100 range, saturation/crosstalk, plus
`upscaleTechnique` / `resolutionMode` / `frameGeneration` on the resolution
side. **Any console cvar mapping into those was silently reverted every
frame** — which is exactly what invalidated the `rt_emis_maxscrcolor 0` test.

**Fix (`deps/RTGL`, RTGL1.dll rebuilt + staged):**
1. `ApplyDevmodeSettings` no longer restores `drawInfoOvrd.enable`,
   `rayReconstructionSticky`, `rrTemporalPrefilterSticky`, or
   `illumSensSticky` — all forced `false` on load. Override *values* still
   persist, so Dev tuning survives a relaunch; only the switches that make them
   replace the game's values reset. Same principle as forcing
   `rt_rr_reset_hold/_now/_debug` to 0 in the launcher.
2. New edge-triggered `debug::Warning` whenever the applied RR value disagrees
   with the game's request: `"Dev override: DLSS Ray Reconstruction forced
   ON/OFF (game requested ...)"`. Needs `-rtdebug` to be visible.
3. `rt_rr_status` now states outright that it reports a *request*, not the
   applied state, and how to confirm the real one.

Also found stuck in that JSON: `rrTemporalPrefilter = true` +
`rrTemporalPrefilterSticky = true`, despite the Dev UI labelling it
"EXPERIMENTAL — default OFF" and blaming it for a "faded duplicate/ghost depth
view". Inert today (`AccumulateForRR` is never called — finding #5 below), but
it was on.

**Deleted** the poisoned `rt/devmode_settings.json` (backup in the session
scratchpad as `devmode_settings.json.bak`).

### What this invalidates, and what survives

| Claim | Status |
|---|---|
| Root cause #1 — RR compiled out of the DLL | **Valid** — binary string/symbol inspection, independent of runtime state |
| Root cause #2 — `CVAR_ARCHIVE` stuck cvars | **Valid** — code fact |
| Root cause #3 — dynlight set churn | **Valid as a code bug** (read directly from source); its *effect on RR* is unmeasured |
| Root cause #4 — ceiling-lamp 33x swing | **Valid as a code bug**; feeds ReSTIR, upstream of both denoisers, so the fix stands. But "confirmed in-game" measured A-SVGF |
| NGX DLL 310.7.0 / Preset E | **Valid** — file inspection |
| "RR is genuinely running" | **False** |
| "RR more stable, no linger" | **False** — that was A-SVGF |
| "`rt_emis_maxscrcolor` rules out proposals item 1" | **False** — override reverted it; item 1 still open |
| Ghosting on shotgun sprite vs flashlight | Not reproducible on retry; parked |

## Root cause #6 (THE one that kept RR off, fixed + verified 2026-08-07)

Root cause #5 was real but was **not** why `rt_rayreconstr` did nothing. After
fixing #5 the cvar still had no effect. Ground-truth logging (added this
session, see below) produced the contradiction that cracked it:

```
gzdoom : RT upscale/RR decision: DLSS2=yes nvDlss=2 wantNativeRr=yes -> rayReconstruction=ON
RTGL   : Setup(): params.upscaleTechnique=2  params.rayReconstruction=1
RTGL   : Denoiser path: A-SVGF (DLSS-RR object=present, DLSS upscaler=off, RR flag=off)
```

`upscaleTechnique=2` is `AMD_FSR2`; `NVIDIA_DLSS` is `3`.

**Cause:** in `RT_UpscaleCvarsToRtgl`, DLSS and FSR2 both write
`pDst->upscaleTechnique`, and the FSR switch runs **second**:

```cpp
switch( nvDlss ) { case 2: pDst->upscaleTechnique = NVIDIA_DLSS; ... }
switch( amdFsr ) { case 2: pDst->upscaleTechnique = AMD_FSR2; ... }  // clobbers
```

`rayReconstruction` was then set anyway, because that check only tested
`nvDlss != 0` and never rechecked that DLSS survived. gzdoom therefore sent
RTGL **"upscaler = FSR2 + rayReconstruction = 1"**, and
`RenderResolutionHelper::Setup` resolves that contradiction by silently
clearing `rayReconstruction` (it requires DLSS) and running A-SVGF.

The trigger was `rt_upscale_fsr2=2` sitting in
`Documents/My Games/GZDoom/gzdoom-rt2.ini` (default `0`). `RT_CVAR` ⇒
`CVAR_ARCHIVE`, the launcher never reset it — **the third time a persisted
archived cvar silently invalidated an entire run of tests** (see #2, #5).

**Fixes (`gzdoom-rt` `23e12994b`):**
1. Upscalers made mutually exclusive — DLSS wins when both are set (RR needs
   it), with a one-time console warning naming both cvars.
2. `rayReconstruction` now gated on the technique that actually survived both
   switches, so the contradiction cannot be reconstructed.
3. Launcher forces `+rt_upscale_fsr2 0`; the stale ini value was corrected
   (backup: `gzdoom-rt2.ini.bak` in the session scratchpad).

### Why this took so long: three layers of silence

Each had to be removed before the bug was even observable.

| Layer | Effect | Fix |
|---|---|---|
| `RgInstanceCreateInfo::allowedMessages = 0` without `-rtdebug` | muted RTGL **WARNING and ERROR** — this is how "RR compiled out of the DLL" (#1) hid | always allow `WARNING\|ERROR` |
| `RT_Print` → `DPrintf( DMSG_WARNING, ... )` | second gate: needs gzdoom `developer >= 2` | `Printf` for warnings |
| No report of the *applied* state anywhere | `rt_rr_status` showed only the request | RTGL logs `Setup()` params + resolved denoiser path |

**Verified in-game, ground truth from inside RTGL:**

| `rt_rayreconstr` | logged denoiser path |
|---|---|
| `1` | `DLSS-RR (ComposeNoisy -> nvDlssRr->Apply)` — upscaler=on, RR flag=on |
| `0` | `A-SVGF (Denoise)` — DLSS upscaler still on |

**DLSS-RR is now confirmed running for the first time in this investigation.**
`nvDlssRr` is non-null, so root cause #1's CMake fix is also confirmed good at
runtime.

## RESOLVED — re-baselined with RR on; investigation closed 2026-08-07

The re-baseline was completed the same day. **Full conclusion lives in
`rr-noise-investigation.md` §10** — read that, not this section, for the
finding and the recommendation. Summary:

1. **Done** — plumbing fixed and verified (root cause #6). Every launch prints
   `Denoiser path: ...` with no `-rtdebug` needed. If it doesn't say `DLSS-RR`,
   no RR observation is valid. That line is the whole acceptance test.
2. **Done** — `rt_rayreconstr 0` vs `1` demonstrably switches denoiser paths,
   verified from inside RTGL in both states.
3. **Done, and it's structural, not a bug.** With RR genuinely running: the raw
   1-spp input is very noisy and *identically* noisy static vs in motion, while
   RR converges when static and fizzles in motion. RR's temporal accumulation
   works; motion costs it history, and the RR path has **no spatial or temporal
   prefilter at all** to fall back on, whereas A-SVGF has anti-firefly plus a
   variance-driven à-trous. A-SVGF is buying stability with blur.
   Measured and ruled out: disocclusion mask, volumetrics, parallax/normal maps,
   sample density (DLAA), preset D (worse), firefly clamp (added ghosting).
   **Recommendation: default to A-SVGF, keep RR as an option.**
4. `rt_emis_maxscrcolor` — not retested. Low prior: volumetrics is the same
   class of unguided `pInColor` contaminant and measured no effect.
5. Disocclusion mask — **validated**: `rt_rr_disocc 0` changes nothing and
   `_show 1` fires sparsely near sprites, i.e. working as designed and not a
   noise source.

**Still genuinely open:** ReSTIR decorrelation (the only lever that adds
information rather than trading artefacts) and the missing `RR_DISOCCLUSION`
barrier in `ImageComposition::Finalize()` (a real RAW hazard, unrelated to this
symptom).

## Superseded NEXT ACTION — verify root cause #4 in-game

1. Launch at MAP02 spawn, watch the 4 lamps. Expect noticeably less salt right
   at them than before, without the lamps looking noticeably less "blinky" —
   40 tics is still a fast fade, not a slow glow.
2. If noise is still visible there, try further: `rt_ceiling_lamp_fade 80` or
   raise `rt_ceiling_lamp_off` (default 0.12, e.g. 0.4) to shrink the swing
   itself rather than just spreading it. Both are live cvars.
3. Also check `rt_hang_lamps` — a sibling system (`rt_main.cpp:4307+`,
   "hanging tech lamps", warm shadow-casting lights at Doom 64 lamp things) —
   for the same fixed-swing pattern, in case other maps show similar localized
   noise at those.
4. Once localized-at-lamp noise is resolved, re-judge overall RR vs A-SVGF
   noise via the Dev GUI toggle. If still worse, the next suspect is the guide
   computation itself (`rr-noise-fix-proposals.md` items 1–3 — note item 1,
   screen-emission, was tested and ruled out for *this* symptom but not
   globally; items 2–3 on PBR/ORM surfaces are untested).
5. Then the disocclusion mask (`rt_rr_disocc 0` vs `1`) — still never tested
   with a working RR and clean cvars. Finding #4 in "Findings that remain
   valid" below (missing `RR_DISOCCLUSION` barrier in
   `ImageComposition::Finalize()`) is unrelated to this root cause #4 (same
   number, different list) and still unfixed — RTGL-side, needs a DLL rebuild.
6. Re-verify lingering under a clean cvar state: toggle `rt_flsh`, trigger an
   explosion, confirm no ~3–7 s delay.

### Original theory (now confirmed — kept for the reasoning trail)

Working theory: the Part 1 dynlight-diff reset trigger
(`rt_rr_reset_on_dynlight`, `RT_UploadGzDoomDynamicLights`) may be firing far
more often than the earlier `rt_dynlight_debug` check suggested. That check
only confirmed the **printed count** stayed flat at 67 — it does **not**
rule out churn: if one light's ID leaves the set the same frame another
light's ID enters, the count is unchanged but `curDynIds != s_prevDynIds` is
still true and a reset still fires. That earlier check was also run *before*
the DLL fix, when RR wasn't consuming `resetHistory` at all, so it never
actually exercised this path under real conditions. Directly plausible if the
map has multiple Pulse-type lights whose `m_currentRadius` independently
oscillates across the `0.01f` cutoff (`rt_main.cpp` upload loop) — net count
stable, membership constantly different, reset firing almost every frame.

Confirmed by code inspection and fixed in `bbe1d1b85` — see root cause #3
above. The predicted mechanism was exactly right, including why the
`rt_dynlight_debug` count check couldn't see it.

`tools\launch-retribution-rt.cmd 1 debug` still writes the full console
transcript to `G:\ai\Doom64-RT\rt-console.log` (gitignored) for anything that
needs sharing back.

---

## Part 1 (committed, unvalidated): transient-light history flush

`sourcecode/gzdoom-rt` `0a42122f5`, all in `rt_main.cpp`. Pulses the
already-wired-but-unused `RgDrawFrameInfo.resetHistory` →
`VulkanDevice.cpp:654,924` → `DLSSRR.cpp:391` `evalParams.InReset`.

Shared `g_rt_lightcut` flag (declared near `FlashlightLightId`, **not** beside
`g_resetposteffects` — `RT_AddFlashlight` is an inline method of a class nested
in the same anonymous namespace and needs forward-visible lookup), set by:

- **Flashlight** (`RT_AddFlashlight`, `rt_rr_reset_on_lightcut`): `rt_flsh`
  toggle or abrupt `battScale` jump > `rt_rr_reset_delta`. Smooth
  `fadeValley()` dying-flicker/blinks excluded on purpose.
- **Dynlights** (`RT_UploadGzDoomDynamicLights`, `rt_rr_reset_on_dynlight`):
  frame-over-frame `unordered_set<stableId>` diff — catches explosion flashes,
  pickups. Muzzle flash deliberately **not** wired in (fires every shot; has
  `rt_mzlflsh_fade`).
- **Level load** (`RT_OnLevelLoad`): unconditional.

Consumed once per frame in `RTFrameBuffer::RT_DrawFrame`, rate-limited by
`rt_rr_reset_min_ms`.

New cvars: `rt_rr_reset_on_lightcut` (on), `rt_rr_reset_delta` (0.5),
`rt_rr_reset_on_dynlight` (on), `rt_rr_reset_min_ms` (250),
`rt_rr_reset_hold` / `rt_rr_reset_now` / `rt_rr_reset_debug` (diagnostics —
all three forced to 0 by the launcher, since `CVAR_ARCHIVE` makes a stuck one
poison later tests).

**Caveat — this was root cause #3, fixed in `bbe1d1b85`:** the original
commit-message claim that flicker/pulse lights "never touch" the dynlight diff
was wrong. Lights crossing the `intensity <= 0.01f` / `m_currentRadius <= 0.01f`
cutoffs entered and left the set. `rt_dynlight_debug` showed a rock-steady count
of 67, but that only proves the *count* didn't change — one ID leaving and a
different ID entering the same frame nets to an unchanged count while still
tripping `curDynIds != s_prevDynIds`. Presence is now recorded before those
cutoffs, so the claim holds by construction. `rt_rr_reset_debug` reports the
actual `+N/-M` deltas if it ever needs re-checking.

---

## Findings that remain valid (from the earlier investigation)

1. **Framebuffer plumbing for the disocclusion mask is correct.**
   `FB_IMAGE_INDEX_RR_DISOCCLUSION = 72`, `VK_FORMAT_R16_SFLOAT`, render-res,
   one `VkImage`, bindings 72 / sampler 153 identical in `Bindings[]` and
   `BindingsSwapped[]` (no ping-pong), same descriptor set for both passes,
   `ShGlobalUniform` std140-identical C++↔GLSL, deployed SPV byte-matches a
   fresh compile. The issue doc's "unallocated framebuffer" theory is **wrong**.

2. **Pass order is the inverse of what the issue doc assumed.** Actual, one
   command buffer: `CmNoisyCompose` (`VulkanDevice.cpp:803`) → `CmCheckerboard`
   (:814) → raster (:820) → `CmPrepareFinal` (:833) → `nvDlssRr->Apply` (:918).
   `CmPrepareFinal`'s output **is** RR's `pInColor`. So the red debug tint in
   `CmPrepareFinal.comp:67-74` is upstream of the denoiser — an unreliable
   instrument regardless of the DLL bug.

3. **`pInDisocclusionMask` is undocumented.** Zero occurrences of
   "disocclusion" in the DLSS-RR Integration Guide (Dec 2025); only a bare
   header comment (`nvsdk_ngx_helpers_dlssd_vk.h:125`). The `10000.0` sentinel
   is a Remix-derived guess. The **documented** per-pixel lever is
   `pInResponsivityMask` (`nvsdk_ngx_helpers_dlssd.h:223`: one channel, range
   **[-1,1]**, R16F or R8_SNORM, input res, key `DLSSD.ResponsivityMask`) —
   RTGL sets neither it nor any transparency/particle guide.

4. **Missing barrier:** `ImageComposition::Finalize()`
   (`ImageComposition.cpp:110-115`) barriers only `SCREEN_EMISSION`, `FINAL`,
   `DEPTH_WORLD`, `SCATTERING` — never `RR_DISOCCLUSION`, despite
   `CmPrepareFinal.comp:70` reading it. Unsynchronised RAW hazard.

5. **Dead code:** `AccumulateForRR()` (`Denoiser.cpp:258`) is never called;
   `VulkanDevice.cpp:798-808` unconditionally uses `ComposeNoisy()` on the RR
   path. So `enableRrTemporalPrefilter` / `rt_rr_temporal` gate nothing and
   `+rt_rr_temporal 0` in the launcher is a no-op.

6. **`rt_main.cpp:2710-2714`** sets `allowedMessages = 0` unless `-rtdebug` is
   passed — all RTGL diagnostics are muted by default. Launcher now supports a
   second arg `debug` to enable it.

---

## Parts 2 & 3 — NOT started, and now need re-planning

`flashlight-linger-fix-plan.md` Parts 2/3 (move the disocclusion debug overlay
downstream of RR; possibly retarget to `pInResponsivityMask`) were written on
the assumption that RR was running and the mask was firing. **That premise was
false at the time.** Re-evaluate only after the NEXT ACTION steps above: with
RR genuinely active, the mask may work fine, may over-fire on noisy 1-spp tile
means (plausible now, given the residual noise level), or may be inert because
`pInDisocclusionMask` is unsupported. All three are still open.

## Docs to reconcile once testing confirms behaviour

- `flashlight-linger-issue.md` — has a "superseded" banner, but its stated cause
  (debug overlay upstream of RR) is now only a *secondary* factor; the primary
  cause was the compiled-out DLL.
- `flashlight-linger-fix-plan.md` — Part 1 marked implemented; Parts 2/3 stale.
- `compat-patches.md` — **done (2026-08-07)**: added the DLL root cause + CMake
  fix (`f133bda`) entry and the pulse-light reset-churn entry (`bbe1d1b85`).
