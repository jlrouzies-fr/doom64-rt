@echo off
rem ===========================================================================
rem  Apply a labelling-page export: textures.json AND the _orm.png maps.
rem
rem    1. In the page, press "copy JSON".
rem    2. Paste it over tools\_material_labels\map01.json (whole file).
rem    3. Run this.
rem    4. Relaunch the game. No rebuild -- both are data.
rem
rem  Both halves are needed and they are not interchangeable:
rem    apply_material_labels.py  -> metallicDefault / roughnessDefault in
rem                                 textures.json, which the renderer reads ONLY
rem                                 for textures that have no _orm map.
rem    bake_material_labels_orm.py -> the G and B channels of the _orm.png maps,
rem                                 which win outright wherever they exist --
rem                                 i.e. for nearly everything in this game.
rem
rem  Usage:  tools\apply-labels.cmd [labels.json]
rem          tools\apply-labels.cmd --revert
rem ===========================================================================
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "PROJ=%%~fI"

set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"

set "LABELS=%~1"
if "%LABELS%"=="" set "LABELS=%PROJ%\tools\_material_labels\map01.json"

rem The game holds the material PNGs open; writing under it is asking for a
rem half-written map and a puzzling render.
taskkill /IM gzdoom.exe /F >nul 2>&1

if /i "%LABELS%"=="--revert" (
  echo === Reverting both halves to the pre-label state ===
  "%PY%" "%PROJ%\tools\apply_material_labels.py" --revert
  "%PY%" "%PROJ%\tools\bake_material_labels_orm.py" --revert
  goto :done
)

if not exist "%LABELS%" (
  echo ERROR: no labels file at "%LABELS%"
  echo        Paste the page's JSON export there first.
  exit /b 1
)

echo === textures.json ===
"%PY%" "%PROJ%\tools\apply_material_labels.py" "%LABELS%"
if errorlevel 1 exit /b 1

echo.
echo === _orm.png maps ===
"%PY%" "%PROJ%\tools\bake_material_labels_orm.py" "%LABELS%"
if errorlevel 1 exit /b 1

:done
echo.
echo Relaunch to see it. Nothing to rebuild.
echo   .\tools\launch-retribution-rt.cmd 1
endlocal
