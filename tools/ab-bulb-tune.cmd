@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Tuning ladder between "no fence shadow" and "shadows but noisy".
rem
rem Where this starts. ab-bulb-softness `pin` (radius 0.02, seglen 256, I 720,
rem samples 4) finally produced fence shadows, confirming the cause: our source
rem was 0.35m = 11.2 map units, against 0.64 for the flashlight and muzzle flash
rem that always worked. A source wider than the occluder cannot cast its shadow,
rem and the fence wires are only a few units thick.
rem
rem `pin` is deliberately extreme on all three axes at once, so its noise is
rem expected rather than a new problem. Three levers, pulling different ways:
rem
rem   radius        smaller = sharper shadow, more variance. Above ~0.10 the
rem                 fence's shadow washes out again -- that is the ceiling.
rem   shadow_samples averages visibility over N points on the CHOSEN light, so it
rem                 attacks the noise directly instead of by blurring the shadow.
rem                 Costs N-1 rays per pixel; this is the one that buys quality
rem                 rather than trading it.
rem   seglen        tighter = more lights = smoother, but every added light is
rem                 another chance for an unoccluded one to refill the umbra, and
rem                 it is what erased these shadows at 113 lights.
rem
rem Intensity tracks seglen to hold total flux roughly constant, so arms differ
rem in shadow quality rather than brightness.
rem
rem ARMS
rem   sharp     r 0.03  seg 192  I 540  S 8   closest to pin, max denoising
rem   balanced  r 0.05  seg 128  I 360  S 8   the expected landing spot
rem   smooth    r 0.07  seg 128  I 360  S 8   softer; watch the fence shadow
rem   dense     r 0.05  seg  96  I 270  S 8   more lights, same sharpness
rem   cheap     r 0.05  seg 128  I 360  S 1   balanced WITHOUT the extra rays,
rem                                           to see what shadow_samples is
rem                                           actually buying and what it costs
rem
rem Judge, in this order:
rem   1. is the fence shadow still there? That is the constraint everything else
rem      is traded against.
rem   2. how noisy is it, in MOTION as well as standing still.
rem   3. does the bulb band still read as a continuous strip, or has it beaded?
rem   4. vid_fps on `cheap` vs `balanced` -- that difference is the cost of
rem      shadow_samples 8.
rem
rem Usage: ab-bulb-tune.cmd <sharp^|balanced^|smooth^|dense^|cheap> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=balanced"
if "%MAP%"==""  set "MAP=1"

if /i "%WHICH%"=="sharp" (
  set "R=0.03" & set "SEG=192" & set "I=540" & set "S=8"
) else if /i "%WHICH%"=="balanced" (
  set "R=0.05" & set "SEG=128" & set "I=360" & set "S=8"
) else if /i "%WHICH%"=="smooth" (
  set "R=0.07" & set "SEG=128" & set "I=360" & set "S=8"
) else if /i "%WHICH%"=="dense" (
  set "R=0.05" & set "SEG=96"  & set "I=270" & set "S=8"
) else if /i "%WHICH%"=="cheap" (
  set "R=0.05" & set "SEG=128" & set "I=360" & set "S=1"
) else (
  echo Usage: %~nx0 ^<sharp^|balanced^|smooth^|dense^|cheap^> [map 1-32]
  exit /b 1
)

rem Both walks together -- they light the same physical band where it turns a
rem corner, so a mismatch shows as a step at the corner.
set "ARGS=+rt_wall_strip_radius %R% +rt_ceiling_edge_radius %R%"
set "ARGS=%ARGS% +rt_wall_strip_seglen %SEG% +rt_ceiling_edge_seglen %SEG%"
set "ARGS=%ARGS% +rt_wall_strip_intensity %I% +rt_ceiling_edge_intensity %I%"
set "ARGS=%ARGS% +rt_shadow_samples %S% +rt_ceiling_edge_debug 1"

echo === bulb tune: %WHICH% (r=%R% seglen=%SEG% I=%I% samples=%S%), MAP%MAP% ===
echo     %ARGS%
echo     judge: 1) fence shadow present  2) noise in MOTION  3) strip continuity  4) vid_fps
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
