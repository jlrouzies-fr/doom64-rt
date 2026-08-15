@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the flashlight HOLD HEIGHT and INTENSITY. Default map 13.
rem
rem THE GEOMETRY, because the two knobs are not independent. The camera sits 41
rem map units up = 1.28 m. rt_flsh_u is the offset from it, negative meaning held
rem below the eye, so the old -0.7 put the source 0.58 m above the floor and the
rem new -0.58 puts it at 0.70 m -- 1.206x.
rem
rem rt_flsh_pitch is NOT touched by any arm. With the angle fixed the triangle is
rem merely SCALED, so raising the source moves the beam's floor contact out by the
rem same 1.206x, 1.44 m -> 1.74 m (46 -> 56 map units). One number buys both the
rem height and the reach. Changing the pitch as well would compound them, which is
rem why `high` is one arm and not two.
rem
rem THE COST, which is the whole reason this file exists. The lit footprint scales
rem 1.206x in BOTH dimensions, so its area grows 1.456x, and the same flux spread
rem over it lands 0.687x as bright. Raising the hold at the old intensity makes the
rem pool DIMMER. Pool brightness against today's shipping 90 at -0.7:
rem
rem   intensity 90  at -0.58  ->  0.69x   (the trap: "I raised it and it got worse")
rem   intensity 108 at -0.58  ->  0.82x   a naive +20%, still dimmer than before
rem   intensity 130 at -0.58  ->  0.99x   break-even: moved out, same brightness
rem   intensity 156 at -0.58  ->  1.19x   THE SHIPPING VALUE, ~+20% as asked
rem   intensity 187 at -0.58  ->  1.43x   if 156 still reads timid
rem
rem ARMS
rem   ship      -0.58 @ 156. What the launcher now does. Start here.
rem   old       -0.70 @ 90.  The previous shipping look, for the back-to-back.
rem   trap      -0.58 @ 90.  The raise with no compensation. Worth seeing once so
rem             the 1.456x is a thing you have watched happen rather than a number
rem             in a comment.
rem   naive     -0.58 @ 108. A literal +20% on the intensity. Also still dimmer.
rem   even      -0.58 @ 130. Break-even brightness at the new distance -- the arm
rem             that isolates the REACH change with the brightness held still.
rem   bright    -0.58 @ 187. One step past shipping.
rem   higher    -0.45 @ 187. Held higher again (0.83 m, 1.43x the original) with
rem             the intensity that keeps the pool at 1.19x. For deciding whether
rem             -0.58 went far enough before touching the pitch.
rem   onlylight -0.70 @ 156. The brightness increase with the ORIGINAL low hold.
rem             If you want it stronger but still want the floor-level framing,
rem             this is that, and it is brighter than shipping (1.73x) because
rem             none of the light is being spent on the larger footprint.
rem
rem Every arm lights the flashlight at launch and sets every rt_flsh_* position and
rem intensity cvar explicitly -- they are CVAR_ARCHIVE, so a value left by one arm
rem leaks into the next and quietly invalidates the comparison.
rem
rem Look at the FLOOR AHEAD OF YOU, not the walls: the wall response barely moves
rem between these, and the whole argument is about where the pool sits and how
rem bright it is when it gets there.
rem
rem Usage: ab-flsh.cmd <ship|old|trap|naive|even|bright|higher|onlylight> [1-34]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=ship"
if "%MAP%"==""  set "MAP=13"

rem Spelled out once. Later +cvar wins, so an arm names only what it changes.
rem Battery off in every arm: a dying cell dims the beam on its own schedule and
rem would put a moving variable in the middle of a brightness comparison.
set "FL=+rt_flsh 1 +rt_flsh_battery 0 +rt_flsh_intensity 156 +rt_flsh_u -0.58 +rt_flsh_r -0.3 +rt_flsh_f 0 +rt_flsh_pitch 22 +rt_flsh_angle 42 +rt_flsh_radius 0.02 +rt_flsh_color ffbe82"

if /i "%ARM%"=="ship"      set "ARGS=%FL%"
if /i "%ARM%"=="old"       set "ARGS=%FL% +rt_flsh_u -0.70 +rt_flsh_intensity 90"
if /i "%ARM%"=="trap"      set "ARGS=%FL% +rt_flsh_intensity 90"
if /i "%ARM%"=="naive"     set "ARGS=%FL% +rt_flsh_intensity 108"
if /i "%ARM%"=="even"      set "ARGS=%FL% +rt_flsh_intensity 130"
if /i "%ARM%"=="bright"    set "ARGS=%FL% +rt_flsh_intensity 187"
if /i "%ARM%"=="higher"    set "ARGS=%FL% +rt_flsh_u -0.45 +rt_flsh_intensity 187"
if /i "%ARM%"=="onlylight" set "ARGS=%FL% +rt_flsh_u -0.70 +rt_flsh_intensity 156"

if not defined ARGS (
  echo Usage: %~nx0 ship^|old^|trap^|naive^|even^|bright^|higher^|onlylight  [1-34]
  exit /b 1
)

echo === flashlight arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo     (battery is OFF in every arm so the beam does not dim on its own.
echo      Look at the floor ahead of you, not the walls.)
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
