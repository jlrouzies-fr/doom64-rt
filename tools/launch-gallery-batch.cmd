@echo off
setlocal EnableExtensions
rem Thin wrapper — real launch + resolution force is in launch_gallery_batch.py
set "ROOT=G:\AI\Doom64-RT"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
"%PY%" "%ROOT%\tools\launch_gallery_batch.py" %*
exit /b %ERRORLEVEL%
