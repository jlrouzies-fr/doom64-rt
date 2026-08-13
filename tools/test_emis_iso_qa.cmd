@echo off
setlocal
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem Walled batch-room emissive isolation at stock mapboost 200.
rem ~7 screenshots (CONTROL / MIRROR / SMON / LAVA / CRT / GLOW / OUTTEX), not 700.
set "ROOT=%PROJ%"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"

cd /d "%ROOT%" || exit /b 1

echo === regen world emis (full mults, visible at boost 200) ===
"%PY%" "%ROOT%\tools\gen_world_emissives.py" || exit /b 1

echo === run sealed-room batch tour ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\run_emis_iso_qa.ps1" ^
  -OutDir "%ROOT%\screen\emis_iso" -EmisMapBoost 200
exit /b %ERRORLEVEL%
