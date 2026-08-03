@echo off
setlocal EnableExtensions
set "ROOT=G:\AI\Doom64-RT"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
rem World emis + existing enemy eyes (WashScratch starts from stock — eyes must be staged)
"%PY%" "%ROOT%\tools\wash-scratch\apply_stage.py" stage_world_emis
if errorlevel 1 exit /b 1
"%PY%" "%ROOT%\tools\wash-scratch\apply_stage.py" stage_enemy_eyes
if errorlevel 1 exit /b 1
set "WASH_TITLE=S06 MAP01 play on WashScratch"
set "WASH_MAPBOOST=200"
set "WASH_MODE=map01"
set "WASH_DYNLIGHT=1"
call "%~dp0_launch.cmd"
