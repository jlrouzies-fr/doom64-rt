@echo off
rem ===========================================================================
rem  Doom 64 - Ray Traced : release launcher
rem
rem  Lives at the ROOT of the release package. Everything it needs is found
rem  relative to this file, so the folder can sit anywhere.
rem
rem  It does three things before starting the game:
rem    1. finds the parts the user has to supply, and explains itself in a
rem       Doom 64 styled window if any are missing,
rem    2. picks an upscaler for the GPU that is actually installed,
rem    3. writes BOTH upscaler cvars -- never one. DLSS and FSR2 share a single
rem       upscaler slot and FSR is applied second, so a stale rt_upscale_fsr2 in
rem       the user's ini silently disables DLSS. That cost this project a day.
rem ===========================================================================
setlocal EnableExtensions EnableDelayedExpansion
for %%I in ("%~dp0.") do set "PROJ=%%~fI"

rem --- layout: release package first, source checkout second -----------------
set "ENGINE=%PROJ%"
if not exist "%ENGINE%\gzdoom.exe" set "ENGINE=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"

set "MODS=%PROJ%\mods"
if not exist "%MODS%" set "MODS=%PROJ%\Doom64-Retribution"

set "GAME=%PROJ%\game"
if not exist "%GAME%" set "GAME=%PROJ%\Doom64-Retribution"

set "PINS=%MODS%\d64rt-pins.cfg"
if not exist "%PINS%" set "PINS=%PROJ%\tools\d64rt-pins.cfg"

set "UI=%PROJ%\launch-doom64-rt-ui.ps1"
set "SETTINGS=%PROJ%\doom64-rt-settings.txt"
if not exist "%PROJ%\docs\img\doom64rt-banner.png" if not exist "%PROJ%\launcher-banner.png" (
  rem no logo shipped: the window falls back to a text title, nothing breaks
)

rem --- the IWAD: the one file we cannot ship ---------------------------------
if not defined D64RT_IWAD (
  for %%W in (
    "%GAME%\doom2.wad"
    "%PROJ%\doom2.wad"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Doom 2\base\doom2.wad"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Doom 2\masterbase\doom2.wad"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Ultimate Doom\base\doom2.wad"
    "C:\Program Files (x86)\GOG Galaxy\Games\DOOM II\doom2.wad"
    "%USERPROFILE%\Documents\GZDoom\doom2.wad"
  ) do if not defined D64RT_IWAD if exist %%W set "D64RT_IWAD=%%~W"
)
set "IWAD=%D64RT_IWAD%"

rem --- the startup check window ----------------------------------------------
rem  It owns the whole verification: registry lookup for Steam and GOG, the file
rem  checks, Browse and Re-check. It writes the IWAD it settled on back to the
rem  settings file, so the next launch starts from the answer.
rem The ModDB download is named D64RTR[v1.5].WAD; this repo also carries a
rem shell-safe D64RTR_v15.WAD copy. Accept whichever the user actually has.
set "MOD="
if exist "%GAME%\D64RTR[v1.5].WAD" set "MOD=%GAME%\D64RTR[v1.5].WAD"
if not defined MOD if exist "%GAME%\D64RTR_v15.WAD" set "MOD=%GAME%\D64RTR_v15.WAD"

if exist "%SETTINGS%" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%SETTINGS%") do (
    if /i "%%A"=="iwad" set "IWAD=%%B"
    if /i "%%A"=="mod"  set "MOD=%%B"
  )
)

if exist "%UI%" (
  powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%UI%" ^
    -Proj "%PROJ%" -EngineDir "%ENGINE%" -ModsDir "%MODS%" -GameDir "%GAME%" ^
    -IwadHint "!IWAD!" -Settings "%SETTINGS%"
  if errorlevel 1 exit /b 1
  if exist "%SETTINGS%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%SETTINGS%") do if /i "%%A"=="iwad" set "IWAD=%%B"
  )
) else (
  rem No PowerShell UI present: still refuse to start half-configured, rather
  rem than failing somewhere inside gzdoom where nobody can read it.
  set "MISSING="
  if not exist "!IWAD!"                       set "MISSING=!MISSING!doom2.wad "
  if not defined MOD                          set "MISSING=!MISSING!D64RTR[v1.5].WAD "
  if not exist "%GAME%\D64RTR_BRIGHTMAPS.PK3" set "MISSING=!MISSING!D64RTR_BRIGHTMAPS.PK3 "
  if not exist "%GAME%\D64MUS.PK3"            set "MISSING=!MISSING!D64MUS.PK3 "
  if not exist "%ENGINE%\gzdoom.exe"          set "MISSING=!MISSING!gzdoom.exe "
  if not exist "%ENGINE%\rt\bin\RTGL1.dll"    set "MISSING=!MISSING!RTGL1.dll "
  if defined MISSING (
    echo.
    echo  Doom 64 - Ray Traced cannot start. Missing: !MISSING!
    echo  Put the Retribution files in "%GAME%" and a doom2.wad you own beside
    echo  them, or set D64RT_IWAD to its full path.
    pause
    exit /b 1
  )
)

rem --- upscaler: pick one, then write BOTH cvars ----------------------------
rem  D64RT_UPSCALER = dlss | fsr | none   overrides the detection.
rem  The whole decision is made inside PowerShell on purpose. Matching the vendor
rem  string with find/findstr depends on those .exe resolving to the Windows ones,
rem  and on a machine with Git or MSYS on PATH they do not -- the probe then fails
rem  silently and every NVIDIA user is handed FSR.
if not defined D64RT_UPSCALER (
  for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command ^
    "if (((Get-CimInstance Win32_VideoController).Name -join ' ') -match 'NVIDIA') {'dlss'} else {'fsr'}" 2^>nul`) do set "D64RT_UPSCALER=%%V"
  if not defined D64RT_UPSCALER set "D64RT_UPSCALER=fsr"
)

if /i "%D64RT_UPSCALER%"=="dlss" (
  set "UPSCALE=+rt_upscale_dlss 2 +rt_upscale_fsr2 0"
) else if /i "%D64RT_UPSCALER%"=="fsr" (
  set "UPSCALE=+rt_upscale_dlss 0 +rt_upscale_fsr2 2"
) else (
  set "UPSCALE=+rt_upscale_dlss 0 +rt_upscale_fsr2 0"
)

rem --- map argument: 1-34, or "menu"; anything after it is passed through -----
rem  %* would repeat the map number we just consumed (+map map13 13), so the
rem  remaining arguments are collected by hand.
set "MAPARG="
set "WHAT=%~1"
if "%WHAT%"=="" set "WHAT=menu"
if /i not "%WHAT%"=="menu" (
  set "N=0%WHAT%"
  set "MAPARG=+map map!N:~-2!"
)

set "REST="
shift
:collect_rest
if "%~1"=="" goto collect_done
set "REST=!REST! %1"
shift
goto collect_rest
:collect_done

echo.
echo   Doom 64 - Ray Traced
echo   engine    : %ENGINE%
echo   iwad      : %IWAD%
echo   upscaler  : %D64RT_UPSCALER%   ^(override with D64RT_UPSCALER=dlss^|fsr^|none^)
echo.

cd /d "%ENGINE%"
start "" "%ENGINE%\gzdoom.exe" -iwad "%IWAD%" ^
  -file "%MOD%" "%GAME%\D64RTR_BRIGHTMAPS.PK3" "%GAME%\D64MUS.PK3" ^
  "%MODS%\d64r-lostsoul-rt.pk3" "%MODS%\d64r-rt-flashlight.pk3" ^
  "%MODS%\d64r-3dfloor-rtfix.wad" "%MODS%\d64r-seqlight-fix.wad" ^
  "%MODS%\d64r-bulb-textures.wad" "%MODS%\d64r-ctel-fix.wad" "%MODS%\d64r-rt-sky.pk3" ^
  -file "%MODS%\d64r-lava-fx.pk3" "%MODS%\d64r-blood-persist.pk3" ^
  "%MODS%\d64r-widescreen-gfx.pk3" "%MODS%\d64r-mugshot.pk3" "%MODS%\d64r-rt-titlelogo.pk3" ^
  -rtnolauncher -width 1280 -height 720 ^
  +exec "%PINS%" %UPSCALE% %MAPARG%%REST%

endlocal
