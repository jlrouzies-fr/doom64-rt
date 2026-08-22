@echo off
setlocal EnableExtensions
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem ---------------------------------------------------------------------------
rem POISON LAB -- one pool of nukage you stand at the edge of, MAP90/MAP91.
rem
rem Build the maps first:
rem   tools\.venv-ai\Scripts\python.exe tools\build_poison_lab.py
rem
rem WHY THIS EXISTS. The bubbles were judged on MAP07, and MAP07 cannot answer
rem the question. Its nukage is at z = -256 in pits: the spawner logged bubbles
rem 583-810 units away and 256 units BELOW the player, where a 20-unit sprite is
rem two pixels. "It does not work" and "it works and you cannot see it" produce
rem the identical screenshot there. The lab puts the surface at eye level, 128
rem units in front of you, in a room with nothing else in it.
rem
rem THE PROBE ROW IS THE FIRST THING TO READ. Six static bubbles, one locked to
rem each frame, stand down the WEST walkway -- turn left. (They started in front
rem of the spawn, and at 72 units a 20-unit sprite covered the pool; auditing the
rem frames and judging the effect do not want the same shot.) They are the
rem control the spawner cannot give you:
rem
rem   six green bubbles      -> the sprites load, the grAb offsets are right, and
rem                             whatever is wrong is the SPAWNER or the water
rem                             surface, not the art.
rem   six "!" placeholders   -> GZDoom never found sprites/PBUB*.png. Nothing
rem                             downstream matters until that is fixed.
rem   nothing at all         -> the pk3 is not loaded, or ZSCRIPT failed. Check
rem                             rt-poison-lab.log for a script error before
rem                             touching anything else.
rem
rem   dark    MAP90 -- lightlevel 0, NOT ONE light thing. Whatever green lands
rem           on the wall came from a bubble. This is the room for the LIGHT.
rem   lit     MAP91 -- lightlevel 160 + a ceiling grid. Read the sprite as a
rem           SHAPE: size, growth, whether the burst reads as a burst.
rem   nowater THE FIRST SUSPECT. rt_water_liquids 0, so the nukage is NOT
rem           tagged RG_MESH_PRIMITIVE_WATER. The RT log shows every D64N1
rem           frame being tagged as water, and a sprite spawned one unit above
rem           a water surface may be occluded by it. If the bubbles appear here
rem           and nowhere else, that is the bug and it is a renderer question,
rem           not a ZScript one.
rem   dense   4x the shipping rate (8), lit room. Use it when you want to see the whole life
rem           of a bubble without waiting for the next one.
rem   still   rate 0 -- only the probe row, nothing spawning. The cleanest look
rem           at the six frames on their own.
rem   big     d64_poison_size 0.7, small 0.25, against a shipping 0.35. The
rem   small   scale is ABSOLUTE -- 1 is the sprite at its drawn 20 px -- so
rem           these numbers keep meaning the same thing across retunes. The
rem           probe row does NOT scale with
rem   small   it -- the probes are the reference for the AUTHORED size, and a
rem           reference that moves with the thing being measured is no
rem           reference. Compare the pool against the row.
rem   sunk    d64_poison_z -6, so the bubbles break the fluid plane instead of
rem           resting on it. The sprite is bottom-anchored, so this is the
rem           direction that reads as "coming out of" the poison.
rem   channel MAP92 -- a 192-unit CORRIDOR of poison instead of a lake, which is
rem           the shape the real maps have. A lake hides the sampler's failure
rem           mode: samples that miss the poison are thrown away, and on a
rem           corridor nearly all of them miss. Test any spawner change here,
rem           not on MAP91.
rem   grey    d64_poison_sat 0 -- the bubbles go grey while the pool stays
rem   vivid   green. The control for "where is the green coming from". vivid is
rem           sat 2, roughly the original art, which read as too saturated
rem           against the poison; shipping (1) is matched to the rendered pool.
rem   nodyn   rt_dynlight 0 in the dark room. GLOBAL, so it kills every dynamic
rem           light in the game. This is the arm that found the white-pill
rem           blowout: the bubbles kept glowing and kept tinting the pool with
rem           it off, which proved the sprite meta was carrying the light and
rem           the per-frame GLDEFS lights were pure loss. They are gone now.
rem
rem Anything after "--" is appended verbatim and wins, for one-off overrides.
rem
rem Usage: poison-lab.cmd [dark|lit|channel|nowater|dense|still|big|small|sunk|grey|vivid|nodyn] [-- +cvar val ...]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
if "%ARM%"=="" set "ARM=lit"

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

set "MAP=MAP91"
set "ARGS="
if /i "%ARM%"=="dark"    set "MAP=MAP90" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 1"
if /i "%ARM%"=="lit"     set "MAP=MAP91" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 1"
if /i "%ARM%"=="nowater" set "MAP=MAP91" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 1 +rt_water_liquids 0"
if /i "%ARM%"=="dense"   set "MAP=MAP91" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 8 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 1"
if /i "%ARM%"=="still"   set "MAP=MAP91" & set "ARGS=+d64_poison_fx 0 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 0"
if /i "%ARM%"=="nodyn"   set "MAP=MAP90" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 1 +rt_dynlight 0"
if /i "%ARM%"=="big"     set "MAP=MAP91" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.7 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 1"
if /i "%ARM%"=="small"   set "MAP=MAP91" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.25 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 1"
if /i "%ARM%"=="sunk"    set "MAP=MAP91" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z -6 +d64_poison_sat 1 +d64_poison_debug 1"
if /i "%ARM%"=="channel" set "MAP=MAP92" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 1 +d64_poison_debug 1"
if /i "%ARM%"=="grey"    set "MAP=MAP91" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 0 +d64_poison_debug 1"
if /i "%ARM%"=="vivid"   set "MAP=MAP91" & set "ARGS=+d64_poison_fx 1 +d64_poison_rate 2 +d64_poison_dist 1100 +d64_poison_size 0.35 +d64_poison_z 1 +d64_poison_sat 2 +d64_poison_debug 1"

if not defined ARGS (
  echo Usage: %~nx0 ^[dark^|lit^|channel^|nowater^|dense^|still^|big^|small^|sunk^|grey^|vivid^|nodyn^] ^[-- +cvar val ...^]
  exit /b 1
)

if not exist "%D64%\d64rpoisonlab.wad" (
  echo ERROR: %D64%\d64rpoisonlab.wad missing.
  echo        Build it:  tools\.venv-ai\Scripts\python.exe tools\build_poison_lab.py
  exit /b 1
)

echo === poison lab: arm "%ARM%", %MAP% ===
echo     %ARGS%
if defined EXTRA echo     extra: %EXTRA%

rem THE WORKING DIRECTORY IS NOT OPTIONAL. The RT build resolves rt/wad, rt/bin
rem and rt/data relative to the CWD, so running gzdoom.exe by full path from
rem anywhere else dies with "Can't find rt/wad directory" before it reaches a
rem log. The exe is still called by FULL PATH: this environment runs with
rem NoDefaultCurrentDirectoryInExePath, so "gzdoom.exe" alone is not found even
rem standing in its own directory. Both halves are needed.
cd /d "%BUILD%"
if errorlevel 1 ( echo ERROR: cannot cd to %BUILD% & exit /b 1 )

rem LOAD ORDER. D64RTR carries the D64N1 TEXTURES/ANIMDEFS entries, so the pool
rem flat comes from it. d64r-poison-fx.pk3 must come BEFORE the lab pk3: the
rem probe actors subclass D64PoisonBubble, and a subclass cannot be compiled
rem before its parent exists.
rem
rem A SHORT COMMAND LINE on purpose -- the full launcher's ~325 pins put the
rem assembled line over cmd.exe's 8191-char limit and silently truncate the
rem passthrough at the end. The pins are exec'd from a file instead.
"%BUILD%\gzdoom.exe" -iwad "%IWAD%" ^
  -file "%D64%\D64RTR_v15.WAD" "%D64%\d64r-poison-fx.pk3" ^
  "%D64%\d64rpoisonlab.wad" "%D64%\d64r-poisonlab-mapinfo.pk3" ^
  +exec "%~dp0d64rt-pins.cfg" ^
  +logfile "%PROJ%\rt-poison-lab.log" ^
  +vid_fullscreen 0 +vid_defwidth 960 +vid_defheight 540 +win_x 0 +win_y 0 ^
  +i_pauseinbackground 0 +rt_verbose 1 ^
  %ARGS% +map %MAP% %EXTRA%

exit /b %ERRORLEVEL%
