@echo off
setlocal EnableExtensions
rem World-emissives-only MAP99 gallery (monitors / EXIT / keys / CRT / lava).
set "ROOT=G:\AI\Doom64-RT"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
"%PY%" "%ROOT%\tools\launch_emis_gallery.py" %*
exit /b %ERRORLEVEL%
