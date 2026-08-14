@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem CONTRAST: dim the shadowless GI without dimming anything you LOOK at.
rem
rem THE STRUCTURAL FACT THIS LADDER IS BUILT ON, and it appears to be unused.
rem HitInfo.inl:554-582 -- for any material WITH an _e map, emission splits:
rem
rem   PRIMARY / reflection : raw _e, scaled by rt_emis_maxscrcolor
rem                          -> what the bulb looks like on screen, and its bloom
rem   INDIRECT             : _e * emissiveMult, then * rt_emis_mapboost
rem                          -> the room-filling GI, which CANNOT be occluded
rem
rem    #if defined( HITINFO_INL_INDIR )
rem        emission *= tr.emissiveMult;
rem    #endif
rem
rem emissiveMult is applied ONLY under INDIR. So rt_ceiling_bulb_emis (which
rem becomes that mult via RG_MESH_PRIMITIVE_EMISSIVE_OVERRIDE) and
rem rt_emis_mapboost are both INDIRECT-ONLY knobs. Turning them down removes
rem shadowless fill and leaves every emissive surface exactly as bright to look
rem at. That is precisely the trade this problem needs, and nothing has ever
rem used it: the docs treat mapboost as "keep stock, dial the per-texture mult".
rem
rem NOTE rt_ceiling_bulb_emis' own description says "0 was shipped briefly and
rem was wrong on screen -- the bulbs went dead flat and stopped blooming". That
rem is STALE: it predates the primary/indirect split (AGENTS pitfall 10, "was _e
rem GI ignoring emissiveMult -- fixed in RTGL HitInfo INDIR"). With an _e map
rem present the mult can no longer reach the primary ray at all. If the bulbs DO
rem go flat on the noglow arm, that assumption is wrong and this whole ladder is
rem void -- say so, and check whether the pane's _e mask is actually on disk.
rem
rem WHY CONTRAST AND NOT COUNT. Count is measured and it is a dead end for
rem shipping: 1 lamp casts a crisp fence shadow, 8 casts eight overlapping copies
rem already blurring (screen/oneLamp.png, screen/oneWithDebug.png), 283 casts
rem nothing -- but thinning to the counts that shadow makes individual point-light
rem pools visible on the lamp texture, which is the failure open-issues 1.6g
rem exists to prevent. Reported from play as "its ugly, we see the single point
rem light on the texture". So the shadow has to be won on contrast instead.
rem
rem AN EARLIER RUN OF THESE ARMS IS VOID. nosecemis+noglow+noboost were once run
rem together WITH rt_debug_visibility, at 283 lights. That view reports visibility
rem for the one light each pixel chose, so at 283 candidates it tints nearly
rem everything and cannot isolate an occluder (practices 34c). Re-run without it.
rem
rem ARMS -- graded, because 0 is a diagnostic and not a shipping value.
rem
rem   base     mapboost 200  bulb_emis 20  sector_emis 0.35   today. Reference.
rem   gi50     mapboost  50                                   4x less emissive GI
rem   gi25     mapboost  25                                   8x less
rem   gi0      mapboost   0                                   all emissive GI off
rem   noglow   mapboost 200  bulb_emis 0                      the lamp pane's GI
rem                                                           only; bulbs must
rem                                                           look IDENTICAL
rem   flat     mapboost  25  bulb_emis 0   sector_emis 0.1    the combination
rem
rem JUDGE, in this order:
rem   1. does a wire shadow appear on the floor or the wall?
rem   2. on noglow, do the BULBS look the same as base? If they dim, the stale
rem      note was right and the split does not hold here.
rem   3. how much darker is the room, and is it darker in a way that reads as
rem      lighting rather than as underexposure? Emissive GI is the "fake, not ray
rem      traced" flatness of practices 16 -- losing some of it is the point.
rem
rem Usage: ab-fillkill.cmd <base^|gi50^|gi25^|gi0^|noglow^|flat> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=gi25"
if "%MAP%"==""  set "MAP=1"

set "BOOST=200"
set "BULB=20"
set "SEMIS=0.35"

if /i "%WHICH%"=="base" (
  rem reference
) else if /i "%WHICH%"=="gi50" (
  set "BOOST=50"
) else if /i "%WHICH%"=="gi25" (
  set "BOOST=25"
) else if /i "%WHICH%"=="gi0" (
  set "BOOST=0"
) else if /i "%WHICH%"=="noglow" (
  set "BULB=0"
) else if /i "%WHICH%"=="flat" (
  set "BOOST=25" & set "BULB=0" & set "SEMIS=0.1"
) else (
  echo Usage: %~nx0 ^<base^|gi50^|gi25^|gi0^|noglow^|flat^> [map 1-32]
  exit /b 1
)

rem Everything else at play values, stated explicitly so no archived leftover can
rem walk into the comparison. rt_shadow_samples in particular is a Quality-menu
rem slider and will otherwise be whatever the ini last held.
set "ARGS=+rt_emis_mapboost %BOOST% +rt_ceiling_bulb_emis %BULB% +rt_sector_emis %SEMIS%"
set "ARGS=%ARGS% +rt_emis_maxscrcolor 3 +rt_ceiling_bulb_noemis 1"
set "ARGS=%ARGS% +rt_ceiling_bulb_spacing 16 +rt_ceiling_bulb_gain 7"
set "ARGS=%ARGS% +rt_ceiling_edge_radius 0.35 +rt_ceiling_edge_intensity 180"
set "ARGS=%ARGS% +rt_ceiling_edge_seglen 64 +rt_ceiling_edge_max 1024"
set "ARGS=%ARGS% +rt_shadow_samples 1 +rt_debug_visibility 0"

echo === fill/contrast: %WHICH% (mapboost=%BOOST% bulb_emis=%BULB% sector_emis=%SEMIS%), MAP%MAP% ===
echo     %ARGS%
echo     judge: 1) wire shadow  2) on noglow the BULBS must look unchanged  3) darker as LIGHTING, not underexposure
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
