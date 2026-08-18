# DLSS Multi Frame Generation (3x/4x) — feasibility and plan

> Scoped 2026-08-18 from the question "could NVIDIA multi frame gen be added?
> right now we have only framegen on/off". Answer: yes, and the integration
> work is smaller than it looks -- the hard parts (Reflex markers, interposer
> swapchain, DX12 interop) are already correct. The blocker is a *vendored
> Streamline version*, plus one quality prerequisite (HUD interpolation) that
> matters far more at 4x than at 2x.
>
> NOT started. This is a scoping doc, filed alongside
> [plan-nrd-denoiser.md](plan-nrd-denoiser.md) and
> [plan-rayreconstruction-secondpass.md](plan-rayreconstruction-secondpass.md)
> as a lane that can be picked up or dropped on its own.

## Ground truth (verified in code and on disk, 2026-08-18)

### The cap is Streamline, not the NGX snippet

`deps/RTGL/Source/Streamline/include/sl_dlss_g.h:73` states the constraint in
the SDK's own words:

```c
//! Must be 1
uint32_t numFramesToGenerate = 1;
```

`sl_version.h:24-26` says why: **Streamline 2.4.10**, the DLSS 3 branch.
Multi Frame Generation shipped on the DLSS 4 branch (Streamline 2.7.x+, NGX
snippet 310.x), where that field accepts 2-4 and `DLSSGState`
(`sl_dlss_g.h:127-135`) gains a max-supported query.

**But the NGX side is already DLSS 4 in this tree.** What is actually on disk:

| DLL | `deps/DLSS/lib/.../rel` | live build `rt/bin` | ships in `gzdoom-rt-1.0.2` |
|---|---|---|---|
| `nvngx_dlss.dll` (SR)  | **310.7** | **310.7** | 3.7.10 |
| `nvngx_dlssd.dll` (RR) | **310.7** | **310.7** | (absent) |
| `nvngx_dlssg.dll` (FG) | **310.7** | 3.7.10 | 3.7.10 |
| `sl.*.dll` (6 files)   | -- | 2.4.10 | 2.4.10 |

Two things fall out of that table:

1. The DLSS 4 FG snippet is **already vendored** at
   `deps/DLSS/lib/Windows_x86_64/rel/nvngx_dlssg.dll` (310.7), pulled in with
   the SR/RR SDK. `tools/build-rtgl.cmd:164-166` stages `nvngx_dlss.dll` and
   `nvngx_dlssd.dll` but **not** `nvngx_dlssg.dll`, so the live build runs a
   DLSS 4 upscaler against a DLSS 3 frame generator.
2. Even after staging it, `sl.dlss_g.dll` 2.4.10 is the plugin that loads and
   drives the snippet, and it has no MFG surface to expose. The Streamline
   drop is unavoidable.

### What is already right, and is the expensive part of any DLSS-G integration

- **Complete Reflex marker set** -- `eSimulationStart/End`,
  `eRenderSubmitStart/End`, `ePresentStart/End`
  (`DLSS3_DX12.cpp:936-961`), plus `slReflexSleep` and `slGetNewFrameToken`.
  MFG's frame pacing lives or dies on these, and they are all present and in
  the right places. Reflex is set to `eLowLatency` at `DLSS3_DX12.cpp:750-756`.
- **Interposer-proxied DXGI swapchain** -- created through
  `dlfg_dxgiFactory_proxy` (`DX12_Swapchain.cpp:974`) with the native
  interface extracted afterwards, and `GetCurrentBackBufferIndex` routed
  through the proxy (`:1209`), which DLSS-G requires on D3D.
- **Signature verification** of `sl.interposer.dll` before load
  (`DLSS3_DX12.cpp:58-63`) -- newer SL DLLs are signed the same way.
- **Vulkan -> DX12 interop is per *rendered* frame.** Generated frames are
  manufactured inside the interposer at present time, so 3x/4x adds no interop
  copies. The multiplier is free on that axis.
- **`rt_framegen` is already an int cvar** (`rt_cvars.inc:1000`, default 0,
  documented `0=off 1=on -1=skip presentation`). Widening its value space
  costs no type change.

### What is wrong today and gets worse with every extra generated frame

**The HUD is interpolated along with the scene.** `VulkanDevice.cpp:1656`
records the surrender in a comment:

```cpp
needHudOnly = false; // providing FB_IMAGE_INDEX_HUD_ONLY to DLSS3 doesn't work
```

Both the HUD-less and the UI tags are commented out in the resource tag array
(`DLSS3_DX12.cpp:691` and `:703`), and `kBufferTypeHUDLessColor` is instead
pointed at `colorOut` -- i.e. DLSS-G is told the fully-composited image is
HUD-less. The FSR3 path does the opposite and does use the HUD-only buffer
(`FSR3_DX12.cpp:485`, `VulkanDevice.cpp:1704`), and the buffer itself exists
and is allocated at upscaled resolution (`DX12_Vulkan.cpp:685`).

At 2x this warps the status bar on one frame in two. At 4x it is three frames
in four. **Doom64 has a large, static, high-contrast status bar** -- this is
the single change most likely to decide whether 4x reads as "smoother" or as
"the HUD is vibrating".

## Phases

### Phase 0 -- the 30-minute probe (do this before anything else)

Add `nvngx_dlssg.dll` to the staging block in `tools/build-rtgl.cmd:164-166`
next to its two siblings, rebuild, and launch with FG on. Either SL 2.4.10
loads the 310.7 snippet (DLSS 4 FG quality at 2x, free) or it refuses and
falls back. Both outcomes are useful and neither costs a day.

Note `tools/d64rt-pins.cfg:85` pins `rt_framegen 0`, so the pin must be
changed for any FG testing at all -- a compiled-in default will not surface.
The A/B arm cfgs under `tools/arms/` all set `rt_framegen 0` explicitly, so
they are unaffected by anything here.

### Phase 1 -- Streamline 2.7.x+ drop

Replace `deps/RTGL/Source/Streamline/include/` (headers) and the six
`sl.*.dll` binaries. `deps/` is gitignored by policy, so the authored half is
an installer step under `tools/` -- extend `tools/build-rtgl.cmd`, or add a
`tools/install-streamline.cmd` next to `tools/build-nrd-deps.cmd`, following
the same pattern.

Expect `DLSSGOptions` to have moved to a later `kStructVersion`; the options
block at `DLSS3_DX12.cpp:732-743` and the feature entry-point fetch at
`:320-352` are the two places that touch it. **Ship this phase at 2x first**
and confirm no regression before adding any multiplier.

### Phase 2 -- HUD-less / UI tagging (the quality prerequisite)

Re-attempt the abandoned tagging: uncomment `DLSS3_DX12.cpp:691` and `:703`,
set `needHudOnly = true` on the DLSS path (`VulkanDevice.cpp:1656`), and point
`kBufferTypeHUDLessColor` at the pre-HUD image rather than at `colorOut`. The
HUD-only buffer is already produced and already copied to DX12
(`VulkanDevice.cpp:1887-1895`); the FSR3 path is the working reference.

Whatever broke this on SL 2.4 may simply be fixed on 2.7 -- but it must be
verified in motion, not from a still: a settled screenshot cannot measure
anything that only misbehaves while the camera moves.

**If this phase cannot be made to work, stop.** 2x with an interpolated HUD is
a defensible trade; 4x with one is not.

### Phase 3 -- the multiplier

- `DLSS3_DX12.cpp:732-743`: set `numFramesToGenerate` from the requested mode,
  after querying the runtime for the supported maximum via `slDLSSGGetState`.
  MFG above 2x is **Blackwell / RTX 50 only**; Ada must clamp to 2 and the
  clamp has to be a runtime query, never a guess.
- **Public API**: `RgFrameGenerationMode` (`RTGL1.h:842-847`) is a 3-state
  enum consumed by value in `rgUtilIsUpscaleTechniqueAvailable`
  (`RTGL1.h:2002`). Prefer a multiplier field in a `pNext`-chained struct
  beside `RgStartFrameRenderResolutionParams::frameGeneration` (`:873`) over
  adding `ON_X3`/`ON_X4` enumerants -- it keeps the availability query's
  signature and ABI intact.
- **Back buffers**: `DefaultSwapchainImageCount = 3` (`Swapchain.cpp:336`)
  feeds the DXGI `BufferCount` (`:904` -> `DX12_Swapchain.cpp:959`). Three is
  thin for 4x present pacing; expect to raise it when the multiplier exceeds
  2, or present stalls will eat the gain. (`MAX_FRAMES_IN_FLIGHT_DX12 = 2` at
  `DX12_Interop.h:62` is unrelated -- it sizes command allocators, not the
  swapchain.)
- `RG_FRAME_GENERATION_MODE_WITHOUT_GENERATED` and the per-frame
  `m_skipGeneratedFrame` toggle (`VulkanDevice.cpp:96-97`) keep working
  unchanged -- it flips `DLSSGMode::eOff`, which is orthogonal to the count.

### Phase 4 -- engine and UI

- `rt_main.cpp:1092-1096`: the `-1 / 0 / 1` switch becomes `-1 / 0 / 2 / 3 / 4`.
  Update the cvar description at `rt_cvars.inc:1000` in the same edit.
- `cvar::rt_available_dlss3fg` (`rt_cvars.cpp:71`) becomes a max-multiplier int
  rather than a bool, fed from `rt_main.cpp:952-964`. Every consumer in
  `rt_cutscene.cpp` (`:619, :942-943, :1306-1312, :1378-1396`) reads it as a
  bool today and needs revisiting.
- The RR mutual exclusion at `rt_main.cpp:1113-1119` (RR forces
  `rt_framegen = 0`) stays as-is and needs no change -- but see the cross-lane
  risk below.
- **The in-game menu entry is compiled out**: `#define FG_BUTTON 0`
  (`rt_cutscene.cpp:544`) gates all six FG menu sites. Today the only control
  is the cvar. Decide deliberately whether MFG ships as a cvar-only option or
  whether `FG_BUTTON` gets turned back on -- if it does, `l_getframegen`
  (`:1387-1400`) needs "2x / 3x / 4x / UNAVAILABLE" instead of "ON / OFF".
- The FPS readout already reframes itself under FG as
  `"%.1f ms Input Latency [NOT ACTUAL FRAME TIME / FPS]"`
  (`rt_cutscene.cpp:1538-1540`). That caveat gets sharper at 4x and the
  wording should probably name the multiplier.
- RTGL's own ImGui dev panel (`VulkanDevice_Dev.cpp:468-483`) has FG radio
  buttons wired to the enum and will need the same treatment.

## Effort

**~2-4 sessions**, assuming Phase 0 does not surprise us:

| Phase | Cost | Risk |
|---|---|---|
| 0 -- stage the 310.7 snippet | minutes | none |
| 1 -- Streamline 2.7 drop, still 2x | ~1 session | SDK API churn; touches SR |
| 2 -- HUD/UI tagging | ~0.5-1 session | **may not be solvable**; gate |
| 3 -- multiplier + back buffers | ~0.5 session | pacing/stall tuning |
| 4 -- cvar, availability, menu | ~0.5-1 session | wide but shallow |

Blast radius is narrow -- nothing here touches the path tracer, the denoiser
lanes or any material/lighting data. That is the main argument in its favour.

## Cross-lane risk

A Streamline 2.7 drop also updates the **DLSS SR** plugin (`sl.dlss.dll`),
which changes upscaling quality and cost on its own. Two consequences:

- Any renderer A/B baseline captured under SL 2.4 is not comparable to one
  captured after. The NRD lane's numbers would need re-basing if it is
  mid-flight.
- It re-opens the ray-reconstruction question, which is **closed on purpose**
  (see [RAYRECONSTRUCTION.md](../RAYRECONSTRUCTION.md) and
  [plan-rayreconstruction-secondpass.md](plan-rayreconstruction-secondpass.md)).
  That verdict was reached deliberately; a newer SL is not by itself a reason
  to reopen it, and the RR/FG mutual exclusion at `rt_main.cpp:1113-1119`
  means the two features can never be on together anyway.

**FSR gets nothing from this.** The vendored FFX frame interpolation is 2x
only, so any multiplier is NVIDIA-exclusive and the availability query and
menu have to say so plainly rather than showing a greyed-out 4x on AMD.

## Honest caveat

MFG's value scales with **base** framerate and display refresh, and DLSS-G
quality degrades below roughly 50-60 fps base -- multiplying to 4x amplifies
that rather than hiding it. On a path-traced Doom64 at the base rates this
renderer actually produces, 3x/4x may buy smoothness that costs more in
artifacts and input latency than 2x does. The honest expected outcome is
"4x is available and correct, 2x remains the recommended setting", and the
work should be judged on whether that is worth 2-4 sessions.

The strongest argument for doing it anyway is Phase 0 + Phase 2: staging the
310.7 snippet and fixing HUD interpolation improve the **existing 2x path**,
independently of whether any multiplier above 2 ever ships.

## Decision gate

Run Phase 0. If SL 2.4.10 accepts the 310.7 snippet and 2x FG looks better for
free, that alone may be the whole worthwhile deliverable. Commit to Phases 1-4
only after Phase 2 is demonstrated to work.

## Verification (when it happens)

- **Not from stills.** Judge HUD stability and interpolation artifacts in
  motion, in play.
- Pre-set launcher arms per multiplier (`tools/arms/fg-2x.cfg`, `fg-3x.cfg`,
  `fg-4x.cfg`), each setting every relevant value explicitly, driven through
  `tools/ab.cmd` -- not console commands handed over at runtime.
- Confirm the change is actually live before trusting any null result: check
  the staged DLL versions in
  `sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/bin` and the reported
  multiplier in `rt-console.log`. This lane has an unusually high chance of a
  silent fallback to 2x looking exactly like a working 4x.
- Watch `DLSSGState::status` for `eFailReflexNotDetectedAtRuntime` and
  `eFailResolutionTooLow` -- both are silent quality killers otherwise.
