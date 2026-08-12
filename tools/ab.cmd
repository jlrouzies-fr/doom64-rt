@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem ONE A/B runner. An arm is a CONFIG FILE, not a command-line string.
rem
rem   .\tools\ab.cmd smoke-fat 03
rem   .\tools\ab.cmd smoke-probeuni
rem   .\tools\ab.cmd list
rem
rem Arms live in tools\arms\*.cfg and are applied with +exec AFTER the base pins
rem in tools\d64rt-pins.cfg, so an arm always wins. Each arm states every value
rem it cares about, because those cvars are CVAR_ARCHIVE and would otherwise
rem inherit whatever the previous arm left in the ini.
rem
rem WHY THIS EXISTS. Every ab-*.cmd used to spell its arm out as "-- +cvar value"
rem on the command line. The launcher already passed ~325 pins the same way, so
rem the assembled line reached 8016 characters -- and cmd.exe truncates at 8191.
rem The passthrough sits at the END of that line, so once the pins grew past the
rem limit the arm was silently dropped and the game ran on defaults while the
rem tool printed the values it believed it had set. Three debugging runs were
rem lost to a shader probe that never activated. A cfg is immune: it is one short
rem +exec, it is diffable, and it can be read back after the fact.
rem
rem Add an arm by dropping a .cfg in tools\arms. Anything after "--" is still
rem appended verbatim and still wins, for one-off tweaks:
rem
rem   .\tools\ab.cmd smoke-full 03 -- +rt_smoke_density 20
rem ---------------------------------------------------------------------------

set "ARMDIR=%~dp0arms"

if /i "%~1"=="list" goto :list
if "%~1"=="" goto :list

set "ARM=%~1"
set "MAP=%~2"
if "%MAP%"=="" set "MAP=03"

set "CFG=%ARMDIR%\%ARM%.cfg"
if not exist "%CFG%" (
  echo ERROR: no such arm: %ARM%
  echo   expected %CFG%
  goto :list
)

rem Collect anything after "--" so one-off overrides still work.
set "EXTRA="
set "SEEN="
for %%A in (%*) do (
  if defined SEEN (
    call set "EXTRA=%%EXTRA%% %%~A"
  ) else (
    if "%%~A"=="--" set "SEEN=1"
  )
)

echo === arm "%ARM%", MAP%MAP% ===
echo     %CFG%
if defined EXTRA echo     extra: %EXTRA%
echo.
echo     Read the arm back in game with `smoke` (or the cvar name) to confirm it
echo     applied -- a tool printing a value is not evidence that the game took it.
echo.
call "%~dp0launch-retribution-rt.cmd" %MAP% debug -- +exec "%CFG%" %EXTRA%
exit /b %ERRORLEVEL%

:list
echo Usage: %~nx0 ^<arm^> [map 1-34] [-- +cvar value ...]
echo.
echo Arms in %ARMDIR%:
for %%F in ("%ARMDIR%\*.cfg") do echo    %%~nF
exit /b 1
