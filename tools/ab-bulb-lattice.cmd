@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Where the SFLATAS / SFLATAQ bulb lights are PLACED. Not how bright they are.
rem
rem Why. These two textures tile their bulbs across the whole flat -- SFLATAS 2x2
rem per 64-unit tile, SFLATAQ 4x4 -- but until now they were lit by the PERIMETER
rem walk, one light every rt_ceiling_edge_seglen around the sector's linedefs.
rem That walk lights a room's EDGES. Every bulb away from a wall cast nothing, so
rem a wide panel stayed dark down its own middle while its art showed lit bulbs
rem there. The faux path (SFLATC) was built to answer exactly this objection and
rem it was simply never applied to the real arrays (open-issues 1.6g).
rem
rem What is NOT changing between the arms: intensity, radius, z-offset, the light
rem budget, and the maximum distance. Both arms feed the same candidate list and
rem the same nearest-N cap. Only the POSITIONS move. If "on" looks brighter, that
rem is the lights being where the bulbs are, not more or hotter lights.
rem
rem ARMS (both set every knob explicitly -- no arm inherits the other's value and
rem no console-typed leftover can survive)
rem   on   - lattice placement: a light inside each painted bulb
rem   off  - the old perimeter walk, for reference
rem
rem Judge: does the light come from the bulbs you can see, or from the room's
rem edges? Stand under the MIDDLE of a wide panel -- that is where the two arms
rem differ most, and where "off" goes dark.
rem
rem Note the emissive glow is NOT this feature and does not change between arms.
rem Per section 12 emission is collected only on indirect bounces, so the bulbs
rem looking bright is never evidence that they are casting.
rem
rem Usage: ab-bulb-lattice.cmd <on^|off> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=on"
if "%MAP%"==""  set "MAP=7"

if /i "%WHICH%"=="on" (
  set "L=1"
) else if /i "%WHICH%"=="off" (
  set "L=0"
) else (
  echo Usage: %~nx0 ^<on^|off^> [map 1-32]
  exit /b 1
)

rem Everything except the placement mode is pinned identically on both arms.
set "ARGS=+rt_ceiling_edge_lattice %L%"
set "ARGS=%ARGS% +rt_ceiling_edge_lamps 1 +rt_ceiling_edge_intensity 180"
set "ARGS=%ARGS% +rt_ceiling_edge_seglen 64 +rt_ceiling_edge_radius 0.35"
set "ARGS=%ARGS% +rt_ceiling_edge_zofs 10 +rt_ceiling_edge_inset 10"
set "ARGS=%ARGS% +rt_ceiling_edge_max 320 +rt_ceiling_edge_maxdist 3072"
set "ARGS=%ARGS% +rt_ceiling_edge_debug 1"

echo === bulb lamp placement: %WHICH% (rt_ceiling_edge_lattice %L%), MAP%MAP% ===
echo     %ARGS%
echo     console line reports "+ N bulb lattice(s)" -- N=0 on the off arm
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
