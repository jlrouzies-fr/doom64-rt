@echo off
setlocal
rem Windowed auto-load MAP01 — no menu clicks needed.
rem Usage: launch-retribution-windowed.cmd [diag|rt|modcompat]
set "MODE=%~1"
if "%MODE%"=="" set "MODE=diag"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke-retribution-auto.ps1" -Mode %MODE% -WaitSeconds 20
