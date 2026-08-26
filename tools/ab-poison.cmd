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
rem   2. the LIGHT   -- a ZScript A_AttachLight with LF_DONTLIGHTSELF, scaled by
rem      d64_poison_light. Since 2026-08-26 that is the ONLY light a bubble
rem      throws: lightIntensity in rt/data/textures.json is 0 on every frame,
rem      the same thing the game's 84 flame sprites do. A meta light sits inside
rem      a 20-unit billboard at zero distance from it, so it lights the sprite
rem      into a white pill AND cannot be tuned; LF_DONTLIGHTSELF fixes the first
rem      and being a cvar fixes the second.
rem
rem      DO NOT CONFUSE IT WITH HOW BRIGHT THE SPRITE LOOKS. That is
rem      emissiveMult in the meta -- screen glow, casts nothing, and NOT a cvar,
rem      because a tinted sprite is a different RTGL1 material with no
rem      textures.json entry. It is a rebuild:
rem
rem        tools/.venv-ai/Scripts/python.exe tools/gen_poison_fx.py --apply --emis 0.6
rem
rem      "d64_poison_light does nothing and the bubbles are too bright" was both
rem      of those at once: the cvar moved the minor term while the meta, which
rem      had been silently wiped from textures.json for weeks, came back
rem      calibrated like a LAVA SPARK.
rem
rem   on      the default: rate 2, so 6 bubbles every 9 tics inside 1100
rem           units.
rem   off     d64_poison_fx 0. The A/B for "is that green coming from the
rem           bubbles or from the flat's own emissive".
rem   dense   4x the shipping rate (8). Too many on purpose -- use it to see the shape of one
rem           bubble's life without waiting for the next.
rem   sparse  1/4 the shipping rate (0.5).
rem   near    draw distance 400. The bubbles crowd around you and the far half
rem           of the lake goes still, which is what the default trades away.
rem   far     draw distance 2200 at 4x the shipping rate. Distance and rate are NOT
rem           independent: doubling the radius quadruples the area, so the rate
rem           has to go up with it or the near field visibly thins out.
rem   nodyn   rt_dynlight 0. GLOBAL -- it kills every dynamic light in the game,
rem           not just these. This is the arm that found the white-pill blowout:
rem           the bubbles kept glowing and kept tinting the pool with it off,
rem           which proved the sprite meta was carrying the light on its own.
rem   debug   d64_poison_debug 1 + rt_verbose 1 -- prints the sector count and
rem           the first three spawn positions on screen and to the log.
rem   roof    the 3D-FLOOR GATE on (shipping), debug on so the log names how many
rem           samples were thrown away as roofed.
rem   noroof  d64_poison_roofgate 0 -- the BEFORE picture, screen/poison3Dfloor.png.
rem
rem BUBBLES ON TOP OF A BRIDGE (screen/poison3Dfloor.png, MAP07 by the exit). Two
rem nukage sectors in the whole game have a solid 3D floor over them, sec164 and
rem sec202, and both fluids sit at z -174 under slabs whose tops are at 42 and
rem 102 -- 144 UNITS of clearance. The bubble was never lifted onto the deck
rem (Actor.Spawn sets FFCF_3DRESTRICT, which disables the step-up branch, and the
rem rise totals about 3 units); it was drawn THROUGH it. The spawner now refuses
rem a sample that a solid rover stands over. Judge it standing ON the deck by the
rem EXIT signs:
rem
rem   .\tools\ab-poison.cmd noroof 7     green dots on the metal
rem   .\tools\ab-poison.cmd roof   7     a clean deck
rem
rem and MAP34 is the regression control -- its 16 rovers are not over liquid, so
rem "roofed" must read 0 there. The isolated version of the same test, with an
rem ordinary prop under the deck as a control, is .\tools\poison-lab.cmd bridge.
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
rem The d64_poison_* A/B cvars are declared NOSAVE in the pk3's CVARINFO, so an
rem arm cannot leak into the next run through the ini. Every arm still sets all
rem of them explicitly.
rem
rem d64_poison_bubbles IS THE EXCEPTION, and it is ARCHIVED: it is the player's
rem setting, driven by Options > Effects, and a setting that forgets itself on
rem quit is broken. Which is exactly why every arm here pins it to 1 -- otherwise
rem a machine where someone turned the effect off in the menu runs every A/B
rem below against no bubbles at all, and blames the arm.
rem
rem Usage: ab-poison.cmd <on|off|dense|sparse|near|far|nodyn|debug|roof|noroof> [1-34]
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

if /i "%ARM%"=="on"     set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 0 +d64_poison_roofgate 1 +d64_poison_bubbles 1"
if /i "%ARM%"=="off"    set "ARGS=+d64_poison_fx 0 +d64_poison_rate 2    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 0 +d64_poison_roofgate 1 +d64_poison_bubbles 1"
if /i "%ARM%"=="dense"  set "ARGS=+d64_poison_fx 1 +d64_poison_rate 8    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 0 +d64_poison_roofgate 1 +d64_poison_bubbles 1"
if /i "%ARM%"=="sparse" set "ARGS=+d64_poison_fx 1 +d64_poison_rate 0.5  +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 0 +d64_poison_roofgate 1 +d64_poison_bubbles 1"
if /i "%ARM%"=="near"   set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2    +d64_poison_dist 400  +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 0 +d64_poison_roofgate 1 +d64_poison_bubbles 1"
if /i "%ARM%"=="far"    set "ARGS=+d64_poison_fx 1 +d64_poison_rate 8    +d64_poison_dist 2200 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 0 +d64_poison_roofgate 1 +d64_poison_bubbles 1"
if /i "%ARM%"=="nodyn"  set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 0 +d64_poison_roofgate 1 +d64_poison_bubbles 1 +rt_dynlight 0"
if /i "%ARM%"=="debug"  set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 1 +d64_poison_roofgate 1 +d64_poison_bubbles 1 +rt_verbose 1"
if /i "%ARM%"=="roof"   set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 1 +d64_poison_bubbles 1 +rt_verbose 1 +d64_poison_roofgate 1"
if /i "%ARM%"=="noroof" set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2    +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_light 1 +d64_poison_lsize 16 +d64_poison_debug 1 +d64_poison_bubbles 1 +rt_verbose 1 +d64_poison_roofgate 0"

if not defined ARGS (
  echo Usage: %~nx0 ^<on^|off^|dense^|sparse^|near^|far^|nodyn^|debug^|roof^|noroof^> [1-34]
  exit /b 1
)

echo === poison arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS% %LOG% %PASS%
exit /b %ERRORLEVEL%
