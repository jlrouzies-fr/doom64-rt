@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B the per-map ILLUMINATED FOG on MAP26, the map it was built for.
rem
rem MAP26's MAPINFO asks for `fade = "00 56 56"` at `fogdensity = 200` -- a heavy
rem cyan fog. Those two keys are rasterizer fog and the RT path never read them,
rem so under RT the map had none. screen/doom64original_level26fog.png is the
rem console game's version of the same corridor and is the reference.
rem
rem What is built is not that fog. Rasterizer fog is a per-pixel lerp toward a
rem colour by distance and cannot be lit; this is the MEDIUM, in RTGL1's froxel
rem volume, which the level's own lamps and lava scatter through. So the thing
rem to look at in every arm is not "is it teal" -- it is whether the fog around
rem a light source is brighter than the fog in an unlit corridor.
rem
rem PROFILES -- pick one and walk the same corridor. Each names its ramp as
rem near -> far over a reach, with the curve that shapes it. The transmittance
rem ladders are computed, not guessed: tau(t) = 0.064*[d0*t + (d1-d0)*t^(k+1)/(k+1)]
rem over the volume's 64 slices, T = exp(-tau).
rem
rem   full      THE SHIPPING ROW via RT_FOG_PRESETS. MAP25, MAP26 and MAP31 only
rem             -- the three cyan VOIDSKY maps, which share one medium; every
rem             other map gets nothing. This is what a player sees.
rem   ramp      the shipping profile forced onto ANY map: 0.01 -> 10, curve 2.4,
rem             reach 32 m. A luminous VEIL rather than an occluder -- it hides
rem             nothing, and with rt_fog_ambient 1 the medium glows on its own
rem             while the level's lights modulate it. On any of the three listed
rem             maps it should be indistinguishable from `full`; if it is not,
rem             the preset table did not apply, and that makes this a free check
rem             that a row is live -- `ab-fog.cmd full 25` against
rem             `ab-fog.cmd ramp 25`, and the same pair on 31.
rem             T at 128/256/512/768/1024 units: 1.00 1.00 0.98 0.93 0.83
rem   veil      the lightest that still reads as fog: 3 -> 70, curve 2.0, 40 m.
rem             Air, not weather. Use when the level's own geometry should carry
rem             the depth and the fog is only tinting it.
rem             T: 0.98 0.95 0.85 0.65 0.41
rem   ramp2     6 -> 320, curve 3.0, 32 m. Same clear air, harder wall.
rem             T: 0.95 0.89 0.60 0.15 0.00
rem   wall      2 -> 700, curve 4.0, 28 m. Nearly nothing until ~600 units, then
rem             shut. The most extreme reading of "clear near, gone far", and the
rem             arm that shows what the curve exponent is really for.
rem             T: 0.98 0.95 0.54 0.01 0.00
rem   deep      6 -> 190 at reach 60 m: the shipping shape stretched over a much
rem             longer distance. For big outdoor-ish rooms where 32 m closes too
rem             early. Same near air, later wall.
rem             T: 0.97 0.95 0.87 0.74 0.54
rem   even      no ramp at all -- the map's own MAPINFO density, uniform, which
rem             is what a newly listed map would get before it is tuned.
rem             The baseline the ramp is an argument against, and the numbers say
rem             why: T 0.71 at 128 units, i.e. nearly a third of the wall two
rem             metres from your face is already fog.
rem   flatramp  the shipping ends at curve 1.0. The failure the curve exists to
rem             avoid: identical densities, and the room you stand in is hazy
rem             immediately -- T 0.87 / 0.63 at 128 / 256 units against the
rem             shipping 0.95 / 0.88. Worth seeing once, then never again.
rem   inverse   the ramp backwards (190 -> 6): thick around you, clear beyond.
rem             Smoke you are standing IN rather than distance haze.
rem   twotone   the shipping ramp with the tint split too: cyan near, deep teal
rem             far. Stylization -- it is one medium, and it cannot really do
rem             this -- but the distance reads colder.
rem
rem FLASHLIGHT. A light at ~0 m lights the froxels in front of it by inverse
rem square, so switching the flashlight on inside fog whites out the screen --
rem physically what a headlight in fog does, and unplayable. rt_fog_light_near
rem (2 m default) fades in-scattering within that distance OF A LIGHT, which
rem removes the glare from a light you are HOLDING and keeps the beam's shaft
rem further down the corridor.
rem   flsh      shipping ramp, flashlight ON at launch. The arm to judge the beam.
rem   flshraw   the same with rt_fog_light_near 0 -- the whiteout, kept so the
rem             fade can be seen doing something rather than trusted.
rem   flshwide  fade 5 m: aggressive, in case 2 m still glares on your monitor.
rem
rem DIAGNOSTIC / ISOLATION
rem   off       rt_fog 0 -- the volumetrics fall back to the plain global
rem             rt_volume_* values. What the map looked like before any of this.
rem   nolight   rt_fog_illum 0 -- the fog lit by the ONE light RTGL1's
rem             TryGetVolumetricLight picks, which is the sun, which on MAP26 is
rem             switched off. So: fog with no source at all. Shows what the
rem             all-lights froxel pass is worth. Expect flat, painted-on fog.
rem   flat      rt_volume_type 2 -- RTGL1's depth-based fog in the same colour.
rem             One exp() per pixel, no volume, no lighting. The cheap version,
rem             and the honest answer to "is the volume worth its cost".
rem   ambient   rt_fog_ambient 4 -- four times the shipping floor. Fog as pure
rem             paint: at this level the lights barely register against it.
rem   noambient rt_fog_ambient 0 -- the other end, and the more interesting one
rem             now that the floor IS the shipping look. Nothing but what the
rem             level's own lights scatter. This is the arm that says how much of
rem             the fog you are seeing is lit and how much is the floor.
rem   grey      the colour taken out (808080), the density kept. Separates how
rem             much of the look is the cyan from how much is the medium.
rem   thin      a third of the MAPINFO-derived density, uniform.
rem   dense     double it, uniform. NOTE both scale the DERIVED density, so they
rem             only bite while a map is on the sentinel -- the ramp arms above
rem             state their densities outright and ignore these.
rem   reach20   rt_fog_far 20 m and reach90 90 m, on the map's own density. The
rem   reach90     volume's reach AND where its 64 slices of precision go. (Named
rem             for the reach: `fog near` / `fog far` in the console are the
rem             RAMP, a different knob entirely.)
rem   moon      the moon put back on (rt_moon_presets 0 + rt_sun_intensity 90).
rem             MAP26 ships with it off because a directional light rakes the
rem             froxel volume from one bearing and the fog reads as a lit slab.
rem             The decision, shown rather than asserted.
rem   debug     full + rt_fog_debug 1: one block per level load naming the map's
rem             MAPINFO fade/fogdensity, whether a preset row matched, and the
rem             values that actually reached RTGL. NOARCH.
rem
rem Every arm sets every rt_fog_* cvar explicitly -- they are CVAR_ARCHIVE, so a
rem value left by one arm would leak into the next and quietly invalidate the
rem comparison.
rem
rem Arms other than `full` and `debug` set rt_fog_presets 0, for the reason every
rem ab-storm.cmd arm does: RT_FOG_PRESETS is applied at LEVEL LOAD and writes
rem rt_fog_color/_density/_far/_ambient/_illum, so on a listed map it would
rem overwrite the arm's own values after the command line was parsed. With the
rem table off, fog is decided by the cvars alone on whatever map is loaded --
rem which is also how you put fog on an unlisted map to look at it.
rem
rem Console, in any arm: `fog` reports the medium and prints a paste-ready
rem RT_FOG_PRESETS row; `fog on 00A0A0 60 45` tunes it live.
rem
rem Usage: ab-fog.cmd <full|ramp|veil|ramp2|wall|deep|even|flatramp|inverse|twotone|flsh|flshraw|flshwide|off|nolight|flat|ambient|noambient|grey|thin|dense|reach20|reach90|moon|debug> [1-32]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=full"
if "%MAP%"==""  set "MAP=26"

rem Defaults, spelled out once. Later +cvar wins, so an arm names only what it
rem changes. colour 000000 and density -1 are the SENTINELS: use the map's own
rem MAPINFO fade and fogdensity. Prefer them -- a literal copy of the map's data
rem here is the copy that goes stale.
set "FOG=+rt_fog 1 +rt_fog_presets 0 +rt_fog_color 000000 +rt_fog_density 0.01 +rt_fog_density_mult 0.3 +rt_fog_density_far 10 +rt_fog_color_far 000000 +rt_fog_curve 1 +rt_fog_far 45 +rt_fog_ambient 1 +rt_fog_lightmult 1 +rt_fog_light_near 2 +rt_fog_illum 1 +rt_fog_debug 0 +rt_volume_type 1 +rt_flsh 0"

if /i "%ARM%"=="full"     set "ARGS=%FOG% +rt_fog_presets 1"

rem Profiles. near -> far over a reach, shaped by the curve.
if /i "%ARM%"=="ramp"     set "ARGS=%FOG% +rt_fog_density 0.01 +rt_fog_density_far 10 +rt_fog_curve 2.4 +rt_fog_far 32"
if /i "%ARM%"=="veil"     set "ARGS=%FOG% +rt_fog_density 3 +rt_fog_density_far 70 +rt_fog_curve 2.0 +rt_fog_far 40"
if /i "%ARM%"=="ramp2"    set "ARGS=%FOG% +rt_fog_density 6 +rt_fog_density_far 320 +rt_fog_curve 3.0 +rt_fog_far 32"
if /i "%ARM%"=="wall"     set "ARGS=%FOG% +rt_fog_density 2 +rt_fog_density_far 700 +rt_fog_curve 4.0 +rt_fog_far 28"
if /i "%ARM%"=="deep"     set "ARGS=%FOG% +rt_fog_density 6 +rt_fog_density_far 190 +rt_fog_curve 2.4 +rt_fog_far 60"
if /i "%ARM%"=="even"     set "ARGS=%FOG% +rt_fog_density -1 +rt_fog_density_far -1 +rt_fog_curve 1"
if /i "%ARM%"=="flatramp" set "ARGS=%FOG% +rt_fog_density 6 +rt_fog_density_far 190 +rt_fog_curve 1.0 +rt_fog_far 32"
if /i "%ARM%"=="inverse"  set "ARGS=%FOG% +rt_fog_density 190 +rt_fog_density_far 6 +rt_fog_curve 2.4 +rt_fog_far 32"
if /i "%ARM%"=="twotone"  set "ARGS=%FOG% +rt_fog_density 6 +rt_fog_density_far 190 +rt_fog_curve 2.4 +rt_fog_far 32 +rt_fog_color 00A0A0 +rt_fog_color_far 004848"

rem Flashlight. +rt_flsh 1 lights it at launch; F still toggles.
if /i "%ARM%"=="flsh"     set "ARGS=%FOG% +rt_fog_density 6 +rt_fog_density_far 190 +rt_fog_curve 2.4 +rt_fog_far 32 +rt_flsh 1"
if /i "%ARM%"=="flshraw"  set "ARGS=%FOG% +rt_fog_density 6 +rt_fog_density_far 190 +rt_fog_curve 2.4 +rt_fog_far 32 +rt_flsh 1 +rt_fog_light_near 0"
if /i "%ARM%"=="flshwide" set "ARGS=%FOG% +rt_fog_density 6 +rt_fog_density_far 190 +rt_fog_curve 2.4 +rt_fog_far 32 +rt_flsh 1 +rt_fog_light_near 5"

rem Isolation.
if /i "%ARM%"=="off"      set "ARGS=%FOG% +rt_fog 0"
if /i "%ARM%"=="nolight"  set "ARGS=%FOG% +rt_fog_illum 0"
if /i "%ARM%"=="flat"     set "ARGS=%FOG% +rt_fog 0 +rt_volume_type 2 +rt_volume_scatter 60 +rt_volume_ambient 0.35"
if /i "%ARM%"=="ambient"  set "ARGS=%FOG% +rt_fog_ambient 4"
if /i "%ARM%"=="noambient" set "ARGS=%FOG% +rt_fog_ambient 0"
if /i "%ARM%"=="grey"     set "ARGS=%FOG% +rt_fog_color 808080"
if /i "%ARM%"=="thin"     set "ARGS=%FOG% +rt_fog_density_mult 0.1"
if /i "%ARM%"=="dense"    set "ARGS=%FOG% +rt_fog_density_mult 0.6"
if /i "%ARM%"=="reach20"  set "ARGS=%FOG% +rt_fog_far 20"
if /i "%ARM%"=="reach90"  set "ARGS=%FOG% +rt_fog_far 90"
if /i "%ARM%"=="moon"     set "ARGS=%FOG% +rt_moon_presets 0 +rt_sun 1 +rt_sun_intensity 90 +rt_moon_geo 1"
if /i "%ARM%"=="debug"    set "ARGS=%FOG% +rt_fog_presets 1 +rt_fog_debug 1"

if not defined ARGS (
  echo Usage: %~nx0 full^|ramp^|veil^|ramp2^|wall^|deep^|even^|flatramp^|inverse^|twotone^|flsh^|flshraw^|flshwide^|off^|nolight^|flat^|ambient^|noambient^|grey^|thin^|dense^|reach20^|reach90^|moon^|debug  [1-32]
  exit /b 1
)

echo === fog arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo     (console: `fog` reports the medium and the ramp; `fog near 12` / `fog far 90`)
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
