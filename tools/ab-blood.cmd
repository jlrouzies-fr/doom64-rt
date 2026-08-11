@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem A/B persistent blood. What this is testing is NOT a renderer setting.
rem
rem The ~0.9 s lifetime is authored in the Retribution WAD's own DECORATE:
rem 64Blood's Spawn runs BLUD D 8 / BLUD CBA 8 / Stop, and Stop is the whole
rem bug. d64r-blood-persist.pk3 replaces 64Blood, 64Blood2 and 64InvisiBlood
rem with copies that end on `BLUD A -1` -- infinite tics, so the splat holds its
rem largest frame forever. The actor still physics-ticks and settles on the
rem floor; only the animation stops.
rem
rem DECORATE CANNOT READ A CVAR, so "off" is not the states ending early -- it is
rem RTBloodPersistHandler expiring the splats after rt_gore_life tics. That is
rem the only reason rt_gore_life exists; leave it at 0 for the real feature.
rem
rem   off       rt_gore_life 32, no jitter, no cap. Stock Retribution -- the
rem             baseline to flip against. If "on" looks the same as this, the
rem             pk3 is not loading; check the startup log for RTBloodPersist.
rem   on        THE DEFAULT. Forever, cap 1500, +/-35%% size jitter, random
rem             mirror, no roll.
rem   uncapped  forever with NO cap at all. The honest perf read: play a heavy
rem             map to the end and watch the frame time. Offscreen splats cost
rem             only a thinker tick (hw_sprites never processes a sprite in an
rem             unseen subsector, so RTGL1 never sees them) -- this arm is what
rem             proves or disproves that.
rem   tight     cap 300. Makes the recycle POP visible: the oldest splat is
rem             destroyed outright, no fade. Use it to judge whether 1500 is
rem             comfortably above the point where you would ever notice.
rem   plain     forever, cap 1500, jitter OFF. The A/B for the randomization
rem             itself -- this is the "same three-blob stamp on every corpse"
rem             look that the jitter exists to break up.
rem   wild      jitter 0.6 AND roll on. Too much on purpose; brackets the
rem             answer from the other side.
rem   roll      the default plus rt_gore_roll 1 and nothing else. THE ONE
rem             UNVERIFIED BIT: ROLLSPRITE is applied in HWSprite::Process,
rem             upstream of the RT upload, so RTGL1 should get already-rotated
rem             geometry -- but that has never been eyeballed here. If the
rem             splats render unrotated, or z-fight the floor, roll stays off.
rem
rem Every arm sets every rt_gore_* cvar explicitly, so a value left over from a
rem previous arm can never leak into the next one. (They are noarchive besides,
rem but the launcher pins them anyway -- belt and braces, same rule as ab-lava.)
rem
rem Usage: ab-blood.cmd <off|on|uncapped|tight|plain|wild|roll> [1-34]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"

rem Anything after the map is forwarded verbatim to the launcher, and lands
rem AFTER the arm's own cvars, so it wins. Same rule as ab-lava.cmd.
set "PASS="
set "IDX=0"
for %%A in (%*) do (
  set /a IDX+=1
  if !IDX! GEQ 3 set "PASS=!PASS! %%~A"
)
if "%ARM%"=="" set "ARM=on"
if "%MAP%"==""  set "MAP=1"

if /i "%ARM%"=="off"      set "ARGS=+rt_gore_life 32 +rt_gore_max 0    +rt_gore_scale_var 0    +rt_gore_roll 0"
if /i "%ARM%"=="on"       set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.35 +rt_gore_roll 0"
if /i "%ARM%"=="uncapped" set "ARGS=+rt_gore_life 0  +rt_gore_max 0    +rt_gore_scale_var 0.35 +rt_gore_roll 0"
if /i "%ARM%"=="tight"    set "ARGS=+rt_gore_life 0  +rt_gore_max 300  +rt_gore_scale_var 0.35 +rt_gore_roll 0"
if /i "%ARM%"=="plain"    set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0    +rt_gore_roll 0"
if /i "%ARM%"=="wild"     set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.6  +rt_gore_roll 1"
if /i "%ARM%"=="roll"     set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.35 +rt_gore_roll 1"

if not defined ARGS (
  echo Usage: %~nx0 ^<off^|on^|uncapped^|tight^|plain^|wild^|roll^> [1-34]
  exit /b 1
)

echo === blood arm "%ARM%", MAP%MAP% ===
echo     %ARGS%

rem A log of its own, for the same reason ab-lava has one: rt-console.log is a
rem single file every launch overwrites, and the startup lines that say whether
rem the DECORATE replacements parsed are the evidence this A/B turns on.
set "LOG=+logfile %~dp0\..\rt-blood.log"

call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS% %LOG% %PASS%
exit /b %ERRORLEVEL%
