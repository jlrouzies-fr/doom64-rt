@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Intensity ladder for Doom 64 bulb-array fixtures (SPACEAZ / SFLATAQ / SFLATAS).
rem
rem Why. 500 was chosen for wall strips because 120 and 250 both read as NO light
rem at all -- a strip sits flush against the surface it lights, so most of its
rem sphere is occluded (section 19). That reasoning was established when a handful
rem of lights were reaching the scene at once. It no longer holds unchanged:
rem the flat walk now covers floors AND ceilings and distributes by distance, so
rem the same room receives many more lights than when 500 was picked. Reported
rem symptom is fizzle/denoiser noise around the fixtures, which is what a dense
rem field of small bright spheres does to a 1-spp ReSTIR signal.
rem
rem Two levers, and they are not the same:
rem   intensity - how bright each sphere is
rem   radius    - how BIG the source is. A larger source softens the shadow
rem               penumbra and lowers variance for the same delivered light, so
rem               it attacks the fizzle directly rather than by dimming.
rem
rem ARMS (every arm sets all four knobs explicitly, so no arm inherits another's
rem value and no console-typed leftover can survive -- section 9)
rem   cur   - I=500 r=0.35   what shipped; the reference point
rem   mid   - I=300 r=0.35   intensity only
rem   low   - I=180 r=0.35   intensity only, further
rem   soft  - I=180 r=0.60   dimmer AND a bigger, softer source
rem   wide  - I=300 r=0.60   bigger source at moderate intensity
rem
rem Judge two things separately: whether the fixtures still read as lit, and
rem whether the fizzle around them is gone. "soft" and "wide" exist because those
rem two can be improved at once, and dimming alone may fix the second by
rem destroying the first.
rem
rem Usage: ab-bulb-intensity.cmd <cur^|mid^|low^|soft^|wide> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=mid"
if "%MAP%"==""  set "MAP=2"

if /i "%WHICH%"=="cur" (
  set "I=500" & set "R=0.35"
) else if /i "%WHICH%"=="mid" (
  set "I=300" & set "R=0.35"
) else if /i "%WHICH%"=="low" (
  set "I=180" & set "R=0.35"
) else if /i "%WHICH%"=="soft" (
  set "I=180" & set "R=0.60"
) else if /i "%WHICH%"=="wide" (
  set "I=300" & set "R=0.60"
) else (
  echo Usage: %~nx0 ^<cur^|mid^|low^|soft^|wide^> [map 1-32]
  exit /b 1
)

rem Wall strips and flat lamps are the SAME physical fixture seen by two walks --
rem a band that turns a corner changes owner. Tuning one without the other makes
rem the corner visible as a brightness step.
set "ARGS=+rt_wall_strip_intensity %I% +rt_wall_strip_radius %R%"
set "ARGS=%ARGS% +rt_ceiling_edge_intensity %I% +rt_ceiling_edge_radius %R%"
set "ARGS=%ARGS% +rt_ceiling_edge_debug 1"

echo === bulb fixture intensity: %WHICH% (I=%I% radius=%R%), MAP%MAP% ===
echo     %ARGS%
echo     check BOTH: fixtures still read as lit, and the fizzle around them
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
