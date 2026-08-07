@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the DLSS-RR disocclusion mask (rt_rr_disocc), which is the ONLY new
rem RR-specific input added on 2026-08-06 -- the window where the worm/black-grain
rem regression appeared. Everything else changed that day either feeds both
rem denoisers (so A-SVGF would show it too, and it does not) or was already
rem cleared by an A/B.
rem
rem This arm only became meaningful after the 2026-08-07 fix: rt_rr_disocc 0 used
rem to leave pInDisocclusionMask BOUND while writing zeros into it, so the "off"
rem arm never actually tested "no mask". An all-zero mask is not the same thing
rem as no mask -- if NGX reads it as per-pixel history VALIDITY rather than as a
rem discard sentinel, all-zero means "drop history everywhere, every frame",
rem which is RR running with no temporal accumulation at all.
rem
rem   0 = pInDisocclusionMask = nullptr  (pre-2026-08-06 state)
rem   1 = mask bound                     (current default)
rem
rem Confirm the arm took: the console log prints
rem   RR guides: pInDisocclusionMask=nullptr|BOUND, ...
rem Check that line before believing any result.
rem
rem Usage: ab-rr-disocc.cmd <0|1> [1-32]
rem ---------------------------------------------------------------------------

rem ARM "show": tints every tile RED at the moment it tells RR to discard
rem history. This measures the mechanism directly instead of asking anyone to
rem judge noise. Stand still -- expect sparse red, mostly around sprites. Then
rem WALK AND TURN. If the screen fills with red while moving and clears when you
rem stop, the mask is firing on camera motion (reprojected tile luminance shifts
rem with parallax and disocclusion, not just with real lighting changes), which
rem wipes RR's history exactly when you move. That would be the cause.
set "MODE=%~1"
set "MAP=%~2"
if "%MODE%"=="" set "MODE=0"
if "%MAP%"==""  set "MAP=2"

if /i "%MODE%"=="show" (
  echo === rt_rr_disocc_show 1, MAP%MAP% ===
  echo     stand still, then WALK: does the screen fill with red while moving?
  call "%~dp0launch-retribution-rt.cmd" %MAP% -- +rt_rr_disocc 1 +rt_rr_disocc_show 1
  exit /b %ERRORLEVEL%
)

if not "%MODE%"=="0" if not "%MODE%"=="1" (
  echo Usage: %~nx0 ^<0^|1^|show^> [1-32]
  exit /b 1
)

echo === rt_rr_disocc %MODE%, MAP%MAP% ===
call "%~dp0launch-retribution-rt.cmd" %MAP% -- +rt_rr_disocc %MODE% +rt_rr_disocc_show 0
exit /b %ERRORLEVEL%
