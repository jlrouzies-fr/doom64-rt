@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B tiled blue noise for the ReSTIR reuse taps (rt_restir_bluenoise), on the
rem CURRENT build, judged on the FINAL image.
rem
rem Bisect narrowed the DLSS-RR worm regression to 3adfcf8 (blue-noise seeding)
rem or b031a21 (ReSTIR debug/shadow/jitter knobs): aug06 is clean, aug07mid
rem (b031a21) is wormy.
rem
rem This was "tested" once before and dismissed as no-difference -- but that was
rem done in the unfiltered debug view, which by construction shows the raw
rem per-pixel signal and hides everything the denoiser's temporal reconstruction
rem does. The whole hypothesis is about temporal behaviour, so that view could
rem not have shown it. Judge the NORMAL image, and judge it in motion.
rem
rem Mechanism: blue noise is right for sampling a VALUE per pixel (it pushes
rem error into high frequencies). 3adfcf8 used it to choose WHICH NEIGHBOUR each
rem pixel reuses. Tiling makes adjacent pixels pick correlated neighbours, so
rem reuse inherits the texture's spatial structure -- and correlated reuse gives
rem correlated residual noise, i.e. filaments at that texture's scale. A-SVGF's
rem spatial filter absorbs it; RR's temporal pass latches on and smears it.
rem
rem   0 = white-noise taps (pre-3adfcf8 behaviour)
rem   1 = tiled blue noise (current default)
rem
rem Usage: ab-rr-bluenoise.cmd <0|1> [1-32]
rem ---------------------------------------------------------------------------

set "MODE=%~1"
set "MAP=%~2"
if "%MODE%"=="" set "MODE=0"
if "%MAP%"==""  set "MAP=2"

if not "%MODE%"=="0" if not "%MODE%"=="1" (
  echo Usage: %~nx0 ^<0^|1^> [1-32]
  exit /b 1
)

echo === rt_restir_bluenoise %MODE%, MAP%MAP% ===
call "%~dp0launch-retribution-rt.cmd" %MAP% -- +rt_restir_bluenoise %MODE%
exit /b %ERRORLEVEL%
