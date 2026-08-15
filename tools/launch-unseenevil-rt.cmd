@echo off
rem DelayedExpansion is needed to accumulate the "--" passthrough in a loop.
rem Safe here: no literal '!' appears anywhere else in this script.
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem Doom 64: Unseen Evil under the native RT renderer, with the brightmap tone
rem overlay applied.
rem
rem WHAT THE OVERLAY IS. D64UnseenEvil-v1.0.3.pk3 pins 18 of its 54 brightmap
rem masks at 255. A GZDoom brightmap is a mask meaning "ignore the room's light
rem here", and the mod's own brightermap_dynamic.fp then multiplies by 1.5 on
rem top, so those texels land near 380% of the raw texture and stick out of an
rem otherwise dark room. d64ue-brightmap-tone.pk3 rescales just those 18 to 192
rem -- the mod's OWN modal ceiling; 36 of its masks already sit between 40 and
rem 244. Nothing is removed and hue is exact, so key trims and door lights keep
rem their colour.
rem
rem IT MUST LOAD AFTER THE MOD. It replaces files at identical paths, so load
rem order is the entire mechanism -- put it first and it does nothing at all.
rem Rebuild it any time with:
rem     python tools\tone_unseenevil_brightmaps.py --write
rem
rem WHICH IWAD. Unseen Evil is an overhaul of DOOM/DOOM II, not a standalone TC:
rem its MAPINFO replaces exactly two levels -- 64UE_DIS carries e3m8special and
rem secretnext E3M9 (Ultimate Doom's E3M8) and 64UE_SIN is cluster 8 -> EndGameC
rem (DOOM II's MAP30). Everything else is the IWAD's own maps. Defaults to
rem doom2.wad; pass "doom1" as the first argument for the Ultimate Doom side.
rem ---------------------------------------------------------------------------
rem
rem   .\tools\launch-unseenevil-rt.cmd            -> doom2.wad, MAP01
rem   .\tools\launch-unseenevil-rt.cmd 7          -> doom2.wad, MAP07
rem   .\tools\launch-unseenevil-rt.cmd 30         -> MAP30, the custom Icon of Sin
rem   .\tools\launch-unseenevil-rt.cmd menu       -> title screen, no +map
rem   .\tools\launch-unseenevil-rt.cmd doom1      -> doom.wad, E1M1
rem   .\tools\launch-unseenevil-rt.cmd doom1 e3m8 -> doom.wad, the custom Dis
rem   .\tools\launch-unseenevil-rt.cmd 5 -- +rt_sky 40      -> extra cvars win
rem
rem Anything that is not a number and not a keyword is passed to +map verbatim,
rem so 64UE_SIN / 64UE_DIS / TITLEMAP / e3m8 all work directly.

rem Project root, derived from this script's own location, so a clone can live
rem anywhere. Nothing below may hardcode an absolute path into the repo.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
set "ENGINE=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"

set "MOD=%PROJ%\Doom64-UnseenEvil\D64UnseenEvil-v1.0.3.pk3"
set "TONE=%PROJ%\Doom64-UnseenEvil\d64ue-brightmap-tone.pk3"
set "PINS=%PROJ%\tools\d64rt-pins.cfg"
rem A separate log from rt-console.log on purpose: that one is the Retribution
rem transcript and gets read after a session, so this must not clobber it.
set "LOGF=%PROJ%\rt-console-unseenevil.log"

rem ---- which IWAD -----------------------------------------------------------
set "WANT=doom2.wad"
if /i "%~1"=="doom1" (
  set "WANT=doom.wad"
  shift
)

if not defined D64RT_UE_IWAD (
  for %%W in (
    "D:\Games\GZDoom\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Doom 2\base\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Doom 2\masterbase\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Ultimate Doom\base\%WANT%"
    "C:\Program Files (x86)\GOG Galaxy\Games\DOOM II\%WANT%"
    "%USERPROFILE%\Documents\GZDoom\%WANT%"
    "%PROJ%\%WANT%"
  ) do if not defined D64RT_UE_IWAD if exist %%W set "D64RT_UE_IWAD=%%~W"
)
set "IWAD=%D64RT_UE_IWAD%"
if not exist "%IWAD%" (
  echo ERROR: no %WANT% found.
  echo        Unseen Evil is an overhaul mod -- it needs a DOOM IWAD you own.
  echo        Set D64RT_UE_IWAD to its full path, e.g.
  echo          set "D64RT_UE_IWAD=C:\Path\To\%WANT%"
  exit /b 1
)

rem ---- files ----------------------------------------------------------------
if not exist "%MOD%" (
  echo ERROR: missing %MOD%
  exit /b 1
)
if not exist "%TONE%" (
  echo ERROR: missing %TONE%
  echo        Build it with: python tools\tone_unseenevil_brightmaps.py --write
  exit /b 1
)

rem ---- passthrough ----------------------------------------------------------
rem Collect the post-"--" passthrough without disturbing %1 parsing above.
set "EXTRA="
set "SEEN_SEP="
for %%A in (%*) do (
  if defined SEEN_SEP (
    set "EXTRA=!EXTRA! %%~A"
  ) else (
    if "%%~A"=="--" set "SEEN_SEP=1"
  )
)

rem ---- map ------------------------------------------------------------------
rem "menu" boots to the title screen with the identical file list and pins.
rem +map jumps straight into play, so the title and intermission screens are
rem otherwise unreachable from here -- and Unseen Evil has a custom TITLEMAP.
set "MAPARG=+map"
set "MAPNUM=%~1"
if /i "%MAPNUM%"=="menu" (
  set "MAPARG="
  set "MAPLUMP="
  goto :launch
)
if "%MAPNUM%"=="" set "MAPNUM=1"
if /i "%WANT%"=="doom.wad" if "%MAPNUM%"=="1" set "MAPNUM=e1m1"

rem A number means a DOOM II map slot; anything else is a lump name and goes
rem through untouched, which is what makes e3m8 / 64UE_SIN / TITLEMAP work.
set /a "N=MAPNUM" 2>nul
if errorlevel 1 goto :byname
if %N% LSS 1 goto :byname
if %N% GTR 32 goto :byname
if %N% LSS 10 (set "MAPLUMP=map0%N%") else (set "MAPLUMP=map%N%")
goto :launch

:byname
set "MAPLUMP=%MAPNUM%"

:launch
cd /d "%ENGINE%" || (
  echo ERROR: engine build not found at %ENGINE%
  echo        Build it with: tools\build-gzdoom-rt.cmd
  exit /b 1
)

echo Unseen Evil ^(RT^)
echo   iwad    %IWAD%
echo   mod     %MOD%
echo   tone    %TONE%   ^(18 brightmaps 255 -^> 192^)
echo   map     %MAPLUMP%
echo   log     %LOGF%
echo.

rem The tone overlay is listed LAST so it wins the load order. The pins run
rem before +map, and %EXTRA% runs last so a one-off cvar still beats a pin --
rem the same ordering contract as launch-retribution-rt.cmd.
rem
rem Keep this command line SHORT. The Retribution launcher once spelled every
rem pin out here, hit cmd.exe's 8191-character limit, and silently dropped the
rem trailing passthrough while still printing the values it believed it had set.
rem That is why the pins live in a cfg and arrive via +exec.
start "" gzdoom.exe ^
  -iwad "%IWAD%" -file "%MOD%" "%TONE%" -rtnolauncher -width 1280 -height 720 ^
  +logfile "%LOGF%" ^
  +exec "%PINS%" ^
  %MAPARG% %MAPLUMP% %EXTRA%
exit /b 0
