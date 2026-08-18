# NRD as a third denoiser path in RTGL1 — feasibility and cost

> **STATUS 2026-08-17: ACTIVE — the decision gate below is satisfied.** The RR
> second pass was measured: full input contract (pre-exposure + exposure texture +
> transparency layer + ReSTIR decorrelation) verified live in `rt-console.log` and
> still null vs A-SVGF (`rr-noise-investigation.md`, 2026-08-17 entry). That is this
> plan's own trigger: correlation/signal shape is inherent to our sampling, which is
> the argument for ReLAX.
>
> **Build findings (verified on this machine, all offline):**
> - Duke-RT does NOT use NRD's CMake: it compiles NRD 4.17.1's seven Source/*.cpp
>   directly into its target with `NRD_NORMAL_ENCODING=2 NRD_ROUGHNESS_ENCODING=1
>   NRD_SUPPORTS_{VIEWPORT_OFFSET,CHECKERBOARD,HISTORY_CONFIDENCE,
>   DISOCCLUSION_THRESHOLD_MIX}=0 NRD_SUPPORTS_BASECOLOR_METALNESS=1
>   NRD_SUPPORTS_ANTIFIREFLY=0 NRD_EMBEDS_SPIRV_SHADERS=1 SPIRV_{S,B,U,T}REG_OFFSET=
>   0/2/3/20` plus ShaderMake's `ShaderBlob.cpp` (the blob READER), and includes a
>   pre-generated `libraries/NRD/_Shaders` header dir. That dir is NOT committed in
>   Duke's tree — it must be generated once (ShaderMake + DXC) and committed on our
>   side.
> - Duke does NOT build NRI either — it stages prebuilt DLLs from a sibling
>   `NRD-Sample/_Bin` we don't have. We build NRI from its standalone CMake
>   (`NRI_STATIC_LIBRARY=ON`, `NRI_ENABLE_D3D11/D3D12=OFF`, VK only).
> - No Vulkan SDK on this machine, but **Windows Kits dxc 1.8.2502 has the `-spirv`
>   backend** (`C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\dxc.exe`)
>   — the one-time `_Shaders` generation runs on it. RTGL's own GLSL uses its
>   vendored `Source/VulkanSDK/1.3.280.0/Bin/glslc.exe` (no dxc there).
> - Also vendor `NRIFramework/External/MathLib` (0.5 MB, headers) — NRD's sources
>   include it; Duke adds it to the include path.
> - Duke's `nri_nrd.cpp` motion contract confirmed at source: `IN_MV` xy in PIXELS,
>   z = `viewZPrev - viewZ`, `motionVectorScale = {1/w, 1/h, 1}`,
>   `isMotionVectorInWorldSpace = false` — matching our `framebufMotion` 2.5D layout.
>   Duke runs `restoreInitialState = false` and writes states back; we run `true`
>   (RTGL keeps everything in GENERAL).
>
> Reference implementation: `sourcecode/Duke-RT` vendors **NRD 4.17.1** and its whole
> integration is **411 lines** (`source/common/rendering/nri/renderer/nri_nrd.cpp`).

## Context

Doom64-RT ships A-SVGF. DLSS-RR is wired but pinned off. Both are all-or-nothing: under
RR, *every* pass in `Denoiser::Denoise()` is skipped, so RR eats raw 1-spp ReSTIR output
while A-SVGF gets gradients, temporal accumulation, anti-firefly, variance and 4× atrous.

NVIDIA's **NRD** (ReLAX / ReBLUR + SIGMA for shadows) is a third option, and it is the one
Duke-RT falls back to when RR is off. Two properties make it a genuinely good hedge rather
than a consolation prize:

- **ReLAX was designed for 1-spp ReSTIR input.** The objection that killed RR here —
  *"RR assumes independent samples, which ReSTIR temporal/spatial reuse violates"*
  (RR guide §3.5) — does not apply to ReLAX, which was built for exactly this signal in
  RTXDI integrations. Duke-RT defaults to it (`nri_nrddenoiser 1`, `nri_cvars.cpp:781`).
- **NRD sidesteps the exposure bug entirely.** It runs *before* compose, on raw
  demodulated radiance. The mechanism the RR second-pass plan is chasing cannot exist on
  this path.

It is also not either/or: NRD + DLSS-SR is a valid shipping combination, and it is what
Duke-RT's three non-RR presets are.

## What already fits, unchanged

The useful surprise: RTGL1's G-buffer largely already matches NRD's contract, because
A-SVGF wanted similar things.

| NRD input | RTGL1 today | Work |
|---|---|---|
| `IN_MV` | `framebufMotion` = `vec4(motionCurToPrev.xy, motionDepthLinearCurToPrev, 0)` (`RaygenPrimary.inl:619`) | **none — this is 2.5D, a supported NRD format verbatim.** Duke-RT sets `isMotionVectorInWorldSpace = false` with `motionVectorScale = {1/w, 1/h, 1}` (`nri_nrd.cpp:291-293, 315`); confirm our xy units are pixels |
| `IN_VIEWZ` | `DepthWorld` (fp16 R) | small convert — world distance → view-space Z |
| `IN_NORMAL_ROUGHNESS` | `Normal` (uint32) + `MetallicRoughness` (unorm8 RG) | repack via `NRD_FrontEnd_PackNormalAndRoughness` |
| `IN_BASECOLOR_METALNESS` | `Albedo` + `MetallicRoughness` | repack |
| specular hit distance | `SpecularHitDistance` (fp16 R) | **already exists** — built for RR |
| separate diffuse/spec | `UnfilteredDirect`, `UnfilteredIndir`, `UnfilteredSpecular` | already separated |
| matrices, jitter, frameIndex | all in `ShGlobalUniform` | plumbing only |

Contract size: **5 inputs, 2 outputs** for `RELAX_DIFFUSE_SPECULAR`. That is the whole
thing.

## What has to be built

### 1. NRI as a *wrapper*, not an owner — the load-bearing finding

`NRDIntegration.hpp` hard-requires NRI (`#error "NRI.h" is not included`), so NRI cannot
be avoided. But it does **not** have to own the device. `NRIWrapperVK.h` exposes:

```c
NriStruct(DeviceCreationVKDesc) {
    Nri(VKBindingOffsets) vkBindingOffsets;
    Nri(VKExtensions) vkExtensions;       // enabled
    VKHandle vkInstance; vkDevice; vkPhysicalDevice;
    uint8_t minorVersion;                 // >= 2
};
```

plus `CreateCommandBufferVK` (wrap our per-frame `VkCommandBuffer`) and `CreateTextureVK`
(wrap our existing `VkImage`s). **RTGL1 keeps owning Vulkan and hands NRD wrapped
handles.** This is the difference between a bolt-on and a rewrite.

`vkBindingOffsets` must match NRD's build-time SPIR-V register shifts, which are declared
in `libraries/NRD/CMakeLists.txt:90-94`: `sReg 0, bReg 2, uReg 3, tReg 20`.

### 2. Four new RGBA16F buffers and a pack pass

The blocker in the current framebuffer set: the unfiltered buffers are `TYPE_PACK_E5`
(`GenerateShaderCommon.py:1543-1545`) — E5B9G9R9, **RGB only, no alpha**. NRD needs
radiance in `.rgb` with hit distance in `.w`.

New: `IN_DIFF_RADIANCE_HITDIST`, `IN_SPEC_RADIANCE_HITDIST`, `OUT_DIFF_*`, `OUT_SPEC_*`.
A new compute pass reads the E5 buffers, **demodulates by albedo** (NRD requires
demodulated radiance) and packs with `RELAX_FrontEnd_PackRadianceAndHitDist` /
`REBLUR_FrontEnd_PackRadianceAndNormHitDist`.

### 3. A diffuse hit distance — the one missing signal

Specular has one; diffuse does not. `ViewDirection.w` already receives an indirect hit
distance but **conditionally** — only when indirect > direct
(`RtRaygenIndirect.inl:485`). Making it unconditional is a small raygen change.

Design compromise to accept up front: NRD takes **one** diffuse signal, so
`UnfilteredDirect + UnfilteredIndir` must be summed and carry a single hit distance.
Duke-RT hit the same wall and says so in a comment — *"current Raze gameplay still
denoises a mixed direct+indirect signal"* (`nri_nrd.cpp:64-65`). Not a defect, just the
shape of the API.

### 4. Checkerboard

RTGL1's `getCheckerboardPix` is a bijective full-res swizzle, not half-rate rendering
(`docs/rayreconstruction/architecture-rr-plan.md`), but the unfiltered buffers are written
in checkerboard *space*. Resolve to regular pixel space before NRD. Leave NRD's own
`checkerboardMode` **OFF** — it means something different.

### 5. Remodulate, then branch

After NRD: multiply diffuse by `ro_d`, specular by `ro_s`, combine. That is
`CmNoisyCompose` with denoised inputs — mostly reuse, not new code.

Then a third arm at the `VulkanDevice.cpp:1324` if/else, which today is binary:
`rt_denoiser` 0 = A-SVGF, 1 = DLSS-RR, 2 = NRD. Plus `rt_nrd_mode` (ReLAX/ReBLUR) and the
accumulation knobs. All `RT_CVAR_NOARCH`.

### 6. Image layout — a real concern with a clean answer

RTGL1 keeps every framebuffer image in `VK_IMAGE_LAYOUT_GENERAL` permanently, while NRD's
`ResourceSnapshot` tracks and mutates states. Duke-RT sets
`resourceSnapshot.restoreInitialState = false` and writes the resulting states back into
its own tracker (`nri_nrd.cpp:352, 375-382`). **We want the opposite:
`restoreInitialState = true`**, so NRD hands every image back in GENERAL and RTGL1's
assumption is never violated.

## Effort

| Piece | Estimate | Risk |
|---|---|---|
| Vendor NRD + NRI + ShaderMake, CMake, DXC/SPIR-V build | ~1 session | low, mechanical |
| NRI device/command-buffer/texture wrapping | 1–2 sessions | **highest** |
| New buffers + pack/demodulate pass | 1–2 sessions | medium — this is the subtle-correctness half |
| Diffuse hit distance in raygen | ~0.5 session | low |
| Remodulate + branch + cvars + A/B arms | ~0.5 session | low |
| Debugging "it's black / it's wrong" | 1–2 sessions | assume it happens |

**Total: 5–8 focused sessions.**

### Costs and risks to weigh

- **Memory:** ~4 new full-res RGBA16F buffers ≈ 32 bytes/px, ~64 MB at 1080p render res,
  plus ReLAX's internal history pool (~15–20 textures). Not free.
- **`apiVersion = VK_API_VERSION_1_2`** (`VulkanDevice_Init.cpp:834`) is *exactly* NRI's
  stated minimum (`minorVersion >= 2`). No headroom. Bumping RTGL1 to 1.3 is trivial on a
  5090 if anything needs it, but check before assuming.
- **Build-time DXC dependency.** `NRD_EMBEDS_SPIRV_SHADERS` is ON, so nothing extra ships
  at runtime — but building NRD needs ShaderMake + DXC with the SPIR-V backend.
- **A third denoiser path to maintain**, and the demodulation contract is the same class
  of subtle-correctness work that has cost this project days before.

### One thing that partly pays for itself

NRD exposes `OUT_VALIDATION` — a built-in per-input validation overlay
(`nri_nrd.cpp:362`). Given that five of this project's day-costing RR faults were
invisible-setting faults, and that `rt_debug_visibility` had to be *invented* to tell
"the ray was never blocked" from "it was blocked and the result was drowned", a
vendor-supplied guide-validation view is worth real money here.

## Honest caveat

ReLAX is a spatiotemporal filter of the same family as A-SVGF. It may land close to what
already ships rather than clearly beating it. The defensible case for NRD is mostly
**RR-independent**: real specular reprojection from true hit distances, SIGMA for
shadows, and the validation overlay. Do not adopt it expecting a step change in motion
stability — adopt it because 1-spp ReSTIR is the input it was designed for, and because
it removes the exposure-ordering problem by construction.

## Decision gate

**Do not start this until `docs/plan-rayreconstruction-secondpass.md` has been measured.**
If the pre-exposure reorder fixes RR, none of this is needed. If it does not, the ReSTIR
correlation hypothesis (`rr-noise-fix-proposals.md` §4) is cheaper than NRD and should be
tried next — and if *that* fails, the reason will most likely be that ReSTIR correlation
is inherent to our sampling, which is precisely the argument for ReLAX and for this plan.

## Verification (when it happens)

Same rules as everything else in this project:

1. **Prove it is live first.** NRD's `OUT_VALIDATION` overlay is the fastest existing
   answer to "did any of this reach the GPU"; wire it before wiring anything else.
2. **Absurd arm before subtle arm** — force an extreme accumulation frame count so the
   image visibly breaks. If it does not, the settings are not arriving.
3. **Regression gate:** `rt_denoiser 0` must be byte-identical to today's A-SVGF.
4. **No brightness shift** across denoiser paths. A shift means demodulate/remodulate is
   not a round trip — check this before judging noise.
5. **Ask the user for the visual verdict, in motion.** Stills cannot measure temporal
   noise, and scalar noise metrics already scored RR and A-SVGF equal once.
