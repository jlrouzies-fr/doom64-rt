# DLSS Ray Reconstruction — read before touching RR

History is in `docs/rayreconstruction/`. **Don't open it unless this file sends you.**

**State (2026-08-07):** RR works, on by default (`rt_rayreconstr 1` + `rt_upscale_dlss 2`).
`rt_rayreconstr 0` → A-SVGF fallback (faster, no RR).

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
- Quality: `rt_spp_direct`/`rt_spp_indirect` [1..8] (default 1, linear cost);
  `rt_restir_initial` [1..32] traces no rays — try it first.
