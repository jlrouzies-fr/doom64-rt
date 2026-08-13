@echo off
setlocal
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem Empty twin of MAP99 gallery: same hall footprint, ZERO texture pillars.
rem Isolates shell/sky/muzzle/RR wash from booth emissives.
set "ROOT=%PROJ%"
set "ENGINE=%ROOT%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=%ROOT%\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=%ROOT%\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "GAL=%ROOT%\Doom64-Retribution\d64remptyg.wad"
set "INFO=%ROOT%\Doom64-Retribution\d64r-emptygallery-mapinfo.pk3"
set "SKY=%ROOT%\Doom64-Retribution\d64r-rt-sky.pk3"
set "SPAWN=%ROOT%\Doom64-Retribution\d64r-gallery-spawn-wallturned.pk3"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"

cd /d "%ENGINE%" || exit /b 1

if not exist "gzdoom.exe" (
  echo ERROR: missing gzdoom.exe
  exit /b 1
)
if not exist "rt\bin\RTGL1.dll" (
  echo ERROR: missing RTGL1.dll — run tools\build-rtgl.cmd
  exit /b 1
)

echo Syncing baseline PBR ...
"%PY%" "%ROOT%\tools\sync_gallery_pbr_set.py" baseline || exit /b 1

echo Building empty gallery wad ...
"%PY%" "%ROOT%\tools\build_empty_gallery.py" || exit /b 1

echo Packing wallturned spawn ...
"%PY%" "%ROOT%\tools\pack_gallery_spawn_wallturned.py" || exit /b 1

echo.
echo ============================================================
echo  EMPTY gallery MAP99 — dark hall, no pillars, wallturned spawn
echo  Should look path-traced: soft sky, muzzle lights STONE2 via PT.
echo  If flat/classic: console check rt_classic 0, rt_upscale_dlss 2
echo ============================================================
echo.

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
  +rt_sky 80 +rt_sky_always true ^
  +rt_classic 0 ^
  +rt_flsh 0 ^
  +rt_mzlflsh true +rt_mzlflsh_intensity 400 ^
  +rt_emis_mapboost 200 +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor 12 ^
  +rt_autoexport_light 50 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1

endlocal
