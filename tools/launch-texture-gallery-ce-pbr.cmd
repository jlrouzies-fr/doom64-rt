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
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
set "CE_PBR=%PROJ%\DoomCE\DOOM64.CE.Addon.GFX.PBR.pk3"
set "CE_OUT=%PROJ%\Doom64-Retribution\Retribution-RT-Materials-CE\manifest.json"

cd /d "%ENGINE%" || exit /b 1
rem MAP99 texture gallery with DoomCE Substance PBR converted to RTGL1 _n/_orm.
rem Same hall as launch-texture-gallery-rt.cmd — only companion maps differ.
rem Convert: python tools\convert_ce_pbr_to_rt.py
rem Restore baseline after: tools\launch-texture-gallery-rt.cmd (re-syncs baseline)

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
if not exist "%CE_PBR%" (
  echo ERROR: missing %CE_PBR%
  echo Put Doom 64 CE Full under %PROJ%\DoomCE\
  exit /b 1
)

echo Converting CE PBR if needed...
"%PY%" "%PROJ%\tools\convert_ce_pbr_to_rt.py" || exit /b 1
echo Syncing CE PBR maps into engine rt\mat ...
"%PY%" "%PROJ%\tools\sync_gallery_pbr_set.py" ce || exit /b 1

echo Texture gallery MAP99 — DoomCE PBR overlay + DLSS-RR
echo   Compare vs baseline: tools\launch-texture-gallery-rt.cmd

start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%GAL%" "%INFO%" "%SKY%" ^
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
  +rt_emis_mapboost 200 +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor 12 ^
  +rt_autoexport_light 50 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1
