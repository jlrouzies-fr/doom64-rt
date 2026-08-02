@echo off
setlocal
rem Official mod binary + STOCK RTGL1 from 1.0.2 (do not mix with RTGL 1.6.3)
cd /d G:\AI\Doom64-RT\runtime-mod

rem Disable overlays if present (RTSS/OBS hooks show in the crash dump modules)
rem Optional: close MSI Afterburner / RivaTuner / OBS before launching.

start "" gzdoom-mod.exe ^
  -iwad "D:\Games\GZDoom\doom2.wad" ^
  -file "G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD" "G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +map map01 ^
  +rt_mod_compat 3 ^
  +r_drawvoxels 0 ^
  +d64_enterfade 0 ^
  +d64_exitfade 0 ^
  +rt_fluid false ^
  +rt_autoexport false ^
  +rt_classic 0
