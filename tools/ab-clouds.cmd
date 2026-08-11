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
rem   tools\ab-clouds.cmd ship 12 6E3CB7
rem
rem The art is achromatic, so the tint IS the cloud colour and also the colour of
rem the moonlight coming through -- every column below is arithmetic off the tint,
rem not sampled. THREE independent axes, and a sweep is only readable if it moves
rem one at a time:
rem   sat  how neon, bought by dropping G
rem   R/B  purple versus pink -- violet wants B well above R, about 0.55-0.72
rem   Y    how deep, i.e. how dark the whole thing sits
rem
rem     tint      sat   R/B     Y   bright cloud  dark cloud   moon I
rem     8660C0   0.50  0.70   111      #7253AC     #110D1E      20.6   = Doom 64's own sky
rem     9C55DC   0.61  0.71   110      #8449C5     #140B22      17.4
rem     A63CFF   0.76  0.65    97      #8D34E4     #160828      15.3   neon
rem     9A28FF   0.84  0.60    80      #8223E4     #140528      12.7   neon, deeper
rem     7F35D2   0.75  0.60    80      #6C2DBC     #110721      12.7   9A28FF faded a little
rem     6E3CB7   0.67  0.60    80      #5D34A3     #0E081C      12.7   9A28FF faded
rem     6135A0   0.67  0.60    70      #522E8F     #0D0719      11.1   <- SHIPPING: faded + deep
rem     543B8C   0.58  0.60    70      #47337D     #0B0816      11.1   fainter still
rem     4E4B82   0.42  0.60    80      #424174     #0A0A14      12.7   last purple rung
rem     C24DFF   0.70  0.76   115      #A442E4     #190A28      18.2   too far: reads PINK
rem
rem TWO AXES, and they are not the same one.
rem   sat  is how NEON it is, and it is bought by dropping G.
rem   R/B  is whether it reads PURPLE or PINK. Violet wants B well above R,
rem        about 0.55-0.70. Once R climbs toward B it is magenta, however
rem        saturated it is -- C24DFF is more saturated than 8660C0 and reads
rem        worse, because it moved along the wrong axis.
rem
rem The cost of neon is LIGHT. G carries most of the luminance, so dropping it to
rem saturate also drops tint luminance, and tint luminance scales the moonlight
rem as well as the picture (moon I above, at rt_sun_intensity 90). Compensate on
rem the transmit rather than by backing off the colour: at 9A28FF, transmit
rem 0.45 -> 0.60 puts moon I back to 16.9, i.e. where it is today.
rem
rem The moonlight HUE, by contrast, stops responding early: it is the
rem transmittance divided by its own luminance and then clamped, so from about
rem sat 0.6 both R and B are pinned at 255 and only G still moves. Past that,
rem saturation changes the sky a lot and the light on the walls very little.
rem
rem HOW THE SHIPPING VALUE WAS ARRIVED AT, because the path is not obvious from
rem the endpoint. 8660C0 first -- the console game's sky measured pixel for pixel
rem (bright #745BAD, dark #100F1F in screen/doom64clouds.png). It matched and read
rem WEAK. Then 9C55DC, then up into the neon range as far as 9A28FF, and from
rem there the answer came back DOWN rather than further out: 6135A0 is 9A28FF
rem faded (sat 0.84 -> 0.67) and deepened (Y 80 -> 70). So the sweep went past the
rem answer in both directions before settling between them, which is the argument
rem for keeping every rung in the table rather than only the winner.
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
if "%TINTHEX%"=="" set "TINTHEX=6135A0"

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
  echo   tint ladder ^(sat = how neon, R/B = purple vs pink, Y = how deep^):
  echo     8660C0 0.50 ^(= Doom 64^) ^| 9C55DC 0.61 ^| A63CFF 0.76 neon ^| 9A28FF 0.84
  echo     6E3CB7 0.67 faded ^| 6135A0 0.67 faded+deep ^(SHIP^) ^| 543B8C 0.58 fainter
  echo   deep or saturated costs LIGHT: pair it with +rt_clouds_transmit 0.60
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
