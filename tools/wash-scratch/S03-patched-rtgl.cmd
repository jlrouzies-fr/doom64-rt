@echo off
setlocal EnableExtensions
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..\..") do set "PROJ=%%~fI"
set "ROOT=%PROJ%"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
"%PY%" "%ROOT%\tools\wash-scratch\apply_stage.py" stage_rtgl_live
if errorlevel 1 exit /b 1
set "WASH_TITLE=S03 patched RTGL + still scrubbed meta"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_MODE=gallery"
set "WASH_DYNLIGHT=0"
call "%~dp0_launch.cmd"
