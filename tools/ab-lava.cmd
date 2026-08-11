@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the lava. Maps with a lava FLOOR, from the UDMF: MAP15 (1 sector),
rem MAP20 (2), MAP21 (2, the big hall -- default here), MAP34 (3, and the only
rem place D64LAVA1/2 appear). 8 lava-floor sectors in the whole game.
rem
rem A UDMF map here is exactly 6 lumps -- MAPxx, TEXTMAP, BEHAVIOR, ZNODES,
rem SCRIPTS, ENDMAP. Any scan that walks a wider window and keys lumps by NAME
rem reads the NEXT map's TEXTMAP and reports every answer shifted by one map.
rem That produced a confident "MAP21 has no lava" here, which is false.
rem
rem TWO INDEPENDENT HALVES, and they were confused for each other for most of a
rem session, so the arms keep them apart:
rem
rem   1. the SURFACE  -- _e / _n / _h / _orm baked by tools\gen_lava_material.py.
rem      Not a cvar at all. Regenerate with --apply, undo with --revert.
rem   2. the LIGHT    -- rt_lava_light_*, analytic sphere lights scattered on a
rem      world grid over every lava sector. This is the half that lights the
rem      ROOM. Without it the lava glows and the walls stay black, because
rem      RTGL1 emissive is not a light source and the lightIntensity in
rem      textures.json only ever worked for sprites.
rem
rem   off      rt_lava_light_on 0 -- surface only. This is what the lava looked
rem            like before the lights existed, and the A/B for "is the room dark
rem            because the lava is dim, or because nothing emits".
rem   on       the default: 180 lumen per light at 96-unit spacing. Lumen is
rem            the scale the whole file uses -- flames are 900.
rem   dim      half intensity, for a room that blows out.
rem   bright   double intensity.
rem   fine     48-unit spacing. Four times as many lights, SAME total brightness
rem            (intensity is scaled by spacing^2), so this isolates evenness from
rem            brightness -- the one comparison a single knob cannot make.
rem   coarse   192-unit spacing, likewise.
rem   tight    small source radius: every grid point throws its own hard shadow,
rem            which reads as a row of lamps under the floor. Shows why the
rem            default radius is wide.
rem   debug    rt_lava_light_debug 1 -- prints how many lava sectors matched, how
rem            many grid points fell in range and how many survived the cap. If
rem            that line says 0 sectors, nothing about intensity will help.
rem
rem Every arm sets every lava cvar explicitly, so a value left in the ini from a
rem previous arm can never leak into the next one.
rem
rem Usage: ab-lava.cmd <off|on|dim|bright|fine|coarse|tight|debug> [1-34]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=on"
if "%MAP%"==""  set "MAP=21"

set "COL=+rt_lava_light_r 255 +rt_lava_light_g 90 +rt_lava_light_b 20"
set "GEO=+rt_lava_light_z 12 +rt_lava_light_max 256 +rt_lava_light_dist 2048"
set "DEF=%COL% %GEO% +rt_lava_light_debug 0"

if /i "%ARM%"=="off"    set "ARGS=+rt_lava_light_on 0 +rt_lava_light_intensity 180 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.6 %DEF%"
if /i "%ARM%"=="on"     set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 180 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.6 %DEF%"
if /i "%ARM%"=="dim"    set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 90 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.6 %DEF%"
if /i "%ARM%"=="bright" set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 360 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.6 %DEF%"
if /i "%ARM%"=="fine"   set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 180 +rt_lava_light_spacing 48 +rt_lava_light_radius 0.6 %COL% %GEO% +rt_lava_light_max 512 +rt_lava_light_debug 0"
if /i "%ARM%"=="coarse" set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 180 +rt_lava_light_spacing 192 +rt_lava_light_radius 0.6 %DEF%"
if /i "%ARM%"=="tight"  set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 180 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.08 %DEF%"
if /i "%ARM%"=="debug"  set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 180 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.6 %COL% %GEO% +rt_lava_light_debug 1"

if not defined ARGS (
  echo Usage: %~nx0 ^<off^|on^|dim^|bright^|fine^|coarse^|tight^|debug^> [1-34]
  exit /b 1
)

echo === lava arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
