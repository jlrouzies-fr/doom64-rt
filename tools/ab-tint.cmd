@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the per-map ALBEDO TINT table (RT_TINT_PRESETS) on MAP13, the map the
rem report came from. Default map is 13; MAP02 is the regression gate.
rem
rem WHAT THIS IS ABOUT. rt_sector_tint_albedo multiplies each sector's
rem peak-normalized Doom 64 colormap hue into the albedo of every world surface,
rem and the launcher pins it at 1.0. A reflected beam is therefore
rem `light x sector_hue x texture_albedo`, and because the hue is peak-normalized
rem it can only ever REMOVE channels. On a cool sector that removal lands on red,
rem which is most of what a warm light is made of.
rem
rem The flashlight is ffbe82 = (1.00, 0.745, 0.51):
rem   on MAP01's #FFAA82  ->  (1.00, 0.50, 0.26)   saturated orange
rem   on MAP13's #6AADFF  ->  (0.42, 0.51, 0.51)   blue-dominant grey, 21% dimmer
rem That is the whole of "the flashlight is yellow on MAP01 and white and weak on
rem MAP13". The muzzle flash (ff8c52, warmer) loses proportionally more.
rem
rem WHY A TABLE AND NOT A GLOBAL, which is the thing this A/B exists to show:
rem MAP02's switch-triggered blue room is `Sector_SetColor(21, 0, 80, 255)`, red
rem retention 0.00 -- the MOST saturated colormap in the game, and the exact case
rem rt_sector_tint_albedo's 1.0 default was chosen to match. Any monotonic global
rem reduction hits it HARDER than it hits MAP13. Run `global06` on MAP02 and look
rem at the room with the flashlight on: the beam goes from (0.00, 0.23, 0.51) at
rem saturation 1.00 to (0.40, 0.44, 0.51) at 0.22. The blue room stops reading
rem blue exactly where you point the light. That arm is here to be REJECTED.
rem
rem ARMS
rem   base      presets off, albedo 1.0. Today's shipping behaviour. The A side.
rem   on        THE TABLE. MAP13 gets 0.63, MAP01 and MAP02 get no row and are
rem             bit-identical to `base`. The B side, and what a player would see.
rem   flsh      `on` with the flashlight lit at launch. THE ARM THAT ANSWERS THE
rem             QUESTION -- the complaint is about the beam, not the ambient.
rem   basefl    `base` with the flashlight lit. Its direct comparison. Run these
rem             two back to back on MAP13 and look at the floor in front of you.
rem
rem   global06  the rejected global: presets off, albedo 0.60 on every map. On
rem             MAP13 it works. Run it on MAP02 with the flashlight on to see
rem             what it costs. Kept so the decision is shown, not asserted.
rem   global035 the same at 0.35 -- further, and further wrong on MAP02.
rem   off       albedo 0.0. The colormap gone from albedo entirely. Not a
rem             candidate; it is the ceiling, so you can see how much of the
rem             look is this one multiply before judging the middle values.
rem
rem   soft      the table's MAP13 value applied by hand (0.63) with the table
rem             OFF, on whatever map you pass. How to try a strength on a map
rem             that has no row without editing the table.
rem   hard      the same at 0.42, the value that would hit MAP01's redKeep 0.90
rem             rather than the shipped 0.85 target. If `on` still reads too
rem             cool to you, this is the next stop.
rem
rem READING IT. The ambient look of a room barely moves between `base` and `on`
rem -- the hue direction is unchanged, only its depth. What moves is the beam.
rem On MAP13 it should go from blue-dominant grey to R > G > B, warm again, and
rem about 25% brighter. If you cannot tell `base` from `on` on MAP01 or MAP02,
rem that is correct: neither has a row.
rem
rem Every arm sets BOTH cvars explicitly. rt_sector_tint_albedo is CVAR_ARCHIVE,
rem so a value left behind by one arm leaks into the next and quietly invalidates
rem the comparison -- the same trap that cost four arms on the exposure bounds.
rem
rem Arms other than `on` and `flsh` set rt_sector_tint_presets 0, for the reason
rem every ab-fog.cmd arm does: RT_TINT_PRESETS is applied at LEVEL LOAD and writes
rem rt_sector_tint_albedo, so on a listed map it would overwrite the arm's own
rem value after the command line was parsed.
rem
rem Usage: ab-tint.cmd <base|on|flsh|basefl|global06|global035|off|soft|hard> [1-34]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=on"
if "%MAP%"==""  set "MAP=13"

rem Spelled out once. Later +cvar wins, so an arm names only what it changes.
rem tint_lights is pinned here too: it is a separate knob (the analytic lights,
rem not the albedo) and leaving it to drift would put a second variable in every
rem comparison.
set "TINT=+rt_sector_tint_presets 0 +rt_sector_tint_albedo 1.0 +rt_sector_tint_lights 0.85 +rt_flsh 0"

if /i "%ARM%"=="base"      set "ARGS=%TINT%"
if /i "%ARM%"=="on"        set "ARGS=%TINT% +rt_sector_tint_presets 1"
if /i "%ARM%"=="flsh"      set "ARGS=%TINT% +rt_sector_tint_presets 1 +rt_flsh 1"
if /i "%ARM%"=="basefl"    set "ARGS=%TINT% +rt_flsh 1"

rem The rejected global. Run these on MAP02, flashlight on.
if /i "%ARM%"=="global06"  set "ARGS=%TINT% +rt_sector_tint_albedo 0.60 +rt_flsh 1"
if /i "%ARM%"=="global035" set "ARGS=%TINT% +rt_sector_tint_albedo 0.35 +rt_flsh 1"
if /i "%ARM%"=="off"       set "ARGS=%TINT% +rt_sector_tint_albedo 0.0 +rt_flsh 1"

rem A strength by hand, on any map, table off.
if /i "%ARM%"=="soft"      set "ARGS=%TINT% +rt_sector_tint_albedo 0.63 +rt_flsh 1"
if /i "%ARM%"=="hard"      set "ARGS=%TINT% +rt_sector_tint_albedo 0.42 +rt_flsh 1"

if not defined ARGS (
  echo Usage: %~nx0 base^|on^|flsh^|basefl^|global06^|global035^|off^|soft^|hard  [1-34]
  exit /b 1
)

echo === tint arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo     (console: `rt_sector_tint_albedo` reports what actually reached the frame.
echo      On MAP13 with the table on it must read 0.63, not 1.0 -- check it before
echo      trusting anything you see. MAP01/MAP02 have no row and must read 1.0.)
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
