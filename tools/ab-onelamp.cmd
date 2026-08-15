@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem TOTAL light count vs the fence's shadow. The isolation ladder.
rem
rem THE NUMBER THIS EXISTS FOR. rt_ceiling_edge_debug in the MAP01 cage room:
rem
rem   uploaded=283 of 275 wanted (cap 1024, within 3072u)
rem     from 16 lamp ceiling(s) + 4 lamp floor(s) + 12 bulb lattice(s)
rem     | faux 4 flat(s) | solo 4 flat(s)
rem
rem 283 lights, and the cap is 1024 -- so nothing is being trimmed and that is
rem the real number competing for every pixel. Two things follow, and both
rem invalidate earlier work:
rem
rem   1. rt_debug_visibility answers "was the light THIS PIXEL CHOSE blocked".
rem      ReSTIR picks one light out of 283 per pixel, so most pixels choose
rem      something that a wall, a pillar or the cage blocks, and the whole room
rem      comes back shadowed (screen/redDebugShadow.png -- nearly every surface
rem      tinted). That is not a statement about the fence. THE DEBUG VIEW CANNOT
rem      ISOLATE ONE OCCLUDER UNTIL THE LIGHT COUNT IS CUT. Run it from here.
rem
rem   2. Every count experiment so far moved only PART of the population.
rem      rt_ceiling_bulb_spacing reaches the 12 lattice panes and nothing else;
rem      rt_ceiling_edge_seglen reaches the 8 perimeter ones; faux and solo have
rem      their own budgets (rt_faux_lamp_max 256, rt_solo_lamp_max 384) that no
rem      arm ever touched. Thinning 12 panes out of 283 lights was never going
rem      to show anything. Practices 34b, for the third time.
rem
rem   The previous version of this file had the same defect: it set
rem   rt_ceiling_edge_max 1 and called that "one lamp", while faux and solo kept
rem   their separate budgets and uploaded 8 more. It also opened by asserting
rem   "rt_debug_visibility 1 shows nothing casts a shadow from the bulb bands",
rem   which was read off the composited view that was broken until 2026-08-14
rem   (practices 34a). Both are fixed here.
rem
rem WHAT IS ALREADY SETTLED, so this ladder is aimed and not a fishing trip.
rem screen/debugMod1.png, the FIXED debug view: the grating's diamond lattice and
rem a humanoid silhouette both resolve cleanly as a shadow map. The fence is in
rem the acceleration structure, alpha-tested correctly, and IS blocking shadow
rem rays. Source size is falsified separately (practices 34). The umbra is
rem produced and then lost, and 283-way summation is the last mechanism standing.
rem
rem ARMS. Every other light source in the world is off in all of them; the only
rem thing moving is how many flat bulb lamps survive the cap.
rem
rem   one     max 1    I 3000    CONFIRMED 2026-08-14: the fence casts. The
rem                              grating's diamonds project across the wall beside
rem                              the cage (screen/oneLamp.png), console reads
rem                              "uploaded=1 of 275 ... faux 0 ... solo 0".
rem   few     max 8    I 375
rem   some    max 32   I 94
rem   all     max 1024 I 11       every lamp, i.e. today's placement with the rest
rem                              of the world's lights removed. The reference.
rem
rem WHAT IS ALREADY ANSWERED, so do not re-run `one` to find out: 1 light casts,
rem 283 do not. Summation is the mechanism. What this ladder is still FOR is
rem WHERE it breaks -- the useful arms now are `few` and `some`, because the fix
rem has to live at a count the room can actually be lit by.
rem
rem Add +rt_debug_visibility 1 by hand to any arm to see the raw shadow map,
rem which at these counts finally means what it says.
rem
rem THIS IS AN ISOLATION TEST, NOT A LOOK TEST -- every other light in the world
rem is off, which no shipping configuration would do. Judge whether a shadow EDGE
rem exists, and do not ship any of these values.
rem
rem Usage: ab-onelamp.cmd <one^|few^|some^|all> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=one"
if "%MAP%"==""  set "MAP=1"

rem FLUX IS CONSERVED ACROSS THE ARMS: intensity is 3000/N, so every arm puts
rem roughly the same total light in the room and the ONLY thing moving is how it
rem is divided. The first version of this ladder held intensity at 3000 in all
rem four arms, so `few` was 8x the light and `some` 32x -- reported as "so much
rem more we cannot make anything out", which is correct and is exactly the
rem confound f7cee45 had to undo in the first density ladder. `all` uses 275
rem rather than 1024 because that is what the room actually wants.
if /i "%WHICH%"=="one" (
  set "MAXL=1"    & set "LI=3000"
) else if /i "%WHICH%"=="few" (
  set "MAXL=8"    & set "LI=375"
) else if /i "%WHICH%"=="some" (
  set "MAXL=32"   & set "LI=94"
) else if /i "%WHICH%"=="all" (
  set "MAXL=1024" & set "LI=11"
) else (
  echo Usage: %~nx0 ^<one^|few^|some^|all^> [map 1-32]
  exit /b 1
)

rem The flat bulb lamps, kept. rt_ceiling_edge_max keeps the NEAREST candidates
rem (the walk collects everything and sorts by distance before capping), so at
rem max 1 it is the lamp in front of you. Radius 0.08 is the dynlight value that
rem demonstrably casts crisply.
set "ARGS=+rt_ceiling_edge_lamps 1 +rt_ceiling_edge_max %MAXL% +rt_ceiling_edge_intensity %LI%"
set "ARGS=%ARGS% +rt_ceiling_edge_radius 0.08 +rt_ceiling_edge_debug 1"

rem Everything else that emits, off. The faux and solo budgets are SEPARATE from
rem rt_ceiling_edge_max and live in the same function, which is why capping that
rem one alone left 8 extra lights uploaded and made the old "one lamp" arm a
rem nine-lamp arm.
set "ARGS=%ARGS% +rt_faux_lamps 0 +rt_solo_lamps 0"
set "ARGS=%ARGS% +rt_wall_strips 0 +rt_hang_lamps 0 +rt_pole_lamp_intensity 0"
set "ARGS=%ARGS% +rt_ceiling_lamps 0 +rt_sector_lights 0 +rt_spin_panels 0"
set "ARGS=%ARGS% +rt_switch_lights 0 +rt_flame_light_on 0 +rt_lava_light_on 0"
set "ARGS=%ARGS% +rt_hand_light_on 0 +rt_dynlight 0"
set "ARGS=%ARGS% +rt_sun 0 +rt_sky 0 +rt_flsh 0 +rt_gunglow 0 +rt_mzlflsh 0"

rem Shadowless fill, off -- otherwise it is a pedestal under whatever umbra forms.
set "ARGS=%ARGS% +rt_sector_emis 0 +rt_emis_mapboost 0 +rt_ceiling_bulb_emis 0"

rem Stated explicitly because it is a Quality-menu slider and will otherwise be
rem whatever was last left in the ini.
set "ARGS=%ARGS% +rt_shadow_samples 1 +rt_debug_visibility 0"

echo === lamp count: %WHICH% (max=%MAXL% I=%LI%, flux held constant), everything else off, MAP%MAP% ===
echo     %ARGS%
echo     CHECK THE CONSOLE: "uploaded=%MAXL% of N wanted" and "faux 0 / solo 0".
echo     If uploaded is not %MAXL%, the arm did not apply and the result is void.
echo     Stand so the fence is between you and the lamp. Judge an EDGE, not brightness.
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
