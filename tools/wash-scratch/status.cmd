@echo off
setlocal
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..\..") do set "PROJ=%%~fI"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
"%PY%" "%PROJ%\tools\wash-scratch\apply_stage.py" status
dir "%PROJ%\sourcecode\gzdoom-rt\build\WashScratch\gzdoom.exe" 2>nul
dir "%PROJ%\sourcecode\gzdoom-rt\build\WashScratch\rt\bin\RTGL1.dll" 2>nul
