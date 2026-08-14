@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem How many lamps can a room have and still cast a readable shadow?
rem The PLAY-REALISTIC version of ab-onelamp -- nothing switched off, flux held.
rem
rem WHAT IS SETTLED, so this ladder is aimed. The MAP01 cage room uploads
rem
rem   uploaded=283 of 275 wanted (cap 1024) from 16 lamp ceiling(s)
rem     + 4 lamp floor(s) + 12 bulb lattice(s) | faux 4 | solo 4
rem
rem and rt_ceiling_edge_max 1024 means none of it is trimmed. Measured with
rem ab-onelamp, every other light in the world off:
rem
rem   1 light    the fence casts a crisp diamond shadow   screen/oneLamp.png
rem   8 lights   EIGHT overlapping copies of that diamond pattern, already
rem              crossing into grey mush                  screen/oneWithDebug.png
rem   283        uniform, no shadow at all                screen/noVisibleShadowFence.png
rem
rem Occlusion is confirmed working (practices 34a), so N lights cast N shadows and
rem N shadows are no shadow.
rem
rem BUT COUNT IS ONLY HALF OF IT, and this header said otherwise for a few hours.
rem MAP93 -- the same fixture alone in a dark room -- shows source RADIUS is just
rem as necessary: at ONE light, radius 0.35 casts nothing and radius 0.02 casts
rem crisply. The claim that source size was "falsified" came from an experiment
rem run inside MAP01 that moved radius while leaving 271 other lights untouched.
rem Both levers are required; see the `shadow` arm below and practices 34.
rem
rem THE TWO COMPENSATIONS, because the knobs do not behave alike.
rem
rem   rt_ceiling_bulb_spacing is ALREADY flux-neutral: addLattice scales a light's
rem   intensity by spaceN^2, so a light carries the energy of the area it stands
rem   for. Raise it freely; brightness does not move.
rem
rem   rt_ceiling_edge_seglen is NOT. The perimeter walk gives every segment the
rem   same `peak`, so doubling seglen halves the light of the 8 panes that take
rem   that path. It needs rt_ceiling_edge_intensity x (seglen/64)^2.
rem
rem   ...and that intensity is SHARED: it is `peak` for the lattice too, where it
rem   is already multiplied by spaceN^2. Raising it for the perimeter walk would
rem   brighten the 12 lattice panes by the same factor. rt_ceiling_bulb_gain is
rem   lattice-only, so each arm divides it by exactly the same number, undoing the
rem   double-compensation. That coupling is the reason a naive count ladder here
rem   always changes brightness -- and why the first three did.
rem
rem ARMS -- lamp COUNT falls left to right, total flux stays put.
rem
rem   dense    spacing 16  seglen 64   I 180   gain 7        today. Reference.
rem   mid      spacing 32  seglen 128  I 720   gain 1.75
rem   sparse   spacing 64  seglen 256  I 2880  gain 0.4375
rem   bare     as sparse, plus rt_faux_lamps 0 + rt_solo_lamps 0 -- the 8
rem            INVENTED fixtures removed. They are a deliberate lie (see
rem            rt_faux_lamps) and they compete for the same pixels, so they are
rem            worth a separate look before anything real is thinned further.
rem
rem JUDGE, in this order:
rem   1. does the fence cast a readable shadow on the floor or the wall?
rem   2. has a wide lamp pane gone dark down its MIDDLE? That is the failure the
rem      lattice was built to fix (open-issues 1.6g) and it is the real cost of
rem      this direction. Stand under the middle of a big pane, not at its edge.
rem   3. has overall brightness moved? It should NOT. If it has, the compensation
rem      above is wrong for this map and the arms cannot be compared.
rem
rem Watch the console: "uploaded=N of M wanted" -- N must FALL across the arms.
rem If it does not, the arm never reached the renderer and the result is void.
rem
rem   pane / panewide / panetight
rem            ONE light per pane at radius 0.5 / 1.0 / 0.25 m -- the (few, LARGE)
rem            cell, which nothing has ever run. WATCH "uploaded=N": at this
rem            stride a small sector can contain no lattice point at all and get
rem            ZERO lights, which looks like the feature failing when it is the
rem            placement. If N collapses, lower SPACE rather than believing it.
rem
rem   shadow   the combination MAP93 says is REQUIRED: one compact light per
rem            fixture (spacing 128, seglen 256, radius 0.02, faux/solo off).
rem            This is the arm to run if the question is "can MAP01's cage cast
rem            at all". Its cost is a visible pool on each pane -- see the arm.
rem
rem Usage: ab-lampcount.cmd <dense^|mid^|sparse^|bare^|pane^|panewide^|panetight^|shadow> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=mid"
if "%MAP%"==""  set "MAP=1"

set "FAUX=1"
set "SOLO=1"

if /i "%WHICH%"=="dense" (
  set "SPACE=16" & set "SEG=64"  & set "LI=180"  & set "GAIN=7"
) else if /i "%WHICH%"=="mid" (
  set "SPACE=32" & set "SEG=128" & set "LI=720"  & set "GAIN=1.75"
) else if /i "%WHICH%"=="sparse" (
  set "SPACE=64" & set "SEG=256" & set "LI=2880" & set "GAIN=0.4375"
) else if /i "%WHICH%"=="pane" (
  rem THE LAST UNTRIED CELL: FEW lights, each LARGE. The grid so far --
  rem   many + small   play at radius 0.15   -> no shadow
  rem   many + large   play at radius 0.35   -> no shadow
  rem   few  + small   ab-onelamp r 0.08     -> crisp shadow, but the single point
  rem                                           light is visible on the pane (ugly)
  rem   few  + LARGE   <- never run
  rem N small spheres give N hard shadows that sum to uniform grey. ONE sphere the
  rem size of the pane gives ONE soft shadow -- a gradient, which still reads as a
  rem shadow -- and being large it should not read as a point on the texture. That
  rem is a different thing from a wide penumbra laid on top of 283 other lights.
  rem 0.5 m = 16 map units, about a lamp pane's own width.
  set "SPACE=128" & set "SEG=256" & set "LI=2880" & set "GAIN=0.4375" & set "RAD=0.5"
) else if /i "%WHICH%"=="panewide" (
  set "SPACE=128" & set "SEG=256" & set "LI=2880" & set "GAIN=0.4375" & set "RAD=1.0"
) else if /i "%WHICH%"=="panetight" (
  set "SPACE=128" & set "SEG=256" & set "LI=2880" & set "GAIN=0.4375" & set "RAD=0.25"
) else if /i "%WHICH%"=="bare" (
  set "SPACE=64" & set "SEG=256" & set "LI=2880" & set "GAIN=0.4375"
  set "FAUX=0"   & set "SOLO=0"
) else if /i "%WHICH%"=="shadow" (
  rem THE COMBINATION THE SHADOW LAB SAYS IS REQUIRED, on a real map.
  rem
  rem MAP93 (tools/build_shadow_lab.py -- one SFLATAS pane in a SPACECM cage,
  rem nothing else in the map) measured both levers, and neither alone works:
  rem
  rem   1 light  radius 0.35   nothing
  rem   1 light  radius 0.02   crisp diamonds on floor, both walls and ceiling
  rem   4 lights radius 0.02   a trace on the ceiling only
  rem   16       radius 0.02   nothing
  rem   16       radius 0.06   nothing
  rem
  rem So: ONE COMPACT LIGHT PER FIXTURE. Radius 0.02 is the flashlight's, which
  rem has always cast through this grating. Spacing 128 is one light per pane;
  rem seglen 256 thins the eight panes that take the perimeter walk instead;
  rem faux and solo are off because they are 8 more lights competing for the
  rem same pixels and two of them are inventions (see rt_faux_lamps).
  rem
  rem THE COST IS THE POINT OF LOOKING. At this density a pane's single light
  rem reads as a visible pool ON the texture -- the failure open-issues 1.6g was
  rem written to prevent, and the reason this is not simply shipped. Judge
  rem whether the shadow is worth it, standing under a wide pane as well as
  rem beside the cage.
  set "SPACE=128" & set "SEG=256" & set "LI=2880" & set "GAIN=0.4375" & set "RAD=0.02"
  set "FAUX=0"    & set "SOLO=0"
) else (
  echo Usage: %~nx0 ^<dense^|mid^|sparse^|bare^|pane^|panewide^|panetight^|shadow^> [map 1-32]
  exit /b 1
)

set "ARGS=+rt_ceiling_edge_lamps 1 +rt_ceiling_edge_lattice 1"
set "ARGS=%ARGS% +rt_ceiling_bulb_spacing %SPACE% +rt_ceiling_edge_seglen %SEG%"
set "ARGS=%ARGS% +rt_ceiling_edge_intensity %LI% +rt_ceiling_bulb_gain %GAIN%"
set "ARGS=%ARGS% +rt_faux_lamps %FAUX% +rt_solo_lamps %SOLO%"

rem Held at play values in every arm, so count is the only thing moving. The wall
rem strips deliberately keep their own intensity: they are a different walk on the
rem same physical band, and dragging them along would confound the corner seam
rem that rt_ceiling_edge_intensity == rt_wall_strip_intensity exists to prevent.
if "%RAD%"=="" set "RAD=0.35"
set "ARGS=%ARGS% +rt_ceiling_edge_radius %RAD% +rt_ceiling_edge_max 1024"
set "ARGS=%ARGS% +rt_ceiling_bulb_emis 20 +rt_ceiling_bulb_aq_scale 0.25"
set "ARGS=%ARGS% +rt_sector_emis 0.35 +rt_emis_mapboost 200"
set "ARGS=%ARGS% +rt_shadow_samples 1 +rt_debug_visibility 0"
set "ARGS=%ARGS% +rt_ceiling_edge_debug 1"

echo === lamp count: %WHICH% (spacing=%SPACE% seglen=%SEG% I=%LI% gain=%GAIN% radius=%RAD% faux=%FAUX%), MAP%MAP% ===
echo     %ARGS%
echo     watch "uploaded=N of M wanted" -- N must FALL across arms or the result is void
echo     judge: 1) fence shadow  2) pane dark down its MIDDLE  3) brightness UNCHANGED
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
