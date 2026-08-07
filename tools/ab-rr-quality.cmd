@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Cost/benefit ladder for RR input quality, cheapest first.
rem
rem Rationale. Everything that could be a BUG has been eliminated by measurement:
rem   direct reservoir M stable in motion   -> light selection accumulates fine
rem   8 spp buys only ~20%                  -> not Monte Carlo variance
rem   InReset flush on/off identical        -> history is not being flushed
rem   disocclusion mask sparse in motion    -> not per-tile invalidation
rem   indirect antilag gate on/off identical-> that gate is a dead no-op under RR
rem   exposure locked: unchanged            -> not auto-exposure drift
rem   guides/spec-hit-dist/blue noise/preset-> all no effect
rem   motion vectors + depth                -> validated by A-SVGF+DLSS-SR using
rem                                            the same buffers and being stable
rem
rem So this is not a defect to find; it is RR being asked to reconstruct from a
rem sparse 1-spp signal. A-SVGF compensates with a heavy variance-guided SPATIAL
rem filter; RR leans on temporal, which motion weakens. The lever left is to hand
rem RR a better-converged frame.
rem
rem ARMS (each prints its values as "ReSTIR uniforms:" in rt-console.log)
rem   stock  - defaults, for reference
rem   free   - NO extra rays at all. More RIS candidates, more spatial reuse taps,
rem            a wider radius and a longer temporal history. Pure image reads.
rem   shadow - free + 4 shadow rays. Direct lighting multiplies by ONE binary
rem            traceVisibility(), and that 0/1 term dominates 1-spp direct
rem            variance; averaging 4 points turns it into a soft fraction.
rem            NOTE: rt_shadow_samples was previously "tested" while stuck at 3
rem            during the rt_restir_tjitter worm regression, so that null is void.
rem   max    - shadow + 2 spp on both terms. Most expensive; the reference point.
rem
rem Judge in motion. Also watch vid_fps -- the point is cost vs benefit, and
rem "free" should cost almost nothing.
rem
rem Usage: ab-rr-quality.cmd <stock|free|shadow|max> [1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=free"
if "%MAP%"==""  set "MAP=2"

set "FREE=+rt_restir_initial 32 +rt_restir_spatial 16 +rt_restir_spatial_radius 40 +rt_restir_mcap 40"

if /i "%WHICH%"=="stock" (
  set "ARGS=+rt_restir_initial 8 +rt_restir_spatial 8 +rt_restir_spatial_radius 30 +rt_restir_mcap 20 +rt_shadow_samples 1 +rt_spp_direct 1 +rt_spp_indirect 1"
) else if /i "%WHICH%"=="free" (
  set "ARGS=%FREE% +rt_shadow_samples 1 +rt_spp_direct 1 +rt_spp_indirect 1"
) else if /i "%WHICH%"=="shadow" (
  set "ARGS=%FREE% +rt_shadow_samples 4 +rt_spp_direct 1 +rt_spp_indirect 1"
) else if /i "%WHICH%"=="max" (
  set "ARGS=%FREE% +rt_shadow_samples 4 +rt_spp_direct 2 +rt_spp_indirect 2"
) else (
  echo Usage: %~nx0 ^<stock^|free^|shadow^|max^> [1-32]
  exit /b 1
)

echo === RR input quality: %WHICH%, MAP%MAP% ===
echo     %ARGS%
echo     judge in motion; watch vid_fps for the cost side
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
