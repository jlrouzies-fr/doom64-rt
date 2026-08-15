@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Show ReSTIR reservoir M (accumulated sample count) instead of radiance.
rem
rem This measures WHY the image is noisy in motion but clean standing still.
rem The raw 1-spp signal is equally noisy either way (user-confirmed), so what
rem cleans it when still is temporal accumulation -- ReSTIR's reservoir M, and
rem then the denoiser's own history. If M collapses when the camera moves, the
rem noise is upstream of BOTH denoisers and no amount of RR tuning can fix it.
rem
rem Green ramp = M/32. Black/dark = M~1, i.e. a single sample, worst case.
rem Bright green = a well-accumulated reservoir.
rem
rem HOW TO READ IT:
rem   1. Stand still ~5s. Expect mostly bright green (M climbing to the cap).
rem   2. Walk forward, strafe, turn. Watch floors and walls at shallow angles.
rem   3. If large areas go dark WHILE MOVING and re-brighten when you stop,
rem      that is M collapse -> history is being rejected by testSurfaceForReuse.
rem   4. If M stays bright while moving, ReSTIR is fine and the instability is
rem      inside DLSS-RR's own temporal pass instead.
rem
rem Suspected cause if (3): testSurfaceForReuse uses a flat relative depth test
rem   abs(curDepth - otherDepth) / curDepth < 0.1
rem which rejects taps on grazing surfaces, where a 1-2px reprojection error
rem moves world depth by far more than 10%. RTXDI uses a plane-distance test
rem instead, which is scale-correct at grazing angles.
rem
rem Usage: ab-restir-m.cmd [1-32]
rem ---------------------------------------------------------------------------

set "MAP=%~1"
if "%MAP%"=="" set "MAP=2"

echo === ReSTIR M debug view, MAP%MAP% ===
echo     stand still, then move: watch floors/walls go dark or stay green
call "%~dp0launch-retribution-rt.cmd" %MAP% -- +rt_debug_restir_m 1 +rt_rayreconstr 0 +rt_upscale_dlss 0
exit /b %ERRORLEVEL%
