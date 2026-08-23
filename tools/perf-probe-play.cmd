@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem STUTTER PROBE, against the INSTALLED release -- not the dev tree.
rem
rem   .\tools\perf-probe-play.cmd 02
rem   .\tools\perf-probe-play.cmd 02 -- +rt_cull_hoist 0
rem
rem WHY THIS EXISTS. The 2026-08-19 MAP02 stutter session produced a result no
rem cvar can explain: the same configuration stuttered on three runs and then
rem stopped, with the two knobs under test back at their defaults. That is warm-up
rem state, not settings -- and the session could not tell the two apart because
rem the arms inherited each other. This launcher makes an arm reproducible:
rem
rem   - EVERY knob under test is stated, so no run inherits the last one. Two of
rem     the three are archived (rt_quality_preset, rt_sector_emis_freeze) and the
rem     third (rt_cull_hoist) is NOARCH and silently resets to 1 on every launch,
rem     which is how the "hoist disabled" arm was lost. Stating all three is the
rem     only way both kinds behave the same.
rem
rem   - rt_quality_apply, NOT +rt_quality_preset. Setting the cvar does not
rem     restore the preset's values: RT_ApplyQualityPresetOnce runs with
rem     includeArchived=false and leaves alone anything the ini already carries,
rem     so a config holding Performance values keeps them while the cvar reads
rem     High. rt_quality_apply is the CCMD that applies unconditionally.
rem
rem     BOTH ARE NEEDED, and the first run of this file proved it. With only the
rem     CCMD the log read:
rem         RT quality preset: High -- 26 cvar(s) set, 0 kept from config
rem         RT quality preset: Performance -- 2 cvar(s) set, 24 kept from config
rem     The second line is RT_ApplyQualityPresetOnce firing later, once the level
rem     exists, still reading rt_quality_preset=4 out of the ini -- so the arm
rem     ended up 24 cvars High and 2 cvars Performance. Setting the cvar as well
rem     makes the one-shot agree with the apply instead of half-undoing it.
rem
rem   - rt_vsync 0. docs/performance.md's first result: with it on, drawframe
rem     pins at a fixed ~6.4 ms and responds to nothing. No measurement may be
rem     taken through a FIFO present block.
rem
rem   - rt_stat_force + rt_stat_every write the phase split to a log, so an
rem     unattended run leaves numbers rather than an impression.
rem
rem READING THE RESULT. The hitch has to land in one of the four phases -- start,
rem lightgen, primupload, drawframe -- or in none of them. None of them means it
rem is outside our code entirely (driver, present, OS), which is where the
rem shader-cache hypothesis lives and where no cvar in this file can reach it.
rem Check `prims=... (peak N)` too: a hitch with a flat peak is not our uploads.
rem ---------------------------------------------------------------------------

set "INSTALL=%D64RT_INSTALL%"
if not defined INSTALL set "INSTALL=G:\Games\Doom64-RT"

if not exist "%INSTALL%\launch-doom64-rt.cmd" (
  echo ERROR: no install at "%INSTALL%"
  echo   set D64RT_INSTALL to the folder holding launch-doom64-rt.cmd
  exit /b 1
)

set "MAP=%~1"
if "%MAP%"=="" set "MAP=02"

rem THE THRESHOLD, in ms. Anything slower than this prints its own line with the
rem phase split, the counts and the position. 14 is about 1.6x the 8.7 ms this
rem install measured on MAP02 at 4K DLSS Balanced, which is low enough to catch a
rem "slight" hitch and high enough that a normal frame never trips it. Raise it
rem on weaker hardware -- a machine whose baseline IS 14 ms would log every frame.
set "SPIKE=%D64RT_SPIKE%"
if not defined SPIKE set "SPIKE=14"

rem Anything after "--" is appended last and therefore wins, for one-off arms.
set "EXTRA="
set "SEEN="
for %%A in (%*) do (
  if defined SEEN (
    call set "EXTRA=%%EXTRA%% %%~A"
  ) else (
    if "%%~A"=="--" set "SEEN=1"
  )
)

rem The log goes beside this file, stamped, so consecutive runs do not overwrite
rem each other -- the whole point is comparing run 1 against run 3.
for /f "tokens=1-4 delims=/:. " %%a in ("%TIME%") do set "TS=%%a%%b%%c"
set "LOG=%~dp0..\perf-probe-map%MAP%-%TS%.log"

echo.
echo   stutter probe   map%MAP%   install %INSTALL%
echo   log             %LOG%
echo.
echo   Stated: quality High, vsync off, hoist 1, emis freeze 2, stats every 35 tics
echo   Confirm in game with `rt_quality_show` -- a tool printing a value is not
echo   evidence that the game took it.
echo.

call "%INSTALL%\launch-doom64-rt.cmd" %MAP% -- ^
  +logfile "%LOG%" ^
  +rt_vsync 0 ^
  +rt_cull_hoist 1 ^
  +rt_sector_emis_freeze 2 ^
  +rt_quality_preset 2 ^
  +rt_quality_apply 2 ^
  +rt_stat_force 1 ^
  +rt_stat_every 35 ^
  +rt_stat_spike %SPIKE% ^
  %EXTRA%

exit /b %ERRORLEVEL%
