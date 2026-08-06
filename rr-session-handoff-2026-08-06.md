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

**Current unresolved question (post-fix): RR is stable (no more lingering)
but noisier than expected — reported as "more stable but noisier than
A-SVGF", resembling the noise level from *before* the 2026-08-05 guide-fix
commit (`0683fbb`) that was supposed to have reduced it (at the cost of the
lingering bug this whole session chased). Not yet diagnosed — see "Next
action" below.

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

- `rt_rr_status`: `DLSS2 available = YES`, `RR REQUESTED = YES`. RR is real.
- `rt_rr_reset_hold` is `CVAR_ARCHIVE` (persists in the ini across launches —
  every `RT_CVAR` does, see `rt_main.cpp:84`: `CVAR_GLOBALCONFIG | CVAR_ARCHIVE`
  unless the name starts with `_`). It was left at `1` from an earlier
  diagnostic and caused the "very noisy" report even though RR was working.
  **Before any further A/B testing, explicitly check/set every `rt_rr_*`
  cvar** (`rt_rr_status`, plus `rt_rr_reset_hold`, `rt_rr_reset_now`,
  `rt_rr_disocc_show`) rather than assuming defaults — a past console session
  can leave any of them stuck.
- RR toggling now works correctly via the **Dev GUI** (confirmed by user);
  console `rt_rayreconstr` may or may not sync live the same way — not
  independently confirmed, use the Dev GUI as the trusted control.
- With RR genuinely active and (per user) a clean `reset_hold`: **lingering
  is fixed** — RR now reads as "more stable" than before. But the image is
  **noisier than A-SVGF**, at a level resembling pre-`0683fbb` (before the
  2026-08-05 guide fixes that reduced noise but caused the lingering this
  whole session set out to fix).

## NEXT ACTION — diagnose the residual RR noise level

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

1. **Isolate the trigger.** With RR active and `reset_hold` confirmed `0`:
   ```
   rt_rr_reset_on_dynlight 0
   rt_rr_reset_on_lightcut 0
   ```
   Stand still, watch the image. If noise drops to a clean/expected level,
   the dynlight (or lightcut) trigger is over-firing — re-enable one at a
   time to find which, then either rate-limit harder
   (`rt_rr_reset_min_ms`) or fix the membership-diff false-positive above.
2. **If noise persists with both triggers off**, it isn't the reset work —
   compare against the pre-`0683fbb` guide fixes directly (`rr-noise-fix-
   proposals.md`, `rr-noise-investigation.md`) to see if this is a known,
   separate regression in the diffuse/specular guide computation.
3. **Only after 1–2**, revisit the disocclusion mask (`rt_rr_disocc 0` vs
   `1`) — it has still never been tested with a working RR + clean cvars.
4. Re-verify lingering is actually fixed under a *clean* cvar state (not
   just "seemed better" while other things were still stuck): toggle
   `rt_flsh`, trigger a barrel/rocket explosion, confirm no ~3–7 s delay.
5. Rapid-fire check: confirm muzzle flash does **not** trigger resets (it's
   deliberately excluded — see Part 1 below).

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
`rt_rr_reset_hold` / `rt_rr_reset_now` (diagnostics).

**Caveat, now the leading suspect for the residual noise (see NEXT ACTION):**
a commit-message claim that flicker/pulse lights "never touch" the dynlight
diff is wrong — lights crossing the `intensity <= 0.01f` /
`m_currentRadius <= 0.01f` cutoffs can enter/leave the set. `rt_dynlight_debug`
showed a rock-steady count of 67, but that only proves the *count* didn't
change — one ID leaving and a different ID entering the same frame nets to an
unchanged count while still tripping `curDynIds != s_prevDynIds`. That check
was also run before the DLL fix, when RR wasn't consuming `resetHistory` at
all, so it never exercised this path for real.

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
- `compat-patches.md` — has the Part 1 follow-up entry; needs the DLL root cause
  and the CMake fix (`f133bda`) added.
