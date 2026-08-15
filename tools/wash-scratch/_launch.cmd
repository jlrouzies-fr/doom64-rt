@echo off
rem Shared WashScratch launcher. Expects WASH_* vars set by caller.
setlocal EnableExtensions
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..\..") do set "PROJ=%%~fI"

if not defined WASH_TITLE set "WASH_TITLE=WashScratch"
if not defined WASH_MAPBOOST set "WASH_MAPBOOST=200"
if not defined WASH_SKY set "WASH_SKY=80"
if not defined WASH_MODE set "WASH_MODE=gallery"
if not defined WASH_DYNLIGHT set "WASH_DYNLIGHT=0"
if not defined WASH_MAXSCR set "WASH_MAXSCR=3"
if not defined WASH_EMPTY set "WASH_EMPTY=0"

set "ROOT=%PROJ%"
set "ENGINE=%ROOT%\sourcecode\gzdoom-rt\build\WashScratch"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=%ROOT%\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=%ROOT%\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "SKY=%ROOT%\Doom64-Retribution\d64r-rt-sky.pk3"
set "SPAWN=%ROOT%\Doom64-Retribution\d64r-gallery-spawn-wallturned.pk3"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
set "FIX=%ROOT%\Doom64-Retribution\d64r-3dfloor-rtfix.wad"
set "SKUL=%ROOT%\Doom64-Retribution\d64r-lostsoul-rt.pk3"
set "MUS=%ROOT%\Doom64-Retribution\D64MUS.PK3"

if not exist "%ENGINE%\gzdoom.exe" (
  echo ERROR: WashScratch missing — run tools\wash-scratch\00-bootstrap.cmd first
  exit /b 1
)
if not exist "%ENGINE%\rt\bin\RTGL1.dll" (
  echo ERROR: missing %ENGINE%\rt\bin\RTGL1.dll
  exit /b 1
)
if not exist "%ENGINE%\rt\bin\nvngx_dlssd.dll" (
  echo ERROR: missing nvngx_dlssd.dll ^(DLSS Ray Reconstruction^)
  echo Fix: python tools\wash-scratch\apply_stage.py fix_nvidia
  echo Or re-run tools\wash-scratch\00-bootstrap.cmd
  exit /b 1
)

cd /d "%ENGINE%" || exit /b 1

if /I "%WASH_MODE%"=="map01" goto :map01
if /I "%WASH_MODE%"=="emis" goto :emis

rem --- texture gallery (MAP99 wallturned) ---
if "%WASH_EMPTY%"=="1" (
  set "GAL=%ROOT%\Doom64-Retribution\d64remptyg.wad"
  set "INFO=%ROOT%\Doom64-Retribution\d64r-emptygallery-mapinfo.pk3"
  "%PY%" "%ROOT%\tools\build_empty_gallery.py" || exit /b 1
) else (
  set "GAL=%ROOT%\Doom64-Retribution\d64rtexg.wad"
  set "INFO=%ROOT%\Doom64-Retribution\d64r-texgallery-mapinfo.pk3"
)
"%PY%" "%ROOT%\tools\pack_gallery_spawn_wallturned.py" || exit /b 1

set "DYN_CVARS="
if "%WASH_DYNLIGHT%"=="1" set "DYN_CVARS=+rt_dynlight 1 +rt_dynlight_intensity 35 +rt_dynlight_radius 0.12"

echo.
echo ============================================================
echo  %WASH_TITLE%
echo  ENGINE=%ENGINE%
echo  mode=gallery  mapboost=%WASH_MAPBOOST%  sky=%WASH_SKY%  dynlight=%WASH_DYNLIGHT%
echo  Pose: wallturned — STONE2 on the right. Quit when done.
echo ============================================================
echo.

start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%GAL%" "%INFO%" "%SKY%" "%SPAWN%" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +sv_cheats 1 +map map99 ^
  +god ^
  +rt_mod_compat 1 +r_drawvoxels 0 ^
  +rt_fluid false +rt_autoexport false ^
  +rt_upscale_dlss 2 +rt_rayreconstr 1 +rt_framegen 0 ^
  +gl_noskyboxes true ^
  +rt_sky %WASH_SKY% +rt_sky_always true ^
  +rt_classic 0 ^
  +rt_flsh 0 ^
  +rt_mzlflsh false ^
  +rt_emis_mapboost %WASH_MAPBOOST% +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor %WASH_MAXSCR% ^
  +rt_autoexport_light 50 ^
  %DYN_CVARS% ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1
exit /b 0

:emis
set "GAL=%ROOT%\Doom64-Retribution\d64remis.wad"
set "INFO=%ROOT%\Doom64-Retribution\d64r-texgallery-batches-mapinfo.pk3"
if not exist "%GAL%" (
  "%PY%" "%ROOT%\tools\build_emis_gallery.py" || exit /b 1
)
echo.
echo ============================================================
echo  %WASH_TITLE%  ^(emis-only hall^)
echo  ENGINE=%ENGINE%  mapboost=%WASH_MAPBOOST%
echo ============================================================
echo.
start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%GAL%" "%INFO%" "%SKY%" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +sv_cheats 1 +map map99 ^
  +god ^
  +rt_mod_compat 1 +r_drawvoxels 0 ^
  +rt_fluid false +rt_autoexport false ^
  +rt_upscale_dlss 2 +rt_rayreconstr 1 +rt_framegen 0 ^
  +gl_noskyboxes true ^
  +rt_sky %WASH_SKY% +rt_sky_always true ^
  +rt_classic 0 +rt_flsh 0 +rt_mzlflsh false ^
  +rt_emis_mapboost %WASH_MAPBOOST% +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor %WASH_MAXSCR% ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1
exit /b 0

:map01
if not exist "%SKUL%" (
  echo ERROR: missing %SKUL% — python tools\pack_lostsoul_rt.py
  exit /b 1
)
set "DYN_CVARS=+rt_dynlight 1 +rt_dynlight_intensity 35 +rt_dynlight_radius 0.12"
if "%WASH_DYNLIGHT%"=="0" set "DYN_CVARS=+rt_dynlight 0"

echo.
echo ============================================================
echo  %WASH_TITLE%  MAP01 play on WashScratch
echo  ENGINE=%ENGINE%  mapboost=%WASH_MAPBOOST%  dynlight=%WASH_DYNLIGHT%
echo ============================================================
echo.
start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%SKUL%" "%MUS%" "%FIX%" "%SKY%" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +sv_cheats 1 +map map01 ^
  +god ^
  +rt_mod_compat 1 +r_drawvoxels 0 ^
  +d64_enterfade 0 +d64_exitfade 0 ^
  +rt_fluid false +rt_autoexport false ^
  +rt_upscale_dlss 2 +rt_rayreconstr 1 +rt_framegen 0 ^
  +gl_noskyboxes true ^
  +rt_sky 200 +rt_sky_always true ^
  +rt_classic 0 ^
  +rt_flsh 1 +rt_flsh_intensity 450 ^
  +rt_emis_mapboost %WASH_MAPBOOST% +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor %WASH_MAXSCR% ^
  %DYN_CVARS% ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1
exit /b 0
