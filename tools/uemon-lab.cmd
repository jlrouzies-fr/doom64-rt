@echo off
setlocal EnableExtensions
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem ---------------------------------------------------------------------------
rem UE MONSTER LAB -- each new monster standing beside the one it replaces.
rem
rem Build the maps first:
rem   python tools\build_uemon_lab.py
rem   python tools\pack_ue_monsters.py
rem
rem WHY THIS EXISTS. The placement handler can be verified from the console
rem census -- pools, conversions, refusals, monster totals -- and every one of
rem those numbers can be right while the monster on screen is the wrong size,
rem sunk into the floor, missing its walk cycle or silent. A census cannot see
rem any of that. Here the reference monster and its replacement stand side by
rem side on a flat floor, so it is a direct comparison.
rem
rem   sergeant / chaingunner / revenant / archvile / mastermind
rem          MAP80..MAP84 -- ONE monster, alone, dark, 768 units away so the
rem          ranged attack is the one you see. This is where you judge an
rem          effect: in a ten-monster room you cannot tell which one fired,
rem          and "casts no light" is indistinguishable from "never attacked".
rem   pairs / pairsdark
rem          MAP88/89 -- reference beside ours, idle. Proportions only.
rem
rem PROVE THE ATTACK FIRED before judging the light:
rem   uemon-lab.cmd archvile +rt_tex_probe AVFR
rem rt_tex_probe prints the texture name the renderer saw and a draw count.
rem No line at all means the attack never happened -- look at the monster, not
rem at the lighting. Effect prefixes: SPO2 CPOS TRC2 AVFR LPUF.
rem
rem Left of each pair is the reference, right is ours:
rem   64ShotgunGuy   -> Former Sergeant      (visual variant, same stats)
rem   64ShotgunGuy   -> Chaingunner
rem   64NightmareImp -> Revenant
rem   64BaronOfHell  -> Arch-Vile
rem   64Arachnotron  -> Spider Mastermind
rem
rem THE HANDLER IS OFF IN HERE (d64_ue_enable 0), on purpose: otherwise it would
rem convert the reference monsters on the left and there would be nothing to
rem compare against. The right-hand ones are placed by editor number instead.

set "ARM=%~1"
if "%ARM%"=="" set "ARM=help"
rem Anything after the arm is appended verbatim, for one-off probes, e.g.
rem   uemon-lab.cmd fight +rt_tex_probe LPUF
set "PASS="
shift
:passloop
if "%~1"=="" goto :passdone
set "PASS=%PASS% %1"
shift
goto :passloop
:passdone

set "IWAD=%D64RT_IWAD%"
if not defined IWAD set "IWAD=%PROJ%\doom2.wad"
set "BUILD=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "D64=%PROJ%\Doom64-Retribution"

rem WAKING THE MONSTER. d64rt-pins.cfg runs `notarget`, so every monster ignores
rem the player and a solo lab shows an idle Arch-Vile forever.
rem
rem Passing "+notarget" to toggle it back does NOT work, and two runs were lost to
rem that: it is a toggle rather than a value ("+notarget 1" does not mean "on"), it
rem is a cheat so it needs a level to exist, and even placed after +map the pin
rem still won -- the log kept reading "No Target ON" with no matching OFF while the
rem command line demonstrably carried it.
rem
rem So the solo labs exec a COPY of the pins with that one line filtered out.
rem Nothing to toggle, nothing to order, and the RT settings are still whatever
rem d64rt-pins.cfg says. The pair labs use the pins as-is and stay idle, which is
rem what you want when comparing proportions.
set "MAP="
set "HOSTILE=%TEMP%\uemon-lab-pins.cfg"
set "PINS=%~dp0d64rt-pins.cfg"
set "ARGS=+d64_ue_enable 0 +d64_ue_debug 2"
rem The solo maps are DARK and the monster is awake: every effect here is
rem emissive, and a lit room hides all of them. notarget is a TOGGLE ccmd and
rem d64rt-pins.cfg already ran it once, so passing +notarget turns it OFF.
if /i "%ARM%"=="sergeant" ( set "MAP=MAP80" & set "PINS=%HOSTILE%" )
if /i "%ARM%"=="chaingunner" ( set "MAP=MAP81" & set "PINS=%HOSTILE%" )
if /i "%ARM%"=="revenant" ( set "MAP=MAP82" & set "PINS=%HOSTILE%" )
if /i "%ARM%"=="archvile" ( set "MAP=MAP83" & set "PINS=%HOSTILE%" )
if /i "%ARM%"=="mastermind" ( set "MAP=MAP84" & set "PINS=%HOSTILE%" )
rem The pair maps are for proportions, so the monsters stay idle.
if /i "%ARM%"=="pairs"       set "MAP=MAP88"
if /i "%ARM%"=="pairsdark"   set "MAP=MAP89"
if defined MAP goto :go
echo Usage: %~nx0 [sergeant^|chaingunner^|revenant^|archvile^|mastermind^|pairs^|pairsdark] [+cvar value ...]
echo.
echo Prove the attack fired before judging the light:
echo   %~nx0 archvile +rt_tex_probe AVFR      (also: SPO2 CPOS TRC2 LPUF)
exit /b 1

:go
rem gzdoom resolves rt/ relative to the CWD, so it must be started from BUILD --
rem and still called by full path, because this environment runs with
rem NoDefaultCurrentDirectoryInExePath.
if /i "%PINS%"=="%HOSTILE%" findstr /v /i /x "notarget" "%~dp0d64rt-pins.cfg" > "%HOSTILE%"
cd /d "%BUILD%"
if errorlevel 1 ( echo ERROR: cannot cd to %BUILD% & exit /b 1 )

rem D64RTR carries the STONE2/FLOOR0_1/CEIL1_1 the lab geometry names and the
rem 64* reference monsters, so it loads first; the lab wad last.
"%BUILD%\gzdoom.exe" -iwad "%IWAD%" ^
  -file "%D64%\D64RTR_v15.WAD" "%D64%\d64r-blood-persist.pk3" "%D64%\d64r-ue-monsters.pk3" "%D64%\d64r-uemon-lab.wad" ^
  +exec "%PINS%" ^
  +logfile "%PROJ%\rt-uemon-lab.log" ^
  +vid_fullscreen 0 +vid_defwidth 960 +vid_defheight 540 +win_x 0 +win_y 0 ^
  +i_pauseinbackground 0 +rt_verbose 1 ^
  %ARGS% +map %MAP% %PASS%

exit /b %ERRORLEVEL%
