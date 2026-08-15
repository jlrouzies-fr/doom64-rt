# Multi-sample-per-pixel path tracing (RTGL1 / Doom64-RT)

## Context

Doom64-RT's path tracer is **1 sample per pixel**. The image only looks clean
because convergence comes from *temporal accumulation* — ReSTIR's reservoir `M`
growing across frames, plus the denoiser's own history. Camera motion
legitimately destroys both (reprojection fails on disocclusions and sprites),
and what remains underneath is the raw 1-spp signal. That is the "fizzle in
motion" chased all session.

This was established by measurement. With DLSS-RR finally running and
verifiable, every *downstream* lever was tried and measured:

| Lever | Result |
|---|---|
| RR preset D vs E | D clearly worse (noisy even static) |
| Firefly clamp before RR | marginal; added weapon-sprite trailing |
| Disocclusion mask on/off | no change (fires sparsely, as designed) |
| Blue-noise ReSTIR reuse taps | no change |
| Multi-point shadow sampling on one light | no change (near-point lights, no penumbra) |
| Temporal tap jitter 2 → 0 | marginal |
| DLAA (native res) | no change — more pixels, still 1 spp each |
| Volumetrics / parallax / normal maps | no change |

They all **redistribute** a fixed quantity of noise; none **adds information**.
More samples per pixel is the only remaining lever that does.

Because sampling happens in the raygen shaders — upstream of the denoiser
choice — this benefits **A-SVGF and DLSS-RR equally**. `rt_rayreconstr` keeps
working unchanged as the performance fallback.

**Goal:** trade GPU time for motion stability, defaulting to today's behaviour
so nothing changes until deliberately raised.

## Decisions

- Scope: **direct + indirect** lighting. Primary rays and reflection/refraction
  stay 1/pixel (G-buffer is 1 sample/pixel; DLAA already handles edge aliasing).
- Range **1..8**, **default 1** — stock behaviour, zero regression risk.
- **Fixed N**, not adaptive: predictable frame time, and an adaptive bug looks
  exactly like the noise we're chasing.
- Denoiser choice untouched; also expose the hardcoded ReSTIR quality constants.

## What exploration established

- **Checkerboard does NOT halve rays.** `getCheckerboardPix`
  (`Source/Shaders/ShaderCommonGLSLFunc.h:315`) is a bijection over `W×H` with an
  exact inverse; every screen-space RT pass dispatches at full `W×H`
  (`Source/PathTracer.cpp:164,206,228,266`). It exists so split water/glass
  surfaces can send reflection down one parity and refraction down the other.
  There is no free 2× here, and no framebuffer is half-width.
- **Direct today:** initial-reservoir pass traces 1 visibility ray; direct pass
  traces 1 shadow ray.
- **Indirect today:** `processIndirect` is called **exactly once** per pixel
  (`RtRaygenIndirect.inl:288`) = 2 bounce rays + 2 shadow rays. No sample loop.
- **`calcInitialReservoir` traces zero rays when called outside the INITIAL
  pass** — its `traceVisibility` is `LIGHT_SAMPLE_METHOD_INITIAL`-gated
  (`RaygenCommon.h:467-478`). So the direct pass can draw fresh RIS candidates
  per sample for free. This is the key enabler.
- **`shadowSamples` is a working end-to-end template** for this exact shape:
  uniform → `std::clamp` in `VulkanDevice.cpp:606` → in-shader loop with a salt
  offset (`RaygenCommon.h:700-726`) → cvar `rt_shadow_samples`.
- **Constraints:** `framebufReservoirs` (STORE_PREV) must stay ONE canonical
  reservoir per pixel or the temporal chain breaks. `framebufUnfiltered*` are
  E5B9G9R9 packed in R32_UINT — must be averaged **in-shader** before storing.
  `framebufIndirectReservoirsInitial` is read by *neighbours* during spatial
  reuse, so it must remain one combined sample per pixel.
- Uniform buffer is sized by `sizeof(ShGlobalUniform)` (`GlobalUniform.cpp:39`)
  so the struct can grow. **All `_pad` slots are used** — add fresh vec4 groups.

## Implementation

### 1. Uniform + API plumbing (follow the `shadowSamples` template exactly)

Add two vec4 groups in `Source/Generated/GenerateShaderCommon.py` (keep std140
16-byte grouping):

`directSamples`, `indirectSamples`, `restirInitialSamples`, `restirSpatialSamples`,
`restirSpatialRadius`, `restirTemporalMCap`, + 2 pads.

Mirror in `Include/RTGL1/RTGL1.h` (`RgDrawFrameIlluminationParams`, append at
end), defaults in `Source/DrawFrameInfo.h`, clamp+assign in
`Source/VulkanDevice.cpp` beside `gu->shadowSamples`.

gzdoom cvars in `rt_main.cpp` beside `rt_shadow_samples` (~:301) and passed in
the `RgDrawFrameIlluminationParams` initialiser (~:4881):
`rt_spp_direct`, `rt_spp_indirect` (1..8, default 1), `rt_restir_initial`
(default 8), `rt_restir_spatial` (default 8), `rt_restir_spatial_radius`
(default 30), `rt_restir_mcap` (default 20).

### 2. Replace the hardcoded ReSTIR constants

`RaygenCommon.h:401` `INITIAL_SAMPLES`, `:510-512` `TEMPORAL_SAMPLES` /
`SPATIAL_SAMPLES` / `SPATIAL_RADIUS`, and the `initReservoir.M * 20` cap at
`:551` become the uniforms above, clamped in shader. Loop bounds must stay
`uint` compares so the compiler can still unroll modestly.

### 3. Direct: N samples (`RaygenCommon.h` + `RtRaygenDirect.rgen`)

Add a `uint sampleIndex` parameter threaded through `calcInitialReservoir` and
`selectLight_Direct`, used **only** to offset the random salt base (a new
`RANDOM_SALT_DIRECT_SPP_BASE 200` with a per-sample stride of 32 in `Random.h`,
clear of `RANDOM_SALT_SHADOW_SAMPLES_BASE 160`). Offsetting the salt is correct
for both RNGs — for `rndBlueNoise8` it rotates the texture slice.

In `processDirectIllumination` (`RaygenCommon.h:744`), loop `N = directSamples`:

- sample 0: exactly today's path — load the stored initial reservoir, so **N=1
  is bit-identical to stock**.
- samples 1..N-1: call `calcInitialReservoir` in-shader for **fresh RIS
  candidates** (zero rays) instead of the stored one, then run the temporal +
  spatial reuse and shading with the offset salt.
- Accumulate `out_diffuse` / `out_specular`, divide by N at the end.
- Keep sample 0's reservoir for `imageStoreReservoir`, and sample 0's
  `distToLight` / `gradientInputs` — the temporal chain and the ASVGF gradient
  input must stay single-valued.

Cost per extra sample: 8 RIS evals + 9 reuse image reads + 1 shadow ray.

### 4. Indirect: N samples (`RtRaygenIndirect.inl`)

In the `RT_RAYGEN_INDIRECT_INIT` `main()` (`:272-291`), loop
`N = indirectSamples` calls to `processIndirect` with per-sample salt offsets
and **RIS-combine** them into one selected sample, then a single
`restirIndirect_StoreInitialSample`. This is textbook ReSTIR "M initial
candidates" and it preserves the storage format (one sample + one weight),
which matters because neighbours read this image during spatial reuse.

Cost per extra sample: 2 bounce rays + 2 shadow rays.

> **Risk to verify during implementation:** the exact weight semantics expected
> by `loadInitialSampleAsReservoir` (`RtRaygenIndirect.inl:299`) and the final
> pass's estimator. Getting this wrong biases GI brightness rather than just
> changing noise. **Acceptance test: at N=1 the image must be pixel-identical to
> stock, and mean scene brightness must not shift as N rises** — only noise
> should change. Do direct (step 3) first and confirm it, then indirect.

## Files

- `deps/RTGL/Source/Generated/GenerateShaderCommon.py` — uniforms
- `deps/RTGL/Source/Shaders/RaygenCommon.h` — direct loop, constants → uniforms
- `deps/RTGL/Source/Shaders/RtRaygenDirect.rgen` — single-valued outputs
- `deps/RTGL/Source/Shaders/RtRaygenIndirect.inl` — indirect loop + RIS combine
- `deps/RTGL/Source/Shaders/Random.h` — new salt bases
- `deps/RTGL/Include/RTGL1/RTGL1.h`, `Source/DrawFrameInfo.h`,
  `Source/VulkanDevice.cpp` — API + clamp
- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp` — cvars

Build: `tools/build-rtgl.cmd` then
`cmake --build sourcecode/gzdoom-rt/build --config RelWithDebInfo --target zdoom`.

## Verification

Judge the **unfiltered** signal, not the final image — that is the only view
showing sample quality rather than denoiser behaviour.

1. **Prove it is live before trusting any result** — grep the staged
   `rt/shaders/*.spv` for the new uniform names (Windows path `G:/...`; Python
   here is Windows Python). This project has produced four silent-plumbing
   failures; assume nothing.
2. **N=1 is a no-op:** launch stock, confirm the image and frame time are
   unchanged from today. This is the regression gate.
3. **Noise falls with N:** `rt_rayreconstr 0` + `rt_upscale_dlss 0`, Dev GUI →
   *Unfiltered diffuse direct*. Compare `rt_spp_direct` 1 vs 4. Noise must
   visibly drop; if it does not, the samples are not independent and the
   implementation is wrong. Repeat for `rt_spp_indirect` on *Unfiltered diffuse
   indirect*.
4. **No brightness shift** between N=1 and N=4 (bias check, esp. indirect).
5. **Then** the real question: final image in motion, both denoisers, at
   `rt_spp_direct 4 / rt_spp_indirect 4`.
6. **Cost:** `vid_fps` at N=1/2/4 — expect roughly linear in rays.
7. `rt_debug_restir_m 1` should show a brighter/steadier `M` as
   `rt_restir_initial` and `rt_restir_mcap` rise.

A/B arms are launched pre-set (copy the launcher to scratchpad, `sed` the
cvars) rather than typed in console.

## Out of scope

- Primary-ray supersampling (G-buffer restructure; DLAA covers aliasing).
- Reflection/refraction pass multi-sampling — add later if mirrors/water read
  as noisy specifically.
- `indirSecondBounce` is inert: its guard is commented out at
  `RtRaygenIndirect.inl:199` with a TODO about "diffuse very red". Pre-existing
  latent bug, worth a separate look, **not** part of this change.
