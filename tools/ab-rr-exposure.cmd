@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Is DLSS-RR's motion instability caused by AUTO-EXPOSURE drift?
rem
rem CmPrepareFinal.comp applies auto exposure to the image:
rem     hdr = hdr * ev100ToLuminousExposure( getCurrentEV100() );
rem and that runs BEFORE the upscaler, so RR's pInColor is already exposed.
rem Meanwhile DLSSRR.cpp hardcodes evalParams.InPreExposure = 1.0f.
rem
rem InPreExposure exists so RR can divide that scale out and keep its temporal
rem history exposure-invariant. Told 1.0 while the real factor moves, RR blends a
rem history captured at one exposure into a frame at another. EV100 ranges 2.0 to
rem 7.7 here = 5.7 stops = a ~52x brightness swing.
rem
rem Standing still, EV100 converges and this is harmless. Walking through
rem differently-lit areas it drifts every frame -- motion-only instability.
rem
rem Why A-SVGF does not suffer: it accumulates BEFORE Finalize, in linear
rem radiance, so its history is exposure-invariant. RR accumulates after exposure
rem is baked in. Same motion vectors, same depth, opposite behaviour.
rem
rem   lock - ev100 min == max, so exposure is CONSTANT. If motion stability
rem          improves clearly, auto-exposure drift is the cause.
rem   auto - stock 2.0 / 7.7, for comparison.
rem
rem JUDGE MOTION STABILITY, NOT BRIGHTNESS. The locked arm will look flatter and
rem differently exposed -- that is expected and is not what is being compared.
rem Walk through a bright area into a dark one, which is where adaptation moves
rem most. A previous attempt set only ev100_min and left max at 7.7, so
rem adaptation still ran and the test showed nothing.
rem
rem If this is confirmed, the real fix is to pass the actual exposure as
rem InPreExposure rather than locking anything.
rem
rem Usage: ab-rr-exposure.cmd <lock|auto> [1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
set "EV=%~3"
if "%WHICH%"=="" set "WHICH=lock"
if "%MAP%"==""  set "MAP=2"
rem HIGHER ev100 = DARKER. 5.0 under-exposed the test scene badly enough that the
rem artifact could not be judged; 3.0 sits near what auto settles on indoors.
if "%EV%"==""   set "EV=3.0"

if /i "%WHICH%"=="lock" (
  set "ARGS=+rt_tnmp_ev100_min %EV% +rt_tnmp_ev100_max %EV%"
) else if /i "%WHICH%"=="auto" (
  set "ARGS=+rt_tnmp_ev100_min 2.0 +rt_tnmp_ev100_max 7.7"
) else (
  echo Usage: %~nx0 ^<lock^|auto^> [1-32] [ev100]
  exit /b 1
)

echo === auto-exposure: %WHICH%, MAP%MAP% ===
echo     %ARGS%
echo     judge MOTION STABILITY, not brightness
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
