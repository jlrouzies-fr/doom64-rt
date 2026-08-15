@echo off
setlocal
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem DIAG: all _e quarantined + all textures.json emis stripped.
rem Isolates sky / RR / additive vs surface emis.
set "ENGINE=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=%PROJ%\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=%PROJ%\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "GAL=%PROJ%\Doom64-Retribution\d64rtexg.wad"
set "INFO=%PROJ%\Doom64-Retribution\d64r-texgallery-mapinfo.pk3"
set "SKY=%PROJ%\Doom64-Retribution\d64r-rt-sky.pk3"
set "SPAWN=%PROJ%\Doom64-Retribution\d64r-gallery-spawn-east.pk3"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"

cd /d "%ENGINE%" || exit /b 1
"%PY%" "%PROJ%\tools\pack_gallery_spawn_east.py" || exit /b 1

echo Gallery DIAG — NO surface _e / NO emis meta. mapboost 200. Try in console:
echo   rt_sky 0          ^(if blotches die -^> sky^)
echo   rt_rayreconstr 0  ^(if blotches die -^> RR^)
echo   rt_emis_mapboost 0
echo   rt_emis_additive_dflt 0

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
  +rt_emis_mapboost 200 +rt_emis_additive_dflt 0 +rt_emis_maxscrcolor 12 ^
  +rt_autoexport_light 0 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1
