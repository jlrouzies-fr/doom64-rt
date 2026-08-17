# DLSS Ray Reconstruction — read before touching RR

History is in `docs/rayreconstruction/`. **Don't open it unless this file sends you.**

**State (2026-08-17, final): RR's three visual artifacts are RESOLVED in play;
the lane's remaining gap is sample hunger, which is not ours to fix.** The user's
ladder verdict: `rr-glow-aslight` fixed the emissive jitter; `rr-local-adapt`
(glow-as-light + global history flushes OFF, tile mask only) fixed the jitter AND
the flashlight switch AND the light squares. That configuration is now the
default (`rt_rr_glowpre 2`, `rt_rr_glowscale 35`, `rt_rr_reset_on_lightcut 0`,
`rt_rr_reset_on_dynlight 0` -- compiled defaults, pins, and `rr-full`). Watch
item: transient lights (explosions, muzzle flashes) lingering as ghosts -- the
global flush existed for those; report if seen. The preset A/B (`rr-preset-def`)
was regenerated on the winning base after its first version was found to carry
the pre-fix config. **The shipping denoiser is NRD/ReLAX (`rt_nrd 1`, 2 spp
advised); A-SVGF is the no-flag default; RR is the experimental lane that
improves with NVIDIA's OTA models.**

**A/B verdict on the first pass (reorder alone): NULL, plus a regression.** With only
`rt_rr_preexposure` (exposure moved after RR, nothing else), the user reported: RR still
noisier than A-SVGF, the stable dark-dot pattern on textures/sprites unchanged, the
pattern still switches when the flashlight toggles — **and a new constant image jitter.**
The jitter was a bug in the reorder itself: `CmRrPostExposure` re-added the screen
emission from a *jittered* render-res buffer with no jitter correction. Pre-reorder, RR
dejittered that content as part of its input; post-RR nothing does. Fixed
unconditionally (same correction as `CmVolumeCompose.comp`).

**Why the reorder alone was never going to be enough — the structural audit.** Comparing
our integration against NVIDIA's RR contract and Duke-RT found four deviations; the
first pass fixed half of one:

1. **Exposure** — reorder landed, but the 1×1 exposure texture was dropped ("null +
   `InPreExposure=1.0` is valid parameterization"). Valid, but wrong for a *neural*
   denoiser: with pre-exposure input the network sees raw radiance whose absolute scale
   swings ~52× with adaptation, and it is not scale-invariant. The old post-exposure
   input was incidentally scale-normalized, so dropping the texture traded one
   contract violation for another. **Now landed: `rt_rr_exptex`** — a 1×1 R32F
   framebuffer written GPU-side by `CmPrepareFinal` thread (0,0), bound as
   `pInExposureTexture`.
2. **Rasterized translucency baked into RR's input.** Every translucent sprite in the
   game (fireballs, flames, plasma, smoke, lens flares) is rasterized into `FINAL`
   *before* RR, while every guide — albedo, normal, depth, MV — describes the opaque
   wall *behind* it: content the network is told is not there, i.e. noise to remove.
   **Now landed: `rt_rr_translayer`** — the world raster pass redirects into an RGBA16F
   layer bound as `pInTransparencyLayer` (NGX composites it after denoise+upscale, the
   SDK's sanctioned route). Additive sprites blend alpha ZERO/ONE so they occlude
   nothing (no dark halos); 'over' sprites accumulate true coverage.
3. **Correlated ReSTIR input** (guide §3.5, `rr-noise-fix-proposals.md` §4). Temporal
   reuse keeps a reservoir winner up to `mcap`=20 frames, so a bad shadowed sample
   persists as a **stable dark dot** — structure a temporal denoiser preserves as
   detail. A-SVGF's spatial atrous blurs these away, which is why it never showed them;
   toggling the flashlight reseeds the reservoirs, which is **exactly the observed
   pattern-switch**. Duke-RT feeds RR plain path tracing with no reuse at all.
   **Now landed: `rt_rr_restir_mcap`** (default 4, −1=off) — caps temporal M on RR
   frames only; A-SVGF frames always use `rt_restir_mcap`.
4. **Fog composited into the input.** Known deviation, deliberately NOT touched: the
   volumetrics were fixed under A-SVGF by a previous session and stay where they are.

**The A/B (rebuilt around the contract):** `.\tools\ab.cmd rr-preexp-probe 2` **first**
(magenta = post-RR pass live; log must show `pInExposureTexture=BOUND`,
`pInTransparencyLayer=BOUND`), then **`rr-full` vs `rr-asvgf`** for the verdict. If
rr-full still loses, `rr-no-translayer` / `rr-no-decorr` / `rr-no-exptex` isolate which
feature carried what, and `rr-legacy` reproduces the pre-redo RR. Judge in play, in
motion: dark dots, flashlight toggle, jitter (must be gone in every arm), fireball/flame
crispness. If the full contract still loses to A-SVGF, the next lever is NRD
(`docs/plan-nrd-denoiser.md`) — not another RR guess.

Also from this session: `rt_rr_preset` (0=Default/4=D/5=E — RR has no J/K), and the
DLSS-RR/DLSS-SR NGX output image is barriered before evaluate (latent cross-frame
hazard).

**Eliminated by measurement (all still valid):** 8 shadow rays (no change); 8 spp (only
~20%, so the residual is *not* Monte Carlo variance); direct reservoir `M` stable in
motion; `InReset` flush on/off identical; disocclusion mask sparse in motion; the
indirect antilag gate (a dead no-op under RR — it reads `framebufDISGradientHistory`,
written only by `Denoise()`, which RR skips); every guide, guide floor, spec hit
distance, blue noise, mip bias and RR preset. Motion vectors and depth are validated by
A-SVGF+DLSS-SR using the same buffers. Render resolution too: DLAA is still unstable in
motion, so it is not spatial reconstruction from a low render res.

A-SVGF's two structural advantages — it accumulates in **linear radiance before
exposure**, and its **spatial atrous erases correlated reservoir noise** — are now both
answered on the RR path (`rt_rr_preexposure`+`rt_rr_exptex`, and `rt_rr_restir_mcap`).
If the full-contract A/B still fails, the documented next step is NRD
(`docs/plan-nrd-denoiser.md`), **not** a new RR guess.

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
- `.\tools\ab.cmd rr-<full|asvgf|legacy|no-translayer|no-decorr|no-exptex> [map]` — the
  input-contract A/B set (cfg arms in `tools/arms/`). **`rr-preexp-probe` first** (magenta
  = post pass live), then `rr-full` vs `rr-asvgf` for the verdict, isolation arms only if
  needed. `rr-preexp-on/off` survive as the reorder-only pair (contract features pinned
  off in both). The ab-rr-*.cmd runners above predate ab.cmd and survive as records.
- Levers: `rt_restir_initial` (launcher now sets **32**) traces no rays and helps both
  denoisers, but is **not yet A/B'd under A-SVGF** — verify before trusting it.
  `rt_spp_direct`/`rt_spp_indirect` [1..8] stay at 1; ~20% at 8 is a poor trade.
