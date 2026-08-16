@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem EDGE LAB -- unattended capture of the "black outlines behind volumetrics"
rem bug (README, Known issues) on MAP93.
rem
rem Build the map first:  python tools\build_edge_lab.py
rem
rem   .\tools\edge-lab.cmd            the repro: a wide, lit smoke curtain
rem   .\tools\edge-lab.cmd off        the control: same frame, rt_smoke 0
rem   .\tools\edge-lab.cmd -- +rt_volume_depthgate 0     one-off overrides
rem
rem It runs ~4 s of game time and quits itself (tools\shot.ps1, see
rem docs\scripted-screenshots.md -- `wait` only defers the REST OF THE SAME
rem command string, which is why the sequence is one quoted argument).
rem
rem THE SMOKE VALUES ARE NOT DEFAULTS AND THAT IS THE POINT. Three things had to
rem be forced before the artefact filled a frame, each of which cost a capture:
rem
rem   rt_smoke_perweapon 0  -- autospawn takes the READY WEAPON's profile, and
rem                            the player spawns holding a pistol, whose row
rem                            multiplies the radius by 0.07. Puffs came out at
rem                            6 cm, well under a froxel, and read as nothing at
rem                            all while the debug log happily reported 128 live
rem                            puffs. The identity profile makes rt_smoke_*
rem                            mean what it says.
rem   density 3, not 14     -- the curtain has to be SEEN THROUGH. At shipping
rem                            density a spread this wide is an opaque wall and
rem                            there are no edges behind it to outline.
rem   a BRIGHT hall         -- smoke is a luminous veil, so what decides whether
rem                            the edges still read is contrast, not opacity. At
rem                            the first version's lightlevel 120 the room was
rem                            darker than the smoke and every density from 2 to
rem                            8 gave the same flat grey frame.
rem ---------------------------------------------------------------------------

for %%I in ("%~dp0..") do set "PROJ=%%~fI"
set "SHOTS=%PROJ%\tools\_edgelab"

set "ARM=%~1"
if /I "%ARM%"=="off" (
  rem THE CONTROL. Same room, same lights, same frame -- no medium. Without it
  rem "there are lines around the sprites" is unattributed: this is what proves
  rem they are the volumetric and not the lighting or the sprite materials.
  set "SMOKE=+rt_smoke 0 +rt_smoke_autospawn 0"
) else (
  set "SMOKE=+rt_smoke_perweapon 0 +rt_smoke_autoweapon 0 +rt_smoke_autospawn 2 +rt_smoke_radius 1.0 +rt_smoke_growth 0.45 +rt_smoke_life 2.5 +rt_smoke_density 3 +rt_smoke_speed 1.0 +rt_smoke_spread 1.4 +rt_smoke_rise 0.4 +rt_smoke_budget 128"
)

rem Anything after "--" is appended verbatim and wins, for one-off arms
rem (+rt_volume_depthgate 0, +rt_volume_dither 0, ...).
set "EXTRA="
set "SEEN="
for %%A in (%*) do (
  if defined SEEN ( call set "EXTRA=%%EXTRA%% %%~A" ) else ( if "%%~A"=="--" set "SEEN=1" )
)

rem rt_flsh 0 explicitly: the flashlight is a lamp AT the eye, and a lamp inside
rem the curtain blows the whole frame to white. Same reason the map's own warm
rem lamp had to move 10 m out to the sides.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJ%\tools\shot.ps1" ^
  -Map map93 -Tics 150 ^
  -ExtraFiles "d64redgelab.wad,d64r-edgelab-mapinfo.pk3" ^
  -OutDir "%SHOTS%" ^
  -LogFile "%SHOTS%\edge-lab.log" ^
  -Extra "+rt_flsh 0 %SMOKE% %EXTRA%"

exit /b 0
