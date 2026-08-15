@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Bisect a sky leak: light arriving in a room that has no lamp and looks sealed.
rem
rem Run these IN THE LEAKING ROOM, in this order. The first two arms cost nothing
rem and decide which of the two sky lights is responsible -- and they want
rem completely different fixes, so guessing here wastes the most time.
rem
rem   nosun    rt_sun 0, sky kept. Kills the MOON (directional).
rem   nosky    rt_sky 0, moon kept. Kills the DOME.
rem   dark     both off. The control: whatever light is left is NOT the sky at
rem            all, and this whole tool is the wrong tree.
rem   nowalls  everything on, but rt_sky_nowalls 1 -- the sky WALL band on
rem            two-sided lines is suppressed everywhere (the engine's own
rem            ML_NOSKYWALLS, applied to every line instead of one). If the leak
rem            dies here it is wall-class and a targeted per-line fix exists.
rem   full     everything on, the shipping configuration. Reference shot.
rem   noreq    full but rt_sun_require_sky 0 -- the STOCK, leaky behaviour. Since
rem            the fix is now on by default, this is the arm that says whether a
rem            leak is one require_sky already handles. If `noreq` leaks and
rem            `full` does not, the fix is working and there is nothing to chase.
rem   proof    full + rt_sun_leak_debug 2. Mode 2 COMPOSES with the fix -- leaks
rem            are dropped first, then survivors are painted -- so ALL RED AND NO
rem            GREEN confirms it. leak_debug is NOARCH, so it cannot stick.
rem
rem Reading it:
rem   only `nosun` fixes it  -> the MOON is finding a pinhole. A directional light
rem                             needs one unblocked shadow ray, so it exposes
rem                             cracks the dim dome never showed. Cheapest real
rem                             fix: give that map a preset with intensity 0 in
rem                             RT_MOON_PRESETS (rt_main.cpp) and it gets no moon.
rem   only `nosky` fixes it  -> the DOME, through a genuine opening. Lower rt_sky,
rem                             or close the aperture in the map data.
rem   `nowalls` fixes it     -> wall-class: the sideways sky band at a wall top.
rem                             Targeted fix is ML_NOSKYWALLS on the offending
rem                             linedefs, patched into a wad the way
rem                             tools/make_seqlight_fix.py patches maps.
rem   nothing fixes it       -> not the sky. Look at rt_sector_emis (a sector over
rem                             the per-map threshold emits), or an attached
rem                             sprite light. tools/scan_fake_lightshafts.py.
rem
rem What the map data could NOT tell us, so do not skip the bisect:
rem tools/scan_sky_apertures.py measured the two aperture classes that ARE
rem representable -- Doom sky-hack ceiling steps (916 game-wide, MAP01 has zero,
rem only 4 are under 32 units) and missing upper textures facing sky (zero,
rem game-wide). Neither explains the reported leaks, which is why there is no
rem "seal gaps under N units" knob here: there are no small gaps to seal. What is
rem left is sub-unit cracks at T-junctions, which no threshold can select.
rem
rem Every arm sets both sky cvars, rt_sky_nowalls AND rt_sun_require_sky
rem explicitly -- RT_CVARs are CVAR_ARCHIVE, so an unset one carries over from the
rem previous arm. require_sky was implicit here until it acquired a non-default
rem value worth comparing against; leaving it implicit would have made `noreq`
rem contaminate every arm run after it.
rem
rem Usage: ab-skyleak.cmd <nosun|nosky|dark|nowalls|full|noreq|proof> [1-32, default 13]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=full"
rem MAP13 is the default because it is the map most likely to show the answer:
rem it is the one carrying the moon (RT_MOON_PRESETS, azimuth 90) and it has 46
rem sky-hack gaps of its own -- min 96, median 288, max 416 units
rem (tools\scan_sky_apertures.py 13). Big, real openings, so `nowalls` will
rem visibly change its outdoor areas; that is the arm doing its job, not a leak.
if "%MAP%"==""  set "MAP=13"

if /i "%ARM%"=="nosun"   set "ARGS=+rt_sun 0 +rt_sky 25 +rt_sky_nowalls 0 +rt_sun_require_sky 1"
if /i "%ARM%"=="nosky"   set "ARGS=+rt_sun 1 +rt_sky 0  +rt_sky_nowalls 0 +rt_sun_require_sky 1"
if /i "%ARM%"=="dark"    set "ARGS=+rt_sun 0 +rt_sky 0  +rt_sky_nowalls 0 +rt_sun_require_sky 1"
if /i "%ARM%"=="nowalls" set "ARGS=+rt_sun 1 +rt_sky 25 +rt_sky_nowalls 1 +rt_sun_require_sky 1"
if /i "%ARM%"=="full"    set "ARGS=+rt_sun 1 +rt_sky 25 +rt_sky_nowalls 0 +rt_sun_require_sky 1"
if /i "%ARM%"=="noreq"   set "ARGS=+rt_sun 1 +rt_sky 25 +rt_sky_nowalls 0 +rt_sun_require_sky 0"
if /i "%ARM%"=="proof"   set "ARGS=+rt_sun 1 +rt_sky 25 +rt_sky_nowalls 0 +rt_sun_require_sky 1 +rt_sun_leak_debug 2"

if not defined ARGS (
  echo Usage: %~nx0 ^<nosun^|nosky^|dark^|nowalls^|full^|noreq^|proof^> [1-32, default 13]
  exit /b 1
)

echo === sky-leak arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo     Stand in the SAME spot for every arm - these are compared by eye.
echo     MAP13 rooms worth standing in: the west hall around (-1900, -500) and
echo     the north colonnade around (300, 770). Both take real moonlight through
echo     real windows, so a leak there is the hard case - light arriving from a
echo     direction the windows cannot explain.
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
