@echo off
rem Shared launcher body for wash-qa/*.cmd
rem Expects: WASH_TITLE, WASH_MAPBOOST, WASH_SKY, WASH_VARIANT (optional: live|indir_kill|clamp)
setlocal EnableExtensions

if not defined WASH_TITLE set "WASH_TITLE=gallery wash QA"
if not defined WASH_MAPBOOST set "WASH_MAPBOOST=200"
if not defined WASH_SKY set "WASH_SKY=80"
if not defined WASH_VARIANT set "WASH_VARIANT=live"
if not defined WASH_MZLFLSH set "WASH_MZLFLSH=1"
if not defined WASH_EMPTY set "WASH_EMPTY=0"

set "ROOT=G:\AI\Doom64-RT"
set "ENGINE=%ROOT%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=%ROOT%\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=%ROOT%\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "SKY=%ROOT%\Doom64-Retribution\d64r-rt-sky.pk3"
set "SPAWN=%ROOT%\Doom64-Retribution\d64r-gallery-spawn-wallturned.pk3"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
set "VARROOT=%ROOT%\tools\wash-qa\variants"

if "%WASH_EMPTY%"=="1" (
  set "GAL=%ROOT%\Doom64-Retribution\d64remptyg.wad"
  set "INFO=%ROOT%\Doom64-Retribution\d64r-emptygallery-mapinfo.pk3"
) else (
  set "GAL=%ROOT%\Doom64-Retribution\d64rtexg.wad"
  set "INFO=%ROOT%\Doom64-Retribution\d64r-texgallery-mapinfo.pk3"
)

cd /d "%ENGINE%" || exit /b 1

if /I "%WASH_VARIANT%"=="live" (
  if exist "%VARROOT%\live\RTGL1.dll" (
    echo Deploying RTGL variant: live
    copy /Y "%VARROOT%\live\RTGL1.dll" "%ENGINE%\rt\bin\" >nul
    if exist "%VARROOT%\live\*.spv" xcopy /Y /Q "%VARROOT%\live\*.spv" "%ENGINE%\rt\shaders\" >nul
  )
) else (
  if not exist "%VARROOT%\%WASH_VARIANT%\RTGL1.dll" (
    echo ERROR: missing variant "%WASH_VARIANT%"
    echo Run first: powershell -File "%ROOT%\tools\wash-qa\prepare-variants.ps1"
    exit /b 1
  )
  echo Deploying RTGL variant: %WASH_VARIANT%
  copy /Y "%VARROOT%\%WASH_VARIANT%\RTGL1.dll" "%ENGINE%\rt\bin\" >nul
  if exist "%VARROOT%\%WASH_VARIANT%\*.spv" (
    xcopy /Y /Q "%VARROOT%\%WASH_VARIANT%\*.spv" "%ENGINE%\rt\shaders\" >nul
  )
)

if not exist "gzdoom.exe" (
  echo ERROR: missing gzdoom.exe
  exit /b 1
)
if not exist "rt\bin\RTGL1.dll" (
  echo ERROR: missing RTGL1.dll
  exit /b 1
)
if not exist "%GAL%" (
  if "%WASH_EMPTY%"=="1" (
    echo Building empty gallery ...
    "%PY%" "%ROOT%\tools\build_empty_gallery.py" || exit /b 1
  ) else (
    echo ERROR: missing gallery wad — run: python tools\build_texture_gallery.py
    exit /b 1
  )
)

if "%WASH_EMPTY%"=="1" (
  echo Ensuring empty gallery wad ...
  "%PY%" "%ROOT%\tools\build_empty_gallery.py" || exit /b 1
) else (
  echo Syncing baseline PBR ...
  "%PY%" "%ROOT%\tools\sync_gallery_pbr_set.py" baseline || exit /b 1
)
echo Packing wallturned spawn ...
"%PY%" "%ROOT%\tools\pack_gallery_spawn_wallturned.py" || exit /b 1

echo.
echo ============================================================
echo  %WASH_TITLE%
echo  spawn: wallturned  mapboost=%WASH_MAPBOOST%  sky=%WASH_SKY%  rtgl=%WASH_VARIANT%  mzlflsh=%WASH_MZLFLSH%
echo  Look: blotchy circular wash on STONE2 right wall while walking / shooting.
echo  Quit when done, then run the next numbered .cmd
echo ============================================================
echo.

if "%WASH_MZLFLSH%"=="0" (
  set "MZL_CVARS=+rt_mzlflsh false"
) else (
  set "MZL_CVARS=+rt_mzlflsh true"
)

start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%GAL%" "%INFO%" "%SKY%" "%SPAWN%" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +sv_cheats 1 +map map99 ^
  +god +fly ^
  +rt_mod_compat 1 +r_drawvoxels 0 ^
  +rt_fluid false +rt_autoexport false ^
  +rt_upscale_dlss 2 +rt_rayreconstr 1 +rt_framegen 0 ^
  +gl_noskyboxes true ^
  +rt_sky %WASH_SKY% +rt_sky_always true ^
  +rt_classic 0 ^
  +rt_flsh 0 ^
  %MZL_CVARS% ^
  +rt_emis_mapboost %WASH_MAPBOOST% +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor 12 ^
  +rt_autoexport_light 50 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1

endlocal
