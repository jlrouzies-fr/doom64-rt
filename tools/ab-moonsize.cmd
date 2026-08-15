@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem The global size gate for sky leaks: how BIG the moon is, in degrees.
rem
rem Confirmed cause of the leaks (screen\level13skyleak.png -- cold blue wash on
rem a ceiling, brightest at the wall/ceiling junction): rt_sun is a directional
rem light at rt_sun_angdiam 0.5 degrees, i.e. a POINT. Its shadow test is one
rem ray, yes or no. So a crack admits exactly as much light as a doorway, and
rem RTGL1 excludes sky geometry from shadow rays entirely
rem (VulkanDevice.cpp: rayCullMaskWorld_Shadow = INSTANCE_MASK_WORLD_0), which
rem means Doom's sky-hack bands at wall tops are holes the moon streams through.
rem
rem No per-surface rule can fix that, because MAP13's WANTED light also comes
rem through holes in walls -- the F_SKY1 window slots. Wanted and unwanted are
rem the same kind of geometry. What separates them is SIZE, and the physical way
rem to act on size is to stop treating the moon as a point:
rem
rem   widen the disc -> RTGL1 samples a point on it per shadow ray
rem                     (sampleDirectionalLight -> sampleDisk)
rem                  -> an opening admits light in proportion to how much of the
rem                     disc it reveals
rem                  -> a doorway reveals all of it and is unchanged;
rem                     a narrow band reveals a sliver and dims smoothly
rem
rem And it falls off with DISTANCE, which is the part that actually matters here:
rem an opening of size d seen from L away subtends d/L, so a 96-unit band still
rem lights the surfaces right beside it and stops washing a ceiling 2000 units
rem away. That is the ceiling wash in the screenshot.
rem
rem This is a soft rolloff, NOT a cutoff. "Too small a hole" is only meaningful
rem relative to how far away you are standing, so no single threshold could have
rem been right -- which is why it is an angle and not a unit count.
rem
rem   real     0.5  - the actual moon. A point light. The leak at its worst;
rem                   this is the shipping value and the control.
rem   soft     3    - barely perceptible softening, small leaks start to fade.
rem   wide     8    - the first value where distant spill should visibly die.
rem   huge    16    - heavy. Shafts go soft-edged; use it to confirm the
rem                   mechanism is the right one before tuning down.
rem   absurd  40    - diagnostic only. If the leak survives THIS, the light is
rem                   not squeezing through a small opening at all and the whole
rem                   theory is wrong. That is the useful thing it tells you.
rem
rem Watch the COST as you go up: this softens the wanted shafts through MAP13's
rem west windows by the same amount. One knob, both effects. The answer is the
rem largest value whose shafts you still like.
rem
rem Noise note: a wider disc means shadow rays disagree more, so the penumbra is
rem noisier at 1 spp. Judge it after the denoiser settles - stand still a second.
rem If it stays grainy, raise rt_shadowrays (launcher pins 4) rather than
rem abandoning the angle.
rem
rem Every arm sets every rt_sun cvar explicitly; RT_CVARs are CVAR_ARCHIVE.
rem rt_moon_presets 0 so the per-map table cannot overwrite the aim mid-test.
rem
rem Usage: ab-moonsize.cmd <real|soft|wide|huge|absurd> [1-32, default 13]
rem ---------------------------------------------------------------------------

set "ARM=%~1"
set "MAP=%~2"
if "%ARM%"=="" set "ARM=real"
if "%MAP%"==""  set "MAP=13"

set "BASE=+rt_sun 1 +rt_sun_intensity 90 +rt_sun_a 25 +rt_sun_b 90 +rt_sun_color B4C8FF"
set "BASE=%BASE%"
set "BASE=%BASE% +rt_moon_presets 0 +rt_sky 25 +rt_sky_nowalls 0 +rt_shadowrays 4"

if /i "%ARM%"=="real"   set "ARGS=%BASE% +rt_sun_angdiam 0.5"
if /i "%ARM%"=="soft"   set "ARGS=%BASE% +rt_sun_angdiam 3"
if /i "%ARM%"=="wide"   set "ARGS=%BASE% +rt_sun_angdiam 8"
if /i "%ARM%"=="huge"   set "ARGS=%BASE% +rt_sun_angdiam 16"
if /i "%ARM%"=="absurd" set "ARGS=%BASE% +rt_sun_angdiam 40"

if not defined ARGS (
  echo Usage: %~nx0 ^<real^|soft^|wide^|huge^|absurd^> [1-32, default 13]
  exit /b 1
)

echo === moon size arm "%ARM%", MAP%MAP% ===
echo     %ARGS%
echo     Compare TWO things in every arm, from the same spot:
echo       1. the LEAK  - the cold wash on the ceiling should fade as you go up
echo       2. the SHAFT - through the west hall windows, should stay worth having
echo     You can also sweep it live without relaunching: rt_sun_angdiam 8
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
