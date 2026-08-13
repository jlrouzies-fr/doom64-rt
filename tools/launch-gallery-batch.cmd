@echo off
setlocal EnableExtensions
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem Thin wrapper — real launch + resolution force is in launch_gallery_batch.py
set "ROOT=%PROJ%"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
"%PY%" "%ROOT%\tools\launch_gallery_batch.py" %*
exit /b %ERRORLEVEL%
