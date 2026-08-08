@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Light COUNT vs shadow contrast for the bulb bands.
rem
rem What rt_debug_visibility 1 established: NOTHING casts a shadow from the bulb
rem bands -- not the fence, not sprites -- while the character still casts one
rem from another source in the same scene. So shadow rays work and the occluders
rem are in the acceleration structure. What fails is specific to these lights.
rem
rem Why count is the suspect. ReSTIR chooses ONE light per pixel. A point sitting
rem in lamp A's shadow does not go dark -- it simply gets assigned lamp B, which
rem nothing occludes. With 113 lamps spread across a ceiling there is almost
rem always an unoccluded one, so visibility comes back 1.0 nearly everywhere and
rem no umbra ever forms. This is not a bug: a ceiling of 113 lamps genuinely is
rem near-shadowless. The original game implies far fewer, brighter fixtures.
rem
rem Each arm keeps total emitted flux roughly constant: doubling the spacing
rem halves the light count, so intensity doubles. If the theory holds, overall
rem brightness stays similar across arms while shadows appear from left to right.
rem That separation is the point of holding flux fixed rather than just thinning
rem the lights out -- otherwise "darker" and "more shadowed" are indistinguishable.
rem
rem ARMS  (seglen = map units between lights; I = intensity each)
rem   dense   seglen  64  I  180   what ships now; the reference
rem   mid     seglen 128  I  360
rem   sparse  seglen 256  I  720
rem   point   seglen 512  I 1440   fewest, strongest
rem
rem What to judge, in this order:
rem   1. do the fence and sprites cast a readable shadow? Check under
rem      +rt_debug_visibility 1 as well as normally -- black there is the
rem      unambiguous answer.
rem   2. does the band still read as a continuous strip, or has it scalloped into
rem      separate blobs? This is the real cost of the fix, and if it bites, the
rem      answer is a tighter seglen with a SMALL radius, not a wide radius.
rem   3. overall brightness, which should NOT move much between arms. If it does,
rem      the flux compensation is wrong and so is the comparison.
rem
rem Watch "uploaded=N of M wanted" in the console: N is the light count driving
rem all of this, and if it does not fall between arms, the arm never reached the
rem renderer and the result is void.
rem
rem Usage: ab-bulb-density.cmd <dense^|mid^|sparse^|point> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=mid"
if "%MAP%"==""  set "MAP=1"

rem RADIUS IS FIXED ACROSS EVERY ARM. The first version of this ladder raised it
rem from 0.35 to 0.80 as it lowered the count, so a softer source cancelled
rem whatever contrast fewer lights bought, and the whole ladder read as "changes
rem nothing". That null was a broken experiment, not a result. 0.10 is near the
rem dynlight radius that demonstrably casts crisp shadows (2026-08-08).
set "R=0.10"

if /i "%WHICH%"=="dense" (
  set "SEG=64"  & set "I=180"
) else if /i "%WHICH%"=="mid" (
  set "SEG=128" & set "I=360"
) else if /i "%WHICH%"=="sparse" (
  set "SEG=256" & set "I=720"
) else if /i "%WHICH%"=="point" (
  set "SEG=512" & set "I=1440"
) else (
  echo Usage: %~nx0 ^<dense^|mid^|sparse^|point^> [map 1-32]
  exit /b 1
)

rem Both walks together: they light the same physical band where it turns a
rem corner, so a spacing mismatch shows as a density step at the corner.
set "ARGS=+rt_wall_strip_seglen %SEG% +rt_wall_strip_intensity %I% +rt_wall_strip_radius %R%"
set "ARGS=%ARGS% +rt_ceiling_edge_seglen %SEG% +rt_ceiling_edge_intensity %I% +rt_ceiling_edge_radius %R%"
set "ARGS=%ARGS% +rt_ceiling_edge_debug 1"

echo === bulb density: %WHICH% (seglen=%SEG% I=%I% radius=%R%), MAP%MAP% ===
echo     %ARGS%
echo     watch the "uploaded=N of M wanted" line -- N is the light count driving contrast
echo     judge: 1) do sprites cast shadows  2) is the strip still continuous  3) brightness steady
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
