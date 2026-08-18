# DLSS-RR noisier than A-SVGF — root causes & fix plan

Research doc, 2026-08-05. Cross-checks **our** native RR integration (published code: branch **`doom64-rt`** of `jlrouzies-fr/RTGL` @ `df2797e7`+`cb067f54` and `jlrouzies-fr/gzdoom-rt` @ `f4c7afd8`) against:

- **NVIDIA DLSS-RR Integration Guide** (`NVIDIA/DLSS` → `doc/DLSS-RR Integration Guide.pdf`, rev. through Dec 2025) + Streamline `ProgrammingGuideDLSS_RR.md` + NGX headers
- **RTX Remix** (`NVIDIAGameWorks/dxvk-remix`) — NVIDIA's own shipping "raw path tracer → RR" integration
- **nvpro-samples/vk_denoise_dlssrr** — official minimal Vulkan RR sample

**Related:** `rr-noise-investigation.md` (symptoms / failed fixes), `../../compat-patches.md`, `../../AGENTS.md`.

> Housekeeping: `../../AGENTS.md` says branch `rayreconstruction` → `doom64-rt.git`. Publicly the RR code lives on branch **`doom64-rt`** of `jlrouzies-fr/gzdoom-rt` + `jlrouzies-fr/RTGL`; no `doom64-rt` repo exists. Fix the pointer or push the missing repo.

---

## 0. TL;DR — ranked causes

| # | Cause | Confidence | Cost | Expected effect |
|---|---|---|---|---|
| 1 | **Guide/color demodulation mismatch** — color fed to RR contains `throughput`, `getMaterialAmbient`, EV100 exposure, screen-emission and rasterized sprites that are in **no guide buffer**; diffuse-albedo guide is raw albedo (not `ro_d`) | High | Shader-only | Less residual **diffuse-direct salt** (our exact symptom) |
| 2 | **Specular-albedo guide is raw F0**, not the env-BRDF preintegrated reflectivity the guide mandates | High | Shader-only | Less noise/boil on **PBR/ORM** surfaces (matches "worse after full-tree ORM") |
| 3 | **`pInSpecularHitDistance` is bound to `DepthWorld`** = primary-hit camera distance — semantically wrong signal | High | 1-line A/B, then plumbing | Less **walk shimmer** on glossy/rough-spec (matches roughness-G A/B) |
| 4 | **ReSTIR reservoir correlation** — no permutation sampling, no boiling filter, white-noise 8-tap spatial reuse; NVIDIA §3.5 explicitly requires decorrelated reservoirs for RR | High | Raygen changes | Less blotchy salt, esp. after **lamp blinks** |
| 5 | **Old `nvngx_dlssd.dll` / preset fallback** — we pin Preset E (transformer, needs SDK ≥ 310.2.1); a stale DLL silently reverts to CNN, whose known signature is **grain in dark scenes** | Medium (unverified) | Zero (verify) | If stale: fixes most of it for free |
| 6 | No transparency layer / masks for **blinking emissives, weapon, particles** | Medium | Medium | Less ghost/salt around SMON/EXIT/lava blink, muzzle, viewmodel |

Items 1–3 are straight contract violations; 4 is a documented requirement we don't meet; 5 is a 5-minute check to do **first**.

---

## 1. What we feed NGX today vs the contract

From `RTGL/Source/DLSSRR.cpp` (create 192–236, eval 353–401) + `CmNoisyCompose.comp` 152–209 + `VulkanDevice.cpp` 792–799 / 916–917:

| NGX param | We bind | Contract / Remix | Verdict |
|---|---|---|---|
| `pInColor` | `FB_FINAL` = ComposeNoisy → volumetrics → checkerboard resolve → **raster sprites/translucency** → **× EV100 exposure** → **+ screenEmis** | Linear HDR pre-tonemap noisy radiance; Remix feeds composite **before** exposure/tonemap; particles via separate layer | **✗** (3 contaminants) |
| `pInDiffuseAlbedo` | `FB_ALBEDO` raw base color; sky = HDR `adjustSky()/π` | "Diffuse component of reflectance", linear; must match what modulates the color | **✗** (missing `1−metallic`, throughput, ambient) |
| `pInSpecularAlbedo` | `getSpecularColor(albedo, metallic)` = F0; sky = 0 | "**Average specular reflectivity given a view direction**" = `EnvBRDFApprox2(F0, r², NoV)`; sky default (0.5,0.5,0.5) | **✗** |
| `pInNormals` (+roughness .w) | world-space normal + roughness, `Roughness_Mode_Packed` set | World or view space OK; **linear** roughness; packed mode flag required | **✓** (verify roughness is perceptual/linear) |
| `pInDepth` | NDC `[0,1]`, `Depth_Type_HW`, no DepthInverted | HW or linear accepted | **✓** |
| `pInMotionVectors` | `(prev−cur)` UV × render size, `MVLowRes`, unjittered | current+MV = previous, pixels | **✓** |
| `pInSpecularHitDistance` | **`FB_DEPTH_WORLD`** — primary-hit view distance | "World-space distance between the **specular ray origin** (primary surface) **and hit point**" | **✗ wrong signal** |
| `pInWorldToViewMatrix` / `pInViewToClipMatrix` | RTGL column-major GL-style `view` / `projection`, raw | "Row Major Order, left multiplication" | **✓ probably** — GL column-major storage is byte-identical to D3D row-major storage of the same transform (translation at floats 12–14 in both). Verify with overlay, don't blind-transpose |
| Exposure | `InPreExposure=1`, no texture — but EV100 **baked into the color** | RR guide §3.7: exposure/auto-exposure/sharpness "**not supported** by DLSS-RR" — feed pre-exposure radiance | **✗** |
| Jitter | Halton(2,3), 64 phases, negated (same as DLSS2) | ≥32 phases recommended | **✓** |
| Preset | `Preset_E` pinned on all 5 quality slots | D/E = transformer (SDK ≥ 310.1 / E ≥ 310.2.1); A–C removed in 310.4.0 | **✓ iff DLL is 310.2.1+** |
| Transparency layer / disocclusion / bias masks | none | Optional; Remix uses all three | missing (see §5) |

---

## 2. P0 — verify before touching code

1. **DLL version.** `tools/build-rtgl.cmd` stages `nvngx_dlssd.dll` from the `deps/DLSS` clone. Confirm the staged DLL in `build/RelWithDebInfo/rt/bin/` is **≥ 310.2.1** (ideally 310.7.0, June 2026) — file properties → product version, or NGX init log. A 3.5–3.8-era DLL ignores our Preset E hint → CNN model → **dark-area grain/boiling is its textbook failure**, and Doom is dark. If stale, restage and re-A/B before anything else.
2. **Dev-DLL guide overlay.** Swap in the *Develop* `nvngx_dlssd.dll` from the SDK (`lib/.../dev/`), hit **Ctrl+Alt+F12** in-game and page through the guide views (jitter scatter plot, MV, albedo, spec-albedo, normals, roughness, depth). This is NVIDIA's officially recommended way to validate guides and will instantly show gross errors (transposed matrices, dead guides, jitter range).
3. **DLAA A/B.** `5090` has headroom: run RR at DLAA (no upscale) once to separate denoise noise from upscale noise.

---

## 3. P1 — contract fixes (shader/binding level, all in `deps/RTGL`)

### 3.1 Make guides match the color exactly (kills diffuse salt)

`CmNoisyCompose.comp` builds:

```glsl
illuminated = ((diffuse + indirect) * ro_d + specBlend * ro_s) * throughput;
illuminated *= getMaterialAmbient(albedo);
```

but the guides are `diffuseAlbedo = albedo` (raw) and `specularAlbedo = ro_s`. RR internally demodulates `color / guide`; every factor present in color but absent from the guide (here: `1−metallic`, `throughput`, `getMaterialAmbient`) survives demodulation as **noise it cannot separate from lighting**. Fix — write the guides RR actually needs:

```glsl
// in CmNoisyCompose alongside PreFinal:
vec3 mod = throughput * getMaterialAmbient(albedo);   // or drop ambient on the RR path entirely
guideDiffuseAlbedo  = ro_d * mod;                     // albedo * (1 - metallic) * mod
guideSpecularAlbedo = envBrdfApprox2(ro_s, roughness*roughness, NoV) * mod;   // §3.2
```

Write them to dedicated (or reused) buffers instead of binding `FB_ALBEDO` raw. Sky: keep the sky radiance path in the diffuse guide but **bounded** (tonemapped, as the nvpro sample does), and set sky **spec** albedo to (0.5,0.5,0.5) per the guide (§3.4.2 — "a common integration error is to leave sky pixels uncleared").

Also reconsider the `mix(specular, indirect, smoothstep(0.5, 0.75, roughness))` fake — it labels indirect radiance as specular while the roughness guide says "rough". Harmless for A-SVGF's dumb compose, but it feeds RR contradictory signals. First try: leave it, fix guides; if rough-spec noise persists, A/B without the blend.

### 3.2 Env-BRDF preintegrated specular albedo (kills PBR/ORM noise)

The guide's exact recommended code (Ray Tracing Gems ch. 32; Remix uses the identical fit in `demodulate.comp.slang:608`):

```hlsl
float3 EnvBRDFApprox2(float3 F0, float alpha, float NoV) {
    NoV = abs(NoV);
    float4 X = float4(1.0, NoV, NoV*NoV, NoV*NoV*NoV);
    float4 Y = float4(1.0, alpha, alpha*alpha, alpha*alpha*alpha);
    float2x2 M1 = float2x2(0.99044, -1.28514, 1.29678, -0.755907);
    float3x3 M2 = float3x3(1.0, 2.92338, 59.4188, 20.3225, -27.0302, 222.592, 121.563, 626.13, 316.627);
    float2x2 M3 = float2x2(0.0365463, 3.32707, 9.0632, -9.04756);
    float3x3 M4 = float3x3(1.0, 3.59685, -1.36772, 9.04401, -16.3174, 9.22949, 5.56589, 19.7886, -20.2123);
    float scale = mul(mul(float2(1.0, NoV), M1), float2(1.0, alpha))  / mul(mul(float3(1.0, NoV, NoV*NoV*NoV), M2), float3(1.0, alpha, alpha*alpha*alpha));
    float bias  = mul(mul(float2(1.0, NoV), M3), float2(1.0, alpha))  / mul(mul(float3(1.0, NoV, NoV*NoV*NoV), M4), float3(1.0, alpha, alpha*alpha*alpha));
    bias *= saturate(F0.g * 50.0);      // official hack for F0 = 0
    return mad(F0, max(0, scale), max(0, bias));
}
// alpha = linearRoughness * linearRoughness
```

(Exact coefficient matrices are in the RR guide appendix / Streamline §4.2.1 and `dxvk-remix` `brdf.slangh:671` — copy from there, the values above are from the published fit; verify against source when porting.)

Optional Remix knob worth copying once the basics land: **roughness-demodulate** the spec guide — `guide *= 0.15 * pow(1.0/(r + 0.1), 1.5)` ("suppress noise / enhance roughness detail"). Directly targets our rough-spec walk shimmer.

### 3.3 Specular hit distance: stop lying to it

`DepthWorld` is *primary-hit distance from the camera* — RR uses this input (plus the matrices) to reproject **reflections**; a wrong value corrupts specular history every frame. Two steps:

1. **Immediate A/B:** `pInSpecularHitDistance = nullptr`. No guide beats a wrong guide. Expect glossy/rough-spec walk noise to drop.
2. **Proper fix:** write real specular hitT (distance from primary surface along the specular bounce ray to its hit) into an R16F buffer at raygen time. `FB_VIEW_DIRECTION.w` already receives an indirect hit distance *conditionally* (`RtRaygenIndirect.inl:485` — only when indirect > direct); make it unconditional for the first specular-lobe ray, or add a dedicated buffer. Remix binds exactly this (`PrimaryIndirectSpecularRadianceHitDistance.a`), option `useSpecularHitDistance` default **true**, "reduce ghosting".

### 3.4 Feed RR pre-exposure, pre-emission, pre-raster color (reorder the tail)

Current RR-path order (`VulkanDevice.cpp`): ComposeNoisy → volumetrics → exposure calc → checkerboard resolve → **raster into Final** → `CmPrepareFinal` (**× EV100**, **+ screenEmis × maxscrcolor**) → **RR** → present.

Problems: (a) auto-exposure swings (dark Doom rooms!) read as global lighting changes to RR's history — and per §3.7 RR *ignores* every exposure parameter, it expects raw radiance; (b) screen emission is added with no guide → RR "denoises" (smears/re-noises) our emissive glow, and blinking SMON/EXIT emission churns history; (c) rasterized viewmodel/sprites sit on pixels whose depth/normal/albedo guides describe the **world behind them** — contradictory input.

Target order:

```
ComposeNoisy (+ volumetrics into color)  →  RR(PreFinal)  →  on the UPSCALED output:
    × EV100 exposure  →  + screenEmis (bilinear-upscaled; it is smooth glow)  →  raster weapon/HUD at output res  →  tonemap/present
```

Side benefit: the viewmodel and HUD raster at full output resolution (crisper than being DLSS'd). If moving the raster pass is too invasive, route it through `pInTransparencyLayer` instead (§5). ScreenEmission is render-res — bilinear upscale is fine, or move it to the transparency layer too.

---

## 4. P2 — decorrelate ReSTIR (the documented requirement we don't meet)

RR guide §3.5 (added Feb 2025), verbatim:

> "DLSS RR **assumes independent samples** and requires that sampling used to generate Inputs must have **minimal correlation both spatially and temporally**. […] **When using ReSTIR GI or RTX DI: Randomize the temporal reuse step.** RR assumes independent samples, **which is violated by ReSTIR temporal and spatial reuse. Permutation sampling helps avoid correlation artifacts.** […] avoid using the same samples for neighboring pixels' reservoirs."

Our `RaygenCommon.h` ReSTIR DI: temporal reuse jittered only ±2 px, spatial reuse **8 samples @ radius 30 px with white-noise `rnd8_4`** over initial reservoirs, M-cap ×20, **zero boiling filter** (grep confirms). Neighboring pixels constantly share the same reservoir samples → correlated blotches that RR preserves as "signal". A-SVGF's temporal accumulation averaged this away, which is exactly why A-SVGF looks stabler.

What Remix ships when RR is on (its `PathTracerPreset::RayReconstruction` + ReSTIR-GI RR preset — copy the *ideas*, tune the numbers):

| Lever | Remix RR value | Our equivalent |
|---|---|---|
| Permutation / randomized temporal reuse | `usePermutationSampling` every frame; diffuse temporal reprojection randomized within **80 px**, reservoir M inflated ÷0.26 — "reduce sample coherency" | Randomize the temporal fetch offset well beyond ±2 px for diffuse; renormalize M accordingly |
| Boiling filter | ReSTIR-GI boiling filter ON, aggressive (remove threshold 62→30) | Add reservoir boiling filter (kill reservoirs whose weight ≫ neighborhood average) — **in raygen, not screen space** |
| Firefly clamp | Integrator-level luminance clamp at radiance-write time, threshold ~1000 (GI initial ×30, secondary spec 120) | Clamp in `RtRaygen*` when writing Unfiltered* — this is NOT the failed `CmNoisyCompose` 5×5 min/max (see §7) |
| Sample counts | RTXDI initial **3** + spatial **2** + disocclusion 2 (fewer, decorrelated > many, correlated) | Try spatial 2–4 with randomized radius vs our 8@30 |
| Hash quality | — (guide: "use high quality hash functions… xxhash32") | Replace `rnd8_4` white-noise offsets with a bigcrush-clean hash |

Also §3.5: "**Avoid checkerboard rendering.**" Our checkerboard is mostly a bijective memory swizzle (full res, fine), **except** split reflection/refraction pixels (`Throughput.a` + `CmCheckerboard` 50% cross-blur) — real alternating-pattern sampling on water/glass. Localized; deprioritize, but it's on the list if glass stays noisy.

Blinking lamps: soft fades (landed) are the right call and stay. Decorrelation is the second half of that fix — after a blink resets history, the first frames are pure initial+spatial reservoirs, i.e. maximum correlation; permutation sampling is what makes those frames RR-digestible.

---

## 5. P3 — content routing (Remix playbook)

| Content | Route | Why |
|---|---|---|
| Rasterized translucency, viewmodel, muzzle/Lost-Soul sprites, particles | `pInTransparencyLayer` (RGBA16F, premultiplied alpha) — "**not denoised, upscaled only**" | Removes guide-contradicting pixels from the denoised path; Remix's default `particleBufferMode = RayReconstructionUpscaling` |
| Blinking / animated emissive faces (SMON, EXIT, lava frames) | Emission component → transparency layer | Remix explicitly moves **sprite-sheet-animated emissives** there "to reduce ghosting" — a 1:1 match for our ANIMDEFS screens |
| Material/texture-change pixels (switch flips, animated flats) | `pInDisocclusionMask` with sentinel `10000.0` | Remix writes 10000 to force RR history discard on `hasMaterialChanged` |
| Blink-lit regions (if salt persists after fades + decorrelation) | `pInBiasCurrentColorMask` / `pInResponsivityMask` | Header-level anti-ghost/responsivity controls; Remix wires the bias mask concept for unordered emissives |

These are additive — do them after §3, they need new plumbing from gzdoom-rt (flagging which draws are "unordered") but each is independently testable.

---

## 6. Smaller checks

- **Roughness linearity:** guide demands **linear (perceptual) roughness** in `normals.w` — verify no `r*r` sneaks in before packing, and that ORM G is perceptual.
- **Matrices:** likely correct as-is (layout equivalence, §1). Confirm once via dev overlay; only transpose if reflections visibly mis-reproject.
- **`InToneMapperType = ONEOVERLUMA`:** Remix leaves it default; not evidence of harm, just note it's an SR-era knob.
- **ASVGF gradient passes still dispatched but unused on the RR path** — dead GPU work, skip them when RR is on.
- **No dynamic resolution** with RR (docs) — we don't use it; keep it that way.
- **Preset experiment:** once the DLL is confirmed ≥ 310.4, A/B Preset **Default vs D vs E** — NVIDIA now recommends Default ("may improve after OTA"); Remix defaults to E ("Truthful Shrimp"), D optional.

---

## 7. Why the previously failed fixes failed (and why these are different)

| Failed attempt (`rr-noise-investigation.md` §4) | Docs' explanation | This plan's counterpart |
|---|---|---|
| `CmNoisyCompose` 5×5 min/max clamp — no-op / hurt | Screen-space post-hoc clamping mangles the noise distribution RR was trained on | Clamp **at radiance-write time in raygen** (luminance threshold, Remix-style) — outliers never enter the signal |
| Luminance boiling ×5 in compose — IQ worse | Same: don't pre-mangle the composed image | Boiling filter **on reservoirs** inside ReSTIR (weight-space, before shading) |
| `rt_rr_temporal` (A-SVGF temporal → RR) — ghosts | §3.5 requires *minimal temporal correlation*; pre-accumulation is the maximum violation | Never revisit. Decorrelation (permutation sampling) is the opposite lever |
| Lamp soft fades — worked | Stable `uniqueID` + eased intensity = temporally coherent light list | Keep; §4 finishes the job on the reservoir side |

---

## 8. Suggested execution order

| # | Item | Status |
|---|---|---|
| 1 | §2.1 DLL version check | ✅ **Done** — 310.7.0 (latest, June 2026) |
| 2 | §2.2 dev-overlay sweep | ⏸ Skipped (no dev DLL; guide validation via visual A/B) |
| 3 | §3.3 step 1: null `pInSpecularHitDistance` | ✅ **Landed** (`DLSSRR.cpp:400`) |
| 4 | §3.1 + §3.2 guide rewrite | ✅ **Landed** (`CmNoisyCompose.comp` + `BRDF.h`); pushed to public RTGL branch 2026-08-06 |
| 5 | §3.4 reorder exposure/emission/raster after RR | ✅ **Landed 2026-08-17**, in two passes. Pass 1 (reorder alone): **A/B verdict NULL** — noise/dark dots unchanged, plus a jitter regression (screen emission re-added post-RR from the jittered render-res buffer with no correction; fixed, `CmRrPostExposure.comp`). Pass 1 also dropped the 1×1 exposure texture as "the SDK's own correct parameterization" — valid for the API, wrong for a non-scale-invariant network fed raw radiance across a ~52× exposure swing. Pass 2 reinstated it: `rt_rr_exptex` (default on), 1×1 R32F written by `CmPrepareFinal` (0,0), bound as `pInExposureTexture` |
| 6 | §3.3 step 2: real specular hitT | ⬜ Pending |
| 7 | §4 ReSTIR decorrelation | ✅ **Landed 2026-08-17** as `rt_rr_restir_mcap` (default 4, −1=off): caps ReSTIR temporal M on RR frames only — a reservoir winner held for 20 frames is a *stable dark dot* the denoiser preserves as detail, and reseeding on flashlight toggle is exactly the observed pattern-switch. Permutation sampling / boiling filter remain unimplemented follow-ups if the cap alone is insufficient |
| 8 | §5 content routing (transparency layer) | ✅ **Landed 2026-08-17** as `rt_rr_translayer` (default on): the world raster pass (every translucent sprite, particles, lens flares) redirects into an RGBA16F layer bound as `pInTransparencyLayer`, NGX-composited after denoise+upscale. Additive sprites blend alpha ZERO/ONE (occlude nothing); 'over' accumulates true coverage. A/B: `rr-full` vs `rr-asvgf`, isolation via `rr-no-translayer`/`rr-no-decorr`/`rr-no-exptex`, `rr-legacy` = pre-redo RR |
| 9 | §5 disocclusion mask (`pInDisocclusionMask`) for transient-light linger | ✅ **Landed 2026-08-06** (tile-luminance change → sentinel 10000.0; see investigation §1.2) |

Log every A/B in `rr-noise-investigation.md` as usual.

---

## 9. Sources

- DLSS-RR Integration Guide: `github.com/NVIDIA/DLSS` → `doc/DLSS-RR Integration Guide.pdf` (§3.4.2 sky albedo, §3.5 sampling/noise, §3.7 exposure unsupported, §3.13 presets, ch. 8 dev overlay)
- Streamline: `github.com/NVIDIA-RTX/Streamline` → `ProgrammingGuideDLSS_RR.md`, `include/sl_dlss_d.h` (row-major matrices, HDR-only, spec-albedo env-BRDF listing)
- NGX headers: `nvsdk_ngx_defs_dlssd.h` (presets D=4/E=5, A–C removed), `nvsdk_ngx_helpers_dlssd_vk.h` (full optional-input list: transparency layer, disocclusion/bias/responsivity masks, colorBeforeTransparency…)
- SDK releases: 310.1.0 (RR transformer, 2025-01), 310.2.1 (Preset E), 310.4.0 (A–C removed), 310.7.0 (2026-06, current)
- RTX Remix: `github.com/NVIDIAGameWorks/dxvk-remix` — `rtx_ray_reconstruction.cpp` (NGX bindings), `demodulate.comp.slang:608` (`evalSpecularAlbedoGGXSchlick`), `prepare_ray_reconstruction.comp.slang` (guide post-processing, roughness demodulation), `restir_gi_temporal_reuse.comp.slang:287` (`useDLSSRRCompatibilityMode` 80-px decorrelation), `rtx_options.cpp:309` (RR path-tracer preset), `geometry_resolver.slangh` (RR G-buffer, particle layer, disocclusion sentinel)
- Official Vulkan sample: `github.com/nvpro-samples/vk_denoise_dlssrr`
- Our code: `jlrouzies-fr/RTGL@doom64-rt` — `Source/DLSSRR.cpp`, `Source/Shaders/CmNoisyCompose.comp`, `Source/Denoiser.cpp:258`, `Source/VulkanDevice.cpp:792,916`; `jlrouzies-fr/gzdoom-rt@doom64-rt` — `src/.../rt_main.cpp`
