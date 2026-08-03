@echo off
setlocal EnableExtensions
set "ROOT=G:\AI\Doom64-RT"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
echo.
echo === WashScratch bootstrap (destroys existing WashScratch tree) ===
echo Play build RelWithDebInfo is NOT touched.
echo.
"%PY%" "%ROOT%\tools\wash-scratch\apply_stage.py" bootstrap
if errorlevel 1 exit /b 1
echo.
echo Next: tools\wash-scratch\S01-stock-baseline.cmd
exit /b 0
