@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Settle rt_sky on the fire-sky maps: what a burning sky should light like.
rem
rem WHY THIS EXISTS. Until the per-map skies landed, every map in the game had
rem the same near-black MOONSKY starfield, and the launcher's rt_sky 25 was tuned
rem against exactly that. The domes are not comparable any more. Mean LINEAR
rem radiance, measured off the actual textures:
rem
rem     MOONSKY starfield      1.0x     <- what 25 was chosen for
rem     SKYMTNA               12x
rem     SKYCLD* / SKYMTNB/C   30-45x
rem     VOIDSKY              186x
rem     FRSKYGRN             410x
rem     FRSKYNRM             953x
rem
rem So at a single global rt_sky, a fire map takes about a THOUSAND times the sky
rem light a starfield map does. That is why nothing was added to replace the moon
rem on these maps when it was switched off (RT_MOON_PRESETS, disc false and
rem intensity 0): the burning dome already IS the light, sampled on ray miss
rem through the map's real F_SKY1 openings with real occlusion, and it needed
rem turning DOWN rather than supplementing.
rem
rem The shipping values -- 1.2 for FRSKYNRM, 2.7 for the dimmer FRSKYGRN -- are
rem parity with the cloud families at the global 25, computed from those
rem radiances. They are arithmetic, not judgement. This tool is the judgement.
rem
rem   off      rt_sky 0. The control: the fire sky lights nothing, and with the
rem            moon already off these maps have ONLY their own lamps. If `off`
rem            and `ship` look the same, the dome is not reaching the room you
rem            are standing in and no value here will fix it -- that is an
rem            aperture problem, go to ab-skyleak.cmd.
rem   quarter  0.3 -- a quarter of shipping.
rem   ship     1.2 (2.7 on the green maps, applied by the preset table).
rem   double   2.4
rem   global   25, the launcher's starfield value applied unchanged. This is what
rem            the fire maps would get with no preset row at all, and it is here
rem            to show why the row exists. Expect it to be blown out.
rem   moon     ship + the moon put back (disc and light) -- the arrangement this
rem            replaced. For deciding whether losing the directional cost any
rem            shape, not just whether the brightness is right.
rem
rem Every arm sets rt_moon_presets 0 so the table cannot overwrite the pin at
rem level load -- the same trap ab-storm.cmd documents for rt_clouds_presets. It
rem also means each arm must state rt_sun/rt_moon_geo explicitly, because
rem RT_CVARs are CVAR_ARCHIVE and an unset one carries over from the last arm.
rem
rem Usage: ab-firesky.cmd <off|quarter|ship|double|global|moon> [22|23|24|28|32]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=ship"
rem MAP22 is the default: it is the first FRSKYNRM map and the brightest sky in
rem the game, so if any value is going to blow out it blows out here first.
if "%MAP%"==""  set "MAP=22"

rem The green maps carry a dimmer sky, so `ship` there is 2.7 rather than 1.2 --
rem see RT_MOON_PRESETS. Keep the two in step or the arm stops meaning "shipping".
set "SHIP=1.2"
if "%MAP%"=="23" set "SHIP=2.7"
if "%MAP%"=="32" set "SHIP=2.7"

set "NOMOON=+rt_sun_intensity 0 +rt_moon_geo 0"
set "YESMOON=+rt_sun_intensity 90 +rt_moon_geo 1"

if /i "%ARM%"=="off"     set "ARGS=+rt_sky 0    %NOMOON%"
if /i "%ARM%"=="quarter" set "ARGS=+rt_sky 0.3  %NOMOON%"
if /i "%ARM%"=="ship"    set "ARGS=+rt_sky %SHIP% %NOMOON%"
if /i "%ARM%"=="double"  set "ARGS=+rt_sky 2.4  %NOMOON%"
if /i "%ARM%"=="global"  set "ARGS=+rt_sky 25   %NOMOON%"
if /i "%ARM%"=="moon"    set "ARGS=+rt_sky %SHIP% %YESMOON%"

if not defined ARGS (
  echo Usage: %~nx0 ^<off^|quarter^|ship^|double^|global^|moon^> [22^|23^|24^|28^|32]
  exit /b 1
)

echo === fire-sky arm "%ARM%", MAP%MAP% (shipping rt_sky here is %SHIP%) ===
echo     %ARGS% +rt_sun 1 +rt_moon_presets 0
echo     Stand in the SAME spot for every arm - these are compared by eye, and
echo     it must be a spot that can SEE sky. An interior room shows nothing on
echo     any arm and will make every value look identical.
echo.
echo     When you have a value you like, put it in that map's row in
echo     RT_MOON_PRESETS (rt_main.cpp) - the `sky` field - and rebuild. Typing
echo     bare `moon` in the console prints the row with the current value in it.
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS% +rt_sun 1 +rt_moon_presets 0
