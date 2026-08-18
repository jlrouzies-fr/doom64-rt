# Shadow contact hardening — plan

> Scoped 2026-08-18 from the observation that DLSS-RR draws shadows that are
> **sharp at the contact point and soften with distance from the blocker**,
> while A-SVGF draws them **uniformly soft at every distance**. This doc is
> about closing that gap on the non-RR path. It is independent of
> [`plan-area-lights-mis`](plan-area-lights-mis.md) — no triangle lights, no
> MIS, no light grid — and it benefits A-SVGF and NRD directly.

## The physics, in one line

For a spherical light of radius `R`, a blocker at distance `d_b` from the
receiver along the shadow ray, and the light at distance `d_l`:

```
penumbra half-width  w  ≈  R * d_b / (d_l - d_b)
```

`d_b → 0` (blocker touching the receiver) ⇒ `w → 0`, a hard contact shadow.
`d_b → d_l` ⇒ `w` blows up, a wide soft shadow. **`d_b` is the only term the
renderer does not have.**

## Ground truth (verified in code, 2026-08-18)

1. **The penumbra is already physically correct in the raw signal — but only at
   `rt_shadow_samples > 1`.** `RaygenCommon.h:923-941` averages visibility over
   N independently sampled points on the *same* chosen light. At the default
   **N = 1** visibility is a binary 0/1 multiply (the shader says so at
   `:905-908`), so **every bit of softness on screen is denoiser blur** — which
   is exactly why it is uniform. `rt_shadow_samples` is `RT_CVAR(...,1,...)` at
   `rt_cvars.inc:1858`, range [1..8], and is **not pinned** anywhere in
   `tools/d64rt-pins.cfg`.
2. **The blocker distance is never recovered.** `traceShadowRay`
   (`RaygenCommon.h:378-387`) traces with `gl_RayFlagsSkipClosestHitShaderEXT`
   and returns `g_payloadShadow.isShadowed == 1` — a bool. `ShPayloadShadow`
   carries `isShadowed` and nothing else (`RtMissShadowCheck.rmiss:26-30`).
3. **The traversal cost is probably already paid.** `getAdditionalRayFlags()`
   (`RaygenCommon.h:197-204`) adds only back-face culling — there is **no
   `gl_RayFlagsTerminateOnFirstHitEXT`**. The ray is nominally traversed to the
   nearest hit and only the closest-hit *shader* is skipped. Drivers may still
   early-out on that pattern, so treat "free" as a hypothesis to measure, not a
   given.
4. **A-SVGF's kernel width cannot know about a penumbra.**
   `CmSVGFAtrous.comp:61` — `STEP_SIZE = 1 << atrousIteration`, a pure function
   of the iteration index over 4 iterations. The only per-pixel modulation is
   depth `w_z`, normal `w_n`, luminance `w_l` (diffuse only) and roughness `w_r`
   (specular only) at `:196-200`. Nothing says "1 px here, 40 px there".
5. **`ViewDirection.w` is not the distance we need.** It carries `distToLight`,
   written by `RtRaygenDirect` (`RtRaygenDirect.rgen:56-76`), consumed by
   A-SVGF for specular virtual-position reprojection
   (`CmSVGFTemporalAccumulation.comp:216-223`) and handed to DLSS-RR as
   `pInSpecularHitDistance` (`CmNoisyCompose.comp:263-285`). That is `d_l`.
   We are missing `d_b`.
6. **NRD SIGMA is already instantiated and unfed.** `NrdDenoiser.cpp:87`
   creates `nrd::Denoiser::SIGMA_SHADOW` — the comment at `:82` says *"SIGMA
   rides along for a future shadow lane"* — and `:369` logs it alive. The
   resource binding block at `:546-560` sets `IN_MV`, `IN_VIEWZ`,
   `IN_NORMAL_ROUGHNESS`, `IN_BASECOLOR_METALNESS`, `IN_DIFF_RADIANCE_HITDIST`,
   `IN_SPEC_RADIANCE_HITDIST` and the two outputs. **No `IN_PENUMBRA`, no
   `OUT_SHADOW_TRANSLUCENCY`.** SIGMA is the penumbra-aware shadow denoiser and
   nothing reaches it.
7. **RR gets it by learned prior, not by measurement.** RR receives no blocker
   distance either — `pInSpecularHitDistance` is `d_l` per (5). It reconstructs
   hardening from the noisy input's local structure because it was trained on
   ground-truth area-light sequences.

## Phases

### Phase 0 — establish that the denoiser is the culprit. Free, no code.

Pin `rt_shadow_samples 4` and look, in motion, with `rt_debug_visibility 1`
(`RtRaygenDirect.rgen:87-100`) — that view shows the raw shadow-ray result with
no denoiser in it at all.

- If the **debug view** hardens at contact and the **final image** stays
  uniformly soft ⇒ the raw signal is right, the filter destroys it, and phases
  1-3 are justified.
- If the **debug view** is also uniform ⇒ the problem is upstream (light radii,
  see the landmines) and phases 1-3 will not fix it.

This is the gate. Do not fund anything below until it has run. **Cost:
minutes.** Worth running on its own merits too — `rt_shadow_samples` is the
largest free lever left in the renderer and has never been A/B'd.

### Phase 1 — recover the blocker distance. ~0.5 session.

- Add `float hitDist` to `ShPayloadShadow` (declared in the generated header —
  **regenerate and clear stale objects**, see landmines).
- Give the shadow SBT a minimal closest-hit shader that writes `gl_HitTEXT`,
  and drop `gl_RayFlagsSkipClosestHitShaderEXT` from `traceShadowRay`. Set
  `hitDist = MAX_RAY_LENGTH` before the trace; `RtMissShadowCheck.rmiss` leaves
  it alone on a miss.
- Alpha-tested geometry already runs any-hit (`RtAlphaTest.rahit`), so grates
  and fences keep working unchanged.
- **Measure the frame cost immediately** against ground truth (3). If a
  closest-hit invocation on shadowed pixels costs more than a few percent, fall
  back to an any-hit that records `min(gl_HitTEXT)` and accept the extra
  any-hit traffic instead.

Ship gate: no visual change at all. `hitDist` is written and read by nothing.

### Phase 2 — compute and carry the penumbra. ~1 session.

- In `traceVisibility` (`RaygenCommon.h:427-436`) return the blocker distance
  alongside visibility. Under the N-tap loop at `:925-941`, accumulate the
  **mean over taps that were actually blocked** — not over all taps, or a
  half-lit pixel reports a blocker at half its true distance.
- Compute `w = R * d_b / max(eps, d_l - d_b)` where `R` is the selected light's
  radius, from `decodeAsSphereLight` (`Light.h:66-78`). `d_l` is already in
  hand. Directional lights use `angularRadius` instead and want
  `w ≈ tan(angularRadius) * d_b`.
- New framebuffer `"Penumbra" : (TYPE_FLOAT16, COMPONENT_R, 0)` in
  `Generated/GenerateShaderCommon.py`, alongside `"SpecularHitDistance"` at
  `:1706`. Written by `RtRaygenDirect` in **checkerboard space**, resolved in
  `CmNoisyCompose` exactly like `SpecularHitDistance` at
  `CmNoisyCompose.comp:263-285`.
- Debug view `rt_debug_penumbra 1`, following the `debugVisibility` pattern.
  Without it the next phase is untestable.

Ship gate: still no visual change. The buffer exists, is populated, and the
debug view shows a plausible field — narrow at contacts, wide under high
blockers.

### Phase 3a — adaptive A-SVGF kernel. ~1-2 sessions. **The cheap route.**

Feed the penumbra into `CmSVGFAtrous.comp` as a **weight term, not as a
per-pixel `STEP_SIZE`.** Modulating the stride directly breaks the à-trous
wavelet's frequency separation and will alias. The safe form is an extra
falloff on `wBase` keyed on the tap's screen-space offset against the
penumbra's screen-space width, so a 1 px penumbra rejects taps that a fixed
kernel would have accepted. Screen-space width needs `viewZ` and the
projection, both already available in the pass.

Also feed `CmSVGFTemporalAccumulation.comp`: a narrow-penumbra pixel should
accumulate a *shorter* history, or contact shadows will lag their blocker.

**Risk:** this is hand-rolling what SIGMA does, inside a filter whose weights
are already delicate. Budget an A/B arm and expect two rounds.

### Phase 3b — NRD SIGMA. ~3-4 sessions. **The correct route, with a catch.**

SIGMA denoises a **shadow mask** (0..1 visibility), not radiance. Today
visibility is multiplied into the direct radiance inside
`processDirectIllumination` before anything is written out. Using SIGMA
therefore forces a **demodulation restructure**: visibility has to leave
`UnfilteredDirect`, travel in its own buffer, be denoised by SIGMA, and be
multiplied back afterwards. That restructure — not the SIGMA wiring — is the
cost.

- Pack with `NRD_FrontEnd_PackShadow(viewZ, hitDist, tanOfLightAngularRadius)`.
  ReSTIR selects a different light per pixel; SIGMA is designed for exactly
  that and needs no special handling, but the recombination must use the *same*
  light the reservoir selected.
- Bind `IN_PENUMBRA` and `OUT_SHADOW_TRANSLUCENCY` in the block at
  `NrdDenoiser.cpp:546-560`.
- **This only helps the NRD lane** unless A-SVGF is also rewired to consume the
  SIGMA output — which is most of phase 3a again. Choose one route, not both.

### Phase 4 — RR. Nothing to do.

RR already produces the behaviour by learned prior (ground truth 7). If RR
becomes the shipping denoiser, phases 3a/3b are unnecessary *for RR* — but
phases 1-2 remain the right thing to have if NGX ever exposes a shadow guide,
and they cost nothing at runtime when unused.

## Landmines

- **Correct shadows expose the light radii as art parameters.** Today the
  radius cvars (`rt_ceiling_edge_radius 0.35`, `rt_solo_lamp_radius 0.06`, the
  `rt_wall_strip_*` set) are tuned against a filter that flattens their effect.
  With contact hardening live, a 0.35 m source at 3 m draws a *visibly* wide
  penumbra and those numbers stop being free. Expect a re-tune pass, and read
  `rt-lighting-practices.md` §34 first — it already measured that compact
  sources are what make grating shadows legible.
- **Spot lights hardcode `l.radius = 0.05`** (`Light.h:112`), ignoring the
  authored radius, which is used only for the `intensity/(πr²)` normalisation
  in `EncodeAsSpotLight`. Every spot in the game will draw a near-hard shadow
  regardless of authoring, and contact hardening is what makes that visible.
  Route the radius through `globalUniform` in phase 2, or accept the artefact
  knowingly.
- **Generated-header regen leaves stale objects** and the new uniform/payload
  fields then silently read **ZERO** — the failure looks like "the feature does
  nothing". `build-rtgl` clears objects now; verify it did.
- **New tuning cvars must be `RT_CVAR_NOARCH`.** A plain `RT_CVAR` is
  `CVAR_ARCHIVE` and persists forever; this project has lost days to exactly
  that.
- **Both A/B arms must set every value explicitly**, `rt_shadow_samples`
  included — an arm that leaves it alone inherits whichever arm ran last.
- **Stills cannot judge this.** A settled screenshot reads "no cost" for
  anything that boils. Every verdict here is a motion verdict.
- **`CmNrdPack.comp:128` hardcodes diffuse `hitDist = 0`** for the NRD lane.
  ReLAX and ReBLUR both drive their blur radius from `hitDist`, so the NRD
  diffuse channel is currently running blind — plausibly a contributor to "NRD
  is noisier than A-SVGF at 1 spp". A separate bug from this plan, but worth
  fixing before or alongside phase 3b.

## Arms

| arm | what it pins |
|---|---|
| `shadow-n1` | `rt_shadow_samples 1`, feature off — the control |
| `shadow-n4` | `rt_shadow_samples 4`, feature off — the phase 0 gate |
| `contact-off` | `rt_shadow_samples 4`, `rt_contact_harden 0` |
| `contact-on` | `rt_shadow_samples 4`, `rt_contact_harden 1` |
| `contact-debug` | `rt_debug_penumbra 1` — the field, not the image |

## What this does not fix

- Indirect/GI shadowing. `wDiffIndir = wBase` at `CmSVGFAtrous.comp:198` — the
  indirect lane has no luminance or variance rejection at all, and this plan
  does not touch it.
- Shadows from emissive geometry, which is not in `lightSources[]` and casts
  none. That is [`plan-area-lights-mis`](plan-area-lights-mis.md).
- Anything at `rt_shadow_samples 1`. The penumbra has to exist in the signal
  before a filter can be taught to preserve it.

**Total: ~2.5 sessions via 3a, ~5 via 3b — and phase 0 may show the honest
answer is "raise `rt_shadow_samples` and stop".** Phases 0-2 are safe stopping
points; each is observably a no-op on its own.
