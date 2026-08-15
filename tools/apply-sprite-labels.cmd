@echo off
rem ===========================================================================
rem  Apply a SPRITE labelling-page export: the per-frame _orm.png maps.
rem
rem    1. In the page, press "copy JSON".
rem    2. Paste it over tools\_material_labels\sprites_<section>.json --
rem       sprites_weapons.json, sprites_monsters.json, sprites_projectiles.json,
rem       sprites_props.json. One file per page, because they get labelled at
rem       different times and applying one must never un-apply the rest.
rem    3. Run this. With no argument it bakes EVERY sprites_*.json it finds.
rem    4. Relaunch the game. No rebuild -- it is data.
rem
rem  Unlike tools\apply-labels.cmd there is NO textures.json half, and that is
rem  deliberate: a sprite needs a PER-TEXEL answer. A shotgun is a metal
rem  receiver, a wooden stock and two hands, and one metallicDefault for the
rem  whole image would be wrong for every sprite this tool exists for.
rem
rem  Usage:  tools\apply-sprite-labels.cmd [labels.json]
rem          tools\apply-sprite-labels.cmd --revert
rem ===========================================================================
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "PROJ=%%~fI"

set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"

set "LABELS=%~1"

rem The game holds the material PNGs open; writing under it is asking for a
rem half-written map and a puzzling render.
taskkill /IM gzdoom.exe /F >nul 2>&1

if /i "%LABELS%"=="--revert" (
  echo === Reverting the sprite _orm maps ===
  "%PY%" "%PROJ%\tools\bake_sprite_materials.py" --revert
  goto :done
)

rem No argument: every section that has been labelled so far. The baker takes
rem them all in one pass, so a fresh sprites_monsters.json does not cost the
rem weapons their materials.
if "%LABELS%"=="" (
  set "FOUND="
  for %%F in ("%PROJ%\tools\_material_labels\sprites_*.json") do set "FOUND=1"
  if not defined FOUND (
    echo ERROR: no tools\_material_labels\sprites_*.json found.
    echo        Paste a page's JSON export there first, e.g. sprites_weapons.json
    exit /b 1
  )
  echo === sprite _orm.png maps ===
  "%PY%" "%PROJ%\tools\bake_sprite_materials.py" "%PROJ%\tools\_material_labels\sprites_*.json"
  if errorlevel 1 exit /b 1
  goto :done
)

if not exist "%LABELS%" (
  echo ERROR: no labels file at "%LABELS%"
  echo        Paste the page's JSON export there first.
  exit /b 1
)

echo === sprite _orm.png maps ===
"%PY%" "%PROJ%\tools\bake_sprite_materials.py" "%LABELS%"
if errorlevel 1 exit /b 1

:done
echo.
echo Relaunch to see it. Nothing to rebuild.
endlocal
