@echo off
setlocal
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
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
rem Empty RT material gallery: MAP99 panels for every unique Retribution map texture.
rem Free roam. Spawns at EAST end wall (yaw 0) via d64r-gallery-spawn-east.pk3.
rem Scene: rt/data/scenes/d64rtexg_map99/  Tracker: texture-status.md
rem Regenerate: python tools\build_texture_gallery.py
rem CE PBR A/B: tools\launch-texture-gallery-ce-pbr.cmd
rem
rem Denoise: native DLSS-RR (same as launch-retribution-rt). dlss 0 = raw noisy PT.
rem Flashlight off by default — hall already has rt_sky; flsh near pillars = fireflies.
rem Toggle in console: rt_flsh 1
rem
rem Emissive QA booths (fly): SMONAA~98, SEXIT~190, CRTRAKA~249,
rem HLAVA1~585, D64LAVA1~713, D64LOGO~682. Stock mapboost; world GI via
rem per-tex emissiveMult (HitInfo INDIR). mod_compat 1 = no brightmap auto-emis.
rem Auto QA: tools\test_gallery_emis_qa.cmd

if not exist "gzdoom.exe" (
  echo ERROR: missing gzdoom.exe under %ENGINE%
  exit /b 1
)
if not exist "rt\bin\RTGL1.dll" (
  echo ERROR: missing rt\bin\RTGL1.dll — run tools\build-rtgl.cmd
  exit /b 1
)
if not exist "rt\bin\nvngx_dlssd.dll" (
  echo ERROR: missing rt\bin\nvngx_dlssd.dll — run tools\build-rtgl.cmd
  exit /b 1
)
if not exist "%GAL%" (
  echo ERROR: missing %GAL% — run: python tools\build_texture_gallery.py
  exit /b 1
)

echo Syncing baseline PBR maps into engine rt\mat ...
"%PY%" "%PROJ%\tools\sync_gallery_pbr_set.py" baseline || exit /b 1

echo Packing east-wall spawn ...
"%PY%" "%PROJ%\tools\pack_gallery_spawn_east.py" || exit /b 1

echo Texture gallery MAP99 — spawn EAST end wall, free roam + DLSS-RR

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
  +rt_emis_mapboost 200 +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor 3 ^
  +rt_autoexport_light 50 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1
