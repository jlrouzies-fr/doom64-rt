@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem A/B LOCALISED VOLUMETRIC SMOKE -- muzzle smoke as a real participating
rem medium, in the same RTGL1 froxel volume the per-map fog uses.
rem
rem This is not a sprite and not a second volume. A puff is a world-space sphere
rem whose density is ADDED to the medium inside RtVolumetric.rgen, so the level's
rem own lights -- including the muzzle flash that just made it -- scatter through
rem it, and CmVolumetricProcess's front-to-back prefix sum gives it correct
rem occlusion and transmittance for free.
rem
rem THE THING TO LOOK AT in every arm is not "is there a grey blob". It is
rem whether the puff is BRIGHTER for the first two or three frames, while its own
rem muzzle flash is still lit, than it is a moment later. If it is not, the smoke
rem is being painted rather than lit, and `nolight` is what that failure looks
rem like on purpose.
rem
rem Fire at a wall in a DARK room. Muzzle smoke lit by nothing but its own flash
rem is the whole feature; in a bright room the level's lighting hides it.
rem
rem PROFILES
rem   full      the shipping numbers.
rem   fat       4x density, radius 0.8 m (over 3 froxel slices at the shipping
rem             reach, so it cannot hide inside one cell), 4 puffs a shot.
rem             Proves the injection is live before anything is tuned -- if this
rem             shows nothing the problem is plumbing, not values. Use it first.
rem   thin      a third of the density: where the puff stops occluding and
rem             becomes a haze you can see the wall through.
rem   still     no rise, no drag, no growth, 6 s life. The puff hangs exactly
rem             where it was born, which is the arm for judging SHAPE and the
rem             froxel resolution without the motion arguing about it.
rem   drift     4 s life with double the rise: watch a puff climb, flatten
rem             against the ceiling and spread. That flattening is the CPU
rem             simulation reading the sector, and is the one thing a GPU
rem             particle sim could not do.
rem   walk      inherit 0 -- the smoke does NOT take the player's velocity. Strafe
rem             while firing: the puffs visibly lag and read as stuck to the
rem             world. Against `full` (0.85) this is what that cvar buys.
rem   glued     inherit 1, the opposite failure: the smoke rides the camera.
rem   edgeonly  rt_smoke_repeat 0 -- spawn on the rising edge of extralight and
rem             nothing else. HOLD DOWN the chaingun or the plasma rifle: those
rem             re-enter their Flash state before A_Light0 clears extralight, so
rem             the edge never re-arms and an entire burst produces ONE puff. The
rem             shipping 5-tic repeat is the fallback for exactly that, and this
rem             arm is what it is a fallback FROM. On the pistol or the shotgun
rem             the two are identical.
rem
rem THE TWO TRAPS, each with the arm that shows it
rem   nearfade  rt_smoke_light_near 2 -- the FOG's value applied inside the puff.
rem             The fog needs that fade or a carried light whites out the screen;
rem             a muzzle flash is at ~0 m from its own smoke, so at 2 m the puff
rem             is fully faded and the effect disappears. Shipping value is 0.
rem   blendslow rt_smoke_illum_blend 0.05 -- the STOCK temporal blend, which is
rem             right for fog. A muzzle flash lasts 2-3 frames: at 0.05 the
rem             volume needs ~0.7 s to respond and as long to let go, so the
rem             smoke lights up AFTER the flash and then lingers. Shipping 0.4.
rem   blendraw  0.9 -- the other end. Responsive and noisy; the volumetric is not
rem             denoised, so this is where the noise floor is.
rem
rem RESOLUTION
rem   reach30   rt_smoke_far 30 instead of 14. NOT a reach knob: the volume's 64
rem             slices spread over it, so 30 m gives 0.47 m cells against 0.22 m
rem             and a puff collapses into one slab. This is the arm that explains
rem             why the shipping value is short.
rem   reach8    8 m, i.e. 0.13 m cells. Finer than the puff needs; here to show
rem             the cost side, since everything past the far plane is shaded with
rem             the far slice.
rem
rem ISOLATION
rem   off       rt_smoke 0 -- the before.
rem   nolight   rt_smoke_illum 0. The puff gets ambient plus whichever single
rem             light TryGetVolumetricLight picked, i.e. usually nothing: flat
rem             grey soup. What smoke looks like painted rather than lit.
rem   probe     rt_smoke_debug 2 -- the SHADER paints magenta in every froxel a
rem             puff covers, ignoring lighting and density entirely. If this
rem             shows a magenta blob at the barrel, the uniform is being read and
rem             the puffs are where they should be, so anything still invisible
rem             is a lighting or density question. If it shows NOTHING, either
rem             the shader cannot see the uniform (check probeall) or the puff is
rem             not where it is believed to be -- inside the wall you are
rem             shooting at, for instance.
rem   probeall  rt_smoke_debug 3 -- green over the WHOLE screen whenever the puff
rem             list is non-empty, with no position test at all. This is the one
rem             that separates the two: probeall green + probe blank means the
rem             data arrives and the sphere test fails; both blank means the
rem             shader is not seeing the uniform.
rem   novol     the arm's own cvars with rt_smoke 0 -- i.e. everything ab-smoke
rem             changes EXCEPT the smoke. Compare against plain
rem             .\tools\launch-retribution-rt.cmd 01 to tell an arm-side
rem             difference (fog off, logging on, -rtdebug) apart from anything
rem             smoke is doing. Use it if the lighting looks off in an arm.
rem   debug     full + rt_smoke_debug 1. Prints once a second: live puff count,
rem             how many were sent, the nearest puff's position/radius/density in
rem             metres, the volume's reach and its slice thickness. This is how
rem             "no smoke visible" is told apart from "no puffs spawned". NOARCH.
rem
rem THE FOG REGRESSION -- run this one before tuning anything
rem   fogsafe   MAP26, the shipping fog profile, with rt_smoke 1 and NOT firing.
rem             It must be PIXEL-IDENTICAL to `ab-fog.cmd ramp`. Both send zero
rem             puffs, and with zero puffs the froxel shader's arithmetic
rem             collapses to exactly the fog's (see Smoke.h). If these two
rem             differ, something that should be per-froxel became per-frame and
rem             smoke is retuning the fog -- which is the one thing this feature
rem             is not allowed to do.
rem   fogsmoke  the same map, firing. Both media in one volume: the fog is a
rem             luminous veil that does not occlude, the puff does. Note the
rem             puff is coarser here -- a fogged map owns rt_fog_far, so the
rem             slices are 45/64 = 0.70 m rather than 0.22 m.
rem
rem Every arm sets every rt_smoke_* cvar explicitly. They are CVAR_ARCHIVE, so a
rem value left in the ini by one arm would leak into the next and quietly
rem invalidate the comparison -- and into normal play afterwards.
rem
rem Default map is 01: an unfogged map, where smoke has the volume to itself and
rem rt_smoke_far decides the resolution. Pass 26 for the fog interaction.
rem
rem Usage: ab-smoke.cmd <full|fat|thin|still|drift|walk|glued|edgeonly|nearfade|blendslow|blendraw|reach30|reach8|off|nolight|debug|probe|probeall|novol|fogsafe|fogsmoke> [1-32]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=full"
if "%MAP%"==""  set "MAP=01"

rem The shipping values, spelled out once. Later +cvar wins, so an arm names only
rem what it changes.
set "SMOKE=+rt_smoke 1 +rt_smoke_density 6 +rt_smoke_color 9E9689 +rt_smoke_count 3 +rt_smoke_budget 24 +rt_smoke_life 1.6 +rt_smoke_radius 0.35 +rt_smoke_growth 0.7 +rt_smoke_speed 1.8 +rt_smoke_spread 0.55 +rt_smoke_rise 0.65 +rt_smoke_drag 1.9 +rt_smoke_inherit 0.85 +rt_smoke_offset 0.7 +rt_smoke_repeat 5 +rt_smoke_far 14 +rt_smoke_ambient 0.08 +rt_smoke_illum 1 +rt_smoke_light_near 0 +rt_smoke_illum_blend 0.4 +rt_smoke_debug 1"

rem Fog OFF by default, and the preset table with it, so an unfogged map stays
rem unfogged and the smoke is the only thing in the volume. The fog arms below
rem put it back deliberately.
set "NOFOG=+rt_fog 0 +rt_fog_presets 0 +rt_volume_type 1"

rem The shipping MAP26 fog, by cvar rather than by table, so it matches
rem ab-fog.cmd's `ramp` arm exactly -- that identity is the whole point of
rem `fogsafe`.
set "FOG26=+rt_fog 1 +rt_fog_presets 0 +rt_fog_color 000000 +rt_fog_density 0.01 +rt_fog_density_mult 0.3 +rt_fog_density_far 10 +rt_fog_color_far 000000 +rt_fog_curve 2.4 +rt_fog_far 32 +rt_fog_ambient 1 +rt_fog_lightmult 1 +rt_fog_light_near 2 +rt_fog_illum 1 +rt_fog_debug 0 +rt_volume_type 1 +rt_flsh 0"

if /i "%ARM%"=="full"      set "ARGS=%NOFOG% %SMOKE%"

rem Profiles.
if /i "%ARM%"=="fat"       set "ARGS=%NOFOG% %SMOKE% +rt_smoke_density 24 +rt_smoke_radius 0.8 +rt_smoke_count 4"
if /i "%ARM%"=="thin"      set "ARGS=%NOFOG% %SMOKE% +rt_smoke_density 2"
if /i "%ARM%"=="still"     set "ARGS=%NOFOG% %SMOKE% +rt_smoke_rise 0 +rt_smoke_drag 12 +rt_smoke_growth 0 +rt_smoke_speed 0 +rt_smoke_spread 0 +rt_smoke_life 6"
if /i "%ARM%"=="drift"     set "ARGS=%NOFOG% %SMOKE% +rt_smoke_life 4 +rt_smoke_rise 1.3"
if /i "%ARM%"=="walk"      set "ARGS=%NOFOG% %SMOKE% +rt_smoke_inherit 0"
if /i "%ARM%"=="glued"     set "ARGS=%NOFOG% %SMOKE% +rt_smoke_inherit 1"
if /i "%ARM%"=="edgeonly"  set "ARGS=%NOFOG% %SMOKE% +rt_smoke_repeat 0"

rem The two traps.
if /i "%ARM%"=="nearfade"  set "ARGS=%NOFOG% %SMOKE% +rt_smoke_light_near 2"
if /i "%ARM%"=="blendslow" set "ARGS=%NOFOG% %SMOKE% +rt_smoke_illum_blend 0.05"
if /i "%ARM%"=="blendraw"  set "ARGS=%NOFOG% %SMOKE% +rt_smoke_illum_blend 0.9"

rem Resolution.
if /i "%ARM%"=="reach30"   set "ARGS=%NOFOG% %SMOKE% +rt_smoke_far 30"
if /i "%ARM%"=="reach8"    set "ARGS=%NOFOG% %SMOKE% +rt_smoke_far 8"

rem Isolation.
if /i "%ARM%"=="off"       set "ARGS=%NOFOG% %SMOKE% +rt_smoke 0"
if /i "%ARM%"=="nolight"   set "ARGS=%NOFOG% %SMOKE% +rt_smoke_illum 0"
if /i "%ARM%"=="debug"     set "ARGS=%NOFOG% %SMOKE% +rt_smoke_debug 1"
if /i "%ARM%"=="probe"     set "ARGS=%NOFOG% %SMOKE% +rt_smoke_debug 2"
if /i "%ARM%"=="probeall"  set "ARGS=%NOFOG% %SMOKE% +rt_smoke_debug 3"
if /i "%ARM%"=="novol"     set "ARGS=+rt_fog 0 +rt_fog_presets 0 +rt_volume_type 1 %SMOKE% +rt_smoke 0"

rem The fog regression. fogsafe defaults to MAP26 because that is the map with a
rem measured transmittance ladder to be identical to.
if /i "%ARM%"=="fogsafe"   set "ARGS=%FOG26% %SMOKE%" & if "%~2"=="" set "MAP=26"
if /i "%ARM%"=="fogsmoke"  set "ARGS=%FOG26% %SMOKE%" & if "%~2"=="" set "MAP=26"

if not defined ARGS (
  echo Usage: %~nx0 full^|fat^|thin^|still^|drift^|walk^|glued^|edgeonly^|nearfade^|blendslow^|blendraw^|reach30^|reach8^|off^|nolight^|debug^|probe^|probeall^|novol^|fogsafe^|fogsmoke  [1-32]
  exit /b 1
)

echo === smoke arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
if /i "%ARM%"=="fogsafe" echo     COMPARE AGAINST: .\tools\ab-fog.cmd ramp 26  -- must be pixel-identical while not firing
echo     (fire at a wall in a DARK room; the tell is the puff being brighter while its own flash is lit)
echo.
echo     DIAGNOSTICS ARE ON (rt_smoke_debug 1). Four probes, in order -- the first
echo     one that goes missing is where the chain breaks:
echo       A0/gate     did extralight rise at all, and did the flash gates pass
echo       A/trigger   the shot was seen; shows the edge/repeat decision
echo       B/spawn     a puff was created, with its position and radius
echo       C/sent      what was packed for RTGL: count, density, distance from eye
echo       D/received  what RTGL1.dll actually got (proves the pNext link)
echo     Full transcript: rt-console.log
rem "debug" is the launcher's -rtdebug switch. It is NOT optional here: RTGL1's
rem own log line (stage D, "what the library received") is a debug::Warning, and
rem rt_main sets allowedMessages=0 without -rtdebug -- so the one probe that can
rem prove the pNext struct arrived would be silently muted.
call "%~dp0launch-retribution-rt.cmd" %MAP% debug -- %ARGS%
exit /b %ERRORLEVEL%
