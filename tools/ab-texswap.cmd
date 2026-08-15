@echo off
setlocal EnableExtensions EnableDelayedExpansion
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem ---------------------------------------------------------------------------
rem SFLATAS, THE CEILING LAMP PANE: how SOFT should its one light be?
rem
rem   ab-texswap.cmd soft            radius 0.06 -- the shipping pin
rem   ab-texswap.cmd crisp           radius 0.02 -- the flashlight's
rem   ab-texswap.cmd crisp 1 -- +rt_solo_lamp_intensity 200
rem
rem THE ART NOW SHIPS BY DEFAULT, so this is no longer an on/off comparison.
rem d64r-sflatas-broken.wad is in the launcher's own -file list (and in
rem package_release.py, launch-doom64-rt.cmd and shot.ps1's base list), which is
rem why there is no `off` arm any more: you cannot get the stock four-bulb pane
rem back by NOT passing something here. To see stock, drop the wad from those
rem lists -- and note the engine's SoloBulbTextures entry would then light one of
rem four intact bulbs and leave three dark, because the art and the table are a
rem pair (docs\lamp-panes-broken-bulbs.md 3).
rem
rem WHAT THE ART IS. SFLATAS paints four bulbs 32 map units apart; the cage
rem grating's openings are about 16, so four lights lay down offset copies of the
rem mesh shadow that fill in each other's gaps and the pattern cancels. Measured
rem alone in a dark room (tools\build_shadow_lab.py, MAP93):
rem
rem   1 light   crisp diamond shadows on floor, walls and ceiling
rem   4 lights  a trace, once the intensity beats the bounce fill
rem   16        nothing, at any source radius
rem
rem So three of the four bulbs are SMASHED in the art and only the survivor is
rem lit. Nothing moved: all four housings still exist, so _n/_h/_orm stay
rem authored and no sector needs panning.
rem
rem WHY RADIUS IS THE KNOB LEFT. Shadow softness scales with source size, and it
rem is very nearly a pure softness knob here -- RTGL1 sets radiance to
rem intensity/(pi r^2) while the solid angle goes as pi r^2 / d^2, so the product
rem is intensity/d^2 and the room does not change brightness with r. 0.02 is what
rem makes a 4-unit fence wire cast at all (rt-lighting-practices 34); 0.06 is
rem what is pinned, and is shared with SFLATCH -- which is the reason it has not
rem simply been lowered. If crisp is the answer, SFLATAS should earn its own pair
rem the way SFLATDE did with rt_solo_small_*.
rem
rem JUDGE, at the MAP01 cage:
rem   1. does the grating cast a readable shadow on the wall or floor?
rem   2. does the pane still read as a light fitting rather than a dead panel?
rem   3. is exactly ONE bulb per 64-unit tile lit, and is it the INTACT one? A
rem      lit patch on a smashed bulb means the SoloBulbTextures offset is wrong --
rem      a ceiling flat's world y is (64 - image y), which has caught this twice.
rem
rem Usage: ab-texswap.cmd <soft^|crisp> [map 1-32] [-- any +cvar ...]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=crisp"
if "%MAP%"==""  set "MAP=1"
if "%MAP%"=="--" set "MAP=1"
set "MAPARG=map0%MAP%"
if %MAP% GEQ 10 set "MAPARG=map%MAP%"

set "EXTRA="
set "SEEN="
for %%A in (%*) do (
  if defined SEEN set "EXTRA=!EXTRA! %%A"
  if "%%A"=="--" set "SEEN=1"
)

if not exist "%PROJ%\Doom64-Retribution\d64r-sflatas-broken.wad" (
  echo run: py -3.13 tools\gen_broken_bulb_flat.py
  exit /b 1
)

rem Intensity is stated in BOTH arms, at the shipping value, so the only thing
rem that differs is the radius. A ladder that moves brightness and softness at
rem once cannot answer either question -- that is the mistake the first density
rem ladder had to undo.
if /i "%WHICH%"=="soft" (
  set "A=+rt_solo_lamps 1 +rt_solo_lamp_radius 0.06 +rt_solo_lamp_intensity 100"
) else if /i "%WHICH%"=="crisp" (
  set "A=+rt_solo_lamps 1 +rt_solo_lamp_radius 0.02 +rt_solo_lamp_intensity 100"
) else (
  echo Usage: %~nx0 ^<soft^|crisp^> [map] [-- any +cvar ...]
  exit /b 1
)
set "A=%A% +rt_solo_lamp_stride 1 +rt_solo_lamp_max 384"

rem Through shot.ps1 -Play rather than launch-retribution-rt.cmd, because the
rem launcher's passthrough lands AFTER its own -file list. Nothing extra needs
rem loading now that the art ships, but keeping one entry point means what you
rem walk around in is exactly what the captures were taken from.
echo === sflatas: %WHICH% %MAPARG% !EXTRA! ===
echo     judge: 1) fence shadow  2) still reads as a lamp  3) ONE lit bulb per tile, the INTACT one
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0shot.ps1" -Play -Map %MAPARG% -Extra "%A%!EXTRA!"
exit /b %ERRORLEVEL%
