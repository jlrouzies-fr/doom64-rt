@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Shadow hardness for the bulb fixtures: source RADIUS, and shadow samples.
rem
rem The finding. rt_dynlight_radius is 0.08 and its own description says
rem "smaller = harder shadows". The bulb lights were given 0.35 -- over four
rem times larger -- to blend discrete spheres into a continuous-looking strip.
rem A 0.35m source throws a penumbra wide enough that no umbra survives, which
rem is why a muzzle flash (a dynlight, radius 0.08) still casts a crisp shadow
rem in the same room where the bulb bands cast none.
rem
rem Why the earlier density ladder missed it: ab-bulb-density RAISED radius as it
rem lowered the light count (0.35 -> 0.80), so the two effects cancelled. That
rem null was a confounded experiment, not evidence. This ladder holds count and
rem intensity fixed and moves radius alone.
rem
rem Second lever, independent of the first. At 1 shadow ray, visibility is a
rem binary 0/1 multiply, so a soft shadow is reconstructed from one random point
rem on the sphere and the denoiser smears it away. rt_shadow_samples averages N
rem points on the SAME chosen light, turning visibility into a fraction -- a real
rem soft shadow instead of noise. So radius controls how soft the shadow IS, and
rem shadow_samples controls whether a soft shadow can be RESOLVED at all.
rem
rem The trade-off to watch: a small radius is what makes the strip scallop into
rem separate blobs (see rt_wall_strip_seglen's note). If `hard` fixes shadows but
rem the strip goes beady, the answer is a small radius plus tighter seglen, not
rem a big radius.
rem
rem ARMS (count and intensity identical in every arm)
rem   soft    r 0.35  samples 1   what ships now; the reference
rem   mid     r 0.20  samples 1
rem   hard    r 0.10  samples 1   about the dynlight radius that already works
rem   hard4   r 0.10  samples 4   same, but soft shadows can actually resolve
rem   dyn     r 0.08  samples 4   exactly the dynlight radius
rem   pin     r 0.02  samples 4   the FLASHLIGHT/muzzle-flash radius, and those
rem                               two do make the fence cast. Also drops the count
rem                               (seglen 256, I 720): small radius and low count
rem                               have never been tried together.
rem
rem Judge: stand so the fence or a prop is between you and a bulb band, and look
rem for an umbra on the wall behind. Then check whether the strip still reads as
rem a strip.
rem
rem Usage: ab-bulb-softness.cmd <soft^|mid^|hard^|hard4^|dyn^|pin> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=hard"
if "%MAP%"==""  set "MAP=1"

if /i "%WHICH%"=="soft" (
  set "R=0.35" & set "S=1"
) else if /i "%WHICH%"=="mid" (
  set "R=0.20" & set "S=1"
) else if /i "%WHICH%"=="hard" (
  set "R=0.10" & set "S=1"
) else if /i "%WHICH%"=="hard4" (
  set "R=0.10" & set "S=4"
) else if /i "%WHICH%"=="dyn" (
  set "R=0.08" & set "S=4"
) else if /i "%WHICH%"=="pin" (
  rem The flashlight and muzzle flash both run rt_*_radius 0.02 and BOTH make the
  rem MAP01 fence cast a shadow. At 1 map unit = 1/32 m that is 0.64 map units
  rem against the 11.2 of the 0.35 default -- 17x. Penumbra width scales with
  rem source size, so an 11-unit source erases the shadow of a 4-unit fence wire
  rem while a 0.64-unit one draws it sharply. Wide occluders (a character, a
  rem wall) are far wider than the penumbra either way, which is exactly the
  rem split observed: everything casts except the fence.
  rem
  rem Paired with sparse spacing on purpose. Small radius and low count have
  rem never been tested TOGETHER: the earlier radius arms ran at 113 lights,
  rem where whatever umbra formed was filled by another lamp.
  set "R=0.02" & set "S=4" & set "SEG=256" & set "I=720"
) else (
  echo Usage: %~nx0 ^<soft^|mid^|hard^|hard4^|dyn^|pin^> [map 1-32]
  exit /b 1
)

if "%SEG%"=="" set "SEG=64"
if "%I%"==""   set "I=180"

rem Held fixed so radius is the only thing moving: same spacing, same intensity,
rem on both walks. The earlier ladder's mistake was letting these drift.
set "ARGS=+rt_wall_strip_radius %R% +rt_ceiling_edge_radius %R% +rt_dynlight_radius 0.08"
set "ARGS=%ARGS% +rt_wall_strip_seglen %SEG% +rt_ceiling_edge_seglen %SEG%"
set "ARGS=%ARGS% +rt_wall_strip_intensity %I% +rt_ceiling_edge_intensity %I%"
set "ARGS=%ARGS% +rt_shadow_samples %S%"

echo === bulb softness: %WHICH% (radius=%R% samples=%S% seglen=%SEG% I=%I%), MAP%MAP% ===
echo     %ARGS%
echo     judge: 1) umbra behind the fence  2) is the strip still continuous
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
