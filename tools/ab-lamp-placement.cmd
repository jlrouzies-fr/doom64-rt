@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem One light per bulb panel (centre) vs one every 64 units around its perimeter.
rem
rem Why this is worth trying. The perimeter walk's light count comes from sector
rem PERIMETER / seglen with a floor of one light per linedef -- it has no relation
rem to the number of bulbs the texture actually shows. Counts:
rem
rem                      per-panel centre     perimeter walk
rem   MAP01                    12                 129
rem   MAP02                    51                 793
rem   MAP03                    93                 817
rem
rem Fewer, stronger, point-like lights is exactly what the shadow work has been
rem pushing toward all along, and one light per fixture is the physically honest
rem model. It should also cut the noise, which comes from many bright sources
rem competing for one ReSTIR pick per pixel.
rem
rem Why it was abandoned before, and what changed. rt_ceiling_lamp_maxspan skips
rem any sector wider than 128 -- section 18: "Large SFLATAQ halls only have edge
rem texture blobs -- a center sphere looks like a fake mid-ceiling light (MAP02)".
rem That is a real objection, but it was formed when the light was large and soft.
rem The `all` arm raises maxspan so every panel gets a centre light, so the
rem objection can be re-judged against a point-like source rather than assumed.
rem
rem At maxspan 128 the coverage is very uneven -- MAP01 6 of 12 panels, MAP02
rem 33 of 51, but MAP03 only 8 of 93. So test `centre` on MAP01/02 and `all` on
rem MAP03, or `both` if the centre light reads wrong in the big halls.
rem
rem ARMS
rem   centre   one light per panel, only panels <= 128 wide. Perimeter walk OFF.
rem   all      same, maxspan 4096 so EVERY panel gets one. Re-tests section 18.
rem   both     centre for small panels + perimeter for the large halls it skips.
rem   edge     perimeter walk only -- today's behaviour, the reference.
rem
rem Blinking is disabled in every arm (rt_ceiling_lamp_off 1) so a flicker is not
rem mistaken for noise while judging.
rem
rem Judge:
rem   1. does the fence cast a readable shadow? Fewer, sharper lights should help.
rem   2. does a centre light look like a real fixture, or like a fake bulb floating
rem      mid-ceiling? That is section 18's objection -- confirm or retire it.
rem   3. noise, in motion. This should be markedly better than the perimeter walk.
rem   4. the "uploaded=" counts in the console.
rem
rem Usage: ab-lamp-placement.cmd <centre^|all^|both^|edge> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=centre"
if "%MAP%"==""  set "MAP=1"

rem One centre light replaces roughly ten perimeter ones, so it carries their
rem combined output. Radius stays point-like: 0.05 = 3.2 map units, which is what
rem lets the fence's thin wires cast at all.
set "CENTRE=+rt_ceiling_lamps 1 +rt_ceiling_lamp_intensity 900 +rt_ceiling_lamp_radius 0.05"
set "CENTRE=%CENTRE% +rt_ceiling_lamp_zofs 8 +rt_ceiling_lamp_off 1 +rt_ceiling_lamp_fade 40"
set "CENTRE=%CENTRE% +rt_ceiling_lamp_debug 1"
set "NOCENTRE=+rt_ceiling_lamps 0 +rt_ceiling_lamp_intensity 0"

set "EDGE=+rt_ceiling_edge_lamps 1 +rt_ceiling_edge_intensity 360 +rt_ceiling_edge_radius 0.05"
rem seglen alone no longer thins an SFLATAS/SFLATAQ pane -- since 2026-08-10 those
rem go through the bulb lattice, whose count knob is rt_ceiling_bulb_spacing. Both
rem are set so "edge" really is the sparse arm it claims to be. The lattice
rem compensates its own energy across spacing, so it needs no intensity partner.
set "EDGE=%EDGE% +rt_ceiling_edge_seglen 128 +rt_ceiling_bulb_spacing 32"
set "EDGE=%EDGE% +rt_ceiling_edge_lattice 1 +rt_ceiling_edge_debug 1"
set "NOEDGE=+rt_ceiling_edge_lamps 0"

if /i "%WHICH%"=="centre" (
  set "ARGS=%CENTRE% +rt_ceiling_lamp_maxspan 128 %NOEDGE%"
) else if /i "%WHICH%"=="all" (
  set "ARGS=%CENTRE% +rt_ceiling_lamp_maxspan 4096 %NOEDGE%"
) else if /i "%WHICH%"=="both" (
  set "ARGS=%CENTRE% +rt_ceiling_lamp_maxspan 128 %EDGE%"
) else if /i "%WHICH%"=="edge" (
  set "ARGS=%NOCENTRE% +rt_ceiling_lamp_maxspan 128 %EDGE%"
) else (
  echo Usage: %~nx0 ^<centre^|all^|both^|edge^> [map 1-32]
  exit /b 1
)

rem Wall strips are the same fixture family seen by a third walk; held fixed so
rem they are not confused with the flat placement being tested.
set "ARGS=%ARGS% +rt_wall_strips 1 +rt_wall_strip_intensity 180 +rt_wall_strip_radius 0.05"
set "ARGS=%ARGS% +rt_wall_strip_seglen 128 +rt_shadow_samples 8"

echo === lamp placement: %WHICH%, MAP%MAP% ===
echo     %ARGS%
echo     judge: 1) fence shadow  2) does a centre bulb look real  3) noise in motion  4) counts
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
