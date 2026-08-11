@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Settle the cloud deck's LOOK against the console game's sky.
rem
rem The reference is screen/doom64clouds.png -- Doom 64's own CLOUDPRP sky, which
rem is a continuous smoky mass, heavy, with no clear sky between the clouds and
rem all of its structure in luminance. screen/ourclouds.png is what the deck
rem looked like before this pass: hard-rimmed islands with BLACK holes punched
rem between them. Measured over the sky region of each:
rem
rem                        darkest 2%   Y std (blotchiness)   pure black
rem     Doom 64              #100F1F         25.2               none
rem     ours, before         #000000         35.8               yes
rem
rem WHAT CHANGED IN THE ART (tools/gen_clouds.py, all of it regenerable):
rem   coverage    0.46 -> 0.72   fewer, bigger gaps between masses
rem   edge        0.20 -> 0.30   wider feathered rim, less cut-out
rem   erode       0.50 -> 0.25   stops the masses being torn into islands
rem   octaves     6    -> 5      smoother field; the target has little fine detail
rem   alpha_floor 0    -> 0.30   the deck CLOSES: no gap shows the backdrop
rem   ambient     0.10 -> 0.06   more contrast between lit tops and dark bases
rem   SHADOW      32   -> 74     the darkest cloud is dark PURPLE, not black
rem
rem The last two are a pair and neither works alone. At zero light a texel IS the
rem shadow colour, so SHADOW sets the dark end and `ambient` sets the contrast --
rem which is how the deck gets both a floor that is not black and structure worth
rem looking at. And alpha_floor is applied to ALPHA ONLY, never to the density
rem the lighting was integrated from: flooring density closes the holes by making
rem every column equally thick, and then the slice you look up at -- the base,
rem under the whole column -- becomes flat paint. That was two failed attempts.
rem
rem WHY THIS TOOL EXISTS. The values above were reasoned and checked against the
rem colour arithmetic, which is exact: a cloud texel is LIT x tint x the shell
rem ramp, so both ends of the range are computable, and MAP12's 8660C0 puts them
rem at #7153AC / #110C1D against Doom 64's #745BAD / #100F1F. The SHAPE is not
rem computable that way. An offline composite of the slices was tried and came
rem out 5-15x off the renderer's actual contrast -- it cannot model 8 discs at
rem different heights seen in perspective with tiling -- so tuning against it
rem would have been false precision. These arms are the honest way to settle it.
rem
rem   ship      the values above, as committed.
rem   old       the pre-pass look: holes, hard rims, black gaps. The before shot.
rem   thin      alpha 0.55 -- deck present but see-through. Is the floor too much?
rem   heavy     alpha 1.0, 8 shells, thick 1.0 -- MAP12's maxed shape on any map.
rem   flat      1 shell -- the volume removed, so what the stack is actually worth.
rem   nodeck    rt_clouds 0 -- the sky without any of it. Control.
rem
rem Regenerating the art is NOT one of these arms: it needs a repack and a
rem restart. Sweep a value with, e.g.
rem   tools\.venv-ai\Scripts\python.exe tools/gen_clouds.py --coverage 0.85 --preview
rem   tools\.venv-ai\Scripts\python.exe tools/pack_rt_sky.py
rem and look at CLOUDSTACK_preview.png (the slices composited as you look up at
rem them) before spending a launch on it.
rem
rem Every arm sets rt_clouds_presets 0 so the per-map table cannot overwrite the
rem pins at level load -- the trap ab-storm.cmd documents -- which also means each
rem arm has to state every value it cares about, since RT_CVARs are CVAR_ARCHIVE
rem and an unset one carries over from the last arm.
rem
rem TINT, and the ladder to sweep it along. Pass one as the third argument:
rem   tools\ab-clouds.cmd ship 12 9859D3
rem
rem The art is achromatic, so the tint IS the cloud colour and also the colour of
rem the moonlight coming through -- both ends of the rendered range are
rem arithmetic. This ladder holds LUMINANCE constant and varies only saturation,
rem which is the point: "stronger purple" should mean more saturated, not
rem brighter or darker. G carries most of the luminance, so the cost of
rem saturation is paid in R and B.
rem
rem     tint      sat   bright cloud   dark cloud   moonlight
rem     6C6C96   0.28      #5B5D86      #0E0E17      #AFC3FF
rem     7A66AA   0.40      #675898      #100E1A      #C6B8FF
rem     8660C0   0.50      #7253AC      #110D1E      #D9ADFF   <- matches Doom 64
rem     9C55DC   0.61      #8449C5      #140B22      #FF9BFF   <- SHIPPING
rem     A852E9   0.65      #8E47D0      #160B24      #FF94FF
rem     B44BF5   0.69      #9841DB      #180A26      #FF89FF   near neon, careful
rem
rem The moonlight column saturates fast because its hue is the transmittance
rem DIVIDED by its own luminance and then clamped -- past about 0.6 both R and B
rem are already pinned at 255 and only G keeps falling, so further saturation
rem changes the light much less than it changes the picture.
rem
rem 8660C0 is what the console game's sky actually measures at (bright #745BAD,
rem dark #100F1F in screen/doom64clouds.png). It read WEAK in motion, so the
rem shipping value is deliberately one rung past the reference rather than on it.
rem
rem Usage: ab-clouds.cmd <ship|old|thin|heavy|flat|nodeck> [map, default 12] [tint hex]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
set "TINTHEX=%~3"
if "%ARM%"=="" set "ARM=ship"
rem MAP12 by default: it is the map the deck is a LIGHT source on, so it shows
rem both halves at once -- the picture and the purple it puts on the level.
if "%MAP%"==""  set "MAP=12"
if "%TINTHEX%"=="" set "TINTHEX=9C55DC"

set "TINT=+rt_clouds_tint %TINTHEX%"
set "BASE=+rt_clouds 1 +rt_clouds_presets 0 %TINT% +rt_clouds_wind 0.010 +rt_clouds_dark 0.45"

if /i "%ARM%"=="ship"   set "ARGS=%BASE% +rt_clouds_alpha 1.0  +rt_clouds_shells 8 +rt_clouds_thick 1.0 +rt_clouds_transmit 0.45"
if /i "%ARM%"=="old"    set "ARGS=%BASE% +rt_clouds_alpha 0.85 +rt_clouds_shells 6 +rt_clouds_thick 0.7 +rt_clouds_transmit 0.22"
if /i "%ARM%"=="thin"   set "ARGS=%BASE% +rt_clouds_alpha 0.55 +rt_clouds_shells 6 +rt_clouds_thick 0.7 +rt_clouds_transmit 0.45"
if /i "%ARM%"=="heavy"  set "ARGS=%BASE% +rt_clouds_alpha 1.0  +rt_clouds_shells 8 +rt_clouds_thick 1.0 +rt_clouds_transmit 0.45"
if /i "%ARM%"=="flat"   set "ARGS=%BASE% +rt_clouds_alpha 1.0  +rt_clouds_shells 1 +rt_clouds_thick 0.0 +rt_clouds_transmit 0.45"
if /i "%ARM%"=="nodeck" set "ARGS=+rt_clouds 0 +rt_clouds_presets 0"

if not defined ARGS (
  echo Usage: %~nx0 ^<ship^|old^|thin^|heavy^|flat^|nodeck^> [map, default 12] [tint hex]
  echo   tint ladder, luminance held, saturation only:
  echo     6C6C96 0.28 ^| 7A66AA 0.40 ^| 8660C0 0.50 ^| 9C55DC 0.61 ^(ship^) ^| A852E9 0.65
  exit /b 1
)

echo === cloud arm "%ARM%", MAP%MAP%, tint %TINTHEX% ===
echo     %ARGS%
echo.
echo     LOOK UP, and stand in the same spot for every arm. What to compare
echo     against screen\doom64clouds.png:
echo       - is there any BLACK between the clouds? There should be none.
echo       - do the masses have soft smoky edges, or cut-out rims?
echo       - is the darkest part still recognisably purple cloud?
echo     `old` is the before shot -- run it second, not first, so you know what
echo     you are looking at.
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
