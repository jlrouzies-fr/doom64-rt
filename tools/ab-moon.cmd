@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the moon: the directional light that replaced MAP13's painted light
rem shafts (screen/level13fakeoutside light streaks.png).
rem
rem Background: the halls' shafts were wedge sectors at lightlevel 255 inside
rem rooms at 170/180, identical to them in every other respect, fanning out of
rem real F_SKY1 windows. rt_sector_emis turned that paint into actual emission.
rem d64r-seqlight-fix.wad drops the wedges to their rooms' lightlevel; rt_sun
rem puts the light back for real, through the real windows, from a moon that is
rem actually painted in the sky (tools\gen_moon_sky.py).
rem
rem   off      no moon at all. The control: this is the halls with the paint
rem            removed and nothing given back, which is what they look like if
rem            the moon is the wrong answer.
rem   dim      intensity 45 -- shafts present but barely, moonlight you notice
rem            only once your eyes adjust.
rem   moon     intensity 90, the launcher default. Start here.
rem   bright   intensity 180 -- shafts as the strongest thing in the room, close
rem            to what the painted wedges used to read as.
rem   noon     intensity 400 and altitude 60. NOT a look to ship: it is a
rem            diagnostic. If the shafts do not land where you expect, this
rem            makes the geometry unmistakable so you can tell a bad azimuth
rem            from a light that is merely too weak to see.
rem   west     the default brightness aimed due west (azimuth 180) instead of
rem            north. Serves MAP13's west hall at full rake and gives the north
rem            colonnade nothing -- the opposite trade to the shipped 90, and
rem            the arm to reach for if a later map wants the west wall favoured.
rem
rem All arms except `west` use azimuth 90, MAP13's settled bearing, so they
rem compare BRIGHTNESS at the aim that ships rather than at the old 135
rem compromise. Change these if you rebaseline MAP13 in RT_MOON_PRESETS.
rem
rem You do not need an arm to try a bearing -- the `moon` CCMD moves the light
rem AND the painted disc together, live:
rem
rem   moon              print the current aim
rem   moon 90           swing both halves to azimuth 90
rem   moon 90 35 140    ...with altitude and intensity too
rem
rem If the DISC and the SHAFTS disagree -- the shafts arrive from a bearing the
rem moon plainly is not at -- that is the sky-rotation sign, which cancels out of
rem any derivation off the dome vertices and has to be settled by looking:
rem
rem   moon flip         reverse it
rem   moon nudge 15     then walk the disc until they line up
rem
rem and pin the resulting rt_sky_yaw in launch-retribution-rt.cmd. The old
rem texture-rebuild route (gen_moon_sky.py --flip-u) still works but is no longer
rem the way to find the answer, only to bake one in.
rem
rem Every arm sets every rt_sun cvar explicitly. RT_CVARs are CVAR_ARCHIVE, so an
rem arm that left one unset would inherit the previous arm's value out of the ini
rem and quietly invalidate the comparison.
rem
rem All arms also set +rt_moon_presets 0. The per-map table (RT_MOON_PRESETS in
rem rt_main.cpp) is applied at level load and would otherwise overwrite the arm's
rem azimuth the moment the map came up -- every arm would silently become the
rem preset, and `west` in particular would compare 90 against 90. Aim found here
rem goes INTO the table afterwards; it is not read from it.
rem
rem Usage: ab-moon.cmd <off|dim|moon|bright|noon|west> [1-32]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=moon"
if "%MAP%"==""  set "MAP=13"

rem Tracking is pinned on in every arm so the disc follows whatever bearing the
rem arm sets; rt_moon_tex_b must stay equal to gen_moon_sky.py --azimuth.
set "COLD=+rt_sun_color B4C8FF +rt_moon_track 1 +rt_moon_tex_b 135 +rt_moon_yawsign 1 +rt_sky_yaw 0 +rt_moon_presets 0"

if /i "%ARM%"=="off"    set "ARGS=+rt_sun 0 +rt_sun_intensity 90  +rt_sun_a 25 +rt_sun_b 90 %COLD%"
if /i "%ARM%"=="dim"    set "ARGS=+rt_sun 1 +rt_sun_intensity 45  +rt_sun_a 25 +rt_sun_b 90 %COLD%"
if /i "%ARM%"=="moon"   set "ARGS=+rt_sun 1 +rt_sun_intensity 90  +rt_sun_a 25 +rt_sun_b 90 %COLD%"
if /i "%ARM%"=="bright" set "ARGS=+rt_sun 1 +rt_sun_intensity 180 +rt_sun_a 25 +rt_sun_b 90 %COLD%"
if /i "%ARM%"=="noon"   set "ARGS=+rt_sun 1 +rt_sun_intensity 400 +rt_sun_a 60 +rt_sun_b 90 +rt_sun_color FFFFFF +rt_moon_track 1 +rt_moon_tex_b 135 +rt_moon_yawsign 1 +rt_sky_yaw 0 +rt_moon_presets 0"
if /i "%ARM%"=="west"   set "ARGS=+rt_sun 1 +rt_sun_intensity 90  +rt_sun_a 25 +rt_sun_b 180 %COLD%"

if not defined ARGS (
  echo Usage: %~nx0 ^<off^|dim^|moon^|bright^|noon^|west^> [1-32]
  exit /b 1
)

echo === moon arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo     MAP13: west hall is around (-1900, -500) and (-1900, 160); the north
echo     colonnade around (200, 770) and (450, 770). Both had painted shafts.
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
