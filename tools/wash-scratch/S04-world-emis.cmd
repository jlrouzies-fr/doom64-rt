@echo off
setlocal EnableExtensions
set "ROOT=G:\AI\Doom64-RT"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
"%PY%" "%ROOT%\tools\wash-scratch\apply_stage.py" stage_world_emis
if errorlevel 1 exit /b 1
set "WASH_TITLE=S04 world allowlist emis only"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_MODE=gallery"
set "WASH_DYNLIGHT=0"
call "%~dp0_launch.cmd"
