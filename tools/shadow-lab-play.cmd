@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem Walk around the SHADOW LAB (MAP93) instead of only screenshotting it.
rem
rem   python tools\build_shadow_lab.py --room 512 --cage 128     build it first
rem   shadow-lab-play.cmd                 shipping 0.35 / 16 -- reproduces the bug
rem   shadow-lab-play.cmd 0.02            radius only -- still nothing
rem   shadow-lab-play.cmd 0.02 128        both -- diamonds on floor, walls, ceiling
rem
rem Args: [radius] [bulb spacing] [-- any +cvar ...]. Defaults are the SHIPPING
rem values, so running it bare gives you the broken case on purpose and the pair
rem is a real A/B. Anything after `--` is appended LAST and therefore wins, so
rem nothing below has to be edited to try something:
rem
rem   shadow-lab-play.cmd 0.02 128 -- +rt_ceiling_bulb_gain 20
rem   shadow-lab-play.cmd 0.02 128 -- +rt_ceiling_edge_zofs 60
rem   shadow-lab-play.cmd 0.02 128 -- +rt_ceiling_bulb_emis 20 +rt_emis_mapboost 200
rem   shadow-lab-play.cmd 0.02 128 -- +rt_debug_visibility 1
rem
rem NOT routed through launch-retribution-rt.cmd: that validates its map argument
rem with `if %N% GTR 34 goto :badmap`, so MAP93 is rejected outright. It goes
rem through tools\shot.ps1 -Play instead, which is the same file list and the same
rem pins the unattended captures used -- so what you walk around in is exactly
rem what was measured.
rem
rem One lamp pane inside a SPACECM cage, in a dark room with NO other light of any
rem kind. That is the point: on MAP01 the same fixture sits among 283 analytic
rem lights and nothing can be isolated (rt-lighting-practices 34c).
rem
rem THE FAMILY IS READ FROM THE WAD, not guessed. build_shadow_lab.py writes the
rem pane texture to tools\_shadowlab_pane.txt, because the two fixture families do
rem NOT share cvars and pointing the wrong set at a pane is a silent no-op:
rem
rem   SFLATAS / SFLATAQ   bulb array  -> rt_ceiling_bulb_spacing, rt_ceiling_edge_radius
rem   SFLATCH / SFLATDE   solo bulb   -> rt_solo_lamp_stride,     rt_solo_lamp_radius
rem
rem SFLATCH paints ONE bulb dead centre of its 64-unit tile, so a 64 cage is 1 bulb
rem and 1 light, and a 128 cage is 4 and 4 -- the "repaint it as a single bulb"
rem idea, already in the game, with no art change needed. Arg 2 is the spacing for
rem a bulb array and the STRIDE for a solo pane (1 = every bulb, 2 = every other).
rem ---------------------------------------------------------------------------
set "RAD=%~1"
set "SPACE=%~2"
if "%RAD%"==""   set "RAD=0.35"
if "%SPACE%"=="" set "SPACE=16"

rem Collect everything after `--` verbatim. Appended after the block below, so a
rem one-off override beats the isolation defaults without editing the file.
set "EXTRA="
set "SEEN="
for %%A in (%*) do (
  if defined SEEN set "EXTRA=!EXTRA! %%A"
  if "%%A"=="--" set "SEEN=1"
)

set "PANE=SFLATAS"
if exist "%~dp0_shadowlab_pane.txt" set /p PANE=<"%~dp0_shadowlab_pane.txt"

rem rt_ceiling_edge_lamps gates the whole walk -- RT_UploadCeilingEdgeLamps returns
rem immediately without it -- so it stays on for BOTH families. Only the inner
rem family and its own knobs change.
set "FAM=bulb"
if /i "%PANE%"=="SFLATCH" set "FAM=solo"
if /i "%PANE%"=="SFLATDE" set "FAM=solo"

if "%FAM%"=="solo" (
  rem Solo bulbs have their own intensity, and 45 is calibrated for a level that
  rem also has every other fixture in it. This room has nothing else, so it is
  rem raised to sit near what a bulb-array light delivers (180 x gain 7 = 1260),
  rem purely so the image is judgeable. Brightness is free here; shape is not.
  set "A=+rt_solo_lamps 1 +rt_solo_lamp_radius %RAD% +rt_solo_lamp_stride %SPACE%"
  set "A=!A! +rt_solo_lamp_intensity 1260 +rt_solo_lamp_max 384 +rt_ceiling_edge_lattice 0"
) else (
  set "A=+rt_solo_lamps 0 +rt_ceiling_edge_radius %RAD% +rt_ceiling_bulb_spacing %SPACE%"
  set "A=!A! +rt_ceiling_edge_lattice 1"
)
rem Every other light source off, so the pane is the only thing lighting the room.
set "A=!A! +rt_ceiling_edge_lamps 1 +rt_ceiling_edge_debug 1"
set "A=!A! +rt_faux_lamps 0 +rt_wall_strips 0 +rt_hang_lamps 0"
set "A=!A! +rt_ceiling_lamps 0 +rt_sector_lights 0 +rt_spin_panels 0 +rt_switch_lights 0"
set "A=!A! +rt_flame_light_on 0 +rt_lava_light_on 0 +rt_hand_light_on 0 +rt_dynlight 0"
set "A=!A! +rt_sun 0 +rt_sky 0 +rt_flsh 0 +rt_sector_emis 0"
set "A=!A! +rt_shadow_samples 1 +rt_debug_visibility 0"

echo === MAP93 shadow lab: %PANE% [%FAM%] radius=%RAD% arg2=%SPACE% !EXTRA! ===
echo     watch the on-screen "uploaded=N" -- N is the light count doing all of this
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0shot.ps1" -Play -Map map93 -ExtraFiles d64rshadowlab.wad -Extra "!A!!EXTRA!"
exit /b %ERRORLEVEL%
