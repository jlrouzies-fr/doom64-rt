@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem A/B Doom 64: Unseen Evil's own lit wall art -- the door indicators, switch
rem lamps and light strips lit from rt_ue_fixture_lights.h, plus the SFLATAP
rem grille pane. Everything here is gated in code on RT_IsUnseenEvil(), so none
rem of it can reach Retribution.
rem
rem   .\tools\ab-ue-fixtures.cmd off      everything off -- the "before" arm
rem   .\tools\ab-ue-fixtures.cmd on       shipped defaults
rem   .\tools\ab-ue-fixtures.cmd soft     half intensity, wider sources
rem   .\tools\ab-ue-fixtures.cmd bright   double intensity
rem   .\tools\ab-ue-fixtures.cmd strips   ONLY the wall strips
rem   .\tools\ab-ue-fixtures.cmd doors    ONLY doors and switches
rem   .\tools\ab-ue-fixtures.cmd grille   ONLY the SFLATAP ceiling panes
rem   .\tools\ab-ue-fixtures.cmd green    defaults + rt_ue_fixture_sat 2.5
rem   .\tools\ab-ue-fixtures.cmd marks    defaults + a CYAN MARKER on every light
rem
rem A map number or name may follow the arm; it defaults to MAP03, which is the
rem densest doom2 map for this work (149 d64_metal7 strip placements and the
rem talldoor's blinking pair). Pass "doom1 e2m7" for the richest map overall.
rem
rem   .\tools\ab-ue-fixtures.cmd marks 10        MAP10: wide doors + 49 grilles
rem   .\tools\ab-ue-fixtures.cmd on doom1 e2m7   194 lit placements, the densest
rem
rem WHICH ARM TO REACH FOR. "marks" is the one that answers a placement report.
rem It drops a cyan sphere at every light this system uploads, so a light that
rem sits below the lamp it belongs to is visible as a marker below the paint --
rem which is the difference between "the light is in the wrong place" and "the
rem light is fine and the fixture is just dim". It also turns on the per-texture
rem census, so rt-console-unseenevil.log lists every wall texture in the level
rem once with LIT or "no row" beside it.
rem
rem WHAT THE NUMBERS MEAN, because two families are deliberately not tuned alike:
rem   rt_ue_fixture_*  a door indicator or switch lamp -- ONE lamp, one sphere
rem                    per texture repeat, a fairly tight source
rem   rt_ue_strip_*    a light strip -- wall art that TILES, so it is lit as a
rem                    CHAIN of overlapping spheres along the whole sidedef at a
rem                    flat per-segment intensity. A longer strip therefore emits
rem                    more total light, which is the point. RTGL1 gives no better
rem                    option: an emissive surface casts nothing, and polygonal
rem                    area lights are compiled out behind #if TRIANGLE_LIGHTS.
rem ---------------------------------------------------------------------------

for %%I in ("%~dp0..") do set "PROJ=%%~fI"

set "ARM=%~1"
if "%ARM%"=="" set "ARM=on"
shift

rem Collect what is left for the launcher BY HAND. `shift` does not touch %* in
rem cmd -- %* is always the ORIGINAL command line -- so forwarding %* after a
rem shift passes the arm along as if it were a map name. That is not a theory:
rem it sent "+map marks" and quietly loaded the wrong level, which looks exactly
rem like the arm doing nothing.
set "REST="
:collect
if "%~1"=="" goto :collected
set "REST=!REST! %~1"
shift
goto :collect
:collected

rem Shared baseline: every cvar this feature owns is set explicitly in EVERY arm,
rem so a stale ini line can never decide an arm's behaviour. (See the project's
rem A/B rule -- an arm that omits a value is an arm that cannot be trusted.)
set "COMMON=+rt_ue_grille_lamps 1 +rt_ue_grille_emis 6 +rt_ue_fixture_lights 1"
set "FIXT=+rt_ue_fixture_intensity 120 +rt_ue_fixture_radius 0.14 +rt_ue_fixture_max 320 +rt_ue_fixture_sat 2"
set "STRIP=+rt_ue_strip_intensity 180 +rt_ue_strip_radius 0.35 +rt_ue_strip_seglen 48"
set "MARK="

if /i "%ARM%"=="off" (
  set "COMMON=+rt_ue_grille_lamps 0 +rt_ue_grille_emis 0 +rt_ue_fixture_lights 0"
) else if /i "%ARM%"=="on" (
  rem defaults, set above
) else if /i "%ARM%"=="soft" (
  set "FIXT=+rt_ue_fixture_intensity 60 +rt_ue_fixture_radius 0.22 +rt_ue_fixture_max 320 +rt_ue_fixture_sat 2"
  set "STRIP=+rt_ue_strip_intensity 90 +rt_ue_strip_radius 0.50 +rt_ue_strip_seglen 40"
) else if /i "%ARM%"=="bright" (
  set "FIXT=+rt_ue_fixture_intensity 240 +rt_ue_fixture_radius 0.14 +rt_ue_fixture_max 320 +rt_ue_fixture_sat 2"
  set "STRIP=+rt_ue_strip_intensity 360 +rt_ue_strip_radius 0.35 +rt_ue_strip_seglen 48"
) else if /i "%ARM%"=="strips" (
  rem Strips only. The fixture family is silenced by intensity rather than by the
  rem feature switch, so the census still reports doors and switches as LIT --
  rem "not uploaded" and "uploaded at zero" stay tellable apart in the log.
  set "COMMON=+rt_ue_grille_lamps 0 +rt_ue_grille_emis 0 +rt_ue_fixture_lights 1"
  set "FIXT=+rt_ue_fixture_intensity 0 +rt_ue_fixture_radius 0.14 +rt_ue_fixture_max 320 +rt_ue_fixture_sat 2"
) else if /i "%ARM%"=="doors" (
  set "COMMON=+rt_ue_grille_lamps 0 +rt_ue_grille_emis 0 +rt_ue_fixture_lights 1"
  set "STRIP=+rt_ue_strip_intensity 0 +rt_ue_strip_radius 0.35 +rt_ue_strip_seglen 48"
) else if /i "%ARM%"=="grille" (
  set "COMMON=+rt_ue_grille_lamps 1 +rt_ue_grille_emis 6 +rt_ue_fixture_lights 0"
) else if /i "%ARM%"=="green" (
  rem Saturation dial only. The lamps are MEASURED pure green already; this exists
  rem for the case where the pool still reads cyan because the surface it lands on
  rem is blue-grey steel. Walk the door with this and with "on" back to back.
  set "FIXT=+rt_ue_fixture_intensity 120 +rt_ue_fixture_radius 0.14 +rt_ue_fixture_max 320 +rt_ue_fixture_sat 2.5"
) else if /i "%ARM%"=="marks" (
  set "MARK=+rt_switch_light_debug 1"
) else (
  echo ERROR: unknown arm "%ARM%".
  echo        off ^| on ^| soft ^| bright ^| strips ^| doors ^| grille ^| green ^| marks
  exit /b 1
)

echo   arm     %ARM%
echo   common  %COMMON%
echo   fixture %FIXT%
echo   strip   %STRIP%
if defined MARK echo   marks   %MARK%
echo   map    !REST!

call "%PROJ%\tools\launch-unseenevil-rt.cmd"!REST! -- %COMMON% %FIXT% %STRIP% %MARK%
