@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the engine flame lights (rt_flame_light_*), and prove they are running.
rem
rem Every open flame in the game is lit by RT_UploadFlameLights() in rt_main.cpp
rem (table RT_FLAME_KINDS), NOT by the sprite's attached light -- those sprites
rem carry lightIntensity 0 in textures.json on purpose. Read that before you
rem reach for the `off` arm: it is TOTAL DARKNESS for every flame, not a
rem fallback to the old look. Full story in docs/flame-lighting.md.
rem
rem   on        the shipped values. Start here.
rem   debug     `on` plus rt_flame_light_debug 1: a cyan marker sphere at every
rem             uploaded flame light, and a count printed every 60 frames. This
rem             is the arm that answers "is this system running at all". The
rem             markers must sit ON the visible flame -- if one is halfway down
rem             a torch pole, the `up` offset for that row is wrong.
rem   steady    flicker 0 and wobble 0. Keeps the corrected POSITION and drops
rem             all the motion. Reach for this, not `off`, when the fire reads
rem             as busy or strobey.
rem   calm      half the shipped flicker and speed. Between `on` and `steady`.
rem   off       rt_flame_light_on 0. Not the old behaviour -- no flame in the
rem             game casts anything. A control, and a way to see how much of a
rem             room's light was coming from its fires.
rem   marble    THE FIZZLE REPRO. Forces the flat 0.09 m source radius this family
rem             shipped with until 2026-08-27, instead of the per-kind radii in
rem             RT_FLAME_KINDS. Every flame light sits INSIDE its own billboard
rem             and those sprites are noShadow, so at 0.09 the sprite's own texels
rem             take 55,000-70,700 -- white speckles crawling across the torch, the
rem             same failure as screen/barrelsBlinkFizzle.png. Run this against
rem             `on` at a wall sconce: it is the whole bug, one cvar apart.
rem   wide      forces 0.60 m. Past what the art supports -- this is the arm that
rem             answers "have the corridor shadows gone mushy yet", not a candidate.
rem
rem WHY RADIUS AND NOT INTENSITY. Far from a sphere light the solid angle goes as
rem PI*r^2/d^2 and cancels the radiance's 1/(PI*r^2) exactly, so how a torch lights
rem its ROOM is independent of the source radius; only the near field -- the sprite
rem itself -- scales, and it scales as 1/r^2. `marble` vs `on` should therefore show
rem a clean sprite and an UNCHANGED room. If the room got darker or brighter, that
rem is a finding.
rem
rem WHERE TO LOOK. The fires are not evenly spread, and this has misled at least
rem one investigation already:
rem
rem   FIRE   (64BigFire)   117 placements -- MAP11, 12, 13, 18 (64 of them!),
rem                        20, 21, 22, 24, 34. MAP18 is the stress test.
rem   BFLM/RFLM/YFLM/GFLM  ONE each, MAP34 ONLY, clustered around
rem                        (600..664, -552..-616). Nowhere else in the game.
rem   TL*/TS*/A03x/GTCH/CAND  the torches and candle, widely placed.
rem
rem So `ab-flame.cmd debug 34` is the only way to see the four loose fires, and
rem `ab-flame.cmd debug 18` is the one that tests the 64-light budget.
rem
rem Every arm sets EVERY rt_flame_light cvar explicitly. They are CVAR_ARCHIVE:
rem an arm that left one unset would inherit the previous arm's value out of the
rem ini and quietly invalidate the comparison.
rem
rem Usage: ab-flame.cmd <on|debug|steady|calm|off|marble|wide> [1-34]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=on"
if "%MAP%"==""  set "MAP=18"

rem Shared across arms. rt_flame_light_radius 0 = the per-kind radii in the engine
rem table; the two radius arms below restate it, so an arm never inherits the ini.
set "BASE=+rt_flame_light_scale 1.0 +rt_flame_light_maxdist 3072 +rt_flame_light_max 64"
set "MOTION=+rt_flame_light_flicker 0.15 +rt_flame_light_speed 0.25 +rt_flame_light_wobble 2.0"

if /i "%ARM%"=="on"     set "ARGS=+rt_flame_light_on 1 %BASE% +rt_flame_light_radius 0    %MOTION% +rt_flame_light_debug 0"
if /i "%ARM%"=="debug"  set "ARGS=+rt_flame_light_on 1 %BASE% +rt_flame_light_radius 0    %MOTION% +rt_flame_light_debug 1"
if /i "%ARM%"=="marble" set "ARGS=+rt_flame_light_on 1 %BASE% +rt_flame_light_radius 0.09 %MOTION% +rt_flame_light_debug 0"
if /i "%ARM%"=="wide"   set "ARGS=+rt_flame_light_on 1 %BASE% +rt_flame_light_radius 0.60 %MOTION% +rt_flame_light_debug 0"
if /i "%ARM%"=="steady" set "ARGS=+rt_flame_light_on 1 %BASE% +rt_flame_light_radius 0    +rt_flame_light_flicker 0    +rt_flame_light_speed 0.25  +rt_flame_light_wobble 0   +rt_flame_light_debug 0"
if /i "%ARM%"=="calm"   set "ARGS=+rt_flame_light_on 1 %BASE% +rt_flame_light_radius 0    +rt_flame_light_flicker 0.08 +rt_flame_light_speed 0.125 +rt_flame_light_wobble 1.0 +rt_flame_light_debug 0"
if /i "%ARM%"=="off"    set "ARGS=+rt_flame_light_on 0 %BASE% +rt_flame_light_radius 0    %MOTION% +rt_flame_light_debug 0"

if not defined ARGS (
  echo Usage: %~nx0 ^<on^|debug^|steady^|calm^|off^|marble^|wide^> [1-34]
  exit /b 1
)

echo === flame arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
if "%MAP%"=="34" echo     MAP34: the four ?FLM loose fires are around (600..664, -552..-616).
if "%MAP%"=="18" echo     MAP18: 64 x 64BigFire -- this is the map that tests rt_flame_light_max.
if /i "%ARM%"=="marble" echo     marble: the PRE-FIX radius. Stand at a wall sconce (A030) and look at the sprite.
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
