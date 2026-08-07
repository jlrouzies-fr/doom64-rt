# DLSS Ray Reconstruction — read before touching RR

History is in `docs/rayreconstruction/`. **Don't open it unless this file sends you.**

**State (2026-08-07): the launcher defaults to A-SVGF (`rt_rayreconstr 0`), not RR.**
RR works and is *correctly configured* — identical jitter, MV scale and NGX feature flags
to DLSS-SR, which is stable on the same buffers. It is simply less stable in **motion** on
this content. Set `+rt_rayreconstr 1` to compare.

**Don't reopen that without new evidence.** Eliminated by measurement, not argument: 8
shadow rays (no change); 8 spp (only ~20%, so the residual is *not* Monte Carlo variance);
direct reservoir `M` stable in motion; `InReset` flush on/off identical; disocclusion mask
sparse in motion; the indirect antilag gate (a dead no-op under RR — it reads
`framebufDISGradientHistory`, written only by `Denoise()`, which RR skips); auto-exposure
locked; every guide, guide floor, spec hit distance, blue noise, mip bias and RR preset.
Motion vectors and depth are validated by A-SVGF+DLSS-SR using the same buffers.

A-SVGF's advantage looks structural: it accumulates in **linear radiance before exposure**
and applies a variance-guided **spatial** filter, which suits sparse 1-spp interiors with
many small dynamic lights. RR accumulates after exposure is baked in and leans on temporal
reconstruction, which motion weakens.

**Untested when work stopped:** render resolution (`ab-rr-res.cmd`). At 1280×720 Balanced,
RR reconstructs from ~742×418, and "detail breaks in motion, stabilises when still" is the
signature of spatial reconstruction rather than sampling — which fits the spp/shadow-ray
nulls. Every earlier resolution test is **void**; they ran during the `rt_restir_tjitter`
regression.

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
- `ab-rr-res.cmd <dlaa|quality|balanced>` — render resolution.
- Levers: `rt_restir_initial` (launcher now sets **32**) traces no rays and helps both
  denoisers, but is **not yet A/B'd under A-SVGF** — verify before trusting it.
  `rt_spp_direct`/`rt_spp_indirect` [1..8] stay at 1; ~20% at 8 is a poor trade.
