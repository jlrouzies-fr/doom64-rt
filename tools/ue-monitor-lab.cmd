@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem THE UNSEEN EVIL MONITOR LAB. One SMONDA wall in an empty room, nothing else.
rem
rem   .\tools\ue-monitor-lab.cmd            MAP96: the spawned 9802s, as UE ships
rem   .\tools\ue-monitor-lab.cmd off        MAP96 with the 9802s OFF -- the engine's
rem                                         steady wall-strip substitute alone
rem   .\tools\ue-monitor-lab.cmd ref        MAP97: a hand-placed 9802, overlay off
rem   .\tools\ue-monitor-lab.cmd both       MAP97: hand-placed + spawned together
rem   .\tools\ue-monitor-lab.cmd debug      MAP96 + the spawn count and strip tally
rem
rem Anything after the arm is passed through, so a one-off cvar still works:
rem   .\tools\ue-monitor-lab.cmd off +rt_wall_strip_intensity 600
rem
rem WHY THE ARMS EXIST. "Nothing from SMONDA" has three causes that look identical
rem on screen -- not uploaded, uploaded into solid geometry, or uploaded correctly
rem and too weak to see. `debug` answers the first two from the tallies. `off`
rem isolates the engine substitute so its contribution can be judged on its own,
rem which is the comparison that showed it was not carrying the effect.
rem
rem PROJ IS TAKEN BEFORE ANY shift: `shift` moves %0 as well as the numbered
rem arguments, so a %~dp0 read after one resolves to the ARGUMENT and the call
rem below looks for the launcher in the repo root. Same reason `%*` is not used to
rem forward the tail -- `%*` is immune to shift and hands the arm name back twice.
rem
rem Build the wad first (or after any edit to it):
rem     python tools\build_ue_monitor_lab.py
rem ---------------------------------------------------------------------------
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
set "LAB=%PROJ%\Doom64-UnseenEvil\d64ue-monitor-lab.wad"

if not exist "%LAB%" (
  echo ERROR: %LAB% missing.
  echo        Build it with:  python tools\build_ue_monitor_lab.py
  exit /b 1
)

set "MAP=map96"
set "ARM=+d64ue_rt_monitorlights 1"

if /i "%~1"=="off"   ( set "ARM=+d64ue_rt_monitorlights 0" & shift & goto :collect )
if /i "%~1"=="ref"   ( set "MAP=map97" & set "ARM=+d64ue_rt_monitorlights 0" & shift & goto :collect )
if /i "%~1"=="both"  ( set "MAP=map97" & set "ARM=+d64ue_rt_monitorlights 1" & shift & goto :collect )
if /i "%~1"=="debug" ( set "ARM=+d64ue_rt_monitorlights 1 +d64ue_rt_monitordebug 1 +rt_wall_strip_debug 1 +rt_dynlight_debug 1" & shift & goto :collect )

:collect
set "REST="
:more
if "%~1"=="" goto :run
set "REST=!REST! %~1"
shift
goto :more

:run
echo   map %MAP%   arm %ARM%%REST%
call "%PROJ%\tools\launch-unseenevil-rt.cmd" %MAP% -- -file "%LAB%" %ARM%%REST%
