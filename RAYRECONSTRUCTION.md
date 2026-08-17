# DLSS Ray Reconstruction — read before touching RR

History is in `docs/rayreconstruction/`. **Don't open it unless this file sends you.**

**State (2026-08-17): REOPENED with new evidence, and the fix is implemented, awaiting
the in-game A/B.** The launcher still defaults to A-SVGF (`rt_rayreconstr 0`) until the
verdict is in. The closing paragraph used to say "no remaining hypothesis" — that was
wrong, and the doc itself named the hypothesis it never tested: *"RR accumulates after
exposure is baked in."* `rr-noise-fix-proposals.md` §3.4 (reorder exposure after RR) sat
at **Deferred** the whole time the investigation was called closed.

**The new evidence (what reopened it):**
- NVIDIA's RR Integration Guide §3.7 (local copy, `deps/DLSS/doc/`): exposure is **not
  supported** by DLSS-RR — the model wants linear pre-exposure radiance. We fed it
  post-exposure color and declared `InPreExposure = 1.0`, a false statement to NGX every
  frame. "Auto-exposure locked" A/Bs below couldn't catch this: locking the *range* still
  bakes a wrong constant in; the mismatch is *structural*, worst when adaptation moves.
- `sourcecode/Duke-RT` (Raze fork, NRI backend, same DLSS-RR SDK) ships RR as its
  *recommended* path and feeds it pre-exposure radiance, applying exposure only after.

**The fix (2026-08-17): `rt_rr_preexposure` (default ON, NOARCH).** CmPrepareFinal skips
its EV100 multiply + screen-emissive add under RR; a new pass (`CmRrPostExposure.comp`)
reapplies both on RR's upscaled output. Host-gated to frames where RR actually runs —
A-SVGF, DLSS-SR and FSR2 paths are byte-identical. A/B:
`.\tools\ab.cmd rr-preexp-probe 2` **first** (magenta = the pass is live), then
`rr-preexp-on` vs `rr-preexp-off`. Judge in play, walking between bright and dark rooms —
the prediction is instability correlated with *adaptation*, not camera motion as such.
Also new: `rt_rr_preset` (0=Default/4=D/5=E — RR has no J/K), and the DLSS-RR/DLSS-SR
NGX output image is now barriered before evaluate (was a latent cross-frame hazard).

**Eliminated by measurement (all still valid):** 8 shadow rays (no change); 8 spp (only
~20%, so the residual is *not* Monte Carlo variance); direct reservoir `M` stable in
motion; `InReset` flush on/off identical; disocclusion mask sparse in motion; the
indirect antilag gate (a dead no-op under RR — it reads `framebufDISGradientHistory`,
written only by `Denoise()`, which RR skips); every guide, guide floor, spec hit
distance, blue noise, mip bias and RR preset. Motion vectors and depth are validated by
A-SVGF+DLSS-SR using the same buffers. Render resolution too: DLAA is still unstable in
motion, so it is not spatial reconstruction from a low render res.

A-SVGF's structural advantage — it accumulates in **linear radiance before exposure** —
is exactly what `rt_rr_preexposure` gives RR. If the A/B still fails, the next documented
lever is ReSTIR decorrelation (`rr-noise-fix-proposals.md` §4: RR's guide §3.5 requires
minimally-correlated samples; our temporal/spatial reuse violates it), **not** a new
guess.

**Every fault that cost this project days was an invisible setting, never a renderer bug:**
RR compiled out of the DLL (CMake `ENV{}` vs `-D`); a Dev-UI sticky override in
`rt/devmode_settings.json` beating the cvar; a stale `rt_upscale_fsr2 2` clobbering the DLSS
upscaler (RR only runs under DLSS); diagnostics muted at three layers hiding all of it; and
`rt_restir_tjitter 0` left from an A/B — stock is 2, and at 0 every pixel reprojects to the
same previous pixel, so reuse correlates and RR smears it into worms A-SVGF hides. That one
looked exactly like an RR defect for a full day. It wasn't.

## Rules

- **Check the log before believing any observation.** Each launch prints `Denoiser path:`,
  `RR guides:`, `ReSTIR uniforms:` (real shader values vs stock) to `rt-console.log`.
- **Tuning knobs use `RT_CVAR_NOARCH`.** Plain `RT_CVAR` is `CVAR_ARCHIVE` and persists
  forever — never add a diagnostic knob as `RT_CVAR`.
- **Both A/B arms must set every value explicitly.** An arm that leaves cvars alone isn't a
  control; it copies whichever arm ran last.
- **"No difference" means check the arm, not conclude.** Three nulls here tested nothing.
- **A bisect landing on the commit that *introduced* a knob is probably finding that knob's
  stuck value.** This happened.
- **Ask the user for visual verdicts** — screenshot analysis gave two confident wrong
  answers, and scalar noise metrics scored RR and A-SVGF equal.

## Tools (`tools/`) and levers

- `launch-retribution-rt.cmd <map> [debug] [-- +cvar val ...]` — `--` args override defaults.
- `ab-restir-stock.cmd <stock|broken>` — worked example of a correct A/B.
- `build-rtgl-variant.cmd <commit> <name>` + `ab-rtgl-baseline.cmd <name>` — swap a historical
  RTGL runtime (DLL **and** its SPIR-V together; uniform layout changes, never mix).
- `ab-rr-quality.cmd <stock|free|shadow|max>` — input-quality cost/benefit ladder.
- `ab-rr-res.cmd <dlaa|quality|balanced>` — render resolution (eliminated: DLAA still bad).
- `.\tools\ab.cmd rr-preexp-<probe|on|off> [map]` — the pre-exposure reorder A/B
  (cfg arms in `tools/arms/`, the current style; the ab-rr-*.cmd runners above predate
  ab.cmd and survive as records). **Probe first.**
- Levers: `rt_restir_initial` (launcher now sets **32**) traces no rays and helps both
  denoisers, but is **not yet A/B'd under A-SVGF** — verify before trusting it.
  `rt_spp_direct`/`rt_spp_indirect` [1..8] stay at 1; ~20% at 8 is a poor trade.
