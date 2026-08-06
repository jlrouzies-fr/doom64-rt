# Fix flashlight / transient-light lingering under DLSS-RR

## Context

After the 2026-08-06 RR guide fixes, DLSS-RR's temporal history became much more
stable — and transient lighting changes now linger: flashlight ON takes ~3–4 s to
reach full brightness, OFF takes ~6–7 s to disappear. Moving the camera through
the stale light briefly reveals the correct state, which is the signature of a
stale temporal history rather than a wrong light list.

The previous attempt (`f56ad00` in `deps/RTGL`, `e59ba9ebf` in
`sourcecode/gzdoom-rt`) added a tile-based disocclusion mask bound to DLSS-RR's
`pInDisocclusionMask`. It produced **zero visible effect**, and six follow-up
experiments (documented in `flashlight-linger-issue.md`) all concluded the write
from `CmNoisyCompose` never reaches the read in `CmPrepareFinal`.

**That conclusion is wrong, and this investigation establishes three things:**

1. **The framebuffer plumbing is correct.** `FB_IMAGE_INDEX_RR_DISOCCLUSION = 72`
   (`Generated/ShaderCommonCFramebuf.h:86`), `VK_FORMAT_R16_SFLOAT`, flags `0`,
   render-resolution, one `VkImage` created once
   (`Framebuffers.cpp:698-784`, never cleared). Bindings 72 / sampler 153 are
   identical in `Bindings[]` and `BindingsSwapped[]`
   (`ShaderCommonCFramebuf.cpp:249/334/419/504`), so there is **no** ping-pong —
   both passes bind `framebuffers->GetDescSet(frameIndex)` and get the same
   image. `ShGlobalUniform` is byte-identical between C++ and GLSL (std140
   verified). The deployed `rt/shaders/*.spv` and `RTGL1.dll` are fresh and
   byte-identical to the build output; no shadow copy is being loaded. The
   suspected root cause in the issue doc ("the buffer may not actually be
   allocated") is disproven.

2. **The debug instrument was broken, not the mask.** The issue doc assumes the
   order is `CmNoisyCompose → DLSS-RR → CmPrepareFinal`. **It is inverted.**
   Actual order in one command buffer (`VulkanDevice.cpp`):
   `CmNoisyCompose` (:803) → `CmCheckerboard` (:814) → raster (:820) →
   `CmPrepareFinal` (:833) → **`nvDlssRr->Apply` (:918)**. `CmPrepareFinal`'s
   output *is* RR's `pInColor` (`DLSSRR.cpp:330,354` — `FB_IMAGE_INDEX_FINAL`).
   So the red debug tint written at `CmPrepareFinal.comp:67-74` is demodulated by
   the albedo guides and pushed through the neural denoiser before reaching the
   screen. A uniform full-screen tint survives that round-trip (hence the magenta
   test passing); a sparse per-tile marker is spatially and temporally
   inconsistent with the guides and gets attenuated. **Every negative result in
   the issue doc was read off an instrument that sits upstream of the denoiser.**

3. **`pInDisocclusionMask` may be a no-op anyway.** The DLSS-RR Integration Guide
   (SWE-DLSS-001-PGRF, Dec 2025) contains **zero** occurrences of "disocclusion".
   The parameter exists only as a bare header comment
   (`nvsdk_ngx_helpers_dlssd_vk.h:125`, `/* optional input res disocclusion mask */`)
   — no format, no value semantics, absent from §3.4's list of supported inputs
   and from §8.1's debug-overlay list. The `10000.0` sentinel is a Remix-derived
   guess, not an NVIDIA contract. The *documented* per-pixel history lever for
   DLSS-D is `pInResponsivityMask` (`nvsdk_ngx_helpers_dlssd.h:223`: one channel,
   API range **[-1,1]**, R16F or R8_SNORM, input resolution, key
   `DLSSD.ResponsivityMask`), which RTGL does not set.

Meanwhile a fully-wired global lever exists and has never been used:
`RgDrawFrameInfo.resetHistory` → `VulkanDevice.cpp:654,924` →
`DLSSRR.cpp:391` `evalParams.InReset`. gzdoom-rt leaves it default-zero
(`rt_main.cpp:4726`), so it only ever fires on engine scene resets.

**Approach: land the global reset first** (small, gzdoom-rt only, no RTGL
rebuild, fixes the reported symptom), **then rebuild the mask's debug instrument
so the localized path can actually be diagnosed** — necessary because the only
diagnostics available on the play machine are in-game observation and the Dev
debug UI (no RenderDoc, no validation layers).

---

## Part 1 — Flashlight history flush (gzdoom-rt only)

All changes in `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp`.
No RTGL changes, no shader regeneration, no `build-rtgl.cmd`.

### 1a. Cvars

Add next to the existing RR cvars (`rt_main.cpp:268-279`, `RT_CVAR` macro):

| cvar | default | purpose |
|---|---|---|
| `rt_rr_reset_on_lightcut` | `true` | master enable for the flush |
| `rt_rr_reset_delta` | `0.5` | min abrupt change in emitted flashlight scale that counts as a cut |
| `rt_rr_reset_min_ms` | `250` | rate limit; suppresses back-to-back flushes |
| `rt_rr_reset_hold` | `false` | **diagnostic**: set `InReset` every frame |
| `rt_rr_reset_now` | `false` | **diagnostic**: fire one flush, then self-clear |

### 1b. Edge detection in `RT_AddFlashlight`

`RT_AddFlashlight` (`rt_main.cpp:2033`) is called unconditionally every frame
(`rt_main.cpp:2029`) and already computes everything needed:

- `wantLight` (`:2053`) — the `rt_flsh` cvar / lightamp powerup state
- `battScale` (`:2142`, final value by `:2239`) — emitted intensity 0..1
- the light is skipped entirely when `!wantLight || battScale <= 0.01f` (`:2244`)

Add a file-scope flag beside the existing `g_resetposteffects` pattern, and set
it just before the `:2244` early-return:

```cpp
// abrupt cut only: rt_flsh toggle, or recharge->on / on->recharge.
// fadeValley() dying-flicker and mid-cycle blinks ramp over 12-32 tics,
// which RR tracks fine -- flushing on those would make the 4 s dying
// phase permanently noisy.
static bool  s_prevWant  = false;
static float s_prevScale = 0.f;
const float  emitted     = wantLight ? battScale : 0.f;

if( wantLight != s_prevWant || std::abs( emitted - s_prevScale ) > float{ cvar::rt_rr_reset_delta } )
{
    g_rt_lightcut = true;
}
s_prevWant  = wantLight;
s_prevScale = emitted;
```

Reset `s_prevWant` / `s_prevScale` in the existing `maptoken != s_maptoken`
block (`:2132-2140`) alongside the other statics.

### 1c. Consume it

At `rt_main.cpp:4726`, add to the `RgDrawFrameInfo` designated initialiser:

```cpp
.resetHistory = static_cast< RgBool32 >(
    bool( cvar::rt_rr_reset_hold ) ||
    ( bool( cvar::rt_rr_reset_on_lightcut ) && std::exchange( g_rt_lightcut, false ) ) ||
    std::exchange( g_rt_reset_now, false ) ),
```

with `rt_rr_reset_now` latched into `g_rt_reset_now` and the cvar written back to
`false` (same pattern as `rt_flsh_charge`/`rt_flsh_battstate` HUD write-back at
`:2241-2242`). Clear `g_rt_lightcut` unconditionally each frame even when the
master cvar is off, so it cannot go stale.

### 1d. Launcher

`tools/launch-retribution-rt.cmd` currently sets **none** of the `rt_rr_disocc*`
cvars, contrary to what `flashlight-linger-issue.md` states. Add the new reset
cvars plus the existing disocc ones so both are A/B-able from one launch. Note
`+rt_rr_temporal 0` in the launcher is **dead** — see Part 3.

---

## Part 2 — Make the disocclusion mask observable (RTGL)

The mask cannot be diagnosed until the debug readout is downstream of DLSS-RR.

### 2a. New post-RR debug effect

Follow the existing `EffectSimple` pattern exactly — it already binds
`DESC_SET_FRAMEBUFFERS` (0) and `DESC_SET_GLOBAL_UNIFORM` (1)
(`Shaders/EfSimple.inl:21-22`, `EffectSimple.h:112-120`), so the shader can read
`framebufRrDisocclusion_Sampler` and `globalUniform.rrDisoccShowMask` directly.

- `Source/Shaders/EfRrDisoccDebug.comp` — `#include "EfSimple.inl"`, modelled on
  `EfColorTint.comp`. Runs at **upscaled** resolution, so map to render res:
  `renderPix = ivec2(vec2(pix) * vec2(renderWidth, renderHeight) / vec2(upscaledWidth, upscaledHeight))`.
- `Source/EffectSimple_Instances.h` — add `EffectRrDisoccDebug` beside
  `EffectColorTint` (`:121-145`).
- `Source/ShaderManager.cpp` — register `{ "EffectRrDisoccDebug", "EfRrDisoccDebug.comp.spv" }`
  in the `G_SHADERS[]` table (`:49-119`).
- `Source/VulkanDevice.h` / `VulkanDevice_Init.cpp` — member + construction
  alongside the other `effect*` members.
- `Source/VulkanDevice.cpp` — apply in the post-RR chain next to the `l_applyIf`
  calls (`:1080-1093`), gated on `globalUniform.rrDisoccShowMask != 0`. Barrier
  `FB_IMAGE_INDEX_RR_DISOCCLUSION` first (`BarrierMultiple`, `Storage`) — the
  same way `DLSSRR.cpp:329-342` already does.

Modes driven by `rt_rr_disocc_show`: `1` = tint fired tiles red; `2` = replace
the image with a full-screen mask visualisation, so a firing mask is unmistakable
even at a glance.

### 2b. Delete the misleading upstream readout

Remove the debug block at `Source/Shaders/CmPrepareFinal.comp:67-74`. It sits
upstream of RR and cannot be trusted; leaving it in guarantees the next
investigation repeats this one.

### 2c. Missing barrier (real defect, now moot but worth noting)

`ImageComposition::Finalize()` (`ImageComposition.cpp:110-115`) barriers only
`SCREEN_EMISSION`, `FINAL`, `DEPTH_WORLD`, `SCATTERING` — it never barriered
`RR_DISOCCLUSION` despite `CmPrepareFinal.comp:70` reading it, an unsynchronised
RAW hazard. Removing the read per 2b resolves it. (The same gap exists for
`MOTION`, `SURFACE_POSITION`, `NORMAL`, `D_I_S_PING_GRADIENT` in `processDebug()`
— pre-existing, out of scope.)

---

## Part 3 — Decide the mask's fate (after Part 2 gives a trustworthy signal)

One in-game run with `rt_rr_disocc_show 2` answers it:

- **Mask fires, ghosting persists** → `pInDisocclusionMask` is inert in DLSS-D
  310.7, consistent with its total absence from the Integration Guide. Retarget
  to `pInResponsivityMask` in `DLSSRR.cpp` (add a second
  `NVSDK_NGX_Parameter_SetVoidPointer` with key `DLSSD.ResponsivityMask` +
  `InResponsivityMaskSubrectBase`). `FB_IMAGE_INDEX_RR_DISOCCLUSION` is already
  `R16_SFLOAT` at render resolution, which the responsivity mask accepts as-is —
  only the written value changes, from the `0 / 10000.0` sentinel
  (`CmNoisyCompose.comp:56,195`) to a graded `[-1,1]` responsivity.
- **Mask never fires** → tune `rt_rr_disocc_ratio` (3.0) / `rt_rr_disocc_mindelta`
  (0.01), and revisit the tile-reprojection gate `t.w > 0.5 * t.y`
  (`CmNoisyCompose.comp:184`), which rejects any tile that does not mostly
  reproject on-screen.

### Dead code to flag (not fixing here)

`AccumulateForRR()` (`Denoiser.cpp:258`) is defined but never called —
`VulkanDevice.cpp:798-808` unconditionally calls `ComposeNoisy()` on the RR path.
So `enableRrTemporalPrefilter` / `rt_rr_temporal` gates nothing, and the
launcher's `+rt_rr_temporal 0` is a no-op. Either remove the cvar or restore the
call site, in a separate change.

---

## Verification (in-game only — no RenderDoc, no validation layers)

**Part 1, in order:**

1. `tools/build-gzdoom-rt.cmd` only. Launch `tools/launch-retribution-rt.cmd`.
2. **Prove the mechanism first.** `rt_rr_reset_hold 1` → the image should become
   visibly noisy/sparkly (RR running with no temporal history at all). If it does
   not change, `InReset` is not reaching NGX and nothing downstream is valid.
   Set back to `0`.
3. **Prove it cures the symptom.** With `rt_flsh_battery 0`, toggle `rt_flsh` and
   confirm the ~3–4 s / ~6–7 s linger from the issue-doc table. Toggle again,
   then immediately `rt_rr_reset_now 1` — the stale light should snap away.
4. **Automatic path.** `rt_rr_reset_on_lightcut 1`, toggle `rt_flsh` on/off
   repeatedly: full brightness and full darkness should now be reached within a
   few frames. Judge the noise burst — if too strong, raise `rt_rr_reset_delta`;
   if edges are missed, lower it.
5. **Battery cycle.** `rt_flsh_battery 1`, `rt_flsh_on_secs 10` to iterate fast.
   Watch a full on → dying → recharge → on cycle. The recharge→on and on→recharge
   jumps should flush; the `fadeValley` dying flicker and mid-cycle blinks should
   **not** (no repeated noise bursts across the 4 s dying phase). Tune
   `rt_rr_reset_min_ms` if bursts cluster.
6. A/B against `rt_rr_reset_on_lightcut 0` to confirm the change is what fixed it.

**Part 2:**

7. `tools/build-rtgl.cmd` (regenerates SPV + DLL, stages into
   `build/RelWithDebInfo/rt/`). Confirm `rt/shaders/EfRrDisoccDebug.comp.spv`
   exists — `ShaderManager.cpp:233` hard-errors at startup if a registered
   shader file is missing, so a silent-stale deploy is not possible.
8. `rt_rr_disocc_show 2` and fire a barrel / muzzle flash. The mask should now be
   plainly visible *because the overlay is downstream of RR*. Sweep
   `rt_rr_disocc_ratio` 3.0 → 1.5 and `rt_rr_disocc_mindelta` 0.01 → 0.005.
9. `rt_rr_disocc_show 0`, `rt_rr_disocc 1`, `rt_rr_reset_on_lightcut 0`: does the
   mask alone reduce explosion ghosting? That answers Part 3.

**Docs:** update `flashlight-linger-issue.md` — the "suspected root cause"
(unallocated framebuffer) and the assumed pass order are both wrong, and the six
recorded negative results were measured upstream of the denoiser. Add the fix to
`compat-patches.md` next to the existing disocclusion-mask entry.
