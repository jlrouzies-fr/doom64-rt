@echo off
setlocal
set "ENGINE=G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "SKUL=G:\AI\Doom64-RT\Doom64-Retribution\d64r-lostsoul-rt.pk3"
set "FIX=G:\AI\Doom64-RT\Doom64-Retribution\d64r-map01-rtfix.wad"
set "SKY=G:\AI\Doom64-RT\Doom64-Retribution\d64r-rt-sky.pk3"
set "MUS=G:\AI\Doom64-RT\Doom64-Retribution\D64MUS.PK3"

cd /d "%ENGINE%" || exit /b 1

rem Native RTGL1 path tracing + DLSS Ray Reconstruction (NOT RTX Remix).
rem No -rtxremix. Uses +rt_rayreconstr 1 (native), not +rt_remix_rayreconstr.
rem Requires tools\build-rtgl.cmd (RTGL1.dll + nvngx_dlssd.dll in rt\bin\).
rem MAP01: d64r-map01-rtfix.wad disables hangy 3D floor.
rem Sky: +gl_noskyboxes + D64RTSKY cubemap. D64MUS.PK3 = OGG music.
rem d64r-lostsoul-rt.pk3: yellow SKUL sprites + LSGL offset-glow EventHandler.
rem Eye/fire mats: engine rt\mat\ + rt\data\textures.json (no extra -file).

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
if not exist "%SKUL%" (
  echo ERROR: missing %SKUL% — run: python tools\pack_lostsoul_rt.py
  exit /b 1
)
if not exist "%MOD%" (
  echo ERROR: missing %MOD%
  exit /b 1
)

echo Native RT + DLSS Ray Reconstruction (no Remix^)
echo   +rt_upscale_dlss 2 +rt_rayreconstr 1 +rt_framegen 0

start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%SKUL%" "%MUS%" "%FIX%" "%SKY%" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +sv_cheats 1 +map map01 ^
  +god +noclip +fly ^
  +rt_mod_compat 3 +r_drawvoxels 0 ^
  +d64_enterfade 0 +d64_exitfade 0 ^
  +rt_fluid false +rt_autoexport false ^
  +rt_upscale_dlss 2 +rt_rayreconstr 1 +rt_framegen 0 ^
  +gl_noskyboxes true ^
  +rt_sky 200 +rt_sky_always true ^
  +rt_classic 0 ^
  +rt_flsh 1 +rt_flsh_intensity 450 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1
