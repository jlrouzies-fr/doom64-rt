# Area lights + MIS — the renderer-baseline initiative

> Scoped 2026-08-17 after the RR post-mortem named the missed bound: RR's
> training pipelines have full BRDF/light MIS and area-light transport; this
> renderer has neither. Filed as its OWN initiative -- it benefits every
> denoiser lane (glossy direct response, lower variance, likely shaves RR's
> 3-spp bill) -- and explicitly NOT as an RR patch. A-SVGF's 1-spp performance
> on today's baseline proves the baseline is serviceable without it.

## Ground truth (verified in code, 2026-08-17)

**Triangle lights in this RTGL1 fork are a half-removed upstream feature.
`TRIANGLE_LIGHTS: 0` cannot simply be flipped:**

- `Source/Shaders/Light.h` behind the flag contains a DELIBERATE
  `#error Refine decoding, as it's obsolete for TriangleLight` -- the upstream
  author abandoned the path when `ShLightEncoded` was compacted. With the flag
  on, every shader including Light.h fails to compile; the game then runs
  against missing/stale SPIR-V and crashes (user-hit).
- The C++ encoder (`EncodeAsTriangleLight`) writes `data_0/1/2` fields from the
  OLD struct layout and has `assert(!transform) // not implemented`.
- Even with the flag off, uploading `RgLightPolygonalEXT` used to hit a FATAL
  `debug::Error` -- downgraded to a Warning (light ignored) on 2026-08-17.
- Emissive geometry emits NOTHING in the light transport today: analytic
  engine-placed lights + the screen-emission glow overlay stand in for it.
  Lights are not in the acceleration structure, so BRDF-sampled rays cannot
  hit them -- full MIS is meaningless until that changes.

## Phases (each independently shippable)

1. **Triangle light re-encode/decode.** Design a packing for 3 positions +
   color + normal in (or beside) today's compact `ShLightEncoded` -- likely a
   side buffer indexed from the encoded entry, since 9 floats do not fit.
   Rewrite `EncodeAsTriangleLight` and `decodeAsTriangleLight` (delete the
   #error), validate `sampleTriangleLight` (solid-angle sampling) and
   `getTriangleLightWeight`. ReSTIR picks them up automatically once they are
   in `lightSources`. ~1-2 sessions.
2. **Engine emission: gzdoom -> RgLightPolygonalEXT.** Walk map surfaces with
   emissive materials, tessellate, upload per frame with intensity from the
   emission calibration. THE HARD PART: stripe-bulb rooms mean hundreds to
   thousands of triangle lights -- the candidate-count pressure the user
   already measured (46 needed at ~dozens of lights) gets much worse, so this
   phase almost certainly requires re-enabling and fixing the LIGHT GRID
   (`LIGHT_GRID_ENABLED 0`, also unfinished upstream). ~2-4 sessions.
3. **Hittable lights + MIS.** Emissive triangles in the BLAS with a light
   index; closest-hit returns emission weighted by the MIS heuristic against
   NEE/ReSTIR's pdf; balance-heuristic weights on both techniques. This is
   the piece that moves our noise statistics toward RR's training
   distribution. ~2-3 sessions.
4. **Re-baseline everything.** All three denoiser lanes re-A/B'd (the glow
   overlay's role shrinks where real area lights exist -- emission calibration
   redone), RR's spp bill re-measured.

**Total: ~6-10 sessions, renderer-wide blast radius.** Do not start casually;
phase 1 alone is safe and self-contained if we ever want to dip a toe.
