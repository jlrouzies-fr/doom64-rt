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

rem Optional add-ons the user downloads themselves. We ship nothing from here
rem and modify nothing in it -- the files are loaded exactly as downloaded.
set "ADDONS=%PROJ%\Addons"

rem  The startup window is WPF; the older WinForms one stays as the fallback for
rem  a machine where WPF will not start (it answers 2, see below). D64RT_UI=classic
rem  picks the WinForms one on purpose.
set "UI=%PROJ%\launch-doom64-rt-ui.ps1"
set "UIFALLBACK=%PROJ%\launch-doom64-rt-ui-classic.ps1"
if /i "%D64RT_UI%"=="classic" set "UI=%UIFALLBACK%"
if not exist "%UI%" set "UI=%UIFALLBACK%"
set "SETTINGS=%PROJ%\doom64-rt-settings.txt"
rem  Written by the startup window when the user ticks "setup is done".
set "CONFIGDONE=%PROJ%\configdone.txt"

rem  ...and the way back in: `launch-doom64-rt.cmd setup` shows the window once
rem  without deleting the marker. D64RT_FORCEUI=1 does the same.
set "FORCEUI="
if /i "%~1"=="setup" set "FORCEUI=1"
if defined D64RT_FORCEUI set "FORCEUI=1"
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

rem  The key is matched by "contains", not by equality, and that is deliberate:
rem  a UTF-8 BOM on the first line of the settings file lands INSIDE %%A, so
rem  `iwad` arrives as `<BOM>iwad` and an == test drops the saved path. The
rem  launcher then had no IWAD, listed doom2.wad as missing, and reopened the
rem  startup window on every start -- with the "setup is done" box still ticked
rem  and every line green, because the window finds the IWAD its own way. The
rem  window no longer writes a BOM; this keeps the files it already wrote working.
rem  The three keys share no substring, so a loose match is safe.
if exist "%SETTINGS%" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%SETTINGS%") do (
    set "K=%%A"
    if not "!K:iwad=!"=="!K!"    set "IWAD=%%B"
    if not "!K:mod=!"=="!K!"     set "MOD=%%B"
    if not "!K:recolor=!"=="!K!" set "RECOLOR=%%B"
  )
)

rem  What the game cannot start without. Cheap, so it runs on EVERY launch --
rem  it is both the console fallback when no PowerShell UI is present and the
rem  reason "setup is done" can never strand anyone: a ticked box skips the
rem  window, a file that has since gone missing brings it straight back.
set "MISSING="
if not exist "!IWAD!"                       set "MISSING=!MISSING!doom2.wad "
if not defined MOD                          set "MISSING=!MISSING!D64RTR[v1.5].WAD "
if not exist "%GAME%\D64RTR_BRIGHTMAPS.PK3" set "MISSING=!MISSING!D64RTR_BRIGHTMAPS.PK3 "
if not exist "%GAME%\D64MUS.PK3"            set "MISSING=!MISSING!D64MUS.PK3 "
if not exist "%ENGINE%\gzdoom.exe"          set "MISSING=!MISSING!gzdoom.exe "
if not exist "%ENGINE%\rt\bin\RTGL1.dll"    set "MISSING=!MISSING!RTGL1.dll "

set "SHOWUI=1"
if exist "%CONFIGDONE%" if not defined MISSING if not defined FORCEUI set "SHOWUI="
if not defined SHOWUI echo   startup check : skipped, configdone.txt is set  ^(launch-doom64-rt.cmd setup^)

rem  0 = go, 1 = the user closed it, 2 = the window could not open at all and the
rem  WinForms one gets a turn. Two runs of the same script cannot both write
rem  %UIRC%, so the code is captured and acted on after the block.
set "UIRC=0"
if defined SHOWUI if exist "%UI%" (
  powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%UI%" ^
    -Proj "%PROJ%" -EngineDir "%ENGINE%" -ModsDir "%MODS%" -GameDir "%GAME%" ^
    -IwadHint "!IWAD!" -Settings "%SETTINGS%"
  set "UIRC=!errorlevel!"
)

if "%UIRC%"=="2" if exist "%UIFALLBACK%" (
  echo   startup check : falling back to the WinForms window
  powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%UIFALLBACK%" ^
    -Proj "%PROJ%" -EngineDir "%ENGINE%" -ModsDir "%MODS%" -GameDir "%GAME%" ^
    -IwadHint "!IWAD!" -Settings "%SETTINGS%"
  set "UIRC=!errorlevel!"
)
rem still 2: neither window opened. Nothing was confirmed, so do not start.
if "%UIRC%"=="2" (
  echo.
  echo  Doom 64 - Ray Traced could not open its startup window.
  echo  Run it again with:  launch-doom64-rt.cmd setup
  pause
  exit /b 1
)
if not "%UIRC%"=="0" exit /b 1

if defined SHOWUI if exist "%SETTINGS%" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%SETTINGS%") do (
    set "K=%%A"
    if not "!K:iwad=!"=="!K!" set "IWAD=%%B"
    if not "!K:mod=!"=="!K!"  set "MOD=%%B"
    rem Written on every launch, so an unticked box CLEARS a previous 1.
    if not "!K:recolor=!"=="!K!" set "RECOLOR=%%B"
  )
)

if defined SHOWUI if not exist "%UI%" (
  rem No PowerShell UI present: still refuse to start half-configured, rather
  rem than failing somewhere inside gzdoom where nobody can read it.
  if defined MISSING (
    echo.
    echo  Doom 64 - Ray Traced cannot start. Missing: !MISSING!
    echo  Put the Retribution files in "%GAME%" and a doom2.wad you own beside
    echo  them, or set D64RT_IWAD to its full path.
    pause
    exit /b 1
  )
)

rem --- flight recorder ------------------------------------------------------
rem  OFF BY DEFAULT. It was shipped always-on for one dev cycle (2026-08-20) to
rem  chase a stutter report, and did its job -- but "one rdtsc per bracket, forty
rem  a frame" was never actually measured against a real player's machine, only
rem  argued from first principles. Shipping an unmeasured per-frame cost to every
rem  player by default is the wrong side of that uncertainty. Opt in with
rem  D64RT_SPIKE_MS set to a nonzero value (or D64RT_SPIKE_REL), same as before.
rem
rem  WHAT IT DOES WHEN ON. rt_stat_force turns on glcycle_t counters for the RT
rem  phases, the playsim and D_Display; rt_stat_spike/_rel print one line per
rem  frame over an adaptive threshold (a multiple of the recent average, so it
rem  self-calibrates to the machine's actual frame rate -- a fixed ms threshold
rem  chosen at 115 fps fired on every frame of a 58 fps session, 2123 lines of
rem  it, 2026-08-19) at RT_DiagPrintLevel: console buffer and the log, never the
rem  on-screen notify overlay unless rt_verbose 1 is also set.
if not defined D64RT_SPIKE_MS set "D64RT_SPIKE_MS=0"
if not defined D64RT_SPIKE_REL set "D64RT_SPIKE_REL=0"

rem  One generation of history. `logfile` truncates on open, so without this the
rem  act of relaunching to show someone the log is what destroys it.
set "LOGF=%PROJ%\rt-console.log"
if exist "%LOGF%" move /y "%LOGF%" "%PROJ%\rt-console.prev.log" >nul 2>&1

set "RECORDER=+logfile "%LOGF%""
if not "%D64RT_SPIKE_MS%"=="0" set "RECORDER=+logfile "%LOGF%" +rt_stat_force 1 +rt_stat_spike %D64RT_SPIKE_MS% +rt_stat_spike_rel %D64RT_SPIKE_REL%"
if not "%D64RT_SPIKE_REL%"=="0" set "RECORDER=+logfile "%LOGF%" +rt_stat_force 1 +rt_stat_spike %D64RT_SPIKE_MS% +rt_stat_spike_rel %D64RT_SPIKE_REL%"

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
rem "setup" is the show-the-window-again keyword, not a map number
if /i "%WHAT%"=="setup" set "WHAT=menu"
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
echo   log       : %LOGF%
echo   upscaler  : %D64RT_UPSCALER%   ^(override with D64RT_UPSCALER=dlss^|fsr^|none^)
echo.

rem --- optional: classic recoloured Cacodemon / Pain Elemental ---------------
rem  D64ClassicRecolored from ModDB, dropped in Addons\ by the user and ticked in
rem  the startup window. Loaded as downloaded -- see README "Art changes" for
rem  which of the two variants to take and what each gets wrong, and note that
rem  the offsets CANNOT be corrected from a companion pk3: gzdoom's SPROFS lump
rem  only adjusts sprites from its own file, and a TEXTURES redeclaration
rem  resolves its self-referencing patch to the OLDEST texture of that name --
rem  Retribution's original -- so the recolour would silently not appear.
set "RECOLORARGS="
if not "%RECOLOR%"=="1" goto :norecolor
if exist "%ADDONS%\D64ClassicRecolored.wad" set RECOLORARGS="%ADDONS%\D64ClassicRecolored.wad"
if not defined RECOLORARGS if exist "%ADDONS%\D64ClassicRecolored_OffsetFix.wad" set RECOLORARGS="%ADDONS%\D64ClassicRecolored_OffsetFix.wad"
:norecolor

rem NO -width/-height ON THIS LINE, and no `rem` inside it either -- a rem
rem between two ^-continued lines is not a comment, it becomes ARGUMENTS, and the
rem first line without a caret silently truncates the command (that is how
rem -rtnolauncher and +exec pins got dropped once).
rem
rem The resolution flags are a COMMAND-LINE OVERRIDE applied after the config is
rem read, so passing them every start undid whatever the player chose in the
rem menus: set it, save, restart, back to 1280x720. The window size is theirs to
rem keep. tools\launch-retribution-rt.cmd still forces it, on purpose -- a test
rem launcher wants a predictable window.
cd /d "%ENGINE%"
start "" "%ENGINE%\gzdoom.exe" -iwad "%IWAD%" ^
  -file "%MOD%" "%GAME%\D64RTR_BRIGHTMAPS.PK3" "%GAME%\D64MUS.PK3" ^
  "%MODS%\d64r-lostsoul-rt.pk3" "%MODS%\d64r-rt-flashlight.pk3" ^
  "%MODS%\d64r-3dfloor-rtfix.wad" "%MODS%\d64r-seqlight-fix.wad" ^
  "%MODS%\d64r-bulb-textures.wad" "%MODS%\d64r-sflatas-broken.wad" ^
  "%MODS%\d64r-ctel-fix.wad" "%MODS%\d64r-map05-skyseam-fix.wad" "%MODS%\d64r-rt-sky.pk3" ^
  -file "%MODS%\d64r-lava-fx.pk3" "%MODS%\d64r-blood-persist.pk3" ^
  "%MODS%\d64r-widescreen-gfx.pk3" "%MODS%\d64r-mugshot.pk3" "%MODS%\d64r-rt-titlelogo.pk3" ^
  %RECOLORARGS% ^
  -rtnolauncher ^
  +exec "%PINS%" %UPSCALE% %RECORDER% %MAPARG%%REST%

endlocal
