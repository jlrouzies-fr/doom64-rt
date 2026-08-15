@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the storm sky -- scrolling clouds and lightning -- on MAP11, the game's
rem one `lightning` map (the MAPINFO keyword that spawns DLightningThinker).
rem
rem The storm fires on its own schedule: 5-20 seconds to the first strike, then
rem 16-31 TICS for a quick double-flash or 2-20 seconds otherwise. Do not sit
rem and wait. Type `thunder` in the console to force a strike in whichever arm
rem you are looking at -- it drives the same RT_OnLightningFlash the thinker
rem calls, so it exercises the exact path. (It does not play the sound; that is
rem S_Sound in the thinker.)
rem
rem   full     everything on, with the per-map table DISABLED and the deck forced
rem            on -- so an arm behaves the same whichever map you point it at.
rem   preset   the shipping configuration: rt_clouds_presets 1, so the deck is
rem            opt-in and only maps listed in RT_CLOUD_PRESETS get clouds
rem            (MAP11 and MAP14 do, MAP01 explicitly does not). This is the arm
rem            that tests what a player actually sees.
rem   nocloud  rt_clouds 0 -- bare MOONSKY starfield, lightning still fires.
rem            The "was the cloud deck worth it" arm.
rem   flat     ONE shell, zero stack thickness -- the deck collapses to a single
rem            plane. The shells are at genuinely different heights, and that
rem            separation is the whole volume; this arm is what proves it, and
rem            it is also the cheapest the deck can be drawn.
rem   thick    8 shells at double thickness -- the other end of the same knob.
rem            Watch for the shells reading as separate SHEETS rather than as
rem            one cloud: that is rt_clouds_thick past its useful range.
rem   still    rt_clouds_wind 0 -- static clouds. The clouds may legitimately not
rem            move at all; this is the arm that decides whether the drift is
rem            adding anything or just drawing attention to itself.
rem   nobolt   rt_lightning_bolt 0 -- flash and directional light, no visible
rem            bolt. Isolates how much of the effect is the LIGHT vs the art.
rem   nolight  rt_lightning_intensity 0 -- bolt and cloud flash, no directional
rem            light. The complement of nobolt, and the one that shows why the
rem            analytic light exists: the sky cubemap is not importance-sampled,
rem            so a painted bolt lights essentially nothing at 1 spp.
rem   nosect   rt_lightning_sectorflash 0 -- suppress the stock F_SKY1
rem            lightlevel flash (106 sectors on MAP11), leaving only the
rem            directional light. Under RT that flash is not merely brightness:
rem            rt_sector_emis makes any sector over the map threshold a surface
rem            EMITTER, so the vanilla flash briefly turns the whole outdoors
rem            into a sourceless glow. Compare against `full` in an open area.
rem   hard     one stroke, fast decay, no cloud flash -- a single hard snap
rem            instead of a stuttering burst. Use it to judge stroke structure.
rem   sharp    rt_lightning_angdiam 1.5 -- near-point light, hard ray-traced
rem            shadows. The strike ALWAYS casts real shadows (it is an analytic
rem            directional light, not a screen flash); this is how readable they
rem            are. Watch for sky leaks: at intensity 2200 a pinhole gap that the
rem            moon never revealed can read as a full-strength shaft.
rem   soft     rt_lightning_angdiam 14 -- the other end. Shadows dissolve at room
rem            distances and the flash reads as a fullscreen brightness pulse;
rem            this is what the default used to be, kept as the leak-safe arm.
rem   debug    full + rt_lightning_debug 1: one line per strike with bearing,
rem            altitude, bolt variant and the stroke pattern, then one line per
rem            frame while the flash is live. NOARCH, so it cannot stick in the
rem            ini the way rt_rr_reset_debug once did.
rem
rem Every arm sets every rt_clouds_* and rt_lightning_* cvar explicitly. They are
rem CVAR_ARCHIVE, so a value left behind by one arm would otherwise leak into the
rem next and quietly invalidate the comparison.
rem
rem And every arm except `preset` also sets rt_clouds_presets 0. That is not
rem tidiness -- RT_CLOUD_PRESETS is applied at LEVEL LOAD and writes rt_clouds,
rem _tint, _alpha and _wind, so on a map with an entry it would silently overwrite
rem the arm's own values after the command line had already been parsed. The
rem `still` arm (wind 0) on MAP11 would have come back with MAP11's 0.014 and
rem looked like the cvar did nothing.
rem
rem Usage: ab-storm.cmd <full|nocloud|flat|thick|still|nobolt|nolight|preset|nosect|hard|sharp|soft|debug> [1-32]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=full"
if "%MAP%"==""  set "MAP=11"

rem Defaults, spelled out once. Each arm below overrides by appending -- later
rem +cvar wins, so an arm only needs to name what it changes.
set "CLOUD=+rt_clouds 1 +rt_clouds_presets 0 +rt_clouds_shells 6 +rt_clouds_horizon 9 +rt_clouds_curve 0.55 +rt_clouds_thick 0.7 +rt_clouds_tiles 6 +rt_clouds_alpha 0.9 +rt_clouds_dark 0.45 +rt_clouds_wind 0.014 +rt_clouds_wind_dir 30 +rt_clouds_shear 0.09 +rt_clouds_occlude 1 +rt_clouds_transmit 0.22 +rt_clouds_tint B4C0DC +rt_clouds_flash 2.2"
set "LTNG=+rt_lightning 1 +rt_lightning_intensity 2200 +rt_lightning_color C8D8FF +rt_lightning_decay 0.18 +rt_lightning_strokes 3 +rt_lightning_angdiam 6 +rt_lightning_alt_min 15 +rt_lightning_alt_max 40 +rt_lightning_bolt 1 +rt_lightning_bolt_size 55 +rt_lightning_sectorflash 1 +rt_lightning_debug 0"

if /i "%ARM%"=="full"    set "ARGS=%CLOUD% %LTNG%"
if /i "%ARM%"=="preset"  set "ARGS=%CLOUD% %LTNG% +rt_clouds_presets 1 +rt_clouds 0"
if /i "%ARM%"=="nocloud" set "ARGS=%CLOUD% %LTNG% +rt_clouds 0"
if /i "%ARM%"=="flat"    set "ARGS=%CLOUD% %LTNG% +rt_clouds_shells 1 +rt_clouds_thick 0"
if /i "%ARM%"=="thick"   set "ARGS=%CLOUD% %LTNG% +rt_clouds_shells 8 +rt_clouds_thick 0.9"
if /i "%ARM%"=="still"   set "ARGS=%CLOUD% %LTNG% +rt_clouds_wind 0"
if /i "%ARM%"=="nobolt"  set "ARGS=%CLOUD% %LTNG% +rt_lightning_bolt 0"
if /i "%ARM%"=="nolight" set "ARGS=%CLOUD% %LTNG% +rt_lightning_intensity 0"
if /i "%ARM%"=="nosect"  set "ARGS=%CLOUD% %LTNG% +rt_lightning_sectorflash 0"
if /i "%ARM%"=="hard"    set "ARGS=%CLOUD% %LTNG% +rt_lightning_strokes 1 +rt_lightning_decay 0.08 +rt_clouds_flash 0"
if /i "%ARM%"=="sharp"   set "ARGS=%CLOUD% %LTNG% +rt_lightning_angdiam 1.5"
if /i "%ARM%"=="soft"    set "ARGS=%CLOUD% %LTNG% +rt_lightning_angdiam 14"
if /i "%ARM%"=="debug"   set "ARGS=%CLOUD% %LTNG% +rt_lightning_debug 1"

if not defined ARGS (
  echo Usage: %~nx0 ^<full^|nocloud^|flat^|thick^|still^|nobolt^|nolight^|preset^|nosect^|hard^|sharp^|soft^|debug^> [1-32]
  exit /b 1
)

echo === storm arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo     (console: `thunder` forces a strike -- do not wait for the schedule)
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
