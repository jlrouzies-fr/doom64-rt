@echo off
rem ===========================================================================
rem  Open one startup-check window on its own, without starting the game.
rem
rem  Called by ui-wpf.cmd (the window that ships) and ui-classic.cmd (the
rem  WinForms fallback), which is what you double-click. Both find exactly the
rem  same things -- the finding lives in launch-doom64-rt-checks.ps1 and is
rem  shared -- so what differs is only how they look at your DPI.
rem ===========================================================================
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "PROJ=%%~fI"

set "VARIANT=%~1"
if "%VARIANT%"=="" set "VARIANT=wpf"
set "UI=%PROJ%\launch-doom64-rt-ui.ps1"
if /i "%VARIANT%"=="classic" set "UI=%PROJ%\launch-doom64-rt-ui-classic.ps1"
if not exist "%UI%" (
  echo   no such window: %VARIANT%
  exit /b 1
)

rem Same layout probing the real launcher does, so the checklist is the real one.
set "ENGINE=%PROJ%"
if not exist "%ENGINE%\gzdoom.exe" set "ENGINE=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "MODS=%PROJ%\mods"
if not exist "%MODS%" set "MODS=%PROJ%\Doom64-Retribution"
set "GAME=%PROJ%\game"
if not exist "%GAME%" set "GAME=%PROJ%\Doom64-Retribution"

rem A scratch settings file: looking at a window must not rewrite the launcher's.
rem configdone.txt is NOT scratch -- it goes where the launcher reads it, so the
rem "setup is done" box can be tested for real from here.
set "SETTINGS=%TEMP%\d64rt-ui-preview.txt"

echo.
echo   window   : %VARIANT%
echo   settings : %SETTINGS%  (scratch)
echo   note     : ticking "setup is done" and pressing RIP AND TEAR writes
echo              %PROJ%\configdone.txt for real. Delete it to undo.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%UI%" ^
  -Proj "%PROJ%" -EngineDir "%ENGINE%" -ModsDir "%MODS%" -GameDir "%GAME%" ^
  -IwadHint "%D64RT_IWAD%" -Settings "%SETTINGS%"
echo   exit %ERRORLEVEL%   (0 = would launch, 1 = closed)
echo.
pause
endlocal
