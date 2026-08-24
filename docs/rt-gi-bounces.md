# GI bounce depth — `rt_gi_bounces`

Report (2026-08-23): *"the game lights don't seem to bounce — all lights, e.g. the
A035/A036 light poles."*

What the source says: the ray-traced GI path length was **hardcoded at 2 bounces,
manually unrolled**, with no cvar and no working API parameter — and that second
bounce was, in the shipped build, both **unlit by any analytic light** under the
live config and **energetically wrong by ~2π**. What reached the screen as
"bounce" was one bounce plus a noisy, over-saturated ghost of a second.

This page is the finding, the fix, and the ladder that judges it. The plan it came
from is in the session log; the code is in `deps/RTGL/Source/Shaders/RtRaygenIndirect.inl`.

## 1. The three findings

### 1a. Depth was 2, unrolled, and its API gate was dead

`RtRaygenIndirect.inl` had `processIndirect()` (bounce 1) calling
`processSecondDiffuseBounce()` (bounce 2, terminal). No loop, no depth parameter.
The gate that was meant to consume `enableSecondBounceForIndirect` sat commented
out:

```glsl
// TODO: investigate why uncommenting this makes diffuse very red
// if( globalUniform.indirSecondBounce != 0 )
{ ... second bounce ... }
```

So the block always ran, the uniform was uploaded and read by nothing, and
nothing could ask for a third bounce. `rt_spp_indirect` is **paths per pixel**,
not path length; `rt_reflrefr_depth` is primary reflect/refract recursion, a
different thing entirely.

### 1b. `rt_shadowrays` decides which bounce vertices may sample lights at all

`RaygenCommon.h` `isDirectIlluminationValid(bounceIndex)` is
`bounceIndex < maxBounceShadowsLights || maxBounceShadowsLights == 0`, and the
shadow ray is gated on the same predicate. `rt_shadowrays` → `maxBounceShadows`
→ that uniform. Bounce indices: `0` primary/volumetric, `1..N` the indirect path.

| `rt_shadowrays` | vertex 1 | vertex 2 |
|---|---|---|
| 1 | **no analytic light at all** | none |
| 2 | lit + shadowed | **none — emissives and sky only** |
| 3+ | lit + shadowed | lit + shadowed |

The live ini held **2**, so vertex 2 collected emissive surfaces and nothing else.
`rt_shadowrays` is `CVAR_ARCHIVE` and deliberately unpinned
(`tools/d64rt-pins.cfg`) — the quality one-shot keeps a value the player touched,
and a startup re-apply of it once cost a day (`rt_quality.cpp`). **Nothing here
writes it.** `0` is not a low value: it means "light every vertex, cast no shadow
rays", and is preserved, never floored.

### 1c. The second bounce was over-weighted by ~2π — the "very red"

`BRDF.h` `evalBRDFLambertian(a) = a/π`. `Random.h` `sampleOrientedHemisphere`
returns `oneOverPdf = π/z`. A cosine-sampled Lambertian bounce therefore has
throughput `(1/π) · z · (π/z) = 1` exactly, albedo applied separately. Bounce 1
gets this right — its pdf leaves as the reservoir weight and `shade()` applies
`oneOverPdf · nl · L · (1/π) = L`. The second bounce applied **only** `* oneOverPdf`:

```glsl
return ( emis + diffuse ) * hitSurf.albedo * oneOverPdf;   // L2 * pi/z, should be L2
```

Under the cosine density `E[π/z] = 2π ≈ 6.3`, with a heavy `1/z` tail. So:

- bounce 2 was ~6× too bright and, being multiplied by albedo, ~6× too saturated
  — on a red-brown Doom wall, *"diffuse very red"*;
- the `1/z` tail is a firefly source;
- `targetPdfForIndirectSample()` is the sample's luminance, so the overweighted
  samples **won** the RIS reservoir and temporal reuse held them for up to
  `rt_restir_mcap` frames. Stable bright dots, not transient ones.

Uncommenting the old gate could only have *disabled* the block (its flag was
hardcoded true), which makes GI darker, not redder — so the historical "very red"
was almost certainly a stale/misaligned uniform slot, which
`tools/check_uniform_layout.py` and the `ShaderCommonC.stamp` object wipe now
guard against. The over-weighting was real and separate, and is what the legacy
switch below preserves.

## 2. What changed

| where | what |
|---|---|
| `RtRaygenIndirect.inl` | `processSecondDiffuseBounce` is gone; `processIndirect` loops `b = 2..indirectBounces`, folding each deeper vertex into **vertex 1's radiance** with its own throughput. The stored `SampleIndirect` (position, normal, reservoir weight) is still the first hit — the spatial-reuse Jacobian and `shade()` reconnect to that vertex, so it must never move. |
| same | `bounceSeed()` — `b ≤ 2` keeps the stock seed (depth 2 is bit-identical by construction); deeper vertices get the "virtual frame" seed the multi-sample loop already uses, because `RANDOM_SALT_DIFF_BOUNCE` has one free index and `processDirectIllumination` draws light-selection numbers from the same salts at every vertex. |
| same, FINAL stage | `rt_debug_restir_m 2` paints the **indirect** reservoir's `M` (the stock `1` only ever showed the direct one). |
| `GenerateShaderCommon.py` | `indirSecondBounce` → `indirectBounces` (same slot); `_padf2` → `indirectLegacyWeight` (float→uint, same 4 bytes). Zero std140 delta. |
| `RTGL1.h`, `DrawFrameInfo.h`, `VulkanDevice.cpp` | `enableSecondBounceForIndirect` → `indirectBounces` (clamped **[1,4]** — `emissionMapBoost` is 200 here and `emis·200·albedoᵏ` compounding over depth is a firefly risk; widen after measurement) + `indirectLegacyBounceWeight`. `debugRestirM` is a uint now. |
| `VulkanDevice_Dev.cpp` | "Shadow rays max depth" slider 0..8 (the old 0..2 encoded "only three bounce indices exist"); "Indirect bounces" slider; legacy checkbox. |
| `rt_cvars.inc` | `rt_gi_bounces` (2) and `rt_gi_bounce_legacy` (1) — **archived**, and in **Options → Quality** ("Bounces per path", "Bounce energy") in both menus, like `rt_shadowrays` beside them. `rt_gi_bounce_shadows` (1) stays `RT_CVAR_NOARCH`: it is the ladder's control, not a setting. |
| `rt_main.cpp` | passes them; when `rt_gi_bounces > 2` and `rt_gi_bounce_shadows`, the **param** `maxBounceShadows` is floored to depth+1 for the frame. No-op at depth 2. |

**Shipped behaviour is unchanged**: depth 2, legacy weight on, floor inert.

## 3. The ladder — `.\tools\ab.cmd <arm> 03`

Arms are cfgs in `tools/arms/gi-*.cfg`. Each pins every quality cvar at the live
ini value and moves **one** thing. Judge on the unfiltered signal —
`rt_debug_show 16` (raw indirect) and `128` (only indirect diffuse) — with
exposure pinned, which the arms do.

| order | arm | what it isolates |
|---|---|---|
| 0 | `gi-shadow2` / `gi-shadow3` / **`gi-shadow4`** | zero shader involvement: vertex 2 unlit → lit. **`shadow4` is the control** — only indices 0/1/2 exist, so it must be pixel-identical to `shadow3`; if not, the ladder is not reaching the shader. |
| 1 | `gi-depth1` | liveness of the new plumbing: removing the (6×-overweighted) second bounce must be *obvious* on layer 16. |
| 2 | `gi-fix` | the energy fix at depth 2. Expect GI-lit areas **dimmer and less saturated**, and the stable bright dots gone. If too dark for the art, the lever is `rt_emis_mapboost` / light intensities — never the `π/z`. |
| 3 | `gi-fix3` / `gi-fix4` vs `gi-fix` | real depth, only meaningful with the fix on. Mean luminance of layer 128 must rise **monotonically with shrinking increments** (`1 + a + a² + a³`, `a ≈ 0.2–0.4`). |
| 3′ | `gi-fix3-unlit` | the "deep but unlit" control — same depth 3, shadow floor off. `fix3 − fix3-unlit` is what lighting the deeper vertex is worth. |
| V6 | `gi-restirm` | `rt_debug_restir_m 2`, then `rt_gi_bounces 4` in the console: the green ramp must not move. If it darkens, a different reconnection vertex is being stored — stop. |

**Read `gi-shadow3` through the confound:** it lights vertex 2 for the first time,
and vertex 2 still carries the 2π overweight there. It may look too bright or too
red. That is finding 1c becoming visible, not evidence against lighting vertex 2 —
judge *where* light reaches; `gi-fix` is the arm for *how much*.

Cost: with `LIGHT_GRID_ENABLED (0)` every bounce vertex runs a full
`rt_restir_initial`-candidate RIS pass over the whole light array, so an extra
bounce costs ~1 bounce ray + 1 shadow ray + 32 RIS evaluations per indirect sample
per pixel, and the RIS ALU dominates on dense-emitter maps. Take `vid_fps` in a
stripe-bulb room *and* a sparse one; one map's number does not generalise.

## 4. Reading the bias check

| depth 2 → 3 → 4 on layer 128 | means |
|---|---|
| depth 3 adds as much as depth 2 did | `throughput` is not accumulating (`*= hit.albedo` missing) |
| super-linear, or fireflies | the `π/z` is still in the loop / legacy stuck on |
| depth 3 adds ~nothing | the shadow floor is not firing — check `rt_gi_bounce_shadows` and that `rt_shadowrays` is not 0 |

## 5. Proving it is live (the plumbing traps this project has paid for)

- **The printed proof is one line in `rt-console.log`:**
  `ReSTIR: … giBounces=N (stock 2), giLegacyWeight=L (stock 1), maxBounceShadows=S (vertex i lit iff i < this)`.
  It is the value *read back from the uniform*, not the cvar, and it re-prints
  whenever depth or shadow depth changes. An arm that shows `giBounces=2` did
  not apply. `gi-fix3` must show `giBounces=3 … maxBounceShadows=4`.
- `tools/build-rtgl.cmd` runs `check_uniform_layout.py`; a same-slot rename and a
  float→uint pad are invisible to it. If it complains, the scalar run moved.
- The build log must print **`=== ShaderCommonC.h changed -- clearing objects ===`**
  on a header-changing build. Its absence is the stale-objects failure.
- `grep -a indirectBounces …/rt/shaders/RtRaygenIndirectInit.rgen.spv` proves
  regen + recompile + staging — **not use**. `indirSecondBounce` grepped in the
  old `.spv` too, and nothing read it. Proof of use is `gi-depth1`.
- A cross-build PNG diff can never show depth-2 identity: `frameId` and the
  reservoir/denoiser history differ between launches. Identity is by
  construction (diff review at `b == 2`: same salt, same seed, `1·w·L == L·w`,
  same mip bias) plus a statistical no-shift on layer 128.

## 6. Still to do — user-gated

- Stage 4: flip `rt_gi_bounce_legacy` default to 0 **after** `gi-fix` is judged.
- Stage 5, remaining part: add `{ "rt_gi_bounces", 3, 2, 2, 1 }` to the
  `rt_quality.cpp` table — **only after Stage 4**, because with the legacy weight
  on, Ultra at depth 3 blows out. Ultra's `rt_shadowrays 4` is already the
  `depth+1` that depth 3 needs; do not lower any existing preset value. The
  archive promotion and the Quality-menu rows are done (2026-08-24). Shipped
  default stays 2.

## 7. Not this page

The A035/A036 poles were suspected of being dim. They are not: GLDEFS gives them
a ~64/~87 dynlight (clamp-then-roll-off makes it ∝ 1/hi²) **plus** a dedicated
analytic sphere at `rt_pole_lamp_intensity` 300 from `RT_UploadHangingTechLamps`.
The dynlight roll-off (`rt_dynlight_rsoft`) is global to every `FDynamicLight`
and was left alone on purpose — AGENTS.md pitfall 28c.
