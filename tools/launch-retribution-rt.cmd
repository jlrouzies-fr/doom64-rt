@echo off
setlocal
set "ENGINE=G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "FIX=G:\AI\Doom64-RT\Doom64-Retribution\d64r-map01-rtfix.wad"
set "SKY=G:\AI\Doom64-RT\Doom64-Retribution\d64r-rt-sky.pk3"
set "MUS=G:\AI\Doom64-RT\Doom64-Retribution\D64MUS.PK3"

cd /d "%ENGINE%"
rem MAP01: d64r-map01-rtfix.wad disables hangy 3D floor.
rem Sky: Retribution sky1=ISUCK is a black dummy; real look is SkyViewpoint skyboxes.
rem Sky: +gl_noskyboxes (sector SkyViewpoint portals = white/black in RT) + D64RTSKY cubemap.
rem D64MUS.PK3 = OGG music pack. Playtest cheats: god / noclip / fly. RT path tracing (not classic).
rem PBR: rt/mat_dev/*_{orm,n,h}.png (developerMode) — gallery-tuned bump strengths below.
rem Only textures processed by gen_ai_pbr (e.g. first 40 gallery booths) have N/H maps.

start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%MUS%" "%FIX%" "%SKY%" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +sv_cheats 1 +map map01 ^
  +god +noclip +fly ^
  +rt_mod_compat 3 +r_drawvoxels 0 ^
  +d64_enterfade 0 +d64_exitfade 0 ^
  +rt_fluid false +rt_autoexport false +rt_upscale_dlss 0 ^
  +gl_noskyboxes true ^
  +rt_sky 200 +rt_sky_always true ^
  +rt_classic 0 ^
  +rt_flsh 1 +rt_flsh_intensity 450 ^
  +rt_normalmap_stren 10.5 +rt_heightmap_stren 10.5
