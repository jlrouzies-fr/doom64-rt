@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the DLSS-RR albedo-guide contents (rt_rr_guide_mode) to bisect the worm
rem artifact. The worms were reportedly ABSENT in the first iterations where RR
rem actually ran, and the 2026-08-06 guide rework is the only change in that
rem window that touches what RR is told the albedo is.
rem
rem   0 = raw albedo / F0                      (pre-2026-08-05 behaviour)
rem   1 = ro_d/envBRDF * throughput * ambient  (current default, the suspect)
rem   2 = ro_d/envBRDF only, no throughput/ambient
rem
rem Mode 2 is the discriminator: if 0 and 2 are both clean, the culprit is
rem throughput+ambient in the guide; if only 0 is clean, it is the reflectivity
rem model (ro_d / envBRDFApprox2) instead.
rem
rem Usage: ab-rr-guide.cmd <0|1|2> [1-32]
rem Everything else is inherited from launch-retribution-rt.cmd, so this stays
rem in sync with the real config. RR is forced on and DLAA is NOT forced --
rem judge at your normal Balanced preset, since that is where it is worst.
rem ---------------------------------------------------------------------------

set "MODE=%~1"
set "MAP=%~2"
if "%MODE%"=="" set "MODE=1"
if "%MAP%"==""  set "MAP=2"

if not "%MODE%"=="0" if not "%MODE%"=="1" if not "%MODE%"=="2" (
  echo Usage: %~nx0 ^<0^|1^|2^> [1-32]
  exit /b 1
)

echo === rt_rr_guide_mode %MODE%, MAP%MAP% ===
call "%~dp0launch-retribution-rt.cmd" %MAP% -- +rt_rr_guide_mode %MODE%
exit /b %ERRORLEVEL%
