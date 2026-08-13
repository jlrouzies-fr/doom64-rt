@echo off
setlocal
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
set "ENGINE=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=%PROJ%\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=%PROJ%\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "GAL=%PROJ%\Doom64-Retribution\d64renemyg.wad"
set "INFO=%PROJ%\Doom64-Retribution\d64r-enemygallery-mapinfo.pk3"
set "SKY=%PROJ%\Doom64-Retribution\d64r-rt-sky.pk3"
set "TOUR=%PROJ%\Doom64-Retribution\d64r-enemy-gallery-tour.pk3"
set "SKUL=%PROJ%\Doom64-Retribution\d64r-lostsoul-rt.pk3"

cd /d "%ENGINE%" || exit /b 1
rem Dark no-aggro enemy eye gallery: MAP98.
rem Rebuild map/tour: python tools\build_enemy_gallery.py
rem Rebuild Lost Soul pack: python tools\pack_lostsoul_rt.py
rem Scene: rt\data\scenes\d64renemyg_map98\
rem Loads: yellow SKUL sprites + LSGL glow handler, gallery wad/mapinfo/tour.
rem Eye mats come from engine rt\mat\ + rt\data\textures.json.

if not exist "gzdoom.exe" (
  echo ERROR: missing gzdoom.exe under %ENGINE%
  exit /b 1
)
if not exist "%GAL%" (
  echo ERROR: missing %GAL% — run: python tools\build_enemy_gallery.py
  exit /b 1
)
if not exist "%INFO%" (
  echo ERROR: missing %INFO% — run: python tools\build_enemy_gallery.py
  exit /b 1
)
if not exist "%TOUR%" (
  echo ERROR: missing %TOUR% — run: python tools\build_enemy_gallery.py
  exit /b 1
)
if not exist "%SKUL%" (
  echo ERROR: missing %SKUL% — run: python tools\pack_lostsoul_rt.py
  exit /b 1
)

echo Enemy gallery MAP98 ^(eyes + Lost Soul SKUL/LSGL pack^)

start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%SKUL%" "%GAL%" "%INFO%" "%SKY%" "%TOUR%" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +sv_cheats 1 +map map98 ^
  +god +notarget ^
  +rt_mod_compat 3 +r_drawvoxels 0 ^
  +rt_fluid false +rt_autoexport false +rt_upscale_dlss 0 ^
  +gl_noskyboxes true ^
  +rt_sky 40 +rt_sky_always true ^
  +rt_sun 0 +rt_flsh 1 +rt_flsh_intensity 80 ^
  +rt_emis_mapboost 1200 +rt_emis_additive_dflt 0.35 ^
  +rt_classic 0
