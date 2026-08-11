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
rem   on       the default: 60 lm per light at 96-unit spacing, ~120 lights in
rem            the MAP21 hall. Well under a torch (900) on purpose -- there are
rem            a hundred of them and each sits 0.75 m off the surface.
rem   dim      600 lm -- what the "some light, underwhelming" shot was.
rem   bright   5400 lm. The arms are 3x apart,
rem            so one run of dim/on/bright brackets the answer.
rem   fine     48-unit spacing. Four times as many lights, SAME total brightness
rem            (intensity is scaled by spacing^2), so this isolates evenness from
rem            brightness -- the one comparison a single knob cannot make.
rem   coarse   192-unit spacing, likewise.
rem   tight    small source radius: every grid point throws its own hard shadow,
rem            which reads as a row of lamps under the floor. Shows why the
rem            default radius is wide.
rem   solo     THE DECISIVE ONE when the room looks unlit. Spacing 4096 so each
rem            lava sector gets one or two grid points, at 3000 lm each. If the
rem            room lights up, the lights work and the only question left is the
rem            number. If a single 3000 lm light in the middle of the lava does
rem            nothing, the lights are not reaching the renderer and no amount of
rem            tuning will help -- which is a completely different bug.
rem EVERY ARM TELEPORTS YOU ONTO THE LAVA on the first frame (rt_lava_autogoto),
rem and the debug/solo/control arms write rt-lava.log instead of rt-console.log.
rem Both exist for the same reason: the first four rounds of "the lava lights
rem nothing" were judged from 48 metres away, and the run that would have shown
rem it was overwritten by the next launch before it could be read. Append
rem "+rt_lava_autogoto 0" if you want to walk there yourself.
rem
rem   control  THE ONE THAT MATTERS NOW. Everything up to LightManager::Add is
rem            verified good by the RTGL probe and the room is still black, so
rem            this uploads a 2000 lm WHITE light one metre above the camera,
rem            through the same code path. If the room stays black with a lamp
rem            on your head, analytic lights are broken here and the lava grid
rem            was never the bug. If it lights up, the grid is at fault and this
rem            is the control to compare against.
rem   debug    rt_lava_light_debug 1 -- prints how many lava sectors matched, how
rem            many grid points fell in range and how many survived the cap. If
rem            that line says 0 sectors, nothing about intensity will help.
rem
rem Every arm sets every lava cvar explicitly, so a value left in the ini from a
rem previous arm can never leak into the next one.
rem
rem Usage: ab-lava.cmd <off|on|dim|bright|fine|coarse|tight|solo|control|debug> [1-34]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=on"
if "%MAP%"==""  set "MAP=21"

set "COL=+rt_lava_light_r 255 +rt_lava_light_g 90 +rt_lava_light_b 20"
set "GEO=+rt_lava_light_z 40 +rt_lava_light_max 256 +rt_lava_light_dist 2048"
set "DEF=%COL% %GEO% +rt_lava_light_debug 0 +rt_lava_autogoto 1"
rem A LOG OF ITS OWN. rt-console.log is one file that every launch overwrites, so
rem the evidence from a lava run was twice destroyed by the next unrelated launch
rem before it could be read. +logfile comes after the launcher's own, so it wins.
set "LOG=+logfile %~dp0\..\rt-lava.log"
t-lava.log"

if /i "%ARM%"=="off"    set "ARGS=+rt_lava_light_on 0 +rt_lava_light_intensity 1800 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.3 %DEF%"
if /i "%ARM%"=="on"     set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 1800 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.3 %DEF%"
if /i "%ARM%"=="dim"    set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 600 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.3 %DEF%"
if /i "%ARM%"=="bright" set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 5400 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.3 %DEF%"
if /i "%ARM%"=="fine"   set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 1800 +rt_lava_light_spacing 48 +rt_lava_light_radius 0.3 %COL% %GEO% +rt_lava_light_max 512 +rt_lava_light_debug 0"
if /i "%ARM%"=="coarse" set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 1800 +rt_lava_light_spacing 192 +rt_lava_light_radius 0.3 %DEF%"
if /i "%ARM%"=="tight"  set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 1800 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.08 %DEF%"
if /i "%ARM%"=="solo"   set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 3000 +rt_lava_light_spacing 4096 +rt_lava_light_radius 0.3 %COL% +rt_lava_light_z 40 +rt_lava_light_max 8 +rt_lava_light_dist 4096 +rt_lava_light_debug 1 +rt_lava_autogoto 1"
if /i "%ARM%"=="control" set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 1800 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.3 %COL% %GEO% +rt_lava_light_debug 2 +rt_lava_autogoto 1"
if /i "%ARM%"=="debug"  set "ARGS=+rt_lava_light_on 1 +rt_lava_light_intensity 1800 +rt_lava_light_spacing 96 +rt_lava_light_radius 0.3 %COL% %GEO% +rt_lava_light_debug 1 +rt_lava_autogoto 1"

if not defined ARGS (
  echo Usage: %~nx0 ^<off^|on^|dim^|bright^|fine^|coarse^|tight^|solo^|control^|debug^> [1-34]
  exit /b 1
)

echo === lava arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
rem The debug and solo arms also pass "debug" -> -rtdebug, which un-mutes RTGL's
rem OWN messages. That is what the LAVA PROBE line in LightManager.cpp needs:
rem rt_main sets allowedMessages=0 without it, so an RTGL-side probe is silent
rem and looks like it never ran.
set "DBG="
if /i "%ARM%"=="debug" set "DBG=debug"
if /i "%ARM%"=="solo"  set "DBG=debug"
if /i "%ARM%"=="control" set "DBG=debug"
call "%~dp0launch-retribution-rt.cmd" %MAP% %DBG% -- %ARGS% %LOG%
exit /b %ERRORLEVEL%
