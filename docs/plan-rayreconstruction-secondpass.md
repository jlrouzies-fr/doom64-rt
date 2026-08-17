# Feed DLSS-RR pre-exposure radiance — the RR second pass

> Read `RAYRECONSTRUCTION.md` first. This plan **reopens** what that file closed, and
> says why. History is in `docs/rayreconstruction/`.

> **STATUS 2026-08-17: IMPLEMENTED, awaiting the in-game A/B.** Every claim below was
> re-verified against the code by an 8-agent evidence pass before implementation; all
> confirmed (some line numbers had drifted — current ones are in `compat-patches.md`,
> which is the authoritative record of what landed). **One design change against this
> plan:** step 3 (the 1×1 exposure texture) was **dropped** — NVIDIA's RR guide §3.7
> (local copy, `deps/DLSS/doc/`) declares exposure inputs unsupported for RR, so with
> genuinely pre-exposure color, `InPreExposure=1.0` + no exposure texture is the SDK's
> own correct parameterization. Duke-RT's exposure-texture binding is generic NRI
> plumbing, not an RR requirement. The A/B: `.\tools\ab.cmd rr-preexp-probe 2` first
> (magenta = pass live), then `rr-preexp-on` vs `rr-preexp-off`.

## Context

`RAYRECONSTRUCTION.md` declares the RR investigation **closed** ("no remaining
hypothesis") and the launcher pins `rt_rayreconstr 0`, shipping A-SVGF. The stated reason
is structural: *"RR accumulates after exposure is baked in and leans on temporal
reconstruction, which motion weakens."*

`sourcecode/Duke-RT` was read to compare integrations. It **contradicts the closed
verdict**: Duke-RT ships RR as its *recommended* path, on the same DLSS-RR SDK, and the
one place its integration structurally differs from ours is precisely the mechanism our
own doc names as the cause — and which `docs/rayreconstruction/rr-noise-fix-proposals.md`
§3.4 left **⏸ Deferred**.

The hypothesis was identified correctly and then never tested. This plan tests it.

## What Duke-RT is (why it is not a like-for-like comparison)

| | Doom64-RT | Duke-RT |
|---|---|---|
| Engine | gzdoom-rt | Raze fork |
| RT backend | RTGL1 (Vulkan) | new backend on **NVIDIA NRI** (D3D12 primary, Vulkan too) |
| NGX wiring | hand-written `deps/RTGL/Source/DLSSRR.cpp` | `nri::UpscalerType::DLRR` — vendor wrapper, no NGX code of its own |
| Base denoiser | A-SVGF | **NRD** (ReLAX default, ReBLUR, SIGMA shadows) |
| Direct/indirect sampling | **ReSTIR DI + GI** | plain path tracing, no ReSTIR (`shaders/TraceOpaque.cs.hlsl`) |
| RR status | pinned **off**, "alpha, does not render well" | **recommended** — 3 of 7 shipped presets are DLRR and the menu warns *"Ray reconstruction is recommended due to visual bugs with other upscalers/denoisers"* (`renderer/nri_cvars.cpp:141-154`) |

Because Duke-RT was built to feed **NRD** from day one, its G-buffer already carried
everything RR wants — demodulated diffuse/specular, `viewZ`, packed normal+roughness, a
real specular hit distance. Its RR guide pass is a thin 179-line shader
(`shaders/DlssBefore.cs.hlsl`), not a retrofit.

**Vulkan is not the difficulty.** Duke-RT's RR path is API-agnostic through NRI, and our
Vulkan wiring is demonstrably sound — the same buffers, jitter and MV scale drive DLSS-SR
stably. The real cost is *hand-rolling* NGX: every one of the five day-costing faults in
`RAYRECONSTRUCTION.md` was a wiring/config fault of the kind a vendor wrapper removes.
That is an integration-surface problem, not a Vulkan problem.

## Where we already match, and where we do not

**Guides are at parity — no work needed.** `CmNoisyCompose.comp` default `rrGuideMode 1`
writes `ro_d * throughput * ambient` and `envBRDFApprox2(ro_s, r², NoV) * throughput *
ambient`, the same `EnvBRDFApprox2` fit Duke-RT uses; normals+roughness are packed to
match `Roughness_Mode_Packed`; `FB_SPECULAR_HIT_DISTANCE` exists and `rt_rr_spechitdist`
defaults **true**; optional guides correctly unbind to `nullptr` rather than zeroing.
Two harmless divergences, both legal: they feed linear `viewZ` with `Depth_Type_Linear`
where we feed NDC with `Depth_Type_HW`, and they leave the render preset at default where
we pin Preset E.

**The gap is the colour buffer.**

- Duke-RT: `Composition` writes a dedicated noisy `RrInput` *before* NRD and bypasses
  opaque denoising (`renderer/nri_frame_graph.cpp:413-422`). Exposure is applied only in
  `FinalPresent` — after RR — and is additionally handed to RR as a separate exposure
  texture (`nri_pass_dispatch.cpp:1274-1283, 1318`).
- Ours: `VulkanDevice.cpp:1437` is literally commented `// upscale finalized image`. By
  the time RR runs, `CmPrepareFinal.comp:295-298` has multiplied in EV100 and added
  screen emission, and `Rasterizer::DrawToFinalImage` (`VulkanDevice.cpp:1346`) has
  composited sprites and the viewmodel into the same buffer. Yet `DLSSRR.cpp:407-409`
  declares `InPreExposure = 1.0f` with no exposure texture and no `AutoExposure` flag.

So RR is told the colour is unexposed when it is not. Whenever auto-exposure adapts, RR's
history sits in a different exposure space than the current frame with no way to know —
and Doom 64 interiors swing auto-exposure hard. The existing `rt_rr_reset_*` history
flushes are papering over exactly this class of problem.

**One asymmetry that is ours alone:** under RR, `Denoiser::ComposeNoisy` is a single
dispatch and *all* of `Denoise()` is skipped; `AccumulateForRR` is dead at the call site
(`VulkanDevice.cpp:1326-1328`) and `rt_rr_firefly` defaults 0.0. RR eats raw 1-spp ReSTIR
output while A-SVGF gets gradients, temporal accumulation, anti-firefly, variance and 4×
atrous. Duke-RT bypasses NRD for RR too — but its input is not 1-spp ReSTIR. If the
reorder is not enough, ReSTIR decorrelation (`rr-noise-fix-proposals.md` §4) is the next
lever, not a new guess.

## The change

Target order, replacing today's `CmPrepareFinal (×EV100, +screenEmis) → raster → RR`:

```
ComposeNoisy (+ volumetrics)  →  RR(linear pre-exposure radiance, + 1×1 exposure texture)
  →  on the UPSCALED output: × EV100  →  + screenEmis (bilinear)  →  raster  →  post-FX
```

Everything is gated on a new `RT_CVAR_NOARCH` (`rt_rr_preexposure`) so it A/Bs without a
rebuild and cannot persist into the ini. **A-SVGF and the DLSS-SR/FSR2 paths must be
untouched** — they keep today's ordering exactly.

### 1. Split exposure and screen emission out of `CmPrepareFinal`

`deps/RTGL/Source/Shaders/CmPrepareFinal.comp` — guard the `// auto exposure` block
(`:295-298`) and the `// screen emissive` block (`:300-316`) behind a new uniform so both
are skipped when RR-preexposure is active. Leave `framebufReactivity`, `processDebug` and
the `rrDisoccShowMask` view where they are; they are render-res and unaffected.

### 2. New post-RR pass at output resolution

New `CmApplyExposure.comp` (register in the RTGL shader list) running at
`UpscaledWidth/Height` immediately after `nvDlssRr->Apply` returns, doing what step 1
removed: `hdr *= ev100ToLuminousExposure(getCurrentEV100())`, then
`hdr += screenEmis * emissionMaxScreenColor` sampling `framebufScreenEmission` with a
**bilinear sampler** (it is render-res and smooth glow, so upsampling is fine). Keep the
`volumeOccludeEmis` attenuation — `volumeTransmittance` must be sampled the same way.

It must run *before* the existing post-FX chain (sharpening/bloom/tint at
`VulkanDevice.cpp:1616+`), which today operates on post-exposure values and must continue
to.

### 3. Bind a 1×1 exposure texture to RR

`InPreExposure` cannot carry this: the exposure value lives on the GPU
(`tonemapping.avgLuminance`, via `getCurrentEV100()` in `Source/Shaders/Exposure.h:38`),
and reading it back to the CPU would add a frame of latency. NGX's `pInExposureTexture`
is documented as *"a 1x1 texture containing the final exposure scale"*
(`deps/DLSS/include/nvsdk_ngx_defs.h:766`) and is present on the Vulkan DLSS-D eval
params (`nvsdk_ngx_helpers_dlssd_vk.h:42`), so it is the right mechanism.

Add a 1×1 R32F framebuffer image, write `ev100ToLuminousExposure(getCurrentEV100())` into
it from the same pass that already reads tonemapping, and bind it in `DLSSRR.cpp`
alongside the other resources. This is what Duke-RT does, and in NRI supplying it clears
`NVSDK_NGX_DLSS_Feature_Flags_AutoExposure` — the supported route, not a workaround.

### 4. The rasterized layer — do this last and separately

`Rasterizer::DrawToFinalImage` (`VulkanDevice.cpp:1346`) puts sprites, translucency and
the viewmodel into the RR input with albedo/normal/depth guides that describe the world
*behind* them. Two options, and the first is recommended:

- **`pInTransparencyLayer`** (RGBA16F premultiplied) — NVIDIA's sanctioned route,
  "not denoised, upscaled only". Much less invasive.
- Moving the raster after RR to output res. Crisper viewmodel, but a real restructure;
  `DrawToSwapchain` (`:1666`) already shows the output-res raster path exists if wanted.

Land steps 1–3 and measure before touching this. It is a separate variable.

### 5. Three unrelated defects found while reading — fix regardless

- **Build break in the no-DLSS stub.** `DLSSRR.h:59-69` declares `Apply` with 11
  parameters; the stub at `DLSSRR.cpp:501-509` defines 9 — `specHitDistEnabled` and
  `disoccMaskEnabled` were added to the real path and header but not the stub. Any build
  without `RG_USE_NATIVE_DLSS2` fails to compile.
- **Output image missing from the pre-evaluate barrier.** `FB_IMAGE_INDEX_UPSCALED_PONG`
  is absent from `DLSSRR.cpp:340-349` although NGX writes it. Latent WAR/WAW hazard.
- **The RR preset is unreachable.** `Preset_E` is hardcoded at `DLSSRR.cpp:221` while
  `rt_dlss_preset` reaches the SR feature only. Add `rt_rr_preset`; the feature-recreate
  path at `:320-338` already handles it cleanly, and NVIDIA now recommends trying Default
  vs D vs E per OTA.

## Files

- `deps/RTGL/Source/Shaders/CmPrepareFinal.comp` — gate exposure + screen emissive
- `deps/RTGL/Source/Shaders/CmApplyExposure.comp` — **new**, post-RR at output res
- `deps/RTGL/Source/Shaders/Exposure.h` — reuse `ev100ToLuminousExposure` / `getCurrentEV100`
- `deps/RTGL/Source/DLSSRR.cpp` — exposure texture binding, barrier fix, preset cvar, stub arity
- `deps/RTGL/Source/VulkanDevice.cpp` — insert the pass after `:1444`, before `:1616`
- `deps/RTGL/Source/Generated/GenerateShaderCommon.py` — new uniform + 1×1 image
- `deps/RTGL/Include/RTGL1/RTGL1.h`, `Source/DrawFrameInfo.h` — API flag
- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_cvars.inc` — `rt_rr_preexposure`,
  `rt_rr_preset` (both `RT_CVAR_NOARCH`)
- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp` — pass them through
- `tools/arms/rr-preexp-*.cfg` + `tools/d64rt-pins.cfg`

Build: `tools/build-rtgl.cmd`, then
`cmake --build sourcecode/gzdoom-rt/build --config RelWithDebInfo --target zdoom`.
Kill any running gzdoom first.

## Verification

Non-negotiable, in this order:

1. **Prove it is live before trusting anything.** Grep the staged `rt/shaders/*.spv` for
   the new uniform, and confirm `rt-console.log` prints `Denoiser path: DLSS-RR`. Five
   silent-plumbing failures have been paid for here already.
2. **Build the absurd arm first.** An arm that forces the exposure factor to an extreme
   after the reorder — if the image does not visibly break, the value is not reaching the
   shader, and no subtle arm can tell you that. Same philosophy as `shaft-probe` and
   `rt_smoke_debug 4`.
3. **Regression gate:** with `rt_rr_preexposure 0` the image and frame time must be
   unchanged from today, and `rt_rayreconstr 0` (the shipping A-SVGF path) must be
   byte-identical either way.
4. **Brightness must not shift** between arms once exposure lands post-RR. A shift means
   the factor is applied twice or not at all — check this before judging noise.
5. **A/B with both arms setting every value explicitly**, launched pre-set from
   `tools/arms/` via `.\tools\ab.cmd`, never typed into the console.
6. **Ask the user for the visual verdict, in motion.** Screenshot analysis has given two
   confident wrong answers here and scalar noise metrics scored RR and A-SVGF equal;
   stills cannot measure temporal noise at all. The specific prediction to test: if
   exposure was the cause, instability should have been correlated with auto-exposure
   *adapting* (walking between a lit and a dark room), not with camera motion as such.
7. Record the result in `docs/rayreconstruction/rr-noise-investigation.md` and update the
   §8 status table in `rr-noise-fix-proposals.md`.

### Doc fix to land regardless of the outcome

`RAYRECONSTRUCTION.md` says "The investigation is closed. There is no remaining
hypothesis." while `rr-noise-fix-proposals.md` §8 lists items 5, 7 and 8 as
deferred/pending — including the exact mechanism the closing paragraph blames. Whichever
way this A/B goes, reconcile the two so the next session is not told a testable question
is unanswerable. If the reorder does not help, that is a real result and the closing
paragraph gets *stronger* — but only once it has been measured.
