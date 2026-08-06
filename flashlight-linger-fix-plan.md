# Fix flashlight / transient-light lingering under DLSS-RR

## Status (2026-08-06)

**Part 1 implemented and built clean** (`tools/build-gzdoom-rt.cmd`, `rt_main.cpp`
recompiled without warnings, `gzdoom.exe` linked). Scope was broadened during
implementation, per explicit feedback: the flashlight is only one instance of
a transient light — the fix now also covers any GZDoom dynamic light newly
appearing or disappearing (barrel/rocket explosion flashes, pickup glow, etc.),
via the same list `RT_UploadGzDoomDynamicLights` already uploads every frame.
Muzzle flash is deliberately excluded from this global-reset mechanism (see
1b) — it stays a Part 2/3 problem. Not yet in-game verified (see Verification).
Part 2/3 (RTGL disocclusion-mask observability + retarget) not yet started.

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

## Part 1 — Transient-light history flush (gzdoom-rt only) — IMPLEMENTED

All changes in `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp`.
No RTGL changes, no shader regeneration, no `build-rtgl.cmd`.

Broadened during implementation beyond flashlight-only: a single shared
`g_rt_lightcut` flag is now set by three independent trigger sources and
consumed once per frame.

### 1a. Cvars

Added next to the existing RR cvars (`rt_main.cpp` cvar block):

| cvar | default | purpose |
|---|---|---|
| `rt_rr_reset_on_lightcut` | `true` | master enable for the flashlight edge trigger |
| `rt_rr_reset_delta` | `0.5` | min abrupt change in emitted flashlight scale that counts as a cut |
| `rt_rr_reset_on_dynlight` | `true` | also trigger on any dynlight appear/disappear (explosions, pickups) |
| `rt_rr_reset_min_ms` | `250` | rate limit; suppresses back-to-back flushes |
| `rt_rr_reset_hold` | `false` | **diagnostic**: set `InReset` every frame |
| `rt_rr_reset_now` | `false` | **diagnostic**: fire one flush, then self-clear |

### 1b. Three trigger sources, one shared flag

`g_rt_lightcut` (with its rate-limit clock `g_rt_lastresetat`) is declared in
the anonymous namespace near `FlashlightLightId`/`DynLightId_Base` — not
beside the similar `g_resetposteffects` further down the file — because
`RT_AddFlashlight` is an inline method of a class nested in that same
namespace and needs ordinary forward-visible lookup (a namespace-scope
static declared *after* the class closes is invisible to an inline method
defined *inside* it; `g_resetposteffects` avoids this only because its own
use sites are themselves outside that class).

**Flashlight edge** (`RT_AddFlashlight`, gated by `rt_rr_reset_on_lightcut`):
reuses `wantLight`/`battScale`, which the battery state machine already
computes every frame. Sets the flag on `rt_flsh` toggle or an abrupt
`battScale` jump `> rt_rr_reset_delta`. Deliberately *not* triggered by the
dying-phase `fadeValley()` flicker or mid-cycle blinks (they ramp smoothly
over 12–32 tics; RR tracks those fine, and flushing on every one would make
the ~4 s dying phase permanently noisy). Edge-tracking statics reset on
`maptoken` change alongside the battery state machine's own statics.

**Dynlight appear/disappear** (`RT_UploadGzDoomDynamicLights`, gated by
`rt_rr_reset_on_dynlight`): this function already walks `primaryLevel->lights`
every frame (the same GZDoom `FDynamicLight` chain that carries GLDEFS-attached
explosion flashes, not just wall lamps) and computes a `stableId` per light. A
`std::unordered_set<uint64_t>` of this frame's uploaded IDs is diffed against
the previous frame's set; any difference (a light entered or left the set)
flushes history. Steady flicker/pulse lights never trigger this — they stay
present in the list the whole time, only their intensity varies via the
existing `blink` remap. Muzzle flash is *not* wired into this mechanism: it
fires far too often (every shot) for a full-screen reset to be tolerable, and
it already has its own mitigation (`rt_mzlflsh_fade`, soft fade-out). Fixing
muzzle-flash ghosting properly is Part 2/3's job (the localized per-pixel
mask), not this global reset.

**Level load** (`RT_OnLevelLoad`): sets the flag unconditionally, alongside
the existing `g_resetposteffects`/`g_resetfluid` — a new scene should always
flush RR history regardless of the other cvars.

### 1c. Consumption (`RTFrameBuffer::RT_DrawFrame`)

Right before building `RgDrawFrameInfo`:

```cpp
bool wantResetHistory = bool{ cvar::rt_rr_reset_hold };

if( g_rt_lightcut )
{
    g_rt_lightcut = false;
    if( curtime - g_rt_lastresetat >= double( cvar::rt_rr_reset_min_ms ) / 1000.0 )
    {
        wantResetHistory = true;
        g_rt_lastresetat = curtime;
    }
}

if( bool{ cvar::rt_rr_reset_now } )
{
    cvar::rt_rr_reset_now = false;
    wantResetHistory      = true;
    g_rt_lastresetat      = curtime;
}
```

then `.resetHistory = static_cast<RgBool32>(wantResetHistory)` in the
designated initialiser. The flag is always cleared when read, and the
per-source cvars already gated *whether* it got set — so consumption doesn't
re-check `rt_rr_reset_on_lightcut`/`rt_rr_reset_on_dynlight`, only the shared
rate limit and the two diagnostic cvars.

### 1d. Launcher

`tools/launch-retribution-rt.cmd` set **none** of the `rt_rr_disocc*` cvars,
contrary to what `flashlight-linger-issue.md` stated. Added those plus the new
reset cvars so both are A/B-able from one launch. Note `+rt_rr_temporal 0` in
the launcher is **dead** — see Part 3.

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
7. **Dynlight path.** Blow up a barrel (or trigger a rocket explosion) near the
   camera and confirm the flash's glow decays promptly instead of lingering.
   `rt_dynlight_debug 1` prints the active-light count each second — watch it
   tick up then back down as the explosion light appears/disappears, and
   confirm a reset accompanies both edges. A/B against
   `rt_rr_reset_on_dynlight 0` to confirm this specific trigger is doing the
   work (not just the flashlight one still being active from step 4).
8. **Muzzle flash sanity check.** Rapid-fire a hitscan weapon and confirm the
   screen does *not* go into a constant noise storm — muzzle flash must not be
   triggering resets. If it is, something is wrong (it should never touch
   `g_rt_lightcut`).

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
