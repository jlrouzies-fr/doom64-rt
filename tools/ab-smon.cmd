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
rem   blink = 0.15 + 0.85 * (curRadius-lo)/(hi-lo)     0.15 .. 1.00
rem   I     = hi * rt_dynlight_intensity * blink
rem   I     = min(I, rt_dynlight_max)              <-- CAP APPLIED HERE
rem   if curRadius > rt_dynlight_rsoft: I *= (rsoft/curRadius)^2
rem
rem At the shipped 40 / 500 / 20 that is trough 144, crest 347.
rem
rem TRAP 1 -- the cap hides the intensity knob. Crest raw is 24*40 = 960 and the
rem   500 cap clips it, so lowering rt_dynlight_intensity does nothing until
rem   hi*scale falls under 500. Measured crest by scale:
rem
rem     scale  40 -> 347     (shipped)
rem     scale  30 -> 347     no change at all
rem     scale  20 -> 333     4% -- looks like the knob is broken
rem     scale  12 -> 200
rem     scale   8 -> 133
rem     scale   5 ->  83
rem
rem   So a useful "dim" arm is 12, not 20. An earlier version of this file had 20
rem   and would have read as "the cvar does nothing".
rem
rem TRAP 2 -- the blink floor and the intensity are COUPLED through the cap, and
rem   setting one without the other does nothing. rt_dynlight_blink_floor is the
rem   dim end of the swing (1 = dead steady, 0.15 = the old hardcoded value), but
rem   at scale 40 a 24/20 monitor's raw crest is 24*40 = 960, so BOTH ends clip on
rem   the 500 cap for any floor above ~0.52 and the swing flattens to 1.00x --
rem   i.e. raising the floor at scale 40 silently turns the flicker OFF entirely
rem   rather than calming it. The scale has to come under the cap first
rem   (24*16 = 384) for the floor to be linear. Shipping pair is 16 / 0.55.
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
rem   when a SMONAA sits 96-224u away. That spill is real, but at 347 intensity
rem   and full saturation it dominates. There is no cvar for this yet; dimming is
rem   the only lever without an engine change.
rem ---------------------------------------------------------------------------
rem
rem All figures below are the 24/20 monitor, which is 127 of the 199 panels.
rem
rem   off      rt_dynlight_flicker 0 -- panels glow but cast nothing. The old
rem            behaviour, and the control.
rem   loud     the first pass: intensity 40, floor 0.15. Trough 100, crest 347,
rem            swing 3.5x. This is the "flickering like crazy and too bright" one,
rem            kept so the shipped values have something to be compared against.
rem   on       SHIPPED: intensity 16, floor 0.55. Trough 147, crest 267,
rem            swing 1.82x. Start here.
rem   calm     intensity 16, floor 0.8 -> swing 1.25x. Barely-there blink, for if
rem            0.55 still reads as strobing across a wall of panels.
rem   steady   intensity 16, floor 1.0 -> no blink at all, constant 267. The
rem            panels still ANIMATE (their _e artwork does), they just stop
rem            modulating the room. This is now possible only because the
rem            roll-off was moved onto the nominal radius; before 2026-08-12 a
rem            floor this high inverted the pulse instead.
rem   dim      intensity 10, floor 0.55 -> crest 167. If 267 is still too much.
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
rem Usage: ab-smon.cmd <off|on|dim|dimmer|nocap|marks> [1-32]
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
set "COMMON=+rt_dynlight 1 +rt_dynlight_max 500 +rt_dynlight_stack_atten 1 +rt_dynlight_minradius 16 +rt_dynlight_radius 0.08 +rt_dynlight_rsoft 20 +rt_dynlight_debug 0 +rt_dynlight_debug_marks 0"

if /i "%ARM%"=="off"    set "ARGS=%COMMON% +rt_dynlight_flicker 0 +rt_dynlight_intensity 16 +rt_dynlight_blink_floor 0.55"
if /i "%ARM%"=="loud"   set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_intensity 40 +rt_dynlight_blink_floor 0.15"
if /i "%ARM%"=="on"     set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_intensity 16 +rt_dynlight_blink_floor 0.55"
if /i "%ARM%"=="calm"   set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_intensity 16 +rt_dynlight_blink_floor 0.8"
if /i "%ARM%"=="steady" set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_intensity 16 +rt_dynlight_blink_floor 1.0"
if /i "%ARM%"=="dim"    set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_intensity 10 +rt_dynlight_blink_floor 0.55"
if /i "%ARM%"=="marks"  set "ARGS=%COMMON% +rt_dynlight_flicker 1 +rt_dynlight_intensity 16 +rt_dynlight_blink_floor 0.55 +rt_dynlight_debug 1 +rt_dynlight_debug_marks 1"

if not defined ARGS (
  echo Usage: %~nx0 ^<off^|loud^|on^|calm^|steady^|dim^|marks^> [1-32]
  exit /b 1
)

echo === SMON monitor light arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo.
echo     24/20 monitor, trough..crest / swing:
echo       off 0 ^| loud 100..347 3.5x ^| on 147..267 1.8x
echo       calm 214..267 1.25x ^| steady 267 flat ^| dim 92..167 1.8x
echo     MAP29: the SMONBA panels at (176,1072) (256,768) (-256,672) (-256,768)
echo            are WHITE static screens. Any green on them is spill from the
echo            SMONAA terminals 96-224u away, whose light is pure (0,255,0).
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
