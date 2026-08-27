@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem A/B the sludge / mud beds. Only TWO maps have a sludge FLOOR, from the UDMF:
rem MAP12 (6 sectors -- the default here) and MAP34 (the fluid sampler, 2).
rem That is why every arm sets rt_sludge_autogoto 1: spawning in sight of one is
rem unlikely, and a verdict judged from the spawn point is worthless.
rem
rem EVERY ARM SETS EVERY VALUE. A knob left unset silently inherits whichever
rem arm ran last, and a null result then gets blamed on the change instead of on
rem the leftover.
rem
rem SLUDGE IS NOT BLOOD, though it uses the same machinery. Blood is a thin skin
rem with liquid channels cut through it and a flow map running down them. Sludge
rem is a thick opaque BED: the point is depth and the ABSENCE of a water
rem reflection, and it has no flow at all (its _h.g/.b are baked to the zero
rem vector, so the advection is dead at the source, not merely turned down).
rem
rem THREE LAYERS, and they fail in ways that look identical:
rem
rem   1. the ART     -- d64r-liquid-art.wad, built by tools\gen_liquid_art.py.
rem      A TX_ patch (D64SCOAG) plus a TEXTURES lump redefining all 128
rem      D64S1_/D64S2_ frames as ONE unshifted copy. Not a cvar. Without the wad
rem      on the command line nothing below can work -- the relief needs an _n to
rem      give back. Check the log for "d64r-liquid-art".
rem   2. the RELIEF  -- rt_sludge_relief. getNormal() overwrites the
rem      normal-mapped normal with the animated water WAVE for any water
rem      surface, so an _n on a liquid is sampled, written to the G-buffer and
rem      then thrown away. This is the knob that gives it back. Sludge's height
rem      comes from the art's full luminance range, not the vein mask blood
rem      uses: 90%% of sludge's texels saturate that mask, so a mask-derived
rem      height would be a flat plateau.
rem   3. the REFLECTION -- rt_sludge_refl / rt_sludge_rough. A mirror is what
rem      sells water; on a mud bed it is the loudest single thing saying "this
rem      is water with brown paint on it".
rem
rem   on        THE DEFAULT. Full relief, reflection 0 (no mirror, NO checkerboard
rem             split: full-res surface, glossy specular sheen), rough 0.8.
rem   off       relief 0, reflection 1, rough 0.1 -- the stylized WATER surface
rem             in a brown palette, i.e. what a sludge pool was before any of
rem             this. The baseline to flip against. If "on" looks the same as
rem             this, the wad is not loading.
rem   norelief  relief 0, reflection still killed. Isolates layer 2: how much of
rem             the depth is the relief and how much is just the dead mirror.
rem   split     reflection 0.12 -- the dim mirror WITH the checkerboard split,
rem             i.e. the version that had the flashlight bug. The A/B for it.
rem   mirror    reflection 1.0 and rough 0.1, relief still ON. Isolates layer 3:
rem             a ridged mud bed that still reflects like a pool. The arm for
rem             "is the reflection actually what was wrong".
rem   deep      relief 1, heightmap 2 -- double parallax. The arm for "not
rem             enough depth".
rem   flat      rt_heightmap_stren 0 -- relief on, PARALLAX off. Separates "the
rem             normal map is doing the work" from "the height map is".
rem   wet       reflection 0.35, rough 0.5 -- a wetter, shinier mud. A look, not
rem             a test.
rem   dry       reflection 0.03, rough 1.0 -- near-matt. The other end.
rem   flagcheck LIQUID SURFACES PAINTED MAGENTA (rt_water_debug 1). If the beds
rem             are not magenta the stylized branch is not running on them and
rem             nothing else here can. NOTE this also paints every other surface
rem             blue -- that is the same diagnostic's caustic probe, not a bug.
rem   caustics  rt_sludge_caustics 1 -- puts the PROJECTED caustics back. Sludge
rem             ships with them OFF: a caustic is light refracted through a
rem             fluid and focused on what lies beyond it, so an opaque bed casts
rem             none. This is the before-picture, not a look.
rem BISECT ARMS -- for "the flashlight makes unstable shadows that vanish when I
rem stop". That symptom means something is AVERAGING the signal over time and the
rem average is flatter than the instantaneous frame, i.e. what you see moving is
rem NOISE rather than relief. Run these in this order; each one splits the search
rem space in half, and rt_heightmap_stren 0 has ALREADY ruled parallax out.
rem
rem   nomaps     rt_heightmap_stren 0 AND rt_normalmap_stren 0. The decisive one:
rem              no parallax and no normal map, so the surface is geometrically
rem              flat. If the instability is STILL there it is not our material at
rem              all -- it is the flashlight on this surface, and every arm below
rem              about the art is a waste of a launch.
rem   softnormal rt_normalmap_stren 0.4. If the instability scales with this, the
rem              normal map carries more high frequency than the pipeline can
rem              resolve and the fix is a softer bake, not a shader change.
rem   normals    rt_debug_show 1024 -- paints the G-buffer NORMALS. Stand still.
rem              Crisp and steady = the normal map is live and stable and the loss
rem              is downstream in lighting or denoise. Shimmering = the normal
rem              itself is the noise source.
rem   raw        rt_debug_show 4 -- UNFILTERED direct diffuse, before A-SVGF. If
rem              the bumps are here and steady, the material and the lighting are
rem              both fine and a denoiser or the upscaler is erasing them. If this
rem              view is a boiling mess, the raw signal really is noise and no
rem              denoiser tuning can help.
rem   denoised   rt_debug_show 32 -- the same layer AFTER A-SVGF. Diff against raw.
rem   nodlss     rt_upscale_dlss 0, native res. If the effect disappears, it is the
rem              upscaler (these pixels are marked reactive, and they are shaded on
rem              HALF the pixels -- the stylized branch checkerboards surface
rem              against reflection).
rem   restir     rt_debug_restir_m 1 -- ReSTIR reservoir M as a green ramp. Stand
rem              still and watch it brighten, then move. Dark in motion = history
rem              rejected, so the raw signal IS noisier moving, upstream of every
rem              denoiser.
rem ---------------------------------------------------------------------------

set "ARM=%~1"
if "%ARM%"=="" set "ARM=on"
set "MAP=%~2"
if "%MAP%"=="" set "MAP=12"

rem Shipping values. Each arm below overrides only what it is testing, but every
rem one of these is written on every launch.
set "RELIEF=1.0"
set "REFL=0"
set "ROUGH=0.8"
set "HEIGHT=1"
set "WDEBUG=0"
set "CAUST=0"
set "NMAP=1"
set "DBGSHOW=0"
set "DLSS=2"
set "RESTIRM=0"

if /i "%ARM%"=="on"        goto :ok
if /i "%ARM%"=="off"       ( set "RELIEF=0.0" & set "REFL=1.0" & set "ROUGH=0.1" & goto :ok )
if /i "%ARM%"=="norelief"  ( set "RELIEF=0.0" & goto :ok )
if /i "%ARM%"=="split"     ( set "REFL=0.12" & goto :ok )
if /i "%ARM%"=="mirror"    ( set "REFL=1.0" & set "ROUGH=0.1" & goto :ok )
if /i "%ARM%"=="deep"      ( set "HEIGHT=2" & goto :ok )
if /i "%ARM%"=="flat"      ( set "HEIGHT=0" & goto :ok )
if /i "%ARM%"=="wet"       ( set "REFL=0.35" & set "ROUGH=0.5" & goto :ok )
if /i "%ARM%"=="dry"       ( set "REFL=0.03" & set "ROUGH=1.0" & goto :ok )
if /i "%ARM%"=="flagcheck" ( set "WDEBUG=1" & goto :ok )
if /i "%ARM%"=="caustics"  ( set "CAUST=1" & goto :ok )
rem --- bisect arms for the "unstable shadows under the flashlight" class ---
if /i "%ARM%"=="nomaps"    ( set "HEIGHT=0" & set "NMAP=0" & goto :ok )
if /i "%ARM%"=="softnormal" ( set "NMAP=0.4" & goto :ok )
if /i "%ARM%"=="raw"       ( set "DBGSHOW=4" & goto :ok )
if /i "%ARM%"=="denoised"  ( set "DBGSHOW=32" & goto :ok )
if /i "%ARM%"=="normals"   ( set "DBGSHOW=1024" & goto :ok )
if /i "%ARM%"=="nodlss"    ( set "DLSS=0" & goto :ok )
if /i "%ARM%"=="restir"    ( set "RESTIRM=1" & goto :ok )

echo Unknown arm "%ARM%".
echo   usage: tools\ab-sludge.cmd ^<on^|off^|norelief^|split^|mirror^|deep^|flat^|wet^|dry^|flagcheck^|caustics^> [map]
echo   bisect: ^<nomaps^|softnormal^|raw^|denoised^|normals^|nodlss^|restir^>
echo   maps with sludge: 12 (6 sectors, default) and 34 (the fluid sampler)
exit /b 1

:ok
echo === sludge beds: arm "%ARM%" on map %MAP% ===
echo     relief %RELIEF%  reflection %REFL%  roughness %ROUGH%  heightmap %HEIGHT%
echo     caustics %CAUST%  water_debug %WDEBUG%  normalmap %NMAP%
echo     debug_show %DBGSHOW%  dlss %DLSS%  restir_m %RESTIRM%
echo     the player is placed on a bed by rt_sludge_autogoto.

call "%~dp0launch-retribution-rt.cmd" %MAP% -- ^
  +rt_sludge_autogoto 1 ^
  +rt_sludge_relief %RELIEF% ^
  +rt_sludge_refl %REFL% ^
  +rt_sludge_rough %ROUGH% ^
  +rt_heightmap_stren %HEIGHT% ^
  +rt_water_debug %WDEBUG% ^
  +rt_sludge_caustics %CAUST% ^
  +rt_normalmap_stren %NMAP% ^
  +rt_debug_show %DBGSHOW% ^
  +rt_upscale_dlss %DLSS% ^
  +rt_debug_restir_m %RESTIRM%
