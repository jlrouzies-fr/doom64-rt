@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the SMON wall monitor lights.
rem
rem Background: Retribution wires its animated wall monitors with 9802
rem PointLightFlicker THINGS placed 4-56 units off the panel face -- SMONAA
rem 88/88 of them, SMONDA 25/27, SMONCA 19/21, SMONEA 6/6, 199 in total. It does
rem not use texture metadata for this, and could not: an emissive _e mask glows
rem but casts nothing.
rem
rem RT_UploadGzDoomDynamicLights skips FlickerLight/RandomFlickerLight outright
rem unless rt_dynlight_flicker is set, and the play launcher pinned it 0. So
rem every one of those 199 lights was dropped before upload and the panels showed
rem their _e glow and nothing else -- animated, but casting no light at all.
rem
rem The tell that identified it, from play on MAP29: of the three SMONDA panels
rem there, exactly one lit the room. Lines 922 and 937 carry a 9802 (skipped);
rem line 927 carries a 9801 PointLightPulse, which is NOT a flicker type and so
rem was never skipped.
rem
rem ---------------------------------------------------------------------------
rem THE INTENSITY MATH -- read this before picking an arm, because the obvious
rem knob does almost nothing at the shipped value.
rem
rem   hi    = max(arg3, arg4)                      24 for a 24/20 monitor
rem   lo    = min(arg3, arg4)                      20
rem   f     = rt_dynlight_blink_floor             0.8 shipped
rem   blink = f + (1-f) * (curRadius-lo)/(hi-lo)      f .. 1.00
rem   I     = hi * rt_dynlight_intensity * blink
rem   I     = min(I, rt_dynlight_max)              <-- CAP APPLIED HERE
rem   if hi > rt_dynlight_rsoft: I *= (rsoft/hi)^2  <-- NOMINAL radius, not current
rem
rem At the shipped 10 / 0.8 / 500 / 20 that is trough 133, crest 167.
rem The figures in TRAP 1 below are at the ORIGINAL scale 40, which is what they
rem are there to explain.
rem
rem TRAP 1 -- the cap hides the intensity knob. Crest raw is 24*40 = 960 and the
rem   500 cap clips it, so lowering rt_dynlight_intensity does nothing until
rem   hi*scale falls under 500. Measured crest by scale:
rem
rem     scale  40 -> 347     the first pass
rem     scale  30 -> 347     no change at all
rem     scale  20 -> 333     4% -- looks like the knob is broken
rem     scale  12 -> 200
rem     scale   8 -> 133
rem     scale   5 ->  83
rem
rem   So a useful dim arm is 12 or below, not 20. An earlier version of this file
rem   used 20 and would have read as "the cvar does nothing". The shipped scale is
rem   10, which is under the cap for every monitor in the game.
rem
rem TRAP 2 -- the blink floor and the intensity are COUPLED through the cap, and
rem   setting one without the other does nothing. rt_dynlight_blink_floor is the
rem   dim end of the swing (1 = dead steady, 0.15 = the old hardcoded value), but
rem   at scale 40 a 24/20 monitor's raw crest is 24*40 = 960, so BOTH ends clip on
rem   the 500 cap for any floor above ~0.52 and the swing flattens to 1.00x --
rem   i.e. raising the floor at scale 40 silently turns the flicker OFF entirely
rem   rather than calming it. The scale has to come under the cap first
rem   (24*10 = 240) for the floor to be linear. Shipping pair is 10 / 0.8.
rem
rem   This also used to be non-monotonic. The roll-off divided by the CURRENT
rem   flickering radius while the blink term multiplied by it, so the two fought:
rem   the crest was divided by (20/24)^2 and the trough was not, and any floor
rem   above ~0.36 INVERTED the pulse (brightest at the dim end). Fixed 2026-08-12
rem   -- the roll-off now uses the fixture's nominal radius, which is constant per
rem   light, so raising the floor always means less flicker.
rem
rem TRAP 3 -- colour is uploaded RAW and fully saturated. SMONAA's light is
rem   (0,255,0), pure primary green with no hue normalisation anywhere in the
rem   dynlight path (unlike the sector-tint path, which peak-normalises). That is
rem   why a green monitor reads as neon, and why SMONBA -- whose own art is a
rem   WHITE static-noise screen and whose own lights are mostly RED -- goes green
rem   when a SMONAA sits 96-224u away. That spill is real, and dimming to 167 has
rem   taken the worst off it, but the HUE is untouched -- there is no saturation
rem   cvar in this path yet, so dimming is still the only lever for it.
rem ---------------------------------------------------------------------------
rem
rem All figures below are the 24/20 monitor, which is 127 of the 199 panels.
rem The shipped values were settled in play over three passes:
rem
rem   scale 40 floor 0.15  ->  100..347  3.47x   "flickering like crazy, too bright"
rem   scale 16 floor 0.55  ->  147..267  1.82x   still too much
rem   scale 10 floor 0.8   ->  133..167  1.25x   SHIPPED
rem
rem At scale 10 nothing clips rt_dynlight_max at all, so every monitor family swings
rem a uniform 1.25x instead of each arg3/arg4 pair behaving differently.
rem
rem   off      rt_dynlight_flicker 0 -- panels glow but cast nothing. The control,
rem            i.e. what the game looked like before any of this.
rem   loud     the first pass, kept so the shipped values have something to be
rem            compared against rather than just asserted.
rem   mid      the second pass, 16 / 0.55.
rem   on       SHIPPED: 10 / 0.8. Start here.
rem   steady   floor 1.0 -> no blink at all, constant 167. The panels still
rem            ANIMATE (their _e artwork does), they just stop modulating the
rem            room. Only possible because the roll-off was moved onto the
rem            nominal radius; before 2026-08-12 a floor this high INVERTED the
rem            pulse instead of flattening it.
rem   dimmer   7 / 0.8 -> 93..117. If 167 is still too much.
rem   marks    magenta marker spheres at each uploaded light plus a console
rem            tally. This is how you tell "this panel has no light thing" apart
rem            from "the light is there and dim", which look identical on screen.
rem            MAP25's SMONEA at (936,-1216) is the one panel in the game with NO
rem            light thing within 96u, so it stays unmarked in every arm.
rem
rem Every arm sets every rt_dynlight cvar explicitly. RT_CVARs are CVAR_ARCHIVE,
rem so an arm that left one unset would inherit the previous arm's value out of
rem the ini and quietly invalidate the comparison.
rem
rem Where to look:
rem   MAP29  SMONAA x4 (green) at (256,672) (256,896) (-256,992) (-176,1072)
rem          SMONBA x4 (white static art) at (176,1072) (256,768) (-256,672)
rem                 (-256,768) -- these are the ones going green from spill.
rem          SMONDA x3 at (-1456,2368) (-1408,2160) (-1360,2368)
rem   MAP02  the densest set in the game, 35 lights.
rem
rem   static      SHIPPED for the SMONBA readout panels: 20/16 9804s at
rem               rndflicker_floor 0.3 -> 60..200, a 3.3x swing re-randomised
rem               every 2 tics. Crest 200 is the BRIGHTEST a fixture can be here
rem               (hi*10, and the rsoft roll-off bites the moment hi passes 20),
rem               against SMONAA's 167 and the first SMONBA pass's 125.
rem   statichard  floor 0.1 -> 20..200, 10x. Nearly cuts out at the trough.
rem   staticcalm  floor 0.6 -> 120..200, 1.67x.
rem   staticoff   floor 1.0 -> flat 200. Isolates "is it too bright" from "is the
rem               flicker too much", which is the pair that keeps getting
rem               conflated. Still 20% brighter than SMONAA.
rem
rem Usage: ab-smon.cmd <off|loud|mid|on|steady|dimmer|marks
rem                    |static|statichard|staticcalm|staticoff> [1-32]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=on"
if "%MAP%"==""  set "MAP=29"

rem Everything the arms do NOT vary, set explicitly so no arm inherits a stale
rem archived value from the one before it.
rem COMMON goes FIRST in every arm, so an arm's own values override it. Putting it
rem last silently cancelled the `marks` arm's debug flags in an earlier version.
rem It sets the debug pair and rsoft explicitly too: without that, one `marks` run
rem would leave magenta spheres archived into every later arm.
rem rt_dynlight_intensity stays at 40 in EVERY arm. It is global to every
rem FDynamicLight, so varying it here would dim doors and torches along with the
rem monitors -- which is exactly the mistake that produced rt_dynlight_flicker_scale.
rem The arms vary that flicker-only scale instead.
set "COMMON=+rt_dynlight 1 +rt_dynlight_intensity 40 +rt_dynlight_max 500 +rt_dynlight_stack_atten 1 +rt_dynlight_minradius 16 +rt_dynlight_radius 0.08 +rt_dynlight_rsoft 20 +rt_dynlight_debug 0 +rt_dynlight_debug_marks 0 +rt_dynlight_rndflicker_floor 0.3"

if /i "%ARM%"=="off"    set "ARGS=%COMMON% +rt_dynlight_flicker 0 +rt_dynlight_flicker_scale 0.25 +rt_dynlight_blink_floor 0.8"
if /i "%ARM%"=="loud"   set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 1.0  +rt_dynlight_blink_floor 0.15"
if /i "%ARM%"=="mid"    set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 0.4  +rt_dynlight_blink_floor 0.55"
if /i "%ARM%"=="on"     set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 0.25 +rt_dynlight_blink_floor 0.8"
if /i "%ARM%"=="steady" set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 0.25 +rt_dynlight_blink_floor 1.0"
if /i "%ARM%"=="dimmer" set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 0.175 +rt_dynlight_blink_floor 0.8"
if /i "%ARM%"=="marks"  set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 0.25 +rt_dynlight_blink_floor 0.8 +rt_dynlight_debug 1 +rt_dynlight_debug_marks 1"

rem --- the SMONBA static panels (9804 RandomFlicker) -------------------------
rem These vary rt_dynlight_rndflicker_floor ONLY. It touches nothing but the 48
rem SMONBA readout lights, because they are the only 9804s in the game -- the
rem 9802 wall keeps blink_floor 0.8 in every arm below, so the green/teal/blue
rem monitors are identical across all four and only the white ones change.
rem On a 20/16 fixture, crest is a fixed 200 and the floor sets the trough:
if /i "%ARM%"=="static"     set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 0.25 +rt_dynlight_blink_floor 0.8 +rt_dynlight_rndflicker_floor 0.3"
if /i "%ARM%"=="statichard" set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 0.25 +rt_dynlight_blink_floor 0.8 +rt_dynlight_rndflicker_floor 0.1"
if /i "%ARM%"=="staticcalm" set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 0.25 +rt_dynlight_blink_floor 0.8 +rt_dynlight_rndflicker_floor 0.6"
if /i "%ARM%"=="staticoff"  set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_flicker_scale 0.25 +rt_dynlight_blink_floor 0.8 +rt_dynlight_rndflicker_floor 1.0"

if not defined ARGS (
  echo Usage: %~nx0 ^<off^|loud^|mid^|on^|steady^|dimmer^|marks^> [1-32]
  exit /b 1
)

echo === SMON monitor light arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo.
echo     24/20 monitor (127 of the 199 panels), trough..crest / swing:
echo       off 0            loud   100..347  3.47x   mid  147..267  1.82x
echo       on  133..167 1.25x (SHIPPED)      steady 167 flat
echo       dimmer 93..117 1.25x
echo     MAP29: the SMONBA panels at (176,1072) (256,768) (-256,672) (-256,768)
echo            are WHITE static screens. Any green on them is spill from the
echo            SMONAA terminals 96-224u away, whose light is pure (0,255,0).
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
