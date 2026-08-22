@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem A/B the poison bubbles -- d64r-poison-fx.pk3, built by tools\gen_poison_fx.py.
rem
rem Maps with a POISON floor, from the UDMF (prefix D64N, which is D64N1_*,
rem D64N2_* and the two D64NUKG stills):
rem
rem   MAP07  50 sectors  <- the default here, and the only map where the effect
rem                         is a room rather than a puddle
rem   MAP22   4    MAP24  4    MAP18  2    MAP16  1    MAP25  1
rem   MAP34   the texture-sampler map: one pool of each fluid, side by side, so
rem           it is the arm to use for "does this read as POISON and not lava".
rem
rem TWO INDEPENDENT HALVES, and they fail in different ways, so keep them apart:
rem
rem   1. the SPAWNER -- a ZScript EventHandler samples a disc around the player,
rem      keeps the samples that land on a D64N floor, and spawns a bubble there.
rem      If the log has no "D64PoisonFx: N poison sector(s)" line at level load,
rem      NOTHING below this point can work: either the pk3 is not loaded or
rem      MAPINFO did not register the handler, and no amount of rate will help.
rem   2. the LIGHT   -- lightIntensity on the SPRITE, from rt/data/textures.json.
rem      That is the whole of it. A GLDEFS pointlight per frame was tried and
rem      removed: a point light inside a 20-unit billboard is at zero distance
rem      from it, so every bubble rendered as a white pill with the art gone.
rem      The sprite meta was already throwing the green, which is what
rem      rt_dynlight 0 proved -- see the "nodyn" arm.
rem
rem   on      the default: 3 bubbles every 9 tics inside 1100 units.
rem   off     d64_poison_fx 0. The A/B for "is that green coming from the
rem           bubbles or from the flat's own emissive".
rem   dense   4x the rate. Too many on purpose -- use it to see the shape of one
rem           bubble's life without waiting for the next.
rem   sparse  1/4 the rate.
rem   near    draw distance 400. The bubbles crowd around you and the far half
rem           of the lake goes still, which is what the default trades away.
rem   far     draw distance 2200 at 4x rate. Distance and rate are NOT
rem           independent: doubling the radius quadruples the area, so the rate
rem           has to go up with it or the near field visibly thins out.
rem   nodyn   rt_dynlight 0. GLOBAL -- it kills every dynamic light in the game,
rem           not just these. This is the arm that found the white-pill blowout:
rem           the bubbles kept glowing and kept tinting the pool with it off,
rem           which proved the sprite meta was carrying the light on its own.
rem   debug   d64_poison_debug 1 + rt_verbose 1 -- prints the sector count and
rem           the first three spawn positions on screen and to the log.
rem
rem SIZE AND HEIGHT are cvars too, and every arm pins them at the shipping
rem values so a tuning session cannot leak into a rate comparison:
rem   d64_poison_size  ABSOLUTE scale on the per-bubble spread (0.7-1.25), where
rem                    1 draws the sprite at its authored 20 px. Ships at 0.35.
rem                    It multiplies the whole spread, so raising it makes a
rem                    bigger lake, not a uniform one.
rem   d64_poison_z     where the bubble's FOOT is DRAWN, relative to the fluid
rem                    plane. It is a SpriteOffset, not a spawn height: an actor
rem                    spawned below floorz is clamped back up onto it on its
rem                    first tic, which is why negative values did nothing at
rem                    first. Try "-- +d64_poison_z -4" for bubbles that break
rem                    the plane rather than rest on it.
rem   d64_poison_sat   colour saturation, RELATIVE TO SHIPPING. 1 is the default
rem                    and is matched to the RENDERED pool (hue 105, sat 0.40 --
rem                    measured off a lab frame, not off the flat, whose albedo
rem                    is nearly black); 2 is roughly the original art, which
rem                    read as too vivid next to the poison; 0 is grey, which is
rem                    the control for "where is the green coming from".
rem                    FIVE RUNGS, not a dial -- see below.
rem
rem WHY SATURATION IS A LADDER AND NOT A CONTINUOUS DIAL. Tinting a sprite at
rem runtime would mean a GZDoom translation, and RTHardwareTexture appends a
rem per-translation SUFFIX to the RTGL1 material name -- so a translated bubble
rem is a different material, has no textures.json entry, and loses its
rem lightIntensity and emissiveMult. It would change colour and stop glowing.
rem So the rungs are baked at build time, one sprite set each, and the cvar
rem picks the nearest. To land between two rungs, move one in
rem tools\gen_poison_fx.py (SAT_SETS) and rebuild.
rem
rem The seven d64_poison_* cvars are declared NOSAVE in the pk3's CVARINFO, so an
rem arm cannot leak into the next run through the ini. Every arm still sets all
rem seven explicitly.
rem
rem Usage: ab-poison.cmd <on|off|dense|sparse|near|far|nodyn|debug> [1-34]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"

rem Anything after the map is forwarded verbatim to the launcher, so a run can be
rem driven unattended. It lands AFTER the arm's own cvars, so it wins -- same
rem rule as the "--" passthrough in launch-retribution-rt.cmd.
set "PASS="
set "IDX=0"
for %%A in (%*) do (
  set /a IDX+=1
  if !IDX! GEQ 3 set "PASS=!PASS! %%~A"
)
if "%ARM%"=="" set "ARM=on"
if "%MAP%"==""  set "MAP=7"

rem A LOG OF ITS OWN. rt-console.log is one file that every launch overwrites, so
rem the evidence from one run is destroyed by the next unrelated launch before it
rem can be read. +logfile comes after the launcher's own, so it wins.
set "LOG=+logfile %~dp0\..\rt-poison.log"

if /i "%ARM%"=="on"     set "ARGS=+d64_poison_fx 1 +d64_poison_rate 1    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 0"
if /i "%ARM%"=="off"    set "ARGS=+d64_poison_fx 0 +d64_poison_rate 1    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 0"
if /i "%ARM%"=="dense"  set "ARGS=+d64_poison_fx 1 +d64_poison_rate 4    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 0"
if /i "%ARM%"=="sparse" set "ARGS=+d64_poison_fx 1 +d64_poison_rate 0.25 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 0"
if /i "%ARM%"=="near"   set "ARGS=+d64_poison_fx 1 +d64_poison_rate 1    +d64_poison_dist 400  +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 0"
if /i "%ARM%"=="far"    set "ARGS=+d64_poison_fx 1 +d64_poison_rate 4    +d64_poison_dist 2200 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 0"
if /i "%ARM%"=="nodyn"  set "ARGS=+d64_poison_fx 1 +d64_poison_rate 1    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 0 +rt_dynlight 0"
if /i "%ARM%"=="debug"  set "ARGS=+d64_poison_fx 1 +d64_poison_rate 1    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 1 +rt_verbose 1"

if not defined ARGS (
  echo Usage: %~nx0 ^<on^|off^|dense^|sparse^|near^|far^|nodyn^|debug^> [1-34]
  exit /b 1
)

echo === poison arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS% %LOG% %PASS%
exit /b %ERRORLEVEL%
