@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Bisect: why do sprites and fences no longer cast visible shadows?
rem
rem Evidence so far
rem   - a muzzle flash still casts a clear shadow          -> shadow rays work
rem   - the fence used to cast a shadow on the wall        -> world geometry too,
rem                                                           not a sprite-only
rem                                                           or alpha-test issue
rem   - ab-bulb-density changed nothing                    -> NOT light count
rem
rem The count result kills the "many lights fill the umbra" theory. What is left
rem must be something that adds light INDEPENDENT of how many analytic lights
rem exist -- i.e. a uniform fill term.
rem
rem Prime suspect: emissive surfaces. rt_sector_emis makes bright surfaces
rem self-emit and rt_emis_mapboost multiplies it by 200. Section 12: emission is
rem only collected on indirect bounces, never through processDirectIllumination,
rem so it cannot cast a shadow at any strength -- it can only ADD diffuse fill.
rem Fill is exactly what erases an umbra, and it does so no matter how the
rem analytic lights are distributed. Section 16 already described this look on
rem MAP03: "uniformly bright and directionless".
rem
rem If that is right, `noemis` restores shadows and `nolights` does not.
rem If BOTH restore them, the cause is additive and neither theory alone holds.
rem If NEITHER does, it is not our lighting at all and the next place to look is
rem RTGL1's traceShadowRay cull mask (Source/Shaders/RaygenCommon.h:322) --
rem shadow rays see only INSTANCE_MASK_WORLD_0, and WORLD_1 is "no shadows"
rem geometry keyed off RG_MESH_PRIMITIVE_NO_SHADOW.
rem
rem ARMS (every arm sets every knob explicitly -- section 9)
rem   all       current build, everything on. The baseline.
rem   noemis    emissive fill OFF, all analytic lights ON.
rem   nolights  all our analytic light paths OFF, emissive fill ON.
rem   stock     both OFF. Only GZDoom dynlights remain -- closest to the
rem             "no tweaks" state where shadows worked.
rem
rem Stand somewhere with a fence or a prop between you and a lamp, and compare
rem the SAME spot across arms. Judge only "is there an umbra", not brightness --
rem the arms differ hugely in brightness by construction.
rem
rem Usage: ab-shadow-hunt.cmd <all^|noemis^|nolights^|stock> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=noemis"
if "%MAP%"==""  set "MAP=1"

rem Defaults, then each arm overrides what it needs.
set "EMIS=+rt_sector_emis 0.35 +rt_emis_mapboost 200"
set "LIGHTS=+rt_wall_strips 1 +rt_ceiling_edge_lamps 1 +rt_hang_lamps 1 +rt_pole_lamp_intensity 300"

if /i "%WHICH%"=="all" (
  rem keep both defaults
) else if /i "%WHICH%"=="noemis" (
  set "EMIS=+rt_sector_emis 0 +rt_emis_mapboost 0"
) else if /i "%WHICH%"=="nolights" (
  set "LIGHTS=+rt_wall_strips 0 +rt_ceiling_edge_lamps 0 +rt_hang_lamps 0 +rt_pole_lamp_intensity 0"
) else if /i "%WHICH%"=="stock" (
  set "EMIS=+rt_sector_emis 0 +rt_emis_mapboost 0"
  set "LIGHTS=+rt_wall_strips 0 +rt_ceiling_edge_lamps 0 +rt_hang_lamps 0 +rt_pole_lamp_intensity 0"
) else (
  echo Usage: %~nx0 ^<all^|noemis^|nolights^|stock^> [map 1-32]
  exit /b 1
)

rem Held fixed across every arm so the comparison stays valid:
rem   dynlight on  - the muzzle flash is the known-good shadow reference
rem   sector_lights off, ceiling_lamps off - not part of this question
set "FIXED=+rt_dynlight 1 +rt_dynlight_intensity 40 +rt_sector_lights 0 +rt_ceiling_lamps 0"

set "ARGS=%EMIS% %LIGHTS% %FIXED%"

echo === shadow hunt: %WHICH%, MAP%MAP% ===
echo     %ARGS%
echo     compare the SAME spot across arms; judge umbra only, not brightness
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
