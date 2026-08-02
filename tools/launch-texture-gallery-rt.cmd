@echo off
setlocal
set "ENGINE=G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "GAL=G:\AI\Doom64-RT\Doom64-Retribution\d64rtexg.wad"
set "INFO=G:\AI\Doom64-RT\Doom64-Retribution\d64r-texgallery-mapinfo.pk3"
set "SKY=G:\AI\Doom64-RT\Doom64-Retribution\d64r-rt-sky.pk3"

cd /d "%ENGINE%"
rem Empty RT material gallery: MAP99 panels for every unique Retribution map texture.
rem Scene: rt/data/scenes/d64rtexg_map99/  Tracker: texture-status.md
rem Regenerate: python tools\build_texture_gallery.py

start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%GAL%" "%INFO%" "%SKY%" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +sv_cheats 1 +map map99 ^
  +god +noclip ^
  +rt_mod_compat 3 +r_drawvoxels 0 ^
  +rt_fluid false +rt_autoexport false +rt_upscale_dlss 0 ^
  +gl_noskyboxes true ^
  +rt_sky 200 +rt_sky_always true ^
  +rt_classic 0
