@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem A/B the coagulated blood pools. Maps with a blood FLOOR, from the UDMF:
rem MAP17 (39 sectors -- the big one, default here), MAP32 (12), MAP08 (9),
rem MAP18 (9), MAP21 (4), MAP23 (3), MAP24 (1), MAP34 (the fluid sampler).
rem 153 blood-floor sectors in the game.
rem
rem EVERY ARM SETS EVERY VALUE. A knob left unset silently inherits whichever
rem arm ran last, and a null result then gets blamed on the change instead of on
rem the leftover.
rem
rem EVERY ARM ALSO SETS rt_blood_autogoto 1, which puts the player on a pool on
rem the first frame. A pool is a puddle in a corner: every verdict judged from
rem the spawn point is worthless, and MAP08's nine sit at z -256 in PITS where
rem "broken" and "working, 256 units below you" are the same screenshot. That is
rem the trap that cost the poison bubbles a round.
rem
rem THREE INDEPENDENT LAYERS, and they fail in ways that look identical:
rem
rem   1. the ART      -- d64r-liquid-art.wad, built by tools\gen_liquid_art.py.
rem      A TX_ patch plus a TEXTURES lump redefining all 128 D64B1_/D64B2_
rem      frames as ONE unshifted copy of it. Not a cvar. Without the wad on the
rem      command line NOTHING below can work: the relief needs an _n to give
rem      back and the pulse needs the flow phase baked into the height map.
rem   2. the RELIEF   -- rt_blood_relief. getNormal() overwrites the
rem      normal-mapped normal with the animated water wave for ANY water
rem      surface, so an _n on a liquid is sampled, written to the G-buffer and
rem      then thrown away. This is the knob that gives it back.
rem   3. the FLOW     -- rt_blood_flow*. A FLOW MAP: a detail texture advected
rem      along the vein direction baked into the height map, so blobs of
rem      liquid slide down each channel. Texture moving, not brightness
rem      pulsing -- the first version pulsed and read as flicker.
rem
rem   on        THE DEFAULT. Full relief, flow 1.0 at 0.5 detail-tiles/s.
rem   off       relief 0 AND flow 0 -- the stylized water surface in a blood
rem             palette, i.e. what a blood pool was before any of this. The
rem             baseline to flip against. If "on" looks the same as this, the
rem             wad is not loading; check the log for "d64r-liquid-art".
rem   norelief  relief 0, flow ON. Isolates layer 3: the flow riding on the old
rem             ripple. If the motion reads here but not in "on", the relief is
rem             burying it rather than the flow being broken.
rem   noflow    relief ON, flow 0. Isolates layer 2: a still, ridged, wet
rem             surface. This is the arm for "do the veins pop".
rem   fast      flow speed 2.0, four times shipping. Not a look -- a test.
rem             Motion too slow to see and motion that is not happening are the
rem             same picture, and this tells them apart in one glance.
rem   slow      flow speed 0.08, for judging the shape of the streaks rather
rem             than their motion.
rem   hard      flow 1.4 -- full-depth contrast on the sliding detail. The arm
rem             for "I cannot see anything move".
rem   soft      flow 0.35 -- a gentle drift.
rem   coarse    flow scale 3 -- streaks twice as long. Bigger, lazier movement.
rem   fine      flow scale 12 -- streaks half as long. Busier.
rem   blobs     aspect 1 -- round blobs instead of streaks. The version-two look
rem             that read as shimmer; kept as the A/B that shows why streaks.
rem   phase     PAINTS THE ADVECTED DETAIL. Not a look -- a test, and the first
rem             one to run if nothing moves. Green blobs sliding ALONG each vein
rem             mean the bake and the plumbing both work and the problem is
rem             tuning. Flat blue means the direction never reached the shader
rem             or the detail never crossed framebufAlbedo.a; tuning cannot help.
rem   flagcheck LIQUID SURFACES PAINTED MAGENTA (rt_water_debug 1). If the pools
rem             are not magenta the stylized branch is not running on them and
rem             nothing else here can. NOTE this also paints every other surface
rem             blue -- that is the same diagnostic's caustic probe, not a bug.
rem   flat      rt_heightmap_stren 0 -- relief on, PARALLAX off. Separates "the
rem             normal map is doing the work" from "the height map is".
rem   nomirror  rt_blood_refl 0 + rt_blood_rough 0.8 -- the SLUDGE treatment,
rem             applied to blood. Two things at once: no mirror reflection of
rem             the room, and NO CHECKERBOARD SPLIT, so every pixel shades the
rem             pool at full resolution. The split is why sludge went to 0: it
rem             rebuilds half the screen columns from their neighbours, and on
rem             a high-contrast authored normal -- which blood has, at relief
rem             1 -- that pattern CRAWLS with the camera under a moving light
rem             and freezes at rest. JUDGE THIS ONE MOVING, with the
rem             flashlight on; a settled screenshot cannot show it.
rem   mirror    rt_blood_refl 1 + rough 0.1 -- the FULL water mirror, i.e.
rem             what blood shipped with before 2026-08-26. The
rem             before-picture for the 0.3 default, not the default.
rem   wet       refl 0.6, rough 0.5 -- twice the shipping mirror. The ladder
rem             is 0 (nomirror) / 0.03 (dry) / 0.3 (default) / 0.6 / 1.0
rem             (mirror). Everything above 0 keeps the split.
rem   dry       refl 0.03, rough 1.0 -- a matte clot. The far end.
rem   caustics  rt_blood_caustics 1 -- puts the PROJECTED caustics back. Blood
rem             ships with them OFF: a caustic is light refracted through a
rem             fluid and focused on what lies beyond it, so an opaque one casts
rem             none, and blood throwing rippling swimming-pool light on its own
rem             walls was the loudest single thing saying "this is water with
rem             red paint on it". This arm is the before-picture, not a look.
rem ---------------------------------------------------------------------------

set "ARM=%~1"
if "%ARM%"=="" set "ARM=on"
set "MAP=%~2"
if "%MAP%"=="" set "MAP=17"

rem Shipping values. Each arm below overrides only what it is testing, but every
rem one of these is written on every launch.
set "RELIEF=1.0"
set "FLOW=1.0"
set "SPEED=0.5"
set "SCALE=6.0"
set "ASPECT=3.0"
set "HEIGHT=1"
set "WDEBUG=0"
set "PDEBUG=0"
set "CAUST=0"
rem Shipping blood reflection: 0.3 of the stylized mirror (was 1.0 until
rem 2026-08-26 -- a pool of congealing blood is not a window into the room),
rem roughness 0 meaning "fall back to rt_water_rough" (0.1). NOTE 0.3 is above
rem zero, so the checkerboard split is still on; only "nomirror" removes it.
set "REFL=0.3"
set "ROUGH=0.0"

if /i "%ARM%"=="on"        goto :ok
if /i "%ARM%"=="off"       ( set "RELIEF=0.0" & set "FLOW=0.0" & goto :ok )
if /i "%ARM%"=="norelief"  ( set "RELIEF=0.0" & goto :ok )
if /i "%ARM%"=="noflow"    ( set "FLOW=0.0" & goto :ok )
if /i "%ARM%"=="fast"      ( set "SPEED=2.0" & goto :ok )
if /i "%ARM%"=="slow"      ( set "SPEED=0.08" & goto :ok )
if /i "%ARM%"=="hard"      ( set "FLOW=1.4" & goto :ok )
if /i "%ARM%"=="soft"      ( set "FLOW=0.35" & goto :ok )
if /i "%ARM%"=="coarse"    ( set "SCALE=3.0" & goto :ok )
if /i "%ARM%"=="fine"      ( set "SCALE=12.0" & goto :ok )
if /i "%ARM%"=="blobs"     ( set "ASPECT=1.0" & goto :ok )
if /i "%ARM%"=="phase"     ( set "PDEBUG=1" & goto :ok )
if /i "%ARM%"=="flagcheck" ( set "WDEBUG=1" & goto :ok )
if /i "%ARM%"=="flat"      ( set "HEIGHT=0" & goto :ok )
if /i "%ARM%"=="caustics"  ( set "CAUST=1" & goto :ok )
if /i "%ARM%"=="nomirror"  ( set "REFL=0.0" & set "ROUGH=0.8" & goto :ok )
if /i "%ARM%"=="mirror"    ( set "REFL=1.0" & set "ROUGH=0.1" & goto :ok )
if /i "%ARM%"=="wet"       ( set "REFL=0.6" & set "ROUGH=0.5" & goto :ok )
if /i "%ARM%"=="dry"       ( set "REFL=0.03" & set "ROUGH=1.0" & goto :ok )

echo Unknown arm "%ARM%".
echo   usage: tools\ab-bloodpool.cmd ^<on^|off^|norelief^|noflow^|fast^|slow^|hard^|soft^|coarse^|fine^|blobs^|phase^|flagcheck^|flat^|caustics^|nomirror^|mirror^|wet^|dry^> [map]
echo   maps with blood: 17 (39 pools, default) 32 (12) 08 (9, in pits) 18 21 23 24 34
exit /b 1

:ok
echo === blood pools: arm "%ARM%" on map %MAP% ===
echo     relief %RELIEF%  flow %FLOW% speed %SPEED% scale %SCALE% aspect %ASPECT%
echo     heightmap %HEIGHT%  caustics %CAUST%  water_debug %WDEBUG%  flow_debug %PDEBUG%
echo     refl %REFL%  rough %ROUGH%   (rough 0 = use rt_water_rough 0.1)
echo     the player is placed on a pool by rt_blood_autogoto.

call "%~dp0launch-retribution-rt.cmd" %MAP% -- ^
  +rt_blood_autogoto 1 ^
  +rt_blood_relief %RELIEF% ^
  +rt_blood_flow %FLOW% ^
  +rt_blood_flow_speed %SPEED% ^
  +rt_blood_flow_scale %SCALE% ^
  +rt_blood_flow_aspect %ASPECT% ^
  +rt_heightmap_stren %HEIGHT% ^
  +rt_water_debug %WDEBUG% ^
  +rt_blood_caustics %CAUST% ^
  +rt_blood_refl %REFL% ^
  +rt_blood_rough %ROUGH% ^
  +rt_blood_flow_debug %PDEBUG%
