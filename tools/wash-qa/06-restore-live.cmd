@echo off
rem Restore live RTGL from variants\live after testing 04/05.
setlocal
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..\..") do set "PROJ=%%~fI"
set "ROOT=%PROJ%"
set "ENGINE=%ROOT%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "VAR=%ROOT%\tools\wash-qa\variants\live"
if not exist "%VAR%\RTGL1.dll" (
  echo ERROR: no stashed live variant. Re-run prepare-variants.ps1 or tools\build-rtgl.cmd
  exit /b 1
)
echo Restoring live RTGL from %VAR%
copy /Y "%VAR%\RTGL1.dll" "%ENGINE%\rt\bin\" >nul
if exist "%VAR%\*.spv" xcopy /Y /Q "%VAR%\*.spv" "%ENGINE%\rt\shaders\" >nul
echo Done. Live DLL restored.
dir "%ENGINE%\rt\bin\RTGL1.dll"
endlocal
