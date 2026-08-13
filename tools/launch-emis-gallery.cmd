@echo off
setlocal EnableExtensions
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem World-emissives-only MAP99 gallery (monitors / EXIT / keys / CRT / lava).
set "ROOT=%PROJ%"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
"%PY%" "%ROOT%\tools\launch_emis_gallery.py" %*
exit /b %ERRORLEVEL%
