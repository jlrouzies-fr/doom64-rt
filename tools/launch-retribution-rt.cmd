@echo off
rem DelayedExpansion is needed to accumulate the "--" passthrough in a loop.
rem Safe here: no literal '!' appears anywhere else in this script.
setlocal EnableExtensions EnableDelayedExpansion
set "ENGINE=G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "SKUL=G:\AI\Doom64-RT\Doom64-Retribution\d64r-lostsoul-rt.pk3"
set "FLSH=G:\AI\Doom64-RT\Doom64-Retribution\d64r-rt-flashlight.pk3"
set "FIX3D=G:\AI\Doom64-RT\Doom64-Retribution\d64r-3dfloor-rtfix.wad"
set "SKY=G:\AI\Doom64-RT\Doom64-Retribution\d64r-rt-sky.pk3"
set "MUS=G:\AI\Doom64-RT\Doom64-Retribution\D64MUS.PK3"
rem Full console transcript (incl. startup) -> shareable log. `logfile` is
rem whitelisted to run at GS_STARTUP (c_dispatch.cpp), so it captures
rem everything from boot, including RTGL -rtdebug output.
set "LOGF=G:\AI\Doom64-RT\rt-console.log"

rem Usage: launch-retribution-rt.cmd [1-32] [debug] [-- +cvar val ...]
rem   Optional map number (default 1) → +map map01 … map32
rem   Second arg "debug" → -rtdebug (RTGL messages to console: DLSS-RR init
rem     success/failure, shader load errors. Muted by default; rt_main.cpp
rem     sets allowedMessages=0 without it, so RR failing is otherwise silent.)
rem   Everything after "--" is appended verbatim to the command line, so it
rem     lands AFTER the cvars below and therefore wins. This is how A/B arms
rem     get pre-set (see ab-rr-guide.cmd) instead of being typed into the
rem     console: a hand-typed cvar is one forgotten keystroke from an invalid
rem     comparison, and CVAR_ARCHIVE then persists the mistake into later runs.
set "RTDEBUG="
if /i "%~2"=="debug" set "RTDEBUG=-rtdebug"

rem Collect the post-"--" passthrough without disturbing %1/%2 parsing above.
set "EXTRA="
set "SEEN_SEP="
for %%A in (%*) do (
  if defined SEEN_SEP (
    set "EXTRA=!EXTRA! %%~A"
  ) else (
    if "%%~A"=="--" set "SEEN_SEP=1"
  )
)
set "MAPNUM=%~1"
if "%MAPNUM%"=="" set "MAPNUM=1"
set /a "N=MAPNUM" 2>nul
if errorlevel 1 goto :badmap
if %N% LSS 1 goto :badmap
if %N% GTR 32 goto :badmap
if %N% LSS 10 (set "MAPLUMP=map0%N%") else (set "MAPLUMP=map%N%")

cd /d "%ENGINE%" || exit /b 1

rem Native RTGL1 path tracing + DLSS Ray Reconstruction (NOT RTX Remix).
rem No -rtxremix. Uses +rt_rayreconstr 1 (native), not +rt_remix_rayreconstr.
rem Requires tools\build-rtgl.cmd (RTGL1.dll + nvngx_dlssd.dll in rt\bin\).
rem All maps: d64r-3dfloor-rtfix.wad strips hangy Sector_Set3dFloor (special 160).
rem Sky: sector skyboxes ignored under RT (white/black fix); d64r-rt-sky forces SPACE night flat + rt_sky_always.
rem d64r-lostsoul-rt.pk3: yellow SKUL sprites + LSGL offset-glow EventHandler.
rem d64r-rt-flashlight.pk3: stylized 5-cell battery HUD (rt_flsh_charge / battstate; F toggles).
rem Eye/fire mats: engine rt\mat\ + rt\data\textures.json (no extra -file).
rem DLSS-RR transient-light ghosting: rt_rr_reset_on_lightcut/on_dynlight flush RR's
rem  temporal history (InReset) on flashlight on/off and dynlight appear/disappear
rem  (barrel/rocket explosions etc; muzzle flash intentionally excluded, too frequent).
rem  rt_rr_disocc* is the separate per-pixel tile mask, still under investigation —
rem  see flashlight-linger-fix-plan.md.
rem  The rt_rr_* diagnostics (reset_hold / reset_now / reset_debug) are forced to 0
rem  below on purpose: every RT_CVAR is CVAR_ARCHIVE, so one left at 1 in a console
rem  session silently persists in the ini and poisons every later A/B test. Set them
rem  from the console when testing, not here.
rem  rt_upscale_fsr2 0 is forced for the same reason and matters more: DLSS and FSR2
rem  share one upscaler slot, FSR2 is applied second, and Ray Reconstruction only
rem  runs under DLSS. A stale rt_upscale_fsr2=2 in the ini silently disabled RR on
rem  every launch while rt_rayreconstr still read 1 (2026-08-07).

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
if not exist "%FIX3D%" (
  echo ERROR: missing %FIX3D% — run: python tools\make_map_3dfloor_rtfix.py
  exit /b 1
)

echo Native RT + DLSS Ray Reconstruction (no Remix^)
echo   map=%MAPLUMP%  +rt_upscale_dlss 2 +rt_rayreconstr 1 +rt_framegen 0

rem Place window ~300px above vertical center (Y grows down). Falls back to 0 (top).
set "WINY=0"
for /f %%i in ('powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [Math]::Max(0, [int](([Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Height-720)/2-300))"') do set "WINY=%%i"
echo win_y=%WINY%

rem Combined 3D-floor strip for every Retribution map that had special 160.
start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%SKUL%" "%FLSH%" "%MUS%" "%FIX3D%" "%SKY%" ^
  -rtnolauncher -width 1280 -height 720 %RTDEBUG% ^
  +logfile "%LOGF%" ^
  +vid_fullscreen 0 +win_x -1 +win_y %WINY% +queryiwad false +sv_cheats 1 +god +notarget +map %MAPLUMP% ^
  +rt_mod_compat 1 +r_drawvoxels 0 ^
  +d64_enterfade 0 +d64_exitfade 0 ^
  +rt_fluid false +rt_autoexport false ^
  +rt_upscale_dlss 2 +rt_upscale_fsr2 0 +rt_rayreconstr 1 +rt_framegen 0 ^
  +gl_noskyboxes false ^
  +rt_sky 25 +rt_sky_always true ^
  +rt_classic 0 ^
  +rt_flsh 0 +rt_flsh_intensity 90 +rt_flsh_angle 42 +rt_flsh_pitch 22 ^
  +rt_flsh_battery 1 +rt_flsh_on_secs 30 +rt_flsh_die_secs 4 +rt_flsh_off_secs 5 ^
  +rt_flsh_color ffbe82 ^
  +rt_emis_mapboost 200 +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor 3 ^
  +rt_sector_lights 0 +rt_sector_flicker 0 ^
  +rt_dynlight 1 +rt_dynlight_flicker 0 +rt_dynlight_intensity 40 +rt_dynlight_max 500 +rt_dynlight_rsoft 40 +rt_dynlight_stack_atten 1 +rt_dynlight_radius 0.08 ^
  +rt_ceiling_lamps 1 +rt_ceiling_lamp_intensity 700 +rt_ceiling_lamp_radius 0.10 ^
  +rt_ceiling_lamp_off 0.12 +rt_ceiling_lamp_fade 40 +rt_ceiling_lamp_maxspan 128 ^
  +rt_hang_lamps 1 +rt_hang_lamp_intensity 220 +rt_hang_lamp_radius 0.09 +rt_hang_lamp_zofs 4 ^
  +rt_translucent_minalpha 0.72 ^
  +rt_rr_temporal 0 ^
  +rt_rr_disocc 1 +rt_rr_disocc_ratio 3.0 +rt_rr_disocc_mindelta 0.01 +rt_rr_disocc_show 0 ^
  +rt_rr_reset_on_lightcut 1 +rt_rr_reset_on_dynlight 1 +rt_rr_reset_delta 0.5 +rt_rr_reset_min_ms 250 ^
  +rt_rr_reset_hold 0 +rt_rr_reset_now 0 +rt_rr_reset_debug 0 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1 %EXTRA%
exit /b 0

:badmap
echo Usage: %~nx0 [1-32]
echo   Optional map number (default 1^). Example: %~nx0 5  -^> +map map05
exit /b 1
