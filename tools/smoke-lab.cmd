@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem SMOKE LAB -- unattended capture of muzzle smoke on MAP97, for tuning it.
rem
rem Build the map first:  python tools\build_smoke_lab.py
rem
rem WHY THIS EXISTS. Muzzle smoke was tuned three times against a description of
rem how it looked in MAP01, and twice the change made it worse in a way the
rem arithmetic did not predict. MAP01 is not dark and not plain: its own lights
rem and wall emissives are in the same froxel volume, so a change to the SMOKE
rem and a change to what is BEHIND it are indistinguishable on screen. MAP97 is
rem a black room with three known fixtures and nothing else.
rem
rem WHAT IT DOES. Fires the chosen weapon profile on a timer with no input
rem (rt_smoke_autoweapon + rt_smoke_autospawn), then takes a screenshot every
rem few tics and quits. The PNGs land in a run folder so two runs can be
rem compared frame for frame.
rem
rem   smoke-lab.cmd                 pistol, shipping values
rem   smoke-lab.cmd 3               shotgun
rem   smoke-lab.cmd 1 -- +rt_smoke_density 12
rem
rem Weapon index is RT_SMOKE_PROFILES order: 1 pistol, 2 chaingun, 3 shotgun,
rem 4 SSG. 0 is the identity profile, which has NO trail -- see the cvar help.
rem ---------------------------------------------------------------------------

set "WPN=%~1"
if "%WPN%"=="" set "WPN=1"

set "IWAD=D:\Games\GZDoom\doom2.wad"
set "BUILD=G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "D64=G:\AI\Doom64-RT\Doom64-Retribution"
set "SHOTS=%~dp0_smokelab"

rem Anything after "--" is appended verbatim and wins, for one-off overrides.
set "EXTRA="
set "SEEN="
for %%A in (%*) do (
  if defined SEEN ( call set "EXTRA=%%EXTRA%% %%~A" ) else ( if "%%~A"=="--" set "SEEN=1" )
)

if not exist "%SHOTS%" mkdir "%SHOTS%"
rem A run folder per invocation, or successive captures overwrite each other and
rem the comparison this tool exists for becomes impossible.
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%T"
set "RUN=%SHOTS%\%STAMP%-w%WPN%"
mkdir "%RUN%"

echo === smoke lab: weapon profile %WPN% ===
echo     shots -^> %RUN%
if defined EXTRA echo     extra: %EXTRA%
echo.

rem THE WORKING DIRECTORY IS NOT OPTIONAL. The RT build resolves rt/wad, rt/bin
rem and rt/data relative to the CWD, so running gzdoom.exe by full path from
rem anywhere else dies with "Can't find rt/wad directory" before it reaches a
rem log. launch-retribution-rt.cmd cds into the build dir for the same reason.
rem The exe is still called by FULL PATH: this environment runs with
rem NoDefaultCurrentDirectoryInExePath, so "gzdoom.exe" alone is not found even
rem standing in its own directory. Both halves are needed -- the cd for the
rem data paths, the full path for the exe.
cd /d "%BUILD%"
if errorlevel 1 ( echo ERROR: cannot cd to %BUILD% & exit /b 1 )
echo     cwd: %CD%

rem NOTE: a SHORT command line on purpose. The full launcher's ~325 pins put the
rem assembled line over cmd.exe's 8191-char limit and silently truncated the
rem passthrough at the end -- three diagnostic runs were lost to that. Here the
rem base pins are exec'd from a file and only the lab's own settings are inline.
"%BUILD%\gzdoom.exe" -iwad "%IWAD%" ^
  -file "%D64%\D64RTR_v15.WAD" "%D64%\d64rsmokelab.wad" "%D64%\d64r-smokelab-mapinfo.pk3" ^
  +exec "%~dp0d64rt-pins.cfg" ^
  +screenshot_dir "%RUN%" +screenshot_type png +screenshot_quiet 1 ^
  +vid_fullscreen 0 +i_pauseinbackground 0 ^
  +rt_dynlight_intensity 150 ^
  +rt_smoke_autoweapon %WPN% +rt_smoke_autospawn 25 ^
  +rt_autoshot 60 +rt_autoshot_every 10 +rt_autoquit 200 ^
  +map MAP97 %EXTRA%

echo.
echo === captured ===
dir /b "%RUN%" 2>nul
exit /b 0
