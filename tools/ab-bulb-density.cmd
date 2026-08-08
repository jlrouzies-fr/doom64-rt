@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem Light COUNT vs shadow contrast for the bulb bands.
rem
rem The problem this exists to test. Sprites stopped casting visible shadows once
rem the bulb bands were lit, but they still cast a clear one from a muzzle flash,
rem and they cast fine before any of this work. So shadow casting is not broken;
rem shadow CONTRAST is being destroyed.
rem
rem Why that follows. A shadow is the absence of one light's contribution. With
rem N lights of roughly equal strength filling a room, blocking one removes about
rem 1/N of the illumination at that point -- the other N-1 fill the umbra straight
rem back in. MAP01's cage reports 113 lights within 1536u, so an occluder hides
rem under 1% of the light reaching the floor. A muzzle flash is a single dominant
rem source, which is why it still reads.
rem
rem This is a property of the light DISTRIBUTION, not of rt_shadowrays,
rem rt_shadow_samples or any sprite flag, and no amount of shadow-ray budget
rem recovers it. The lever is fewer, stronger lights.
rem
rem Each arm keeps total emitted flux roughly constant: doubling the spacing
rem halves the light count, so intensity doubles to compensate. If the theory is
rem right, overall brightness stays similar across arms while shadows sharpen
rem from left to right -- and that separation is the whole point of holding flux
rem fixed rather than just thinning the lights out.
rem
rem ARMS  (seglen = map units between lights; I = intensity each)
rem   dense   seglen  64  I 180   what ships now; the reference
rem   mid     seglen 128  I 360
rem   sparse  seglen 192  I 540
rem   point   seglen 256  I 720   fewest, strongest
rem
rem What to judge, in this order:
rem   1. do sprites and props cast a readable shadow?
rem   2. does the band still read as a continuous strip, or has it gone scalloped
rem      into separate blobs? (rt_wall_strip_seglen's own note warns that spacing
rem      wider than the source radius scallops -- so the arms raise radius with
rem      spacing to hold the strip together as long as possible)
rem   3. overall brightness, which should NOT move much between arms
rem
rem Usage: ab-bulb-density.cmd <dense^|mid^|sparse^|point> [map 1-32]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=mid"
if "%MAP%"==""  set "MAP=1"

if /i "%WHICH%"=="dense" (
  set "SEG=64"  & set "I=180" & set "R=0.35"
) else if /i "%WHICH%"=="mid" (
  set "SEG=128" & set "I=360" & set "R=0.50"
) else if /i "%WHICH%"=="sparse" (
  set "SEG=192" & set "I=540" & set "R=0.65"
) else if /i "%WHICH%"=="point" (
  set "SEG=256" & set "I=720" & set "R=0.80"
) else (
  echo Usage: %~nx0 ^<dense^|mid^|sparse^|point^> [map 1-32]
  exit /b 1
)

rem Both walks together: they light the same physical band where it turns a
rem corner, so a spacing mismatch shows as a density step at the corner.
set "ARGS=+rt_wall_strip_seglen %SEG% +rt_wall_strip_intensity %I% +rt_wall_strip_radius %R%"
set "ARGS=%ARGS% +rt_ceiling_edge_seglen %SEG% +rt_ceiling_edge_intensity %I% +rt_ceiling_edge_radius %R%"
set "ARGS=%ARGS% +rt_ceiling_edge_debug 1"

echo === bulb density: %WHICH% (seglen=%SEG% I=%I% radius=%R%), MAP%MAP% ===
echo     %ARGS%
echo     watch the "uploaded=N of M wanted" line -- N is the light count driving contrast
echo     judge: 1) do sprites cast shadows  2) is the strip still continuous  3) brightness steady
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
