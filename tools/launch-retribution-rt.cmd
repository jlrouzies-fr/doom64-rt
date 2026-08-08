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

rem Native RTGL1 path tracing. NOT RTX Remix, no -rtxremix.
rem
rem rt_rayreconstr 0 -- A-SVGF, not DLSS-RR. RR works and is correctly configured
rem (2026-08-07: identical jitter, MV scale and NGX feature flags to DLSS-SR), but
rem it stays measurably less stable in MOTION than A-SVGF on this content. Every
rem candidate cause was eliminated by measurement -- see RAYRECONSTRUCTION.md.
rem A-SVGF has a structural advantage here: it accumulates in linear radiance
rem BEFORE exposure and applies a variance-guided spatial filter, which suits
rem sparse 1-spp interiors with many small dynamic lights. Set +rt_rayreconstr 1
rem to compare; the tools/ab-rr-*.cmd arms all force RR on regardless.
rem
rem rt_restir_initial 32 (was 8) -- more RIS candidate lights per pixel. Traces NO
rem rays, so it is nearly free, and it improves light selection for BOTH denoisers.
rem Not yet A/B'd under A-SVGF specifically; use tools/ab-rr-quality.cmd to check
rem it and the other zero-ray ReSTIR knobs before assuming it helps.
rem
rem The expensive lever is rt_spp_direct / rt_spp_indirect [1..8], left at 1.
rem Measured ~20% improvement at 8, which is a poor trade -- and that result also
rem shows the residual motion noise is NOT Monte Carlo variance.
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
rem  see docs/rayreconstruction/flashlight-linger-fix-plan.md.
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

echo Native RT path tracing, A-SVGF denoiser (no Remix^)
echo   map=%MAPLUMP%  +rt_upscale_dlss 2 +rt_rayreconstr 0 +rt_framegen 0

rem Place window ~300px above vertical center (Y grows down). Falls back to 0 (top).
set "WINY=0"
for /f %%i in ('powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [Math]::Max(0, [int](([Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Height-720)/2-300))"') do set "WINY=%%i"
echo win_y=%WINY%

rem rt_tnmp_ev100_min/max are forced because the ini had BOTH pinned to 1. Equal
rem bounds lock auto-exposure, and EV100 1 exposes the scene very bright, so every
rem region is lifted, no umbra ever reads dark, and shadows vanish globally --
rem independent of every lighting cvar. It survived from an ab-rr-exposure run:
rem CVAR_ARCHIVE wrote it once and it applied to every launch after. Four lighting
rem A/B arms (density x2, emissive fill, all-lights-off) all came back negative
rem because none of them could reach it. Same story for rt_lightlevel_min/max,
rem which the ini had at 200/1 -- min ABOVE max (2026-08-08).
rem
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
  +rt_upscale_dlss 2 +rt_upscale_fsr2 0 +rt_rayreconstr 0 +rt_framegen 0 ^
  +gl_noskyboxes false ^
  +rt_sky 25 +rt_sky_always true ^
  +rt_classic 0 ^
  +rt_flsh 0 +rt_flsh_intensity 90 +rt_flsh_angle 42 +rt_flsh_pitch 22 ^
  +rt_flsh_battery 1 +rt_flsh_on_secs 30 +rt_flsh_die_secs 4 +rt_flsh_off_secs 5 ^
  +rt_flsh_color ffbe82 ^
  +rt_tnmp_ev100_min 2 +rt_tnmp_ev100_max 7.7 ^
  +rt_lightlevel_min 80 +rt_lightlevel_max 230 +rt_lightlevel_exp 2 ^
  +rt_illum_sens_direct 1 +rt_illum_sens_indirect 0.75 +rt_illum_sens_spec 1 ^
  +rt_shadowrays 4 ^
  +rt_emis_mapboost 200 +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor 3 ^
  +rt_sector_tint_lights 0.85 +rt_sector_tint_albedo 1.0 ^
  +rt_sector_emis 0.35 +rt_sector_emis_minlight 160 +rt_sector_emis_margin 40 +rt_sector_emis_debug 0 ^
  +rt_sector_lights 0 +rt_sector_flicker 0 ^
  +rt_dynlight 1 +rt_dynlight_flicker 0 +rt_dynlight_intensity 40 +rt_dynlight_max 500 +rt_dynlight_rsoft 20 +rt_dynlight_stack_atten 1 +rt_dynlight_minradius 16 ^
  +rt_dynlight_debug 0 +rt_dynlight_debug_marks 0 +rt_wall_tex_debug 0 +rt_dynlight_radius 0.08 ^
  +rt_ceiling_lamps 0 +rt_ceiling_lamp_intensity 0 +rt_ceiling_lamp_radius 0.10 ^
  +rt_ceiling_lamp_off 0.12 +rt_ceiling_lamp_fade 40 +rt_ceiling_lamp_maxspan 128 ^
  +rt_hang_lamps 1 +rt_hang_lamp_intensity 220 +rt_hang_lamp_radius 0.09 +rt_hang_lamp_zofs 4 ^
  +rt_pole_lamp_intensity 300 +rt_pole_lamp_zfrac 0.88 ^
  +rt_wall_strips 1 +rt_wall_strip_intensity 180 +rt_wall_strip_minlight 120 ^
  +rt_wall_strip_seglen 64 +rt_wall_strip_radius 0.35 +rt_wall_strip_max 128 +rt_wall_strip_debug 0 +rt_wall_strip_debug_marks 0 ^
  +rt_ceiling_edge_lamps 1 +rt_ceiling_edge_intensity 180 +rt_ceiling_edge_seglen 64 ^
  +rt_ceiling_edge_radius 0.35 +rt_ceiling_edge_zofs 10 +rt_ceiling_edge_inset 10 ^
  +rt_ceiling_edge_max 320 +rt_ceiling_edge_maxdist 1536 ^
  +rt_ceiling_edge_debug 0 +rt_ceiling_edge_debug_marks 0 ^
  +rt_light_mark_intensity 25 +rt_light_mark_max 24 ^
  +rt_translucent_minalpha 0.72 ^
  +rt_rr_temporal 0 ^
  +rt_rr_disocc 1 +rt_rr_disocc_ratio 3.0 +rt_rr_disocc_mindelta 0.01 +rt_rr_disocc_show 0 ^
  +rt_rr_reset_on_lightcut 1 +rt_rr_reset_on_dynlight 1 +rt_rr_reset_delta 0.5 +rt_rr_reset_min_ms 250 ^
  +rt_rr_reset_hold 0 +rt_rr_reset_now 0 +rt_rr_reset_debug 0 ^
  +rt_restir_initial 32 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1 %EXTRA%
exit /b 0

:badmap
echo Usage: %~nx0 [1-32]
echo   Optional map number (default 1^). Example: %~nx0 5  -^> +map map05
exit /b 1
