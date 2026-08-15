@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Render resolution A/B for DLSS-RR motion stability.
rem
rem ALL previous resolution tests are VOID: they ran while rt_restir_tjitter was
rem stuck at 0, whose worm artifact dominated the frame. That includes the DLAA
rem comparison that produced (and then retracted) the "DLAA resolves it" claim.
rem This is a fresh test on a clean build.
rem
rem Why resolution is now the leading candidate. Measured and eliminated:
rem   8 shadow rays        -> no change     |  8 spp -> only ~20%
rem   direct reservoir M stable in motion   |  exposure locked -> no change
rem   InReset / disocclusion mask / indirect antilag gate -> no change
rem   every guide, blue noise, mip bias, preset           -> no change
rem   RR vs SR: identical jitter, MV scale and NGX feature flags
rem So the lighting ESTIMATE is not the noise source. What is left is SPATIAL
rem RECONSTRUCTION: the window is 1280x720, so Balanced renders ~742x418 and RR
rem must reconstruct 1280x720 from a noisy 1-spp frame at that size. Static, the
rem jittered subpixel samples accumulate and detail resolves; in motion that
rem accumulation breaks -- which is exactly "detail breaks up when moving,
rem stabilises when still". A-SVGF escapes it because DLSS-SR upscales an
rem already-denoised, detail-complete image.
rem
rem   dlaa     - rt_upscale_dlss 6, native render res, no upscaling at all
rem   quality  - rt_upscale_dlss 1
rem   balanced - rt_upscale_dlss 2 (current default)
rem
rem If dlaa is stable in motion and balanced is not, the answer is render
rem resolution and the fix is a settings recommendation, not code. Watch vid_fps:
rem DLAA costs a lot more, and that trade is the real decision.
rem
rem Usage: ab-rr-res.cmd <dlaa|quality|balanced> [1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=dlaa"
if "%MAP%"==""  set "MAP=2"

if /i "%WHICH%"=="dlaa" (
  set "ARGS=+rt_upscale_dlss 6"
) else if /i "%WHICH%"=="quality" (
  set "ARGS=+rt_upscale_dlss 1"
) else if /i "%WHICH%"=="balanced" (
  set "ARGS=+rt_upscale_dlss 2"
) else (
  echo Usage: %~nx0 ^<dlaa^|quality^|balanced^> [1-32]
  exit /b 1
)

echo === render resolution: %WHICH%, MAP%MAP% ===
echo     %ARGS%   (rt_rayreconstr stays 1)
echo     judge motion stability on detailed lit surfaces; watch vid_fps for cost
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
