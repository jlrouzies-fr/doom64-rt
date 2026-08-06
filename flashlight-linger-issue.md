# Flashlight / transient-light lingering under DLSS-RR

## Symptom (2026-08-06)

After the 2026-08-06 RR guide fixes (corrected diffuse/specular guides in `CmNoisyCompose` + `envBRDFApprox2` in `BRDF.h`), DLSS-RR denoising quality improved significantly. However, transient lighting changes now **linger** for seconds because RR's temporal history is much more stable:

| Action | Observed delay |
|---|---|
| Turn flashlight **ON** | ~3–4 seconds to reach full brightness |
| Turn flashlight **OFF** | ~6–7 seconds for light to fully disappear |

Any movement (weapon swing, camera) through the fading light "forces a refresh" and briefly shows the correct dark state, confirming the issue is RR temporal history, not the light list itself. This was **not present before** the guide fixes — the old raw-albedo/raw-F0 guides made RR's history unstable (noisy), which masked this problem.

## What was tried

### 1. DLSS-RR disocclusion mask (Claude Fable / GaetanRouzies, merged 2026-08-06)

The upstream commit (`f56ad00` in `deps/RTGL` + `e59ba9ebf` in `sourcecode/gzdoom-rt`) added a tile-based disocclusion mask:

- **`CmNoisyCompose.comp`**: Per-frame tile-luminance comparison (16×16 tiles, 256-tap mean of `getLuminance(diffuse + indirect)`, motion-reprojected via `framebufMotionDlss`). On ratio > `rt_rr_disocc_ratio` (3.0), writes sentinel `10000.0` to `framebufRrDisocclusion`.
- **`DLSSRR.cpp`**: Binds `pInDisocclusionMask = FB_IMAGE_INDEX_RR_DISOCCLUSION` for NGX DLSS-RR.
- **`gzdoom-rt/rt_main.cpp`**: New cvars `rt_rr_disocc`, `rt_rr_disocc_ratio`, `rt_rr_disocc_mindelta`, `rt_rr_disocc_show`.
- **`CmPrepareFinal.comp`**: Debug overlay — if `rrDisoccShowMask != 0` and `texelFetch(framebufRrDisocclusion_Sampler).r > 0`, tints the tile red.

**Result: zero visible effect.** No red tiles ever appeared with `rt_rr_disocc_show 1`, even after lowering `rt_rr_disocc_ratio` to 1.5 and `rt_rr_disocc_mindelta` to 0.005. The launcher at `tools/launch-retribution-rt.cmd` was updated with these cvars.

### 2. Force-test: always write 10000.0 to every pixel

Modified `CmNoisyCompose.comp` to unconditionally write `DISOCC_FORCE_HISTORY_DISCARD` (10000.0) to `framebufRrDisocclusion` for every on-screen pixel:

```glsl
mask = DISOCC_FORCE_HISTORY_DISCARD;  // always fire
#if 0
// ... original luminance condition ...
#endif
imageStore(framebufRrDisocclusion, pix, vec4(mask));
```

**Result: still no red tiles.** The debug overlay in `CmPrepareFinal` reads `0.0` from the sampler.

### 3. Barrier: add `FB_IMAGE_INDEX_RR_DISOCCLUSION` to `ImageComposition::Finalize()`

Hypothesis: the buffer wasn't being transitioned from the layout NGX left it in. Added `FB_IMAGE_INDEX_RR_DISOCCLUSION` to the barrier list in `Finalize()` (which runs `CmPrepareFinal`).

**Result: still no red tiles.**

### 4. Hardcoded magenta tint in CmPrepareFinal

To verify the SPV is actually loading:

```glsl
hdr = mix(hdr, vec3(1.0, 0.0, 1.0), 0.3);
```

**Result: magenta tint visible on screen.** Confirms `CmPrepareFinal.comp.spv` and the RTGL DLL are loading correctly.

### 5. Read via storage image (binding 72) vs sampler (binding 153)

To isolate whether the sampler descriptor is the broken link:

```glsl
// read via storage image (binding 72):
float disoccDebug = imageLoad(framebufRrDisocclusion, pix).r;
if(disoccDebug > 0.0) { hdr = mix(hdr, vec3(4,0,0), 0.5); }  // red

// read via sampler (binding 153):
if(texelFetch(framebufRrDisocclusion_Sampler, pix, 0).r > 0.0)
    { hdr = mix(hdr, vec3(0,1,0), 0.5); }  // green
```

**Result: neither red nor green appears — only magenta.** Both storage image read and sampler read return `0.0`, even though CmNoisyCompose writes `10000.0` to every pixel.

### 6. Null `pInDisocclusionMask` in DLSS-RR

Hypothesis: NGX transitions the disocclusion buffer to a layout incompatible with subsequent reads. Set `evalParams.pInDisocclusionMask = nullptr` so NGX never touches the buffer.

**Result: still no red or green — only magenta.** NGX layout transitions are NOT the cause.

## Current state

| What works | What doesn't |
|---|---|
| CmNoisyCompose shader compiles and is dispatched (RR path) | Write to `framebufRrDisocclusion` is **not visible** to CmPrepareFinal |
| CmPrepareFinal shader loads and runs (magenta tint) | `imageLoad(framebufRrDisocclusion)` returns 0 |
| `framebufRrDisocclusion_Sampler` is declared in descriptor set (binding 153) | `texelFetch(framebufRrDisocclusion_Sampler)` returns 0 |
| Descriptor set layout includes bindings for RrDisocclusion (72 + 153) | Buffer value never crosses from write to read |
| DLSS-RR runs (image looks denoised) | — |
| `nvngx_dlssd.dll` is 310.7.0 (latest) | — |

The write from CmNoisyCompose to `framebufRrDisocclusion` **never reaches** the CmPrepareFinal read. The buffer is defined, its descriptors are allocated, but the two compute dispatches operate on effectively different data.

## Suspected root cause

The `framebufRrDisocclusion` buffer (R16F, index 72) may not actually be **allocated** in the framebuffer pool. The framebuffer enumeration (`ShaderCommonCFramebuf.h`, `ShaderCommonCFramebuf.cpp`) was regenerated by `GenerateShaderCommon.py` to include the new indices, and the descriptor set layout is rebuilt from those counts. But the actual Vulkan image creation (`Framebuffers::CreateImages`) might have a hardcoded limit or a generation issue that silently skips the new framebuffers — so the image handle is `VK_NULL_HANDLE`, and writes to a null storage image are no-ops.

Alternative: the `ShFramebuffers_Count` constant might not include the new frames, causing the descriptor set layout to be truncated. Or the `FRAMEBUFFERS_HISTORY_LENGTH` × `ShFramebuffers_Count` image creation loop might stop short.

## Next steps (do not attempt until agreed)

1. **Verify image allocation:** Check `Framebuffers::CreateImages()` to confirm `imageViews[72]` is a valid handle. Add a debug-named `VK_IMAGE` with the name "RrDisocclusion" visible in RenderDoc / Nsight.
2. **RenderDoc / Nsight capture:** Capture a frame and inspect the `framebufRrDisocclusion` image after CmNoisyCompose — does it contain `10000.0` values? If yes, the write works but the read path is broken. If no, the image was never allocated.
3. **Test with a known-working buffer:** Temporarily repurpose `framebufPreFinal` or another confirmed-working buffer to carry the disocclusion signal. This would prove whether the issue is specific to the new buffer indices.
4. **Bypass the disocclusion buffer entirely:** Write the mask as the **alpha channel** of an existing buffer (e.g. `framebufDiffColorHistory.a`) and read it from there. This avoids any framebuffer-creation issues.
5. **Once plumbing works:** Restore the luminance condition and tune per-pixel instead of per-tile for thin-object detection (weapon trails).