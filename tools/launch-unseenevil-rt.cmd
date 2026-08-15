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
rem   .\tools\launch-unseenevil-rt.cmd bare       -> no Retribution patches at all
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

rem ---- Retribution patches carried over -------------------------------------
rem WHICH OF OURS TRANSFER, AND WHY MOST DO NOT. Every d64r-*.pk3 was checked for
rem what it inherits from and replaces. The great majority are Retribution-shaped
rem and cannot come here:
rem
rem   d64r-blood-persist.pk3  NO -- and this is the tempting one, because it is
rem       what DECLARES the nine rt_gore_* cvars the pins set, so the "Unknown
rem       command" lines at startup point straight at it. Its DECORATE is
rem       "ACTOR RTBloodPersist : 64Blood replaces 64Blood", plus 64Blood2,
rem       64InvisiBlood, 64Cacodemon, 64Arachnotron, 64NightmareImp,
rem       64PainElemental, 64SpiderMastermind. None of those actors exist here --
rem       DOOM's blood is `Blood` -- so loading it is a startup script error, not
rem       persistent blood. The nine unknown-command lines are the correct and
rem       harmless result of sharing one pins file across two mods.
rem   d64r-seqlight-fix.wad / d64r-3dfloor-rtfix.wad / d64r-ctel-fix.wad /
rem   d64r-bulb-textures.wad  NO -- map and texture replacements for Retribution's
rem       own MAP01-34. Nothing here has those maps.
rem   d64r-mugshot.pk3 / d64r-widescreen-gfx.pk3 / d64r-rt-titlelogo.pk3  NO --
rem       they override the status bar, TITLEPIC and title music, and Unseen Evil
rem       ships its own (StatusBarClass = D64UE_StatusBar, a custom TITLEMAP).
rem   d64r-rt-sky.pk3  NO -- Unseen Evil has its own sky system, GLDEFS.skies plus
rem       the sky_3d.fp and skyfire.fp shaders.
rem
rem   d64r-rt-flashlight.pk3  YES. Self-contained and free of Doom 64 actor
rem       dependencies: one EventHandler, a KEYCONF binding F to the engine's
rem       rt_flsh_toggle, two sound cvars of its own, three wavs. AddEventHandlers
rem       is additive, so it sits alongside Unseen Evil's handlers rather than
rem       replacing them. Worth having precisely because this is a dark
rem       path-traced game.
rem
rem       CAVEAT, untested in play: the battery HUD is authored against
rem       Retribution's ForceScaled 320x240 bar, so on Unseen Evil's own status
rem       bar it may not land where intended. It draws from RenderOverlay, which
rem       is independent of the status bar, so the worst case is cosmetic. Launch
rem       with "bare" as the first argument to drop it and every other patch.
set "FLSH=%PROJ%\Doom64-Retribution\d64r-rt-flashlight.pk3"
rem The quotes live INSIDE the value: PROJ is derived from this script's path and
rem a clone can sit somewhere with a space in it, at which point an unquoted
rem expansion would split into two bogus -file arguments.
set "PATCHES="%FLSH%""
if not exist "%FLSH%" set "PATCHES="
set "PINS=%PROJ%\tools\d64rt-pins.cfg"
rem A separate log from rt-console.log on purpose: that one is the Retribution
rem transcript and gets read after a session, so this must not clobber it.
set "LOGF=%PROJ%\rt-console-unseenevil.log"

rem ---- leading keywords -----------------------------------------------------
rem ONE loop for all of them, deliberately, so they compose in ANY order. Written
rem first as two separate "if ... shift" blocks, which worked for "bare doom1" and
rem quietly broke "doom1 bare": the second keyword had already slid into %1 by the
rem time its own test was reached, so it fell through to the map parser and became
rem "+map bare". Consuming them in a loop removes the ordering entirely.
set "WANT=doom2.wad"
:flags
if /i "%~1"=="bare"  ( set "PATCHES=" & shift & goto :flags )
if /i "%~1"=="doom1" ( set "WANT=doom.wad" & shift & goto :flags )

rem Steam's modern "Ultimate Doom" depot is a BUNDLE: one app folder holds every
rem classic IWAD, with DOOM.WAD at base\ and the rest one level down in
rem base\doom2\, base\tnt\, base\plutonia\. Both layouts are searched.
rem
rem base\ IS PREFERRED OVER rerelease\ ON PURPOSE, and the order below is the
rem whole of that decision. The 2024 KEX re-release ships its own doom.wad and
rem doom2.wad next to the classic ones with DIFFERENT contents and sizes
rem (doom2: 14951361 vs the classic 14604584). AGENTS.md pins 14604584 as the
rem known-good size for this project and warns against a differently-sized copy,
rem so rerelease\ is never listed here -- if it were found first, everything
rem downstream would silently be running against a different game.
if not defined D64RT_UE_IWAD (
  for %%W in (
    "D:\Games\GZDoom\%WANT%"
    "G:\SteamLibrary\steamapps\common\Ultimate Doom\base\%WANT%"
    "G:\SteamLibrary\steamapps\common\Ultimate Doom\base\doom2\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Doom 2\base\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Doom 2\masterbase\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Ultimate Doom\base\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Ultimate Doom\base\doom2\%WANT%"
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
if defined PATCHES (echo   patches %PATCHES%) else (echo   patches none ^("bare"^))
echo   map     %MAPLUMP%
echo   log     %LOGF%
echo.
echo   Nine "Unknown command rt_gore_*" lines at startup are EXPECTED here: those
echo   cvars are declared by Retribution's blood pk3, which cannot load on DOOM.
echo.

rem The tone overlay is listed LAST so it wins the load order. The pins run
rem before +map, and %EXTRA% runs last so a one-off cvar still beats a pin --
rem the same ordering contract as launch-retribution-rt.cmd.
rem
rem -nostartup IS LOAD-BEARING, not tidiness. Unseen Evil's GAMEINFO sets
rem STARTUPTYPE = "Hexen", so GetGameStartScreen() builds a Hexen start screen.
rem d_main.cpp then takes its OTHER branch -- V_Init2() EARLY, under the start
rem screen, followed by StartScreen->Render() -- and that Render draws through a
rem just-created RTGL1 renderer and dies with an access violation. The dialog it
rem raises is "GZDoom Very Fatal Error", which MASKS whatever the real error was,
rem so this also hid a ZScript failure underneath it for the whole investigation.
rem -nostartup makes GetGameStartScreen return nullptr, which is the LATE path --
rem the one Retribution has always used, because it is GAME_Doom and never
rem matched the Hexen/Heretic/Strife branches in the first place.
rem
rem Keep this command line SHORT. The Retribution launcher once spelled every
rem pin out here, hit cmd.exe's 8191-character limit, and silently dropped the
rem trailing passthrough while still printing the values it believed it had set.
rem That is why the pins live in a cfg and arrive via +exec.
start "" gzdoom.exe ^
  -iwad "%IWAD%" -file "%MOD%" %PATCHES% "%TONE%" -rtnolauncher -nostartup -width 1280 -height 720 ^
  +logfile "%LOGF%" ^
  +exec "%PINS%" ^
  %MAPARG% %MAPLUMP% %EXTRA%
exit /b 0
