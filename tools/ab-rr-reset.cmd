@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Is DLSS-RR's temporal history being flushed while the camera moves?
rem
rem Established: ReSTIR reservoir M stays high in motion (ab-restir-m.cmd), so
rem light selection is fine and the instability is DOWNSTREAM, in RR's own
rem temporal history. Two triggers can wipe that history, and one of them is
rem driven by camera motion:
rem
rem   rt_rr_reset_on_dynlight - fires whenever the set of UPLOADED dynamic light
rem     IDs changes frame-over-frame. That set is culled by visibility, so simply
rem     walking makes lights enter and leave it. Each change sets InReset, which
rem     discards RR's entire history -- up to 4x/second under the 250ms rate
rem     limit. Clean when still (set stable), noisy in motion (history wiped).
rem   rt_rr_reset_on_lightcut - flashlight on/off only. Not motion-driven.
rem
rem NOTE: every A/B run before 2026-08-07 evening is void. They all ran with
rem rt_restir_tjitter stuck at 0, whose worm artifact dominated the image.
rem
rem ARMS
rem   debug - default settings + rt_rr_reset_debug 1. Walk around for ~20s, then
rem           read rt-console.log: it prints each flush with its cause plus a
rem           once-a-second fired/suppressed tally. A steady stream of flushes
rem           while moving, and near-silence while still, confirms the mechanism.
rem   off   - rt_rr_reset_on_dynlight 0 (flashlight cut still flushes). If motion
rem           noise drops sharply, this is the cause.
rem   on    - rt_rr_reset_on_dynlight 1, the current default, for comparison.
rem
rem Usage: ab-rr-reset.cmd <debug|off|on> [1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=debug"
if "%MAP%"==""  set "MAP=2"

if /i "%WHICH%"=="debug" (
  set "ARGS=+rt_rr_reset_on_dynlight 1 +rt_rr_reset_on_lightcut 1 +rt_rr_reset_debug 1"
) else if /i "%WHICH%"=="off" (
  set "ARGS=+rt_rr_reset_on_dynlight 0 +rt_rr_reset_on_lightcut 1 +rt_rr_reset_debug 0"
) else if /i "%WHICH%"=="on" (
  set "ARGS=+rt_rr_reset_on_dynlight 1 +rt_rr_reset_on_lightcut 1 +rt_rr_reset_debug 0"
) else (
  echo Usage: %~nx0 ^<debug^|off^|on^> [1-32]
  exit /b 1
)

echo === RR history flush: %WHICH%, MAP%MAP% ===
echo     %ARGS%
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
