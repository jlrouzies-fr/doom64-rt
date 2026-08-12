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
rem   off       rt_gore_life 32, no jitter, no cap, burst off. Stock Retribution -- the
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
rem THE EXPLOSION HALF. Rockets and barrels used to leave no blood at all, and
rem that is stock GZDoom rather than Retribution: blood is spawned by ATTACK
rem code only, and P_RadiusAttack calls P_DamageMobj + P_TraceBleed, neither of
rem which spawns a blood actor. RTBloodPersistHandler.WorldThingDamaged now
rem throws a splash of the same splats on DMG_EXPLOSION.
rem
rem   boom      the defaults plus rt_gore_burst_debug 1. START HERE. Every burst
rem             prints "RTBloodBurst: <class> dmg N -> M splats". NOTHING
rem             PRINTED MEANS THE FEATURE IS NOT LIVE -- check the log for
rem             RTBloodPersistHandler before concluding anything from the
rem             screen. Barrels with nothing near them must print nothing: the
rem             barrel does not bleed (GetBloodType is null) and that is the
rem             negative control, not a failure.
rem   noboom    burst OFF, everything else at default. The flip-against
rem             baseline for the explosion half only. Debug stays 1 on purpose:
rem             if a line prints here, the arm did not take.
rem   bigboom   count 12, speed 7, lift 5. Too much on purpose -- brackets the
rem             count/speed from above before the defaults are settled.
rem
rem Every arm sets every rt_gore_* cvar explicitly, so a value left over from a
rem previous arm can never leak into the next one. (They are noarchive besides,
rem but the launcher pins them anyway -- belt and braces, same rule as ab-lava.)
rem That is why adding the five rt_gore_burst_* cvars meant editing all seven of
rem the arms above and not only the new ones.
rem
rem Usage: ab-blood.cmd <off|on|uncapped|tight|plain|wild|roll|boom|noboom|bigboom|color|nocolor> [1-34]
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

rem BURST is the five explosion cvars, appended to every arm. The contract is
rem that an arm sets EVERY rt_gore_* it does not mean to inherit, so adding a
rem family means every existing arm grows -- there is no default-by-omission.
set "BURST=+rt_gore_burst 1 +rt_gore_burst_count 5 +rt_gore_burst_speed 4.0 +rt_gore_burst_lift 3.0 +rt_gore_burst_debug 0"

if /i "%ARM%"=="off"      set "ARGS=+rt_gore_life 32 +rt_gore_max 0    +rt_gore_scale_var 0    +rt_gore_roll 0 +rt_gore_burst 0 +rt_gore_burst_count 5 +rt_gore_burst_speed 4.0 +rt_gore_burst_lift 3.0 +rt_gore_burst_debug 0"
if /i "%ARM%"=="on"       set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.35 +rt_gore_roll 0 %BURST%"
if /i "%ARM%"=="uncapped" set "ARGS=+rt_gore_life 0  +rt_gore_max 0    +rt_gore_scale_var 0.35 +rt_gore_roll 0 %BURST%"
if /i "%ARM%"=="tight"    set "ARGS=+rt_gore_life 0  +rt_gore_max 300  +rt_gore_scale_var 0.35 +rt_gore_roll 0 %BURST%"
if /i "%ARM%"=="plain"    set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0    +rt_gore_roll 0 %BURST%"
if /i "%ARM%"=="wild"     set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.6  +rt_gore_roll 1 %BURST%"
if /i "%ARM%"=="roll"     set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.35 +rt_gore_roll 1 %BURST%"

if /i "%ARM%"=="boom"     set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.35 +rt_gore_roll 0 +rt_gore_burst 1 +rt_gore_burst_count 5  +rt_gore_burst_speed 4.0 +rt_gore_burst_lift 3.0 +rt_gore_burst_debug 1"
if /i "%ARM%"=="noboom"   set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.35 +rt_gore_roll 0 +rt_gore_burst 0 +rt_gore_burst_count 5  +rt_gore_burst_speed 4.0 +rt_gore_burst_lift 3.0 +rt_gore_burst_debug 1"
rem BLOOD COLOUR. Not a gore cvar at all -- rt_tex_translations is the engine
rem fix that gives a palette-translated texture its own RTGL1 material name.
rem Without it every translation of BLUDA0 uploads under one name and RTGL1
rem keeps only the first, so per-monster BloodColor renders as whatever blood
rem happened to be drawn first. LAUNCH-TIME ONLY: the name is cached per
rem hardware texture, so this cannot be flipped from the console -- which is the
rem whole reason these two arms exist.
rem   color     translations ON + the rename debug print. MAP03 (21 Nightmare
rem             Imps, 8 Cacodemons) or MAP14 (all four new families at once).
rem             No rename lines in the log = the fix is not live; stop there
rem             rather than judging a colour on screen.
rem   nocolor   translations OFF. Everything bleeds red again.
if /i "%ARM%"=="color"    set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.35 +rt_gore_roll 0 %BURST% +rt_tex_translations 1 +rt_tex_translations_debug 1"
if /i "%ARM%"=="nocolor"  set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.35 +rt_gore_roll 0 %BURST% +rt_tex_translations 0 +rt_tex_translations_debug 1"

if /i "%ARM%"=="bigboom"  set "ARGS=+rt_gore_life 0  +rt_gore_max 1500 +rt_gore_scale_var 0.35 +rt_gore_roll 0 +rt_gore_burst 1 +rt_gore_burst_count 12 +rt_gore_burst_speed 7.0 +rt_gore_burst_lift 5.0 +rt_gore_burst_debug 1"

if not defined ARGS (
  echo Usage: %~nx0 ^<off^|on^|uncapped^|tight^|plain^|wild^|roll^|boom^|noboom^|bigboom^|color^|nocolor^> [1-34]
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
