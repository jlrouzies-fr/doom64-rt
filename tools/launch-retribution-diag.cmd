@echo off
setlocal
set "ENGINE=G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo"
cd /d "%ENGINE%"
start "" gzdoom.exe ^
  -iwad "D:\Games\GZDoom\doom2.wad" ^
  -file "G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD" "G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3" ^
  -nosound -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +map map01 ^
  +rt_mod_compat 3 +r_drawvoxels 0 ^
  +d64_enterfade 0 +d64_exitfade 0 ^
  +rt_fluid false +rt_autoexport false +rt_upscale_dlss 0 ^
  +rt_classic 1 +rt_classic_llpow 1 +rt_classic_llmin 0.4
