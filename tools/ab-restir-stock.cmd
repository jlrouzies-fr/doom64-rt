@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Pin the three cvars introduced by b031a21 to their stock-equivalent values,
rem on the CURRENT build.
rem
rem Bisect result: aug07bn (3adfcf8) is clean, aug07mid (b031a21) is wormy, so
rem the DLSS-RR worm regression entered in b031a21 -- "Add ReSTIR M debug view,
rem shadow-sample and temporal-jitter knobs".
rem
rem That commit did two separable things: it added three cvars, and it
rem restructured the direct-lighting code around them. This arm separates those.
rem The stock equivalents are:
rem   rt_restir_tjitter 2    == the old hardcoded TEMPORAL_RADIUS 2
rem   rt_shadow_samples 1    == the old single traceVisibility()
rem   rt_debug_restir_m 0    == debug view off
rem
rem   stock  = all three pinned to the values the code used before the commit
rem   live   = whatever they currently resolve to (default or ini)
rem
rem If "stock" is clean, a cvar was carrying a non-stock value and the code is
rem fine -- most likely rt_restir_tjitter, since jitter 0 makes every pixel
rem reproject to exactly the same previous pixel, which correlates temporal reuse
rem across the whole frame and turns residual noise into structure.
rem If "stock" is still wormy, the regression is in the restructure itself.
rem
rem Usage: ab-restir-stock.cmd <stock|live> [1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=stock"
if "%MAP%"==""  set "MAP=2"

rem BOTH arms set every value EXPLICITLY. An arm that just omits the cvars is
rem worthless here: these are CVAR_ARCHIVE, so the previous run's values persist
rem and an "leave it at whatever it is" arm silently becomes a copy of whichever
rem arm ran last. That already produced one false "no difference" result.
if /i "%WHICH%"=="stock" (
  set "ARGS=+rt_restir_tjitter 2 +rt_shadow_samples 1 +rt_debug_restir_m 0 +rt_rr_spechitdist 1"
) else if /i "%WHICH%"=="broken" (
  rem The exact values found stuck in the config on 2026-08-07, i.e. leftovers
  rem from this session's A/B runs. rt_restir_tjitter 0 is the suspected cause:
  rem no jitter means every pixel reprojects to exactly the same previous pixel,
  rem so neighbouring pixels reuse in lockstep and the residual noise becomes
  rem spatially correlated -- filaments once RR's temporal pass smears it.
  set "ARGS=+rt_restir_tjitter 0 +rt_shadow_samples 3 +rt_debug_restir_m 0 +rt_rr_spechitdist 0"
) else (
  echo Usage: %~nx0 ^<stock^|broken^> [1-32]
  exit /b 1
)

echo === b031a21 cvars: %WHICH%, MAP%MAP% ===
echo     %ARGS%
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
