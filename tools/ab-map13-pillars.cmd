@echo off
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem MAP13 courtyard pillars — "they get illuminated regularly".
rem
rem The pillars are the H119 sectors 47-52, 61-69. Ruled out from the map data, so do
rem not re-check these:
rem   - lightlevel is a constant 200; no sector special, no tag
rem   - no ACS light call reaches them (MAP13's three are on tags 7, 30, 31)
rem   - no linedef special touches any of them
rem   - no 9801/9802 pulsing light thing exists anywhere on MAP13
rem   - no cloud deck (MAP13 has no RT_CLOUD_PRESETS entry, launcher pins rt_clouds 0),
rem     so the moon is not being modulated
rem   - no lightning (it fires only on maps carrying the MAPINFO `lightning` keyword;
rem     MAP13 does not)
rem
rem So the sector is not animating -- something is LIGHTING them periodically. The one
rem time-varying light source within range is FLAME FLICKER: rt_flame_light_flicker is
rem 0.15 at rt_flame_light_speed 0.25, i.e. slow, and six 64WallTorchRed stand 341-499
rem units from the pillars. They are the nearest large vertical surfaces to those
rem torches, which is why the effect could land on them and not on the dark courtyard
rem floor.
rem
rem Two runs answer it. Everything else is pinned identically in every arm, so a
rem difference between runs is the arm and nothing else.
rem
rem   base       as shipped
rem   noflicker  rt_flame_light_flicker 0   -- flames become STEADY lights, same brightness
rem   noflame    rt_flame_light_on 0        -- no flame lights at all
rem   nodyn      rt_dynlight 0              -- no GZDoom light things either
rem   flat       all light animation off
rem
rem rt_lightlevel_watch 1 is the instrument that matters now: it prints EVERY sector
rem whose lightlevel moves, as it moves -- 'sector 126: 200 -> 255'. No texture name
rem needed, no filtering, so it cannot be pointed at the wrong surface and read as a
rem null. Stand where the pillars flicker, watch them do it a few times, quit, and send
rem the log.
rem
rem   lines appear  -> the sector IS being animated, and the line names which one and
rem                    by how much, which identifies the mechanism immediately
rem   NOTHING       -> no sector is changing. The pulse is then a LIGHT or the
rem                    denoiser, and that is a real answer rather than another guess.
setlocal EnableExtensions
set "ARM=%~1"
if "%ARM%"=="" set "ARM=base"

rem NOTE: rt_sun_intensity is pinned to 90 by the base launcher, not 1. An arm that
rem "restores" it to 1 would silently darken the map and invalidate the comparison.
set "X="
if /i "%ARM%"=="base"      set "X=+rt_flame_light_on 1 +rt_flame_light_flicker 0.15 +rt_dynlight 1"
if /i "%ARM%"=="noflicker" set "X=+rt_flame_light_on 1 +rt_flame_light_flicker 0    +rt_dynlight 1"
if /i "%ARM%"=="noflame"   set "X=+rt_flame_light_on 0 +rt_flame_light_flicker 0    +rt_dynlight 1"
if /i "%ARM%"=="nodyn"     set "X=+rt_flame_light_on 1 +rt_flame_light_flicker 0.15 +rt_dynlight 0"
if /i "%ARM%"=="flat"      set "X=+rt_flame_light_on 0 +rt_flame_light_flicker 0    +rt_dynlight 0"
if not defined X (
  echo Usage: %~nx0 [base^|noflicker^|noflame^|nodyn^|flat]
  exit /b 1
)

echo MAP13 pillars — arm: %ARM%
echo   %X%
call "%~dp0launch-retribution-rt.cmd" 13 -- ^
  +logfile "%PROJ%\rt-map13-pillars-%ARM%.log" ^
  +rt_tex_probe H119 +rt_lightlevel_watch 1 %X%
