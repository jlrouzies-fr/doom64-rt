@echo off
setlocal
set "ENGINE=G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "SKUL=G:\AI\Doom64-RT\Doom64-Retribution\d64r-lostsoul-rt.pk3"
set "FLSH=G:\AI\Doom64-RT\Doom64-Retribution\d64r-rt-flashlight.pk3"
set "FIX=G:\AI\Doom64-RT\Doom64-Retribution\d64r-map01-rtfix.wad"
set "SKY=G:\AI\Doom64-RT\Doom64-Retribution\d64r-rt-sky.pk3"
set "MUS=G:\AI\Doom64-RT\Doom64-Retribution\D64MUS.PK3"

cd /d "%ENGINE%" || exit /b 1

rem Native RTGL1 path tracing + DLSS Ray Reconstruction (NOT RTX Remix).
rem No -rtxremix. Uses +rt_rayreconstr 1 (native), not +rt_remix_rayreconstr.
rem Requires tools\build-rtgl.cmd (RTGL1.dll + nvngx_dlssd.dll in rt\bin\).
rem MAP01: d64r-map01-rtfix.wad disables hangy 3D floor.
rem Sky: sector skyboxes ignored under RT (white/black fix); d64r-rt-sky forces SPACE night flat + rt_sky_always.
rem d64r-lostsoul-rt.pk3: yellow SKUL sprites + LSGL offset-glow EventHandler.
rem d64r-rt-flashlight.pk3: battery HUD bar (reads rt_flsh_charge / rt_flsh_battstate).
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
if not exist "%FLSH%" (
  echo ERROR: missing %FLSH% — run: python tools\pack_rt_flashlight.py
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
  -file "%MOD%" "%BM%" "%SKUL%" "%FLSH%" "%MUS%" "%FIX%" "%SKY%" ^
  -rtnolauncher -width 1280 -height 720 ^
  +vid_fullscreen 0 +queryiwad false +sv_cheats 1 +map map01 ^
  +god +fly ^
  +rt_mod_compat 1 +r_drawvoxels 0 ^
  +d64_enterfade 0 +d64_exitfade 0 ^
  +rt_fluid false +rt_autoexport false ^
  +rt_upscale_dlss 2 +rt_rayreconstr 1 +rt_framegen 0 ^
  +gl_noskyboxes false ^
  +rt_sky 25 +rt_sky_always true ^
  +rt_classic 0 ^
  +rt_flsh 0 +rt_flsh_intensity 90 +rt_flsh_angle 42 +rt_flsh_pitch 22 ^
  +rt_flsh_battery 1 +rt_flsh_on_secs 30 +rt_flsh_die_secs 4 +rt_flsh_off_secs 5 ^
  +rt_flsh_color ffbe82 ^
  +rt_emis_mapboost 200 +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor 3 ^
  +rt_sector_lights 0 +rt_sector_flicker 0 ^
  +rt_dynlight 1 +rt_dynlight_flicker 0 +rt_dynlight_intensity 40 +rt_dynlight_radius 0.08 ^
  +rt_ceiling_lamps 1 +rt_ceiling_lamp_intensity 900 +rt_ceiling_lamp_radius 0.08 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1
