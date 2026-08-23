@echo off
setlocal EnableExtensions
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem ---------------------------------------------------------------------------
rem PILLAR LAB -- MAP01's pre-exit pillar alone in a room. MAP94 dark, MAP95 lit.
rem
rem Build the maps first:
rem   tools\.venv-ai\Scripts\python.exe tools\build_pillar_lab.py
rem
rem WHY THIS EXISTS. rt_pillar_chase logged `chased=6` with its multiplier
rem swinging 0.35..1.00 every lap, and showed NOTHING on screen. The instrument
rem said working, the eye said not. In MAP01's hall that is unreadable: twelve
rem wall strips, a bulb lattice, faux panels, a moon and a level of emissive GI
rem are all candidates for whatever you are actually looking at.
rem
rem THE FIRST THING TO READ IS THE LOG, NOT THE SCREEN. rt-pillar-lab.log:
rem
rem   uploaded=4 ... chased=4 | winding-flipped=4
rem      the four panels matched, the chase is scaling them, and the winding fix
rem      rescued all four from the centrespot test. This is the healthy line.
rem   uploaded=0
rem      the minlight gate ate them. The ring is at 150 against
rem      rt_wall_strip_minlight 120, so this means the arm did not apply.
rem   chased=0 with uploaded=4
rem      the lights are placed but kChasePillars did not match. Check that the
rem      map is MAP94/MAP95 and that the ring still carries tag 29.
rem   winding-flipped=0
rem      you are running an engine built BEFORE the fix. The panels are one-sided
rem      walls on a RING sector, so all four must flip.
rem
rem   dark    MAP94 -- room at lightlevel 64. Nothing in the map can light the
rem           walls except the four bulb panels, so whatever lands on them is
rem           theirs. THE room for "is the light escaping the pillar at all".
rem   lit     MAP95 -- room at 150. Read the chase as a SHAPE rather than as a
rem           presence: does the bright face travel, and in which direction.
rem   off     dark room, rt_pillar_chase 0. The control: four static panels.
rem   hard    floor 0.12, width 100 -- one face clearly THE lit one at any moment.
rem           If `chase` reads as breathing rather than turning, this says whether
rem           the shape is right and only the contrast is wrong.
rem   slow    period 6s. For deciding DIRECTION, which 1.83s is too quick to call.
rem   ccw     the same, reversed. The shipping direction is clockwise because
rem           script 12 steps tag 20 -> 21 -> 22... and those sit at DECREASING
rem           angles around the pillar.
rem   marks   magenta marker spheres at every light position, chase off. If the
rem           markers are visible the placement is fine and the problem is
rem           elsewhere; if they are inside the pillar you are looking straight
rem           at the bug this lab was built for.
rem   bulbsoff  rt_pillar_chase_bulbs 0 -- the analytic lights sweep, the PAINTED
rem           bulbs stay lit at full strength. This is the state the feature
rem           shipped in first, and the reason it read as "nothing is turning":
rem           four permanently-on lamps with a light moving somewhere behind them.
rem   bulbsonly the reverse control: chase_floor 1.0, so the analytic lights hold
rem           STILL and only the painted bulbs switch. Says how much of the effect
rem           each half is carrying, which "both at once" cannot.
rem   bulbsdead bulb_floor 0 at 6s. An unlit bulb goes fully black -- watch for it
rem           reading as a HOLE in the panel rather than a lamp that is out. That
rem           is why the shipping floor is 0.05 and not 0.

rem   sphere  rt_pillar_chase_spot 0 -- panel lights back to spheres sitting ON the
rem           panel. A 0.35 m sphere is 11.2 map units at 2 units off a 32-unit
rem           face, so the panel is INSIDE its own light and clips white at every
rem           point in the cycle. This is why the bulbs read as always-on. The
rem           before shot for the spot fix.
rem   nolights rt_wall_strip_intensity 0 -- no analytic lights at all, bulbs still
rem           chasing. THE DECISIVE ONE. If the bulbs switch here and not in
rem           `sphere`, the self-lighting is what was hiding them and nothing is
rem           wrong with the emissive path.

rem   screenraw rt_pillar_chase_bulb_screen 0 -- RTGL1 back to using the RAW _e
rem           sample on the primary ray, which is its normal rule. The chase runs,
rem           the bulbs never change. This is how the feature shipped TWICE before
rem           anyone read HitInfo.inl, and it is the before shot for the flag.

rem   spot    rt_pillar_chase_spot 1 -- panel lights aimed off the wall instead of
rem           sitting on it. Keeps the panel out of its own light, but LOSES the
rem           pool at the base: RTGL1 clamps a spot cone to 89 degrees so it cannot
rem           express a hemisphere, and the floor is at about 90 from a horizontal
rem           axis. Off by default for exactly that reason.
rem   pushed  spheres, but standing 14 units off the panel instead of 2. The middle
rem           ground: the panel stops being swallowed by its own 11.2-unit emitter
rem           and the floor still gets lit. Try this if the panel albedo washes out.

rem   nogi    rt_pillar_chase_bulb_gi 1 -- the panels feed the GI at 1 instead of the
rem           material's 20. The room goes dark with only the four spheres left:
rem           the before shot for "no more light cast", and the proof that the
rem           PANELS, not the spheres, are most of what this fixture casts.

rem   lag0    lagsec 0 -- bulbs and lights on the identical crest, no hold-back.
rem           The bulbs should read as running AHEAD of the light: the pool
rem           arrives late through the denoiser history, the painted bulb does
rem           not. This is the before shot for rt_pillar_chase_bulb_lagsec.
rem   lag045  lagsec 0.45 / lag080 lagsec 0.8 -- bracket the shipping 0.6. Found
rem   lag080  by eye: 25 degrees (0.13 s) still led by about half a second, so
rem           the propagation delay is near 0.6 s. If 0.6 trails, try 0.45; if
rem           it still leads, 0.8.
rem   slowlag0 period 6 s, lag 0. THE TEST OF THE THEORY: a denoiser lag is a
rem           fixed number of FRAMES, so at a 3.3x longer lap it is 3.3x fewer
rem           degrees and the mismatch should mostly vanish on its own. If the
rem           bulbs still lead by the same angle here, it is not lag and the
rem           cvar is the wrong fix.

rem   buried  THE BUG ON PURPOSE: rt_wall_strip_winding 0 restores the old
rem           centrespot nudge, which puts all four lights in the void core.
rem           The before shot. Expect the panels to go dead.
rem
rem Anything after "--" is appended verbatim and wins, for one-off overrides.
rem
rem Usage: pillar-lab.cmd [dark|lit|off|hard|slow|ccw|marks|buried|bulbsoff|bulbsonly|bulbsdead|sphere|nolights|screenraw|spot|pushed|nogi|lag0|lag045|lag080|lag120|slowlag0] [-- +cvar val ...]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
if "%ARM%"=="" set "ARM=dark"

set "EXTRA="
set "SEEN="
for %%A in (%*) do (
  if defined SEEN ( call set "EXTRA=%%EXTRA%% %%~A" ) else ( if "%%~A"=="--" set "SEEN=1" )
)

rem The IWAD comes from the same environment variable the main dev launcher
rem uses, so this file carries no machine-specific path.
set "IWAD=%D64RT_IWAD%"
if not defined IWAD set "IWAD=D:\Games\GZDoom\doom2.wad"
set "BUILD=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "D64=%PROJ%\Doom64-Retribution"

rem Every arm states EVERY chase value. These cvars are CVAR_ARCHIVE, so an arm
rem that sets only what it changes inherits the rest from whatever the previous
rem run left in the ini -- which is how an A/B quietly stops being one.
set "BASE=+rt_wall_strips 1 +rt_wall_strip_intensity 180 +rt_wall_strip_minlight 120 +rt_wall_strip_seglen 64 +rt_wall_strip_radius 0.35 +rt_wall_strip_debug 1 +rt_wall_strip_debug_marks 0 +rt_wall_strip_winding 1 +rt_pillar_chase_cw 1 +rt_pillar_chase_debug 1 +rt_pillar_chase_bulbs 1 +rt_pillar_chase_bulb_emis 1.0 +rt_pillar_chase_bulb_gi 50 +rt_pillar_chase_bulb_lagsec 0.6 +rt_pillar_chase_bulb_screen 1 +rt_pillar_chase_bulb_floor 0.05 +rt_pillar_chase_spot 0 +rt_pillar_chase_lightofs 2 +rt_pillar_chase_spot_outer 88 +rt_pillar_chase_spot_inner 0"

set "MAP=MAP94"
set "ARGS="
if /i "%ARM%"=="dark"   set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140"
if /i "%ARM%"=="lit"    set "MAP=MAP95" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140"
if /i "%ARM%"=="off"    set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 0 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140"
if /i "%ARM%"=="hard"   set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.12 +rt_pillar_chase_width 100"
if /i "%ARM%"=="slow"   set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 6.0 +rt_pillar_chase_floor 0.12 +rt_pillar_chase_width 100"
if /i "%ARM%"=="ccw"    set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 6.0 +rt_pillar_chase_floor 0.12 +rt_pillar_chase_width 100 +rt_pillar_chase_cw 0"
if /i "%ARM%"=="marks"  set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 0 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_wall_strip_debug_marks 1"
if /i "%ARM%"=="bulbsoff" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_bulbs 0"
if /i "%ARM%"=="bulbsonly" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 1.0 +rt_pillar_chase_width 140"
if /i "%ARM%"=="bulbsdead" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 6.0 +rt_pillar_chase_floor 0.12 +rt_pillar_chase_width 100 +rt_pillar_chase_bulb_floor 0.0"

if /i "%ARM%"=="sphere" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_spot 0"
if /i "%ARM%"=="nolights" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_wall_strip_intensity 0"

if /i "%ARM%"=="screenraw" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_bulb_screen 0"

if /i "%ARM%"=="spot" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_spot 1"
if /i "%ARM%"=="pushed" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_lightofs 14"

if /i "%ARM%"=="nogi" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_bulb_gi 1"

if /i "%ARM%"=="lag0" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_bulb_lagsec 0"
if /i "%ARM%"=="lag045" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_bulb_lagsec 0.45"
if /i "%ARM%"=="lag080" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_bulb_lagsec 0.8"

if /i "%ARM%"=="lag120" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_bulb_lagsec 1.2"
if /i "%ARM%"=="slowlag0" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 6.0 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_pillar_chase_bulb_lagsec 0"

if /i "%ARM%"=="buried" set "MAP=MAP94" & set "ARGS=%BASE% +rt_pillar_chase 1 +rt_pillar_chase_period 1.83 +rt_pillar_chase_floor 0.35 +rt_pillar_chase_width 140 +rt_wall_strip_winding 0"

if not defined ARGS (
  echo Usage: %~nx0 ^[dark^|lit^|off^|hard^|slow^|ccw^|marks^|buried^|bulbsoff^|bulbsonly^|bulbsdead^|sphere^|nolights^|screenraw^|spot^|pushed^|nogi^|lag0^|lag045^|lag080^|lag120^|slowlag0^] ^[-- +cvar val ...^]
  exit /b 1
)

if not exist "%D64%\d64rpillarlab.wad" (
  echo ERROR: %D64%\d64rpillarlab.wad missing.
  echo        Build it:  tools\.venv-ai\Scripts\python.exe tools\build_pillar_lab.py
  exit /b 1
)

echo === pillar lab: arm "%ARM%", %MAP% ===
echo     %ARGS%
if defined EXTRA echo     extra: %EXTRA%
echo.
echo     Read rt-pillar-lab.log FIRST. The line that matters:
echo       uploaded=4 ... chased=4 ^| winding-flipped=4
echo.

rem THE WORKING DIRECTORY IS NOT OPTIONAL. The RT build resolves rt/wad, rt/bin
rem and rt/data relative to the CWD, so running gzdoom.exe by full path from
rem anywhere else dies with "Can't find rt/wad directory" before it reaches a
rem log. The exe is still called by FULL PATH: this environment runs with
rem NoDefaultCurrentDirectoryInExePath, so "gzdoom.exe" alone is not found even
rem standing in its own directory. Both halves are needed.
cd /d "%BUILD%"
if errorlevel 1 ( echo ERROR: cannot cd to %BUILD% & exit /b 1 )

rem D64RTR carries the SFLATAQ / SPACEAA / SPACEAG / SPACEAB entries the lab's
rem geometry names, so it must load before the lab wad.
rem
rem A SHORT COMMAND LINE on purpose -- the full launcher's ~325 pins put the
rem assembled line over cmd.exe's 8191-char limit and silently truncate the
rem passthrough at the end. The pins are exec'd from a file instead.
"%BUILD%\gzdoom.exe" -iwad "%IWAD%" ^
  -file "%D64%\D64RTR_v15.WAD" "%D64%\d64rpillarlab.wad" ^
  +exec "%~dp0d64rt-pins.cfg" ^
  +logfile "%PROJ%\rt-pillar-lab.log" ^
  +vid_fullscreen 0 +vid_defwidth 960 +vid_defheight 540 +win_x 0 +win_y 0 ^
  +i_pauseinbackground 0 +rt_verbose 1 ^
  %ARGS% +map %MAP% %EXTRA%

exit /b %ERRORLEVEL%
