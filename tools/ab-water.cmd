@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the Doom 64 water look on the flats tagged isWater by
rem tools\set_water_meta.py (D64W2_01: MAP10, MAP11, MAP34 -- default map here
rem is 10; D64W1_01: MAP08/14/15/16/22/23/30/34).
rem
rem   stock    rt_water_style 0 -- RTGL's physical water: refract into the media,
rem            Beer-Lambert absorb, mirror the rest. Over-real for this art, and
rem            these are opaque FLOOR flats so the refraction half has nothing
rem            under it to show.
rem   styl     rt_water_style 1 -- the default. Opaque deep blue body carrying
rem            the flat's own caustic veins, Fresnel-weighted reflection on top.
rem   flat     styl with the reflection nearly off (reflmax 0.05) -- isolates how
rem            much of the look is the body/caustics vs the reflection.
rem   mirror   near-mirror: reflmin 0.8 / reflmax 1.0, and wavestren dropped to
rem            1.2 so the reflected image stays readable instead of being
rem            shattered by the wave normal. Closest to Doom II RT's isMirror
rem            water, but keeping the blue body and caustics underneath.
rem   noglow   styl with rt_water_glow 0 -- caustics fully lighting-dependent.
rem            Judge this in a DARK water room: if the pattern disappears there,
rem            the default 0.15 sheen is doing real work.
rem
rem Every arm sets every water cvar explicitly, so a value left over in the ini
rem from a previous arm can never leak into the next one.
rem
rem   debug    paints every surface the shader sees as water -- MAGENTA where
rem            the stylized branch runs, GREEN where RTGL flagged it water but
rem            the stylized gate rejected it, NOTHING if the primitive never
rem            got RG_MESH_PRIMITIVE_WATER -- in which case the "RT water:
rem            tagging" line is also missing from the log. Also
rem            turns on rt_prim_debug, which dumps every world texture name +
rem            BLAS/RASTERIZED state to rt-console.log. rt_water_debug is
rem            NOARCH so it cannot stick in the ini.
rem
rem   nocaus   styl with the PROJECTED caustics off (rt_water_caustics 0), to
rem            separate the pattern on the water itself from the light it
rem            casts on the walls. Also the perf A/B: with it 0, no probe ray.
rem
rem Usage: ab-water.cmd <stock|styl|flat|mirror|noglow|nocaus|debug> [1-32]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=styl"
if "%MAP%"==""  set "MAP=10"

set "TINT=+rt_water_tint_r 5 +rt_water_tint_g 23 +rt_water_tint_b 61"
set "BASE=+rt_water_caustic 1.5 +rt_water_rough 0.1 +rt_water_veinref 0.1"
set "CAUS=+rt_water_caustics 1.2 +rt_water_caustic_scale 0.8 +rt_water_caustic_speed 0.35 +rt_water_caustic_dist 192"
set "WAVE=+rt_water_wavestren 0.4 +rt_water_wavespeed 0.2 +rt_water_areascale 0.35"

if /i "%ARM%"=="stock"  set "ARGS=+rt_water_style 0 %TINT% %BASE% %WAVE% %CAUS% +rt_water_reflmin 0.1 +rt_water_reflmax 0.75 +rt_water_glow 0.15"
if /i "%ARM%"=="styl"   set "ARGS=+rt_water_style 1 %TINT% %BASE% %WAVE% %CAUS% +rt_water_reflmin 0.1 +rt_water_reflmax 0.75 +rt_water_glow 0.15"
if /i "%ARM%"=="flat"   set "ARGS=+rt_water_style 1 %TINT% %BASE% %WAVE% %CAUS% +rt_water_reflmin 0.0 +rt_water_reflmax 0.05 +rt_water_glow 0.15"
if /i "%ARM%"=="mirror" set "ARGS=+rt_water_style 1 %TINT% %BASE% %WAVE% %CAUS% +rt_water_reflmin 0.8 +rt_water_reflmax 1.0 +rt_water_glow 0.15 +rt_water_wavestren 0.4"
if /i "%ARM%"=="nocaus" set "ARGS=+rt_water_style 1 %TINT% %BASE% %WAVE% %CAUS% +rt_water_reflmin 0.1 +rt_water_reflmax 0.75 +rt_water_glow 0.15 +rt_water_caustics 0"
if /i "%ARM%"=="noglow" set "ARGS=+rt_water_style 1 %TINT% %BASE% %WAVE% %CAUS% +rt_water_reflmin 0.1 +rt_water_reflmax 0.75 +rt_water_glow 0"
if /i "%ARM%"=="debug"  set "ARGS=+rt_water_style 1 %TINT% %BASE% %WAVE% %CAUS% +rt_water_reflmax 0.75 +rt_water_glow 0.15 +rt_water_debug 1 +rt_prim_debug 1"

if not defined ARGS (
  echo Usage: %~nx0 ^<stock^|styl^|flat^|mirror^|noglow^|nocaus^|debug^> [1-32]
  exit /b 1
)

echo === water arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
rem The debug arm also passes "debug" -> -rtdebug, which un-mutes RTGL's own
rem messages. The one that matters is "Reloaded texture meta: rt/data/textures.json":
rem without that line the JSON never parsed, and no amount of shader work can help.
set "DBG="
if /i "%ARM%"=="debug" set "DBG=debug"
call "%~dp0launch-retribution-rt.cmd" %MAP% %DBG% -- %ARGS%
exit /b %ERRORLEVEL%
