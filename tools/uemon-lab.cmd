@echo off
setlocal EnableExtensions
rem This script's own folder, captured once so no later line has to re-expand it.
set "HERE=%~dp0"
rem Repo root, derived from this script's own location.
for %%I in ("%HERE%..") do set "PROJ=%%~fI"
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
rem          IDLE BY DEFAULT (notarget). Add the word `fight` to wake it:
rem            uemon-lab.cmd mastermind fight
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
rem
rem AND THAT 0 FOLLOWS YOU OUT OF THE LAB. d64_ue_enable is `server bool`, so it
rem ARCHIVES, and every launcher here shares one ini with the release build --
rem so running this lab once wrote d64_ue_enable=false into the player config and
rem the monsters silently stopped appearing in normal play, with the pk3 loaded
rem and the launcher box ticked. launch-doom64-rt.cmd now asserts +d64_ue_enable 1
rem whenever it loads the pk3, which is the fix; do not rely on this file leaving
rem the value as it found it, because a game that is killed never writes it back.

set "ARM=%~1"
if "%ARM%"=="" set "ARM=help"
rem Anything after the arm is appended verbatim, for one-off probes, e.g.
rem   uemon-lab.cmd mastermind +rt_tex_probe LPUF
rem ...except the bare word `fight`, which is eaten here and wakes the monster.
set "PASS="
set "FIGHT="
shift
:passloop
if "%~1"=="" goto :passdone
if /i "%~1"=="fight" (
  set FIGHT=+exec "%HERE%uemon-lab-hostile.cfg"
) else (
  set "PASS=%PASS% %1"
)
shift
goto :passloop
:passdone

set "IWAD=%D64RT_IWAD%"
if not defined IWAD set "IWAD=%PROJ%\doom2.wad"
set "BUILD=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "D64=%PROJ%\Doom64-Retribution"

rem WAKING THE MONSTER IS OPT-IN. d64rt-pins.cfg runs `notarget`, so by default
rem every monster here ignores the player -- which is what you want for the job
rem this lab is mostly used for: standing nose to nose with a sprite and reading
rem its emissive mask. A Mastermind that lasers you on sight never HOLDS a
rem non-firing frame long enough to see, so "some dots still there when not
rem firing" is unanswerable while it is hostile.
rem
rem The word `fight` undoes the pins' notarget with a SECOND exec of
rem uemon-lab-hostile.cfg, applied on top -- see that file for why it is not a
rem "+notarget" on the command line, and not a filtered copy of the pins either.
rem
rem THE PINS ALWAYS LOAD. The previous version exec'd a findstr-filtered COPY of
rem them, and findstr could not filter that file at all -- when it failed the copy
rem was empty and the lab ran with NO pins: monsters hostile for the wrong reason,
rem no god, and every RT cvar at its compiled default instead of the shipped one,
rem with nothing printed to say so. god comes from the pins, as it always did.
set "MAP="
set "PINS=%HERE%d64rt-pins.cfg"
set "ARGS=+d64_ue_enable 0 +d64_ue_debug 2"
rem The solo maps are DARK: every effect here is emissive, and a lit room hides
rem all of them. notarget is a TOGGLE ccmd and d64rt-pins.cfg already ran it
rem once, so `fight` turns it OFF -- passing +notarget yourself would too, which
rem is the opposite of what the name suggests.
if /i "%ARM%"=="sergeant"   set "MAP=MAP80"
if /i "%ARM%"=="chaingunner"   set "MAP=MAP81"
if /i "%ARM%"=="revenant"   set "MAP=MAP82"
if /i "%ARM%"=="archvile"   set "MAP=MAP83"
if /i "%ARM%"=="mastermind"   set "MAP=MAP84"
rem The pair maps are for proportions, so the monsters stay idle.
if /i "%ARM%"=="pairs"       set "MAP=MAP88"
if /i "%ARM%"=="pairsdark"   set "MAP=MAP89"
if defined MAP goto :go
echo Usage: %~nx0 [sergeant^|chaingunner^|revenant^|archvile^|mastermind^|pairs^|pairsdark] [fight] [+cvar value ...]
echo.
echo Monsters are IDLE by default (god + notarget), so you can walk up to a
echo sprite and read it. Add `fight` to wake them:
echo   %~nx0 mastermind fight
echo.
echo Prove the attack fired before judging the light:
echo   %~nx0 archvile fight +rt_tex_probe AVFR    (also: SPO2 CPOS TRC2 LPUF)
exit /b 1

:go
rem gzdoom resolves rt/ relative to the CWD, so it must be started from BUILD --
rem and still called by full path, because this environment runs with
rem NoDefaultCurrentDirectoryInExePath.
cd /d "%BUILD%"
if errorlevel 1 ( echo ERROR: cannot cd to %BUILD% & exit /b 1 )

rem D64RTR carries the STONE2/FLOOR0_1/CEIL1_1 the lab geometry names and the
rem 64* reference monsters, so it loads first; the lab wad last.
"%BUILD%\gzdoom.exe" -iwad "%IWAD%" ^
  -file "%D64%\D64RTR_v15.WAD" "%D64%\d64r-blood-persist.pk3" "%D64%\d64r-ue-monsters.pk3" "%D64%\d64r-uemon-lab.wad" ^
  +exec "%PINS%" %FIGHT% ^
  +logfile "%PROJ%\rt-uemon-lab.log" ^
  +vid_fullscreen 0 +vid_defwidth 960 +vid_defheight 540 +win_x 0 +win_y 0 ^
  +i_pauseinbackground 0 +rt_verbose 1 ^
  %ARGS% +map %MAP% %PASS%

exit /b %ERRORLEVEL%
