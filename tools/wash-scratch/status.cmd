@echo off
setlocal
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
"%PY%" "G:\AI\Doom64-RT\tools\wash-scratch\apply_stage.py" status
dir "G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\WashScratch\gzdoom.exe" 2>nul
dir "G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\WashScratch\rt\bin\RTGL1.dll" 2>nul
