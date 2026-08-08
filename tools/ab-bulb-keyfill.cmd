@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Key/fill split: a bright room AND readable shadows, the way raster gets both.
rem
rem The problem this solves. Tuning lamp intensity alone always loses: high
rem values make the room too bright, low values lose the shadows. That is not a
rem tuning failure, it is structural -- the lamps are doing BOTH jobs at once, so
rem the same number controls the room's brightness and its shadow contrast.
rem
rem Raster does not have that problem because the two are separate systems:
rem sector lightlevel is flat ambient that casts nothing, and dynamic lights add
rem the shadowed contribution on top. A shadow there reads as "less light" in an
rem already-bright room, never as black.
rem
rem The same split exists here, for a reason usually written up as a limitation.
rem Section 12: an emissive surface is NOT a light source in RTGL1 -- emission is
rem collected only when an indirect bounce ray happens to land on it, never
rem through processDirectIllumination, so it can never cast a pool of light or a
rem shadow at any strength. That makes it a perfect ambient term:
rem
rem   KEY  = the bulb lamps. Few, point-like (small radius), shadow-casting.
rem   FILL = rt_sector_emis x rt_emis_mapboost. Brightness that physically
rem          CANNOT erase a shadow edge.
rem
rem So tune the RATIO. Push fill up until the room is bright enough, then set key
rem purely for how strong you want the shadows -- the two stop fighting.
rem
rem The cost of fill, and why it is not free: emission at 1 spp indirect is weak,
rem noisy and directionless (section 12 again), and section 16 records what too
rem much of it looks like -- "uniformly bright and directionless: the fake, not
rem ray traced look". So the arms walk fill up in steps rather than jumping to it.
rem
rem ARMS            key I    fill emis   mapboost
rem   keyonly        360      0.00        200      today's behaviour, for reference
rem   lowfill        300      0.25        200
rem   midfill        220      0.40        200      expected landing spot
rem   highfill       160      0.55        200      most raster-like; watch for flat
rem   flatcheck      100      0.70        200      deliberately too far, to SEE the
rem                                                failure mode section 16 names
rem
rem Radius, spacing and shadow samples are FIXED across every arm, so the only
rem thing moving is the key/fill balance.
rem
rem Judge:
rem   1. is the room bright enough WITHOUT the lamps being cranked?
rem   2. is there a readable shadow behind the fence -- grey, not black, is the
rem      target. Raster shadows are not black either.
rem   3. at the high-fill end, has the image gone flat and directionless? That is
rem      the failure mode, and it arrives before the room gets too bright.
rem
rem Usage: ab-bulb-keyfill.cmd <keyonly^|lowfill^|midfill^|highfill^|flatcheck> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=midfill"
if "%MAP%"==""  set "MAP=1"

if /i "%WHICH%"=="keyonly" (
  set "I=360" & set "EMIS=0.00"
) else if /i "%WHICH%"=="lowfill" (
  set "I=300" & set "EMIS=0.25"
) else if /i "%WHICH%"=="midfill" (
  set "I=220" & set "EMIS=0.40"
) else if /i "%WHICH%"=="highfill" (
  set "I=160" & set "EMIS=0.55"
) else if /i "%WHICH%"=="flatcheck" (
  set "I=100" & set "EMIS=0.70"
) else (
  echo Usage: %~nx0 ^<keyonly^|lowfill^|midfill^|highfill^|flatcheck^> [map 1-32]
  exit /b 1
)

rem Fixed in every arm: a point-like source is what makes the fence's thin wires
rem cast at all (the flashlight casts at 0.02 = 0.64 map units; 0.35 = 11.2 does
rem not), and shadow_samples 8 keeps that sharp shadow from reading as speckle.
set "FIXED=+rt_wall_strip_radius 0.05 +rt_ceiling_edge_radius 0.05"
set "FIXED=%FIXED% +rt_wall_strip_seglen 128 +rt_ceiling_edge_seglen 128"
set "FIXED=%FIXED% +rt_shadow_samples 8"

set "ARGS=+rt_wall_strip_intensity %I% +rt_ceiling_edge_intensity %I%"
set "ARGS=%ARGS% +rt_sector_emis %EMIS% +rt_emis_mapboost 200"
set "ARGS=%ARGS% %FIXED% +rt_ceiling_edge_debug 1"

echo === key/fill: %WHICH% (lamp I=%I%, sector_emis=%EMIS%), MAP%MAP% ===
echo     %ARGS%
echo     judge: 1) room bright enough  2) shadow readable and GREY not black  3) still directional?
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
