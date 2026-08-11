@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the switch-face lights (rt_switch_light_*), and check their PLACEMENT.
rem
rem Retribution's switches change art when thrown (ANIMDEFS CMPSW##A -> ON ->
rem CMPSW##B) and the ON art lights up: SWXC's demon face gains red eyes, SWXSG's
rem plate gains a pink gem. gen_world_emissives.py makes those texels glow; this
rem feature is the other half, one analytic light on the lit face, because an
rem emissive surface is not a light source under RTGL1.
rem
rem   on        the shipped values. Start here.
rem   debug     `on` plus rt_switch_light_debug 1: a cyan marker at every switch
rem             light and a per-60-frame dump of texture, pegging branch and
rem             world position. THIS IS THE ARM THAT MATTERS. The vertical
rem             placement is derived from the sidedef's pegging flags and row
rem             offset, which is a convention, not a measurement -- this project
rem             has been bitten twice by exactly that (see the notes at
rem             RT_UploadWallStripLights and rt_spin_panel_yaw). The markers must
rem             sit ON the lit eyes.
rem   bright    intensity 150. Not a look to ship: it makes a light that landed in
rem             the wrong place obvious from across the room, which a correct-but-
rem             dim light and a misplaced-and-dim light both fail to do.
rem   off       rt_switch_lights 0. A TRUE revert, unlike rt_flame_light_on: the
rem             eyes still glow, they just light nothing. This is the control for
rem             "is the light doing anything at all".
rem
rem   raise / lower   +8 and -8 on rt_switch_light_zofs. Use these ONLY after
rem             `debug` shows every marker off by the SAME amount in the SAME
rem             direction. If some are high and others low, the pegging branch is
rem             wrong for one of the three sidedef parts and no global offset can
rem             fix it -- read the branch and the `why` column in the debug dump,
rem             which prints which one placed each light.
rem
rem WHERE TO LOOK. SWXC demon-face switch faces, by map:
rem   MAP20 x21   MAP15 x10   MAP18 x9   MAP12 x8   MAP22 x8   MAP16 x7
rem   MAP24 x7    MAP30 x7    MAP23 x5   MAP13 x4   MAP21 x3   MAP31 x3
rem   MAP10 x2    MAP34 x1
rem MAP20 is the default for that reason. Remember a switch is only lit AFTER you
rem throw it -- an unthrown switch is the A frame and correctly emits nothing, so
rem "no lights in MAP20" means nothing until you have pressed one.
rem
rem Every arm sets every rt_switch_light cvar explicitly. RT_CVARs are
rem CVAR_ARCHIVE, so an arm that left one unset would inherit the previous arm's
rem value out of the ini and quietly invalidate the comparison.
rem
rem Usage: ab-switch.cmd <on|debug|bright|off|raise|lower> [1-34]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=debug"
if "%MAP%"==""  set "MAP=20"

set "BASE=+rt_switch_light_radius 0.06 +rt_switch_light_ofs 2 +rt_switch_light_maxdist 2048 +rt_switch_light_max 48"

if /i "%ARM%"=="on"     set "ARGS=+rt_switch_lights 1 %BASE% +rt_switch_light_intensity 60  +rt_switch_light_zofs 0  +rt_switch_light_debug 0"
if /i "%ARM%"=="debug"  set "ARGS=+rt_switch_lights 1 %BASE% +rt_switch_light_intensity 60  +rt_switch_light_zofs 0  +rt_switch_light_debug 1"
if /i "%ARM%"=="bright" set "ARGS=+rt_switch_lights 1 %BASE% +rt_switch_light_intensity 150 +rt_switch_light_zofs 0  +rt_switch_light_debug 1"
if /i "%ARM%"=="off"    set "ARGS=+rt_switch_lights 0 %BASE% +rt_switch_light_intensity 60  +rt_switch_light_zofs 0  +rt_switch_light_debug 0"
if /i "%ARM%"=="raise"  set "ARGS=+rt_switch_lights 1 %BASE% +rt_switch_light_intensity 60  +rt_switch_light_zofs 8  +rt_switch_light_debug 1"
if /i "%ARM%"=="lower"  set "ARGS=+rt_switch_lights 1 %BASE% +rt_switch_light_intensity 60  +rt_switch_light_zofs -8 +rt_switch_light_debug 1"

if not defined ARGS (
  echo Usage: %~nx0 ^<on^|debug^|bright^|off^|raise^|lower^> [1-34]
  exit /b 1
)

echo === switch arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo     Throw a switch first -- the A frame is unlit and correctly emits nothing.
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
